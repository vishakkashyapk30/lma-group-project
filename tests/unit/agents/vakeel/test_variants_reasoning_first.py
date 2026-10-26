"""S15 / A13 reasoning-first structured output (`Switches.output_format='reasoning_first'`; Sweep 2, `docs/literature-to-code-map.md`).

The drafting, reply and reword schemas carry a free `reasoning` field before the answer fields. The reasoning is stored, never cited,
never checked and never read as an answer. Default (`answer_only`) is byte-identical: `test_variants_golden.py`.
"""

from __future__ import annotations

import json

from tests.fakes.models import ScriptedLLM, Seq
from tests.unit.agents._helpers import SpyBudget, build_agent, make_state
from tests.unit.agents.vakeel import _variants_helpers as vh
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, UNSUPPORTED_G1, pack
from vakeel_sahayak.agents.vakeel.agent import REASONING_ROOM, VakeelAgent
from vakeel_sahayak.agents.vakeel.prompts import REASONING_NOTE, DraftedGround, DraftedGroundReasoned, ReasonedReply
from vakeel_sahayak.models.json_schema import schema_of
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor
from vakeel_sahayak.schemas.sparring import Reply

PARITY = Factor.PARITY_WITH_CO_ACCUSED
CITED = [("DLHC-2022-1187", 14)]
SNEAKY = "Thinking aloud: also [A:SC-2014-0463#21] and [F:charge_sheet] might help; the accused will surely be granted bail."


def s15() -> Switches:
    return Switches.for_variant("S15")


def ground(reasoning: str, argument: str) -> dict:
    return {"reasoning": reasoning, "argument": argument, "authorities": [{"doc_id": d, "para": p} for d, p in CITED]}


def llm_for(draft: dict, revisions: list[dict] | None = None) -> ScriptedLLM:
    return ScriptedLLM(by_prompt=[("vakeel.reword_claim", Seq(*(revisions or [draft]))), ("vakeel.draft_ground", draft)], strict=False, default="")


def run_one(paragraphs, dossier, rights, llm, switches):
    agent, ctx, toolbox = build_agent(VakeelAgent, llm=llm, switches=switches)
    grounds = agent.draft_grounds(make_state(dossier, rights), [pack(PARITY, paragraphs, CITED)])
    return agent, ctx, agent.repair_or_flag(agent.check_claims(grounds))


# ---- selection ------------------------------------------------------------------------------------------------------------------
def test_selection_and_implemented():
    assert s15().output_format == "reasoning_first" and s15().variant() == "S15"
    assert Switches.for_variant("A13").variant() == "S15"
    # RECONCILED: S15b (free text then parse) is built in `orchestration/structured_output.py` (the structured-call layer, not Vakeel): it is in the registry now
    assert "S15" in IMPLEMENTED_VARIANTS and "S15b" in IMPLEMENTED_VARIANTS
    assert_variant_implemented("A13")
    assert_variant_implemented("S15b")


def test_the_reasoning_field_comes_first_in_the_schema_and_the_default_has_none():
    props = list(schema_of(DraftedGroundReasoned)["properties"])
    assert props[0] == "reasoning" and props[1] == "argument"
    assert list(schema_of(ReasonedReply)["properties"])[0] == "reasoning"
    assert "reasoning" not in schema_of(DraftedGround)["properties"] and "reasoning" not in schema_of(Reply)["properties"]


def test_the_default_prompt_and_schema_are_unchanged(paragraphs, dossier, expected_rights_report):
    llm = llm_for(ground("", SUPPORTED_G1))
    run_one(paragraphs, dossier, expected_rights_report, llm, None)
    draft = [c for c in llm.calls if "vakeel.draft_ground" in c.prompt][0]
    assert REASONING_NOTE not in draft.prompt and '"reasoning"' not in json.dumps(draft.json_schema) and draft.max_tokens == 900


# ---- behaviour --------------------------------------------------------------------------------------------------------------------
def test_the_prompt_asks_for_reasoning_first_and_leaves_room_for_it(paragraphs, dossier, expected_rights_report):
    llm = llm_for(ground("The co-accused has the same role, so parity applies.", SUPPORTED_G1))
    run_one(paragraphs, dossier, expected_rights_report, llm, s15())
    draft = [c for c in llm.calls if "vakeel.draft_ground" in c.prompt][0]
    assert REASONING_NOTE in draft.prompt and list(draft.json_schema["properties"])[0] == "reasoning"
    assert draft.max_tokens == int(900 * REASONING_ROOM)


def test_the_claim_is_the_argument_field_and_citations_still_render(paragraphs, dossier, expected_rights_report):
    llm = llm_for(ground("Parity: same role.", SUPPORTED_G1))
    agent, ctx, grounds = run_one(paragraphs, dossier, expected_rights_report, llm, s15())
    g = grounds[0]
    assert g.argument.startswith(SUPPORTED_G1) and g.check == ClaimCheck.SUPPORTED  # a Qualification note may follow
    assert g.authorities and g.authorities[0].citation  # rendered from corpus metadata
    assert "Parity: same role." not in g.argument


def test_the_reasoning_is_stored_but_never_cited_checked_or_trusted(paragraphs, dossier, expected_rights_report):
    """Markers and a prediction inside the reasoning change nothing: only the argument is read as the claim."""
    llm = llm_for(ground(SNEAKY, SUPPORTED_G1))
    agent, ctx, grounds = run_one(paragraphs, dossier, expected_rights_report, llm, s15())
    g = grounds[0]
    assert {(a.doc_id, a.para) for a in g.authorities} == set(CITED)  # SC-2014-0463#21 from the reasoning is not cited
    assert "charge_sheet" not in g.depends_on.facts and g.check == ClaimCheck.SUPPORTED
    assert agent.reasoning_of("G1") == [SNEAKY]
    events = [e for e in ctx.log.events if (e.outputs or {}).get("type") == "reasoning_first"]
    assert events and events[0].outputs["variant"] == "S15" and events[0].outputs["reasoning"] == SNEAKY
    # the checker never saw it
    assert all(SNEAKY not in json.dumps(e.model_dump(mode="json")) for e in ctx.log.events if (e.outputs or {}).get("type") in {"check", "repair", "flag"})


def test_a_reasoning_free_answer_is_still_valid_and_counted_as_empty(paragraphs, dossier, expected_rights_report):
    llm = llm_for({"argument": SUPPORTED_G1, "authorities": []})
    agent, _, grounds = run_one(paragraphs, dossier, expected_rights_report, llm, s15())
    assert grounds[0].check == ClaimCheck.SUPPORTED
    assert agent.output_signals()["empty_reasoning"] == 1


def test_repair_still_works_and_its_reasoning_is_kept_apart(paragraphs, dossier, expected_rights_report):
    llm = llm_for(ground("first thoughts", UNSUPPORTED_G1), [ground("second thoughts", SUPPORTED_G1)])
    agent, _, grounds = run_one(paragraphs, dossier, expected_rights_report, llm, s15())
    assert grounds[0].check == ClaimCheck.REPAIRED and grounds[0].argument.startswith(SUPPORTED_G1)
    assert agent.reasoning_of("G1") == ["first thoughts", "second thoughts"]
    assert agent.output_signals()["calls"] == 2


def test_a_spent_budget_still_flags_instead_of_failing(paragraphs, dossier, expected_rights_report):
    agent, ctx, _ = build_agent(VakeelAgent, llm=llm_for(ground("r", SUPPORTED_G1)), switches=s15(), budgets=SpyBudget(exhausted=True))
    grounds = agent.draft_grounds(make_state(dossier, expected_rights_report), [pack(PARITY, paragraphs, CITED)])
    assert grounds and grounds[0].check == ClaimCheck.NEEDS_REVIEW
    assert agent.output_signals()["calls"] == 0


# ---- the whole run, offline ---------------------------------------------------------------------------------------------------------
def test_offline_run_is_deterministic_and_signals_are_in_the_state():
    a = vh.digests(vh.canonical_run(vh.build(switches=s15())))
    b = vh.digests(vh.canonical_run(vh.build(switches=s15())))
    assert a == b
    env = vh.build(switches=s15())
    out = vh.run_both(env)
    sig = out.state.variant_signals["output"]
    assert sig["variant"] == "S15" and sig["calls"] >= 3 and sig["reasoning_words"] > 0 and sig["empty_reasoning"] == 0
    assert json.dumps(sig) and vh.events_of(env, "output_signals", "VAKEEL")


def test_the_offline_arm_changes_no_claim_only_adds_the_reasoning():
    base = vh.run_both(vh.build())
    arm = vh.run_both(vh.build(switches=s15()))
    assert [g.argument for g in base.state.brief.grounds] == [g.argument for g in arm.state.brief.grounds]
    assert [g.check for g in base.state.brief.grounds] == [g.check for g in arm.state.brief.grounds]
    assert [(o.id, o.against, o.factor, o.objection) for o in base.record.objections] == [(o.id, o.against, o.factor, o.objection) for o in arm.record.objections]


def test_replies_carry_reasoning_too_and_it_stays_out_of_the_reply_text():
    env = vh.build(switches=s15())
    out = vh.run_both(env)
    keys = {e.outputs["claim"] for e in vh.events_of(env, "reasoning_first", "VAKEEL")}
    assert any(k.startswith("reply:") for k in keys)
    for o in out.record.objections:
        assert o.reply is None or "Template reasoning" not in o.reply.text
