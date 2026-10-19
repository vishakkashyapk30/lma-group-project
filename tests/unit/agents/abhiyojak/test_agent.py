"""AbhiyojakAgent (plan §3.2, §9): class facts (pass today) and sparring behaviour (fail until implemented)."""

from __future__ import annotations

import inspect
import re

import pytest

from tests.fakes.models import ScriptedLLM
from tests.unit.agents._helpers import (
    CASE_DATE,
    build_agent,
    make_ground,
    make_state,
    models_yaml,
    tools_yaml,
)
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.agents.abhiyojak.isolation import VISIBLE_STORES
from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.enums import AgentName, ClaimCheck, Factor, SparringVerdict, StoreName
from vakeel_sahayak.schemas.sparring import Objection, ObjectionGround, Reply, SparringRecord

GENERAL_FACTORS = {"gravity_and_punishment", "flight_risk", "witness_tampering", "antecedents", "statutory_bar"}


# ---- class facts -----------------------------------------------------------------------------------------------------
def test_class_facts():
    """Abhiyojak is a concrete BaseAgent named ABHIYOJAK on the shared 14B model."""
    assert issubclass(AbhiyojakAgent, BaseAgent) and not inspect.isabstract(AbhiyojakAgent)
    assert AbhiyojakAgent.NAME == AgentName.ABHIYOJAK
    assert AbhiyojakAgent.ROLE_MODEL == "agents_14b"
    assert "abhiyojak" in models_yaml()["llm"]["agents_14b"]["used_by"]


@pytest.mark.parametrize("method", ["run", "raise_objections", "judge_replies", "spar"])
def test_method_exists(method):
    """The plan §9 round steps exist as methods."""
    assert callable(getattr(AbhiyojakAgent, method))


def test_sparring_budget_in_config_is_two_rounds_two_objections_per_ground():
    """configs/budgets.yaml: rounds 2, objections_per_ground 2 (plan §9)."""
    import yaml
    from tests.unit.agents._helpers import REPO_ROOT

    cfg = yaml.safe_load((REPO_ROOT / "configs" / "budgets.yaml").read_text(encoding="utf-8"))
    assert cfg["sparring"] == {"rounds": 2, "objections_per_ground": 2}


# ---- scripts ---------------------------------------------------------------------------------------------------------
def og(**kw) -> dict:
    return {k: v for k, v in kw.items()}


def obj(oid, against, factor, text, grounds) -> dict:
    return {"id": oid, "against": against, "factor": factor, "objection": text, "grounds": grounds, "reply": None, "verdict": None, "reason": None}


BANK = og(store="advocacy.objections", doc_id="DLHC-2023-0911", para=6)
OBJECTIONS = [
    obj("O1", "G1", "parity_with_co_accused", "Unlike Co-accused-1 the applicant received the money into his own account", [BANK, og(fact="fir")]),
    obj("O2", "G1", "parity_with_co_accused", "The role of the applicant is not identical to that of Co-accused-1", [og(fact="co_accused_bail")]),
    obj("O3", "G1", "parity_with_co_accused", "A third objection against the same ground", [BANK]),
    obj("O4", "G2", "charge_sheet_filed", "Further investigation is pending despite the charge sheet", [og(fact="charge_sheet")]),
    obj("O5", "general", "gravity_and_punishment", "The offence is an economic offence of some gravity", [og(store="law.statutes", doc_id="BNS 318(4)")]),
    obj("O6", "general", "witness_tampering", "Charges are not framed and the complainant is yet to be examined", [og(fact="trial_stage")]),
    obj("O7", "general", "antecedents", "Antecedents of the applicant are not disclosed", [og(fact="antecedents")]),
    obj("O8", "general", "flight_risk", "The applicant has no recorded roots in the community", [og(fact="personal")]),
    obj("O9", "general", "statutory_bar", "Check whether a special-act bar applies", [og(store="law.statutes", doc_id="BNS 318(4)")]),
    obj("OX", "G2", "charge_sheet_filed", "An ungrounded objection the model made up", []),
]


def abhiyojak_llm(objections=OBJECTIONS, verdicts=None) -> ScriptedLLM:
    """ASSUMPTION (one place to adjust): round-1 calls ask for objections as a JSON list of Objection-shaped dicts;
    round-2 prompts list the verdict labels (the text 'UNANSWERED') and are answered with {verdict, reason}."""

    def responder(prompt: str, schema):
        if "UNANSWERED" in prompt:
            return {"verdict": "PARTLY", "reason": "The reply covers only part of the objection."}
        return objections

    return ScriptedLLM(by_prompt=[(re.compile(""), responder)], strict=False, default="")


@pytest.fixture()
def state(dossier, expected_rights_report):
    grounds = [
        make_ground("G1", Factor.PARITY_WITH_CO_ACCUSED, "Co-accused with an identical role has been enlarged on bail [F:co_accused_bail] [A:DLHC-2022-1187#14]", [("DLHC-2022-1187", 14)], check=ClaimCheck.SUPPORTED),
        make_ground("G2", Factor.CHARGE_SHEET_FILED, "Once the charge sheet is filed custodial interrogation is no longer required [F:charge_sheet] [A:SC-2014-0463#21]", [("SC-2014-0463", 21)], check=ClaimCheck.SUPPORTED),
        make_ground("G3", Factor.CUSTODY_PERIOD, "Prolonged custody without trial weighs in favour of bail [F:custody_days] [A:DLHC-2021-0420#11]", [("DLHC-2021-0420", 11)], check=ClaimCheck.SUPPORTED),
    ]
    return make_state(dossier, expected_rights_report, brief=BailBrief(case_id="case-0007", grounds=grounds))


# ---- round 1 ---------------------------------------------------------------------------------------------------------
def test_at_most_two_objections_per_ground_plus_general_ones(state):
    """Three scripted objections against G1 are cut to two; general ones are limited to the five named topics."""
    agent, _, _ = build_agent(AbhiyojakAgent, llm=abhiyojak_llm(), budgets=BudgetTracker())
    out = agent.raise_objections(state)
    per_ground = {}
    for o in out:
        per_ground[o.against] = per_ground.get(o.against, 0) + 1
    assert all(n <= 2 for gid, n in per_ground.items() if gid != "general")
    assert per_ground.get("G1") == 2
    general = [o for o in out if o.against == "general"]
    assert general and {o.factor for o in general} <= GENERAL_FACTORS
    assert len({o.id for o in out}) == len(out)  # no duplicates when several calls return the same objection


def test_every_objection_has_a_ground_and_ungrounded_ones_are_dropped(state):
    """Each kept objection cites a bank paragraph, reasoning paragraph, statute or dossier fact; 'OX' (no grounds) is gone."""
    agent, _, _ = build_agent(AbhiyojakAgent, llm=abhiyojak_llm(), budgets=BudgetTracker())
    out = agent.raise_objections(state)
    assert "OX" not in {o.id for o in out}
    for o in out:
        assert o.grounds, o.id
        for g in o.grounds:
            assert g.fact or (g.doc_id and (g.store in VISIBLE_STORES)), (o.id, g)


def test_objections_use_only_the_prosecution_side_tools(state):
    """Round 1 consults the objection bank and stays inside Abhiyojak's allow-list, bounded by the case date."""
    llm = abhiyojak_llm()
    agent, ctx, toolbox = build_agent(AbhiyojakAgent, llm=llm, budgets=BudgetTracker())
    agent.raise_objections(state)
    allowed = set(tools_yaml()["abhiyojak"])
    assert {c.name for c in toolbox.calls} <= allowed
    assert toolbox.count("search_objections") >= 1  # ASSUMPTION: it looks up what prosecutors actually argued
    for method, kw in toolbox.world.stores[StoreName.ADVOCACY_OBJECTIONS].calls:
        assert kw["before"] == CASE_DATE


def test_prompts_do_not_leak_vakeel_notes(state):
    """Nothing Vakeel-side reaches the model prompt (plan §9 isolation)."""
    llm = abhiyojak_llm()
    agent, _, _ = build_agent(AbhiyojakAgent, llm=llm, budgets=BudgetTracker())
    state = state.model_copy(update={"vakeel_notes": "VAKEEL_PRIVATE_NOTE we are weak on antecedents"})
    agent.raise_objections(state)
    assert llm.calls
    assert not any("VAKEEL_PRIVATE_NOTE" in p for p in llm.prompts)


# ---- round 2 ---------------------------------------------------------------------------------------------------------
def objection_with_reply(oid: str, text: str, reply: bool = True) -> Objection:
    return Objection(
        id=oid, against="G1", factor="parity_with_co_accused", objection=text,
        grounds=[ObjectionGround(fact="fir")],
        reply=Reply(text=f"Reply to {oid}", check=ClaimCheck.SUPPORTED) if reply else None,
    )


def verdict_llm(table: dict[str, tuple[str, str]]) -> ScriptedLLM:
    """table: unique objection phrase -> (verdict, reason). One objection in the prompt -> one dict; several -> a list."""

    def responder(prompt: str, schema):
        hits = [(m, v) for m, v in table.items() if m in prompt]
        if len(hits) == 1:
            return {"verdict": hits[0][1][0], "reason": hits[0][1][1]}
        return [{"id": f"O{i + 1}", "verdict": v[0], "reason": v[1]} for i, (_, v) in enumerate(hits)]

    return ScriptedLLM(by_prompt=[(re.compile(""), responder)], strict=False, default="")


TABLE = {
    # RECONCILED: the key was "money into his own account", which is not a substring of the objection it is meant to match
    # ("The money went into his own account"), so the scripted judge never found it and answered with a list.
    "money went into his own account": ("ANSWERED", "The reply shows the account was the co-accused's."),
    "role is disputed": ("PARTLY", "The reply covers the role but not the money trail."),
    "complainant is yet to be examined": ("UNANSWERED", "The reply does not address pending examination."),
}


def three_objections() -> list[Objection]:
    return [
        objection_with_reply("O1", "The money went into his own account"),
        objection_with_reply("O2", "The accused role is disputed"),
        objection_with_reply("O3", "The complainant is yet to be examined"),
    ]


def test_judge_replies_gives_a_verdict_and_reason_for_each(state):
    """Each reply is marked ANSWERED, PARTLY or UNANSWERED with a non-empty reason."""
    agent, _, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=BudgetTracker())
    out = agent.judge_replies(state, three_objections())
    assert [o.id for o in out] == ["O1", "O2", "O3"]
    assert [o.verdict for o in out] == [SparringVerdict.ANSWERED, SparringVerdict.PARTLY, SparringVerdict.UNANSWERED]
    assert all(o.reason and o.reason.strip() for o in out)


def test_unanswered_objection_becomes_a_needs_review_item_for_counsel(state):
    """UNANSWERED goes to counsel: an event names the objection and NEEDS_REVIEW; answered ones do not."""
    # ASSUMPTION: the hand-over to counsel is an event in the case log carrying the objection id and 'NEEDS_REVIEW'.
    agent, ctx, _ = build_agent(AbhiyojakAgent, llm=verdict_llm(TABLE), budgets=BudgetTracker())
    agent.judge_replies(state, three_objections())
    flagged = [e for e in ctx.log.events if "NEEDS_REVIEW" in e.model_dump_json()]
    assert any("O3" in e.model_dump_json() for e in flagged)
    assert not any("O1" in e.model_dump_json() for e in flagged)


def test_objection_without_a_reply_is_unanswered_without_asking_the_model(state):
    """Plan §9 example O2: reply null -> UNANSWERED with a reason, and no model call is needed."""
    llm = ScriptedLLM()  # strict, no scripts: any call fails
    agent, _, _ = build_agent(AbhiyojakAgent, llm=llm, budgets=BudgetTracker())
    out = agent.judge_replies(state, [objection_with_reply("O9", "Charges are not framed", reply=False)])
    assert out[0].verdict == SparringVerdict.UNANSWERED and out[0].reason
    assert llm.calls == []


# ---- the whole sparring run ------------------------------------------------------------------------------------------
def test_spar_runs_exactly_two_rounds_and_every_objection_is_judged(state):
    """The record says rounds == 2 and every kept objection has a verdict after round 2."""
    agent, _, _ = build_agent(AbhiyojakAgent, llm=abhiyojak_llm(), budgets=BudgetTracker())
    record = agent.spar(state)
    assert isinstance(record, SparringRecord)
    assert record.rounds == 2 and record.case_id == "case-0007"
    assert record.objections and all(o.verdict in set(SparringVerdict) for o in record.objections)
    assert all(o.reason for o in record.objections)


def test_spar_lists_ungrounded_objections_as_discarded(state):
    """'OX' had no grounds: it is not in the record's objections and is listed in `discarded`."""
    # ASSUMPTION: `discarded` holds a string naming the objection (its id and/or text).
    agent, _, _ = build_agent(AbhiyojakAgent, llm=abhiyojak_llm(), budgets=BudgetTracker())
    record = agent.spar(state)
    assert "OX" not in {o.id for o in record.objections}
    assert any("OX" in d or "ungrounded objection" in d for d in record.discarded)


def test_spar_stays_within_the_sparring_budget(state):
    """Model calls are bounded: round 1 at most one per ground plus one general call, round 2 one per objection."""
    # ASSUMPTION: bound = (3 grounds + 1 general) + (2 per ground * 3 + 5 general) = 15 calls.
    llm = abhiyojak_llm()
    budgets = BudgetTracker()
    agent, _, _ = build_agent(AbhiyojakAgent, llm=llm, budgets=budgets)
    agent.spar(state)
    assert 1 <= len(llm.calls) <= 15
    snapshot = budgets.snapshot()
    assert snapshot.tokens_spent <= snapshot.tokens_cap


def test_spar_never_exceeds_two_objections_per_ground(state):
    """Whatever the model returns, no ground collects more than the configured two objections."""
    agent, _, _ = build_agent(AbhiyojakAgent, llm=abhiyojak_llm(), budgets=BudgetTracker())
    record = agent.spar(state)
    counts: dict[str, int] = {}
    for o in record.objections:
        if o.against != "general":
            counts[o.against] = counts.get(o.against, 0) + 1
    assert all(n <= 2 for n in counts.values())
