"""S8 / A2b self-critique-only repair (`Switches.repair_mode='self_critique'`; Sweep 2, `docs/literature-to-code-map.md`).

Vakeel's repair step uses the drafting model alone: it re-reads its own claim (CRITIC's critique step without tools; Huang et al., ICLR 2024)
and rewrites what it flags. No NLI, no `check_claim`, no re-retrieval. The default (`repair_mode='grounded'`) is byte-identical to before:
see `test_variants_golden.py`.
"""

from __future__ import annotations

import json

import pytest

from tests.fakes.models import ScriptedLLM, Seq
from tests.unit.agents._helpers import SpyBudget, build_agent, make_ground, make_state
from tests.unit.agents.vakeel import _variants_helpers as vh
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, UNSUPPORTED_G1, model_ground, pack
from vakeel_sahayak.agents.vakeel import offline
from vakeel_sahayak.agents.vakeel.agent import SELF_CRITIQUE_NOTICE, VakeelAgent
from vakeel_sahayak.models.offline_llm import OfflineRequest
from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, OpenIssueType

PARITY = Factor.PARITY_WITH_CO_ACCUSED
CITED = [("DLHC-2022-1187", 14)]


def s8() -> Switches:
    return Switches.for_variant("S8")


def review(*flags: str | None) -> dict:
    """A SelfReview answer: one entry per sentence; a string flags that sentence with that reason, None accepts it."""
    return {"reviews": [{"sentence": i + 1, "ok": f is None, "reason": f or ""} for i, f in enumerate(flags)]}


def routed(draft: str, reviews: list[dict] | dict, revisions: list[str] | str = "") -> ScriptedLLM:
    """A model whose three Vakeel tasks are answered separately: the draft, the self-critique reviews, the revisions."""
    draft_ground = model_ground("G1", PARITY.value, draft, CITED)
    revs = [revisions] if isinstance(revisions, str) else list(revisions)
    revised = [model_ground("G1", PARITY.value, t, CITED) for t in revs] or [draft_ground]
    return ScriptedLLM(
        by_prompt=[
            ("vakeel.self_critique", Seq(*reviews) if isinstance(reviews, list) else reviews),
            ("vakeel.self_revise", Seq(*revised)),
            ("vakeel.reword_claim", Seq(*revised)),
            ("vakeel.draft_ground", draft_ground),
        ],
        strict=False, default="",
    )


def agent_for(llm: ScriptedLLM, switches: Switches | None = None, **kw):
    return build_agent(VakeelAgent, llm=llm, switches=switches, **kw)


def run_one(paragraphs, dossier, rights, llm, switches=None):
    """Draft, check and repair one parity ground on the scripted model; returns the agent, the toolbox, the grounds and the llm."""
    agent, ctx, toolbox = agent_for(llm, switches)
    state = make_state(dossier, rights)
    grounds = agent.draft_grounds(state, [pack(PARITY, paragraphs, CITED)])
    return agent, toolbox, agent.repair_or_flag(agent.check_claims(grounds)), ctx


# ---- selection -------------------------------------------------------------------------------------------------------
def test_the_variant_is_selected_through_for_variant_and_is_implemented():
    assert s8().repair_mode == "self_critique" and s8().variant() == "S8"
    assert Switches.for_variant("A2b").variant() == "S8"
    assert "S8" in IMPLEMENTED_VARIANTS
    assert_variant_implemented("S8")
    assert_variant_implemented("A2b")


def test_the_default_is_grounded_and_has_no_self_critique():
    assert Switches().repair_mode == "grounded"
    agent, _, _ = build_agent(VakeelAgent, llm=ScriptedLLM(strict=False, default=""))
    assert agent.repair_signals() == {}


def test_self_critique_cannot_combine_with_no_check_repair():
    with pytest.raises(ValueError):
        Switches(repair_mode="self_critique", no_check_repair=True)


# ---- no outside evidence ---------------------------------------------------------------------------------------------
def test_no_nli_no_check_claim_and_no_retrieval(paragraphs, dossier, expected_rights_report):
    """The self-critique arm reads no source: `check_claim` is never called and Sutradhar is never asked to re-retrieve."""
    asked: list[str] = []
    llm = routed(UNSUPPORTED_G1, review("the date is wrong"), SUPPORTED_G1)
    agent, ctx, toolbox = build_agent(VakeelAgent, llm=llm, switches=s8())
    agent.retriever = lambda *a: asked.append("retrieve")  # type: ignore[assignment]
    grounds = agent.draft_grounds(make_state(dossier, expected_rights_report), [pack(PARITY, paragraphs, CITED)])
    agent.repair_or_flag(agent.check_claims(grounds))
    assert toolbox.count("check_claim") == 0
    assert asked == []
    for name in ("search_reasoning", "search_case_docs", "get_paragraph"):
        assert toolbox.count(name) == 0, name


def test_a_flagged_sentence_is_rewritten_and_the_claim_is_repaired(paragraphs, dossier, expected_rights_report):
    llm = routed(UNSUPPORTED_G1, [review("not what the source says"), review(None)], SUPPORTED_G1)
    agent, _, grounds, _ = run_one(paragraphs, dossier, expected_rights_report, llm, s8())
    assert grounds[0].check == ClaimCheck.REPAIRED
    assert grounds[0].argument.startswith(SUPPORTED_G1.split("[F:")[0])
    sig = agent.repair_signals()
    assert sig["critic_calls"] == 2 and sig["revise_calls"] == 1 and sig["claims_repaired"] == 1
    assert sig["sentences_flagged"] == 1 and sig["claims_flagged_at_first_read"] == 1


def test_the_model_that_accepts_its_own_wrong_draft_is_not_corrected(paragraphs, dossier, expected_rights_report):
    """The failure Huang et al. describe: an unsupported claim (a date that is not in the source) passes when the model re-reads itself.

    The grounded default flags the same draft NEEDS_REVIEW with the NLI check.
    """
    accept = routed(UNSUPPORTED_G1, review(None))
    _, _, grounds, _ = run_one(paragraphs, dossier, expected_rights_report, accept, s8())
    assert grounds[0].check == ClaimCheck.SUPPORTED and "05.12.2024" in grounds[0].argument
    default = routed(UNSUPPORTED_G1, review(None))
    _, _, base, _ = run_one(paragraphs, dossier, expected_rights_report, default, None)
    assert base[0].check != ClaimCheck.SUPPORTED


def test_the_rule_only_guards_still_run(paragraphs, dossier, expected_rights_report):
    """A prediction is flagged even when the model's own reading accepts it: the guard reads no source."""
    text = "The applicant is likely to be granted bail [F:co_accused_bail] [A:DLHC-2022-1187#14]"
    llm = routed(text, review(None), SUPPORTED_G1)
    env = run_one(paragraphs, dossier, expected_rights_report, llm, s8())
    ctx = env[3]
    first = next(e for e in ctx.log.events if (e.outputs or {}).get("type") == "check")
    assert "prediction" in first.outputs["failing"][0]["problems"]
    assert env[2][0].check == ClaimCheck.REPAIRED  # reworded to a sentence without the prediction


def test_at_most_max_rounds_rewrites_and_the_critic_reads_once_per_pass(paragraphs, dossier, expected_rights_report):
    """A critic that always flags: 1 initial reading + `max_rounds` re-readings, at most `max_rounds` rewrites per sentence; then NEEDS_REVIEW."""
    llm = routed(UNSUPPORTED_G1, review("still wrong"), UNSUPPORTED_G1 + " again")
    agent, _, grounds, _ = run_one(paragraphs, dossier, expected_rights_report, llm, s8())
    assert grounds[0].check == ClaimCheck.NEEDS_REVIEW  # kept, never dropped
    sig = agent.repair_signals()
    assert sig["critic_calls"] == 1 + agent.max_rounds
    assert sig["revise_calls"] <= agent.max_rounds * 1


# ---- budgets ---------------------------------------------------------------------------------------------------------
def test_a_spent_budget_never_accepts_a_claim_silently():
    llm = ScriptedLLM(strict=False, default="")
    agent, ctx, _ = build_agent(VakeelAgent, llm=llm, switches=s8(), budgets=SpyBudget(exhausted=True))
    g = make_ground("G1", PARITY, SUPPORTED_G1, CITED, check=ClaimCheck.NEEDS_REVIEW)
    out = agent.repair_or_flag([g])
    assert out[0].check == ClaimCheck.NEEDS_REVIEW
    assert llm.calls == []
    assert any((e.outputs or {}).get("type") == "model_failed" for e in ctx.log.events)


def test_the_calls_are_charged_to_the_token_budget(paragraphs, dossier, expected_rights_report):
    llm = routed(UNSUPPORTED_G1, [review("wrong"), review(None)], SUPPORTED_G1)
    spy = SpyBudget()
    agent, ctx, _ = build_agent(VakeelAgent, llm=llm, switches=s8(), budgets=spy)
    grounds = agent.draft_grounds(make_state(dossier, expected_rights_report), [pack(PARITY, paragraphs, CITED)])
    agent.repair_or_flag(agent.check_claims(grounds))
    assert sum(c["tokens"] for c in spy.charges) > 0
    assert len(llm.calls) == len([c for c in spy.charges if c["tokens"]])


# ---- signals, labels, honesty ----------------------------------------------------------------------------------------
def test_events_are_labelled_and_the_signals_are_in_the_state(paragraphs, dossier, expected_rights_report):
    env = vh.build(switches=s8())
    out = vh.run_both(env)
    events = vh.events_of(env, "self_critique", "VAKEEL")
    assert events and all(e.outputs["variant"] == "S8" and e.outputs["outside_evidence"] is False for e in events)
    assert vh.events_of(env, "repair_signals", "VAKEEL")
    sig = out.state.variant_signals["repair"]
    assert sig["variant"] == "S8" and sig["critic_calls"] >= 3 and sig["claims_reviewed"] == 3
    assert json.dumps(sig)  # plain data


def test_the_brief_says_that_no_source_check_was_run():
    out = vh.run_both(vh.build(switches=s8()))
    items = [i.item for i in out.state.brief.open_issues if i.type == OpenIssueType.NEEDS_REVIEW]
    assert SELF_CRITIQUE_NOTICE in items
    default = vh.run_both(vh.build())
    assert SELF_CRITIQUE_NOTICE not in [i.item for i in default.state.brief.open_issues]
    assert default.state.variant_signals == {}


def test_replies_are_self_critiqued_too():
    env = vh.build(switches=s8())
    vh.run_both(env)
    keys = {e.outputs["claim"] for e in vh.events_of(env, "self_critique", "VAKEEL")}
    assert any(k.startswith("reply:") for k in keys) and {"G1", "G2", "G3"} <= keys


# ---- offline determinism and the offline stand-in --------------------------------------------------------------------
def test_offline_runs_are_deterministic():
    a = vh.digests(vh.canonical_run(vh.build(switches=s8())))
    b = vh.digests(vh.canonical_run(vh.build(switches=s8())))
    assert a == b


def test_offline_self_critique_differs_from_the_grounded_run_on_case_0007():
    """Case-0007 offline: the grounded checker flags every ground (the fixture NLI rejects the offline glosses); the self-reader accepts them all."""
    grounded = vh.run_both(vh.build())
    selfie = vh.run_both(vh.build(switches=s8()))
    assert {g.check for g in grounded.state.brief.grounds} == {ClaimCheck.NEEDS_REVIEW}
    assert {g.check for g in selfie.state.brief.grounds} == {ClaimCheck.SUPPORTED}


def req(claim: list[dict]) -> OfflineRequest:
    return OfflineRequest(task="vakeel.self_critique", instructions="", data={"case": {"claim": claim}}, prompt="", schema=None)


def test_offline_stand_in_flags_only_what_is_visible_on_the_page():
    out = offline.self_critique_offline(req([
        {"sentence": 1, "text": "Parity applies [F:co_accused_bail]."},
        {"sentence": 2, "text": "No marker here."},
        {"sentence": 3, "text": "Parity applies [F:fir]."},
        {"sentence": 4, "text": "A wrong date 01.01.1999 [F:co_accused_bail]."},
    ]))["reviews"]
    ok = {r["sentence"]: r["ok"] for r in out}
    assert ok == {1: True, 2: False, 3: False, 4: True}  # 3 repeats 1; 4 is wrong but unreadable without the source
