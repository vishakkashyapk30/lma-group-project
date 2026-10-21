"""S11b / S11c draft debate and three-sample vote (`Switches.draft_mode='debate'|'vote'`; Sweep 2, `docs/literature-to-code-map.md`).

Only the drafting of a ground changes; the kept draft goes through the usual check and repair. Default (`single`): `test_variants_golden.py`.
"""

from __future__ import annotations

import json

import pytest

from tests.fakes.models import ScriptedLLM, Seq
from tests.unit.agents._helpers import SpyBudget, build_agent, make_state
from tests.unit.agents.vakeel import _variants_helpers as vh
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, UNSUPPORTED_G1, model_ground, pack
from vakeel_sahayak.agents.vakeel.agent import DRAFT_SAMPLES, DRAFT_TEMPERATURE, VakeelAgent
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor

PARITY = Factor.PARITY_WITH_CO_ACCUSED
CITED = [("DLHC-2022-1187", 14)]
OTHER = "Co-accused with an identical role has been enlarged on bail [F:co_accused_bail] [A:DLHC-2022-1187#14] and the applicant is a first offender [F:antecedents]"


def sw(v: str) -> Switches:
    return Switches.for_variant(v)


def g(text: str) -> dict:
    return model_ground("G1", PARITY.value, text, CITED)


def agent_with(llm, switches, **kw):
    return build_agent(VakeelAgent, llm=llm, switches=switches, **kw)


def draft(paragraphs, dossier, rights, llm, switches):
    agent, ctx, toolbox = agent_with(llm, switches)
    grounds = agent.draft_grounds(make_state(dossier, rights), [pack(PARITY, paragraphs, CITED)])
    return agent, ctx, grounds


class Temps(ScriptedLLM):
    """A scripted model that also keeps the temperatures it was called with."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.temps: list[float] = []

    def generate(self, prompt, max_tokens=1024, temperature=0.0, json_schema=None):
        self.temps.append(temperature)
        return super().generate(prompt, max_tokens, temperature, json_schema)


def test_selection_and_implemented():
    assert sw("S11b").draft_mode == "debate" and sw("S11c").draft_mode == "vote"
    assert sw("S11b").variant() == "S11b" and sw("S11c").variant() == "S11c"
    assert {"S11b", "S11c"} <= IMPLEMENTED_VARIANTS
    assert_variant_implemented("S11b")
    assert_variant_implemented("S11c")
    assert Switches().draft_mode == "single" and VakeelAgent.draft_signals


# ---- vote -------------------------------------------------------------------------------------------------------------------
def test_vote_draws_three_independent_drafts_and_keeps_the_medoid(paragraphs, dossier, expected_rights_report):
    """Two of three drafts agree; the odd one out (a date that is not in the source) loses the vote."""
    llm = Temps(by_prompt=[("vakeel.draft_ground", Seq(g(SUPPORTED_G1), g(UNSUPPORTED_G1), g(SUPPORTED_G1)))], strict=False, default="")
    agent, ctx, grounds = draft(paragraphs, dossier, expected_rights_report, llm, sw("S11c"))
    assert len(llm.calls) == DRAFT_SAMPLES == 3 and set(llm.temps) == {DRAFT_TEMPERATURE}
    assert grounds[0].argument.startswith(SUPPORTED_G1)
    assert "05.12.2024" not in grounds[0].argument
    ev = [e for e in ctx.log.events if (e.outputs or {}).get("type") == "draft_vote"][0]
    assert ev.outputs["variant"] == "S11c" and ev.outputs["drafts"] == 3 and 0 < ev.outputs["agreement"] < 1 and ev.outputs["tokens"] > 0
    assert agent.draft_signals()["variant"] == "S11c" and agent.draft_signals()["grounds"] == 1


def test_the_default_makes_one_draft_call_at_temperature_zero(paragraphs, dossier, expected_rights_report):
    llm = Temps(by_prompt=[("vakeel.draft_ground", g(SUPPORTED_G1))], strict=False, default="")
    agent, ctx, _ = draft(paragraphs, dossier, expected_rights_report, llm, None)
    assert len(llm.calls) == 1 and llm.temps == [0.0] and agent.draft_signals() == {}


def test_vote_with_a_model_that_cannot_answer_leaves_an_empty_flagged_ground(paragraphs, dossier, expected_rights_report):
    agent, ctx, grounds = agent_with(ScriptedLLM(strict=False, default=""), sw("S11c"), budgets=SpyBudget(exhausted=True))
    out = agent.draft_grounds(make_state(dossier, expected_rights_report), [pack(PARITY, paragraphs, CITED)])
    assert out[0].check == ClaimCheck.NEEDS_REVIEW


# ---- debate -----------------------------------------------------------------------------------------------------------------
def debate_llm(a1, b1, a2, b2):
    """Round 1 answers go to instances A then B; round 2 revisions in the same order."""
    return Temps(by_prompt=[("vakeel.debate_revise", Seq(g(a2), g(b2))), ("vakeel.draft_ground", Seq(g(a1), g(b1)))], strict=False, default="")


def test_debate_is_two_instances_two_rounds_and_each_sees_the_other(paragraphs, dossier, expected_rights_report):
    llm = debate_llm(UNSUPPORTED_G1, OTHER, SUPPORTED_G1, SUPPORTED_G1 + " [F:antecedents]")
    agent, ctx, grounds = draft(paragraphs, dossier, expected_rights_report, llm, sw("S11b"))
    rounds = [c for c in llm.calls if "vakeel.debate_revise" in c.prompt]
    firsts = [c for c in llm.calls if "vakeel.draft_ground" in c.prompt]
    assert len(firsts) == 2 and len(rounds) == 2 and len(llm.calls) == 4
    assert OTHER.split(" [F:")[0] in rounds[0].prompt  # instance A read instance B's first draft
    assert "UNTRUSTED_DOCUMENT_DATA" in rounds[0].prompt  # as data, not instructions
    ev = [e for e in ctx.log.events if (e.outputs or {}).get("type") == "draft_debate"][0]
    assert ev.outputs["variant"] == "S11b" and ev.outputs["rounds"] == 2 and ev.outputs["drafts"] == 4 and ev.outputs["tokens"] > 0
    assert grounds[0].argument.startswith(SUPPORTED_G1)
    assert agent.draft_signals()["variant"] == "S11b"


def test_debate_that_converges_is_counted(paragraphs, dossier, expected_rights_report):
    llm = debate_llm(SUPPORTED_G1, SUPPORTED_G1, SUPPORTED_G1, SUPPORTED_G1)
    agent, _, _ = draft(paragraphs, dossier, expected_rights_report, llm, sw("S11b"))
    assert agent.draft_signals()["converged"] == 1 and agent.draft_signals()["mean_agreement"] == 1.0


def test_similarity_helpers():
    sim = VakeelAgent._similarity
    assert sim(SUPPORTED_G1, SUPPORTED_G1) == 1.0 and sim("", "") == 1.0
    assert 0 < sim(SUPPORTED_G1, UNSUPPORTED_G1) < 1.0 and 0 < sim(SUPPORTED_G1, OTHER) < 1.0


# ---- the whole run, offline ------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("variant", ["S11b", "S11c"])
def test_offline_runs_are_deterministic_and_signals_are_in_the_state(variant):
    a = vh.digests(vh.canonical_run(vh.build(switches=sw(variant))))
    b = vh.digests(vh.canonical_run(vh.build(switches=sw(variant))))
    assert a == b
    env = vh.build(switches=sw(variant))
    out = vh.run_both(env)
    sig = out.state.variant_signals["draft"]
    assert sig["variant"] == variant and sig["grounds"] == 3 and sig["tokens"] > 0 and sig["mean_agreement"] == 1.0  # the offline model repeats itself
    assert json.dumps(sig)


@pytest.mark.parametrize("variant", ["S11b", "S11c"])
def test_the_offline_arm_costs_more_tokens_and_changes_no_claim(variant):
    base = vh.run_both(vh.build())
    arm = vh.run_both(vh.build(switches=sw(variant)))
    assert [x.argument for x in base.state.brief.grounds] == [x.argument for x in arm.state.brief.grounds]
    assert arm.state.budget.tokens_spent > base.state.budget.tokens_spent
