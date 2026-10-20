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
