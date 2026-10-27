"""B6 (no model, never imports the factor tagger or anything that builds G1) and the B0L / B0S model arguments (docs/evaluation-plan.md 3.1)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from tests.fakes.models import ScriptedLLM
from vakeel_sahayak.eval.baselines import b0_single_pass, b6_expert_rule
from vakeel_sahayak.eval.runners.systems import system_runner
from vakeel_sahayak.schemas.bail_brief import DRAFT_LABEL, BailBrief

FACTS = "The accused was arrested on 20.08.2024 under Section 318(4) BNS. Charge sheet filed 02.11.2024."


def case(world):
    return {"case_id": "case-0007", "facts": FACTS, "before": world.case_date}


def test_b6_calls_no_model_and_returns_a_labelled_brief(make_ctx, toolbox):
    llm = ScriptedLLM(strict=True)  # any model call raises
    brief = b6_expert_rule.run_case(case(toolbox.world), make_ctx(llm=llm, toolbox=toolbox))
    assert isinstance(brief, BailBrief) and brief.label == DRAFT_LABEL and brief.grounds and llm.calls == []
    assert brief.statutory_position.sections == ["318(4) BNS"]


def test_b6_does_not_load_the_factor_tagger_or_the_gold_builders():
    """A fresh interpreter imports B6 and runs its section finder: neither the keyword factor tagger nor `pipelines.gold` is loaded."""
    code = ("import sys; from vakeel_sahayak.eval.baselines import b6_expert_rule as b; b.find_sections('Section 318(4) BNS');"
            "bad=[m for m in sys.modules if m.startswith('vakeel_sahayak.pipelines.gold') or m.endswith('pipelines.factor_tagger') or m.endswith('pipelines.order_facts')];"
            "print(bad); sys.exit(1 if bad else 0)")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr


def test_b0l_and_b0s_use_the_teacher_and_the_small_model_roles(monkeypatch, make_ctx, toolbox):
    roles: list[str] = []
    llm = ScriptedLLM(strict=False, default=BailBrief(case_id="case-0007").model_dump_json())

    def fake_get_llm(role):
        roles.append(role)
        return llm

    monkeypatch.setattr("vakeel_sahayak.models.factory.get_llm", fake_get_llm)
    for system, role in (("b0l", "teacher"), ("b0s", "munshi_4b")):
        runner, _ = system_runner(system)
        runner(case(toolbox.world), make_ctx(llm=None, toolbox=toolbox))
        assert roles[-1] == role


def test_b0_with_the_offline_stand_in_runs_without_a_model(monkeypatch, make_ctx, toolbox):
    monkeypatch.setenv("VS_MODELS", "offline")
    from vakeel_sahayak.models.factory import get_llm

    brief = b0_single_pass.run_case_with_model(case(toolbox.world), make_ctx(llm=get_llm("agents_14b"), toolbox=toolbox), None)
    assert brief.label == DRAFT_LABEL and brief.grounds


@pytest.mark.parametrize("name", ["full", "b0", "b0l", "b0s", "b1", "b2", "b3", "b4", "b6", "A2", "A8", "A9"])
def test_every_system_name_resolves(name):
    runner, switches = system_runner(name)
    assert callable(runner) and switches.variant() in {"full", name.upper()}


# ---- B0L as a real larger-model arm on the hosted backends -----------------------------------------------------------------------------------------------------

def _hosted(monkeypatch, backend):
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.setenv("VS_LLM_BACKEND", backend)
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    monkeypatch.setenv("SARVAM_API_KEY", "test-not-a-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-key")
    monkeypatch.delenv("VS_B0L_MODEL", raising=False)
    from vakeel_sahayak.models import factory

    factory._LLM_CACHE.clear()


def test_b0l_and_b0_resolve_different_model_ids_under_sarvam(monkeypatch):
    _hosted(monkeypatch, "sarvam")
    from vakeel_sahayak.models import factory
    from vakeel_sahayak.models.sarvam import adapters

    real = adapters.sarvam_config
    monkeypatch.setattr(adapters, "sarvam_config", lambda: {**real(), "chat": {**real()["chat"], "model": "sarvam-30b"}})  # the base model B0 runs on in this check
    b0_model = factory.get_llm("agents_14b").model_id
    assert b0_single_pass.b0l_model_id() == "sarvam-105b"
    b0l_client = factory.get_llm_model("agents_14b", b0_single_pass.b0l_model_id())
    assert b0l_client.model_id == "sarvam-105b" and b0_model == "sarvam-30b" and b0l_client.model_id != b0_model
    monkeypatch.setenv("VS_B0L_MODEL", "sarvam-other")
    assert b0_single_pass.b0l_model_id() == "sarvam-other"


def test_b0l_records_its_model_and_flags_when_it_equals_b0(monkeypatch, make_ctx, toolbox):
    _hosted(monkeypatch, "sarvam")
    from vakeel_sahayak.models import factory

    seen = []
    llm = ScriptedLLM(strict=False, default=BailBrief(case_id="case-0007").model_dump_json())
    llm.model_id = "sarvam-105b"
    monkeypatch.setattr(factory, "get_llm_model", lambda role, model: (seen.append(model), llm)[1])
    ctx = make_ctx(llm=llm, toolbox=toolbox)
    b0_single_pass.run_case_with_model(case(toolbox.world), ctx, "teacher")
    sig = ctx.eval_record["variant_signals"]["b0l"]
    assert seen == ["sarvam-105b"] and sig == {"model_id": "sarvam-105b", "b0_model_id": "sarvam-105b", "same_model_as_b0": True}
    assert ctx.llm is llm  # restored


def test_b0l_on_openai_is_refused_not_duplicated(monkeypatch):
    _hosted(monkeypatch, "openai")
    with pytest.raises(NotImplementedError, match="B0L is unavailable"):
        system_runner("b0l")
    system_runner("b0")  # B0 itself is unaffected
    monkeypatch.setenv("VS_B0L_MODEL", "gpt-5-mini")
    system_runner("b0l")
    assert b0_single_pass.b0l_model_id() == "gpt-5-mini"


def test_b0l_offline_and_the_manifest_extra(monkeypatch):
    monkeypatch.setenv("VS_MODELS", "offline")
    assert b0_single_pass.b0l_model_id() is None
    from vakeel_sahayak.eval.runners.driver import _system_manifest_extra

    assert _system_manifest_extra("b0") is None and _system_manifest_extra("b0l") is None
    _hosted(monkeypatch, "sarvam")
    assert _system_manifest_extra("b0l") == {"b0l_model": "sarvam-105b"} and _system_manifest_extra("full") is None
