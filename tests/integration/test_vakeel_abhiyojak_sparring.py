"""Vakeel <-> Abhiyojak sparring (plan §8.1, §9, §6.2 step 3).

Real modules: VakeelAgent (draft, reply, check), AbhiyojakAgent (raise, judge, spar, context isolation), SutradharAgent.delegate
(which routes objections to Vakeel and replies back), BaseAgent.call_tool, the event log mirror, the tool allow-lists
(configs/tools.yaml). Fakes: the stores and the scripted LLMs (`h.sparring_llm`, scripts in tests/integration/_helpers.py: five
objections O1-O5 of which O3 is a third objection against one ground and O5 is ungrounded; replies for O1, O2, O4; verdicts
ANSWERED, PARTLY, UNANSWERED).

ASSUMPTIONS: a discarded objection is named in `SparringRecord.discarded` and in a logged event containing the word 'discard';
a hand-over to counsel is an event naming the objection and NEEDS_REVIEW; kept objections are not cut to O1, O2, O4 exactly
(O2's ground is a reasoning paragraph that must have been retrieved), so only O1, O4 and the discarding of O3 and O5 are asserted.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.integration import _helpers as h
from tests.unit.agents._helpers import tools_yaml
from tests.unit.agents.vakeel._scripts import pack
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.enums import AgentName, ClaimCheck, Factor, SparringVerdict, StoreName
from vakeel_sahayak.schemas.sparring import Objection, ObjectionGround

SECRET_STATE = {"vakeel_notes": h.VAKEEL_NOTE, "vakeel_plan": f"{h.VAKEEL_NOTE} plan"}


def packs(paragraphs):
    return [
        pack(Factor.PARITY_WITH_CO_ACCUSED, paragraphs, [("DLHC-2022-1187", 14)]),
        pack(Factor.CHARGE_SHEET_FILED, paragraphs, [("SC-2014-0463", 21)]),
        pack(Factor.CUSTODY_PERIOD, paragraphs, [("DLHC-2021-0420", 11)]),
    ]


def make_env(install_stores, **overrides):
    """Vakeel and Abhiyojak as separate agents with separate LLMs, one shared log and one shared toolbox."""
    world = h.case_0007_world()
    install_stores(world.stores)
    tb = h.ScenarioToolbox(world)
    vakeel_llm = h.make_llm(where="ada", ground=h.ground_responder(), reply=h.reply_responder(), free="")
    abh_llm = h.make_llm(where="ada", objections=h.objections_responder(), judge=h.judge_responder(), free="")
    vakeel, vctx, _ = h.build_agent(VakeelAgent, llm=vakeel_llm, toolbox=tb, world=world)
    abh, actx, _ = h.build_agent(AbhiyojakAgent, llm=abh_llm, toolbox=tb, world=world, log=vctx.log, budgets=BudgetTracker())
    state = h.make_state(world.dossier, world.rights)
    return SimpleNamespace(world=world, tb=tb, vakeel=vakeel, abh=abh, vllm=vakeel_llm, allm=abh_llm, log=vctx.log, state=state, **overrides)


def drafted(env, paragraphs):
    grounds = env.vakeel.draft_grounds(env.state, packs(paragraphs))
    brief = BailBrief(case_id=h.CASE_ID, grounds=env.vakeel.repair_or_flag(env.vakeel.check_claims(grounds)))
    return env.state.model_copy(update={"brief": brief, **SECRET_STATE})


def round_trip(env, state):
    """Round 1 (objections) -> Vakeel replies -> round 2 (verdicts), as Sutradhar routes them (plan §6.2 step 3)."""
    objections = env.abh.raise_objections(state)
    replies = env.vakeel.reply_to_objections(state, objections)
    by_id = {o.id: r for o, r in zip(objections, replies)}
    with_replies = [o.model_copy(update={"reply": by_id.get(o.id)}) for o in objections]
    return objections, with_replies, env.abh.judge_replies(state, with_replies)


# ---- context isolation -------------------------------------------------------------------------------------------
def test_abhiyojak_prompts_never_contain_vakeels_notes_or_plan(install_stores, paragraphs):
    """Plan §9: it does not see Vakeel's plan or notes, so it cannot simply agree with them."""
    env = make_env(install_stores)
    state = drafted(env, paragraphs)
    assert state.vakeel_notes == h.VAKEEL_NOTE  # the marker really is on Vakeel's side of the state
    round_trip(env, state)
    assert env.allm.calls
    assert not [p for p in env.allm.prompts if h.VAKEEL_NOTE in p]


def test_abhiyojak_sees_the_drafted_grounds_and_the_dossier(install_stores, paragraphs):
    """It attacks what was drafted: the grounds with their cited material, and the dossier facts."""
    env = make_env(install_stores)
    state = drafted(env, paragraphs)
    env.abh.raise_objections(state)
    blob = "\n".join(env.allm.prompts)
    assert "G1" in blob and "DLHC-2022-1187" in blob
    assert "Co-accused-1" in blob and "318(4)" in blob


def test_abhiyojak_calls_only_its_own_tools_and_stores(install_stores, paragraphs):
    """Plan §9: its stores are the objection bank, refusal reasoning and statutes (plus the case's own facts and docs); never the defence bank, similar orders or the citation graph."""
    env = make_env(install_stores)
    state = drafted(env, paragraphs)
    before = len(env.tb.calls)
    env.abh.raise_objections(state)
    env.abh.judge_replies(state, [])
    mine = {c.name for c in env.tb.calls[before:]}
    assert mine <= set(tools_yaml()["abhiyojak"])
    stores = env.world.stores
    assert stores[StoreName.ADVOCACY_ARGUMENTS].calls == [] and stores[StoreName.CASELAW_SIMILAR].calls == []
    assert stores[StoreName.CASELAW_CITATIONS].calls == []


def test_abhiyojak_queries_are_bounded_by_the_case_date(install_stores, paragraphs):
    env = make_env(install_stores)
    env.abh.raise_objections(drafted(env, paragraphs))
    calls = env.world.stores[StoreName.ADVOCACY_OBJECTIONS].calls
    assert calls and all(kw["before"] == h.AS_OF for _, kw in calls)


# ---- round 1 -----------------------------------------------------------------------------------------------------
def test_at_most_two_objections_per_ground_and_ungrounded_ones_are_discarded(install_stores, paragraphs):
    """Plan §9: up to two objections per ground; O3 is a third against G1 and O5 cites a paragraph that does not exist."""
    env = make_env(install_stores)
    kept = env.abh.raise_objections(drafted(env, paragraphs))
    ids = [o.id for o in kept]
    assert "O1" in ids and "O4" in ids
    assert "O3" not in ids and "O5" not in ids
    per_ground: dict[str, int] = {}
    for o in kept:
        per_ground[o.against] = per_ground.get(o.against, 0) + 1
    assert all(n <= 2 for g, n in per_ground.items() if g != "general")


def test_every_kept_objection_is_grounded(install_stores, paragraphs):
    """Plan §9: each cites an objection-bank paragraph, a refusal reasoning paragraph, a statute or a dossier fact."""
    env = make_env(install_stores)
    for o in env.abh.raise_objections(drafted(env, paragraphs)):
        assert o.grounds, o.id
        for g in o.grounds:
            assert g.fact or (g.doc_id and g.store in ("advocacy.objections", "caselaw.reasoning", "law.statutes")), (o.id, g)


def test_ungrounded_objection_is_discarded_and_logged(install_stores, paragraphs):
    """'Ungrounded objections are discarded and logged' (plan §9): in the record and as an event."""
    env = make_env(install_stores)
    record = env.abh.spar(drafted(env, paragraphs))
    assert "O5" not in {o.id for o in record.objections}
    assert any("O5" in d for d in record.discarded)
    assert [e for e in env.log.events if "O5" in e.model_dump_json() and "discard" in e.model_dump_json().lower()]


# ---- replies and checking ----------------------------------------------------------------------------------------
def test_replies_cite_rendered_authorities_and_are_checked(install_stores, paragraphs):
    """Plan §9: 'Vakeel answers each objection under the same citation and checking rules': the reply to O1 cites DLHC-2022-1187#14 with a citation rendered from metadata and passes its check."""
    env = make_env(install_stores)
    _, with_replies, _ = round_trip(env, drafted(env, paragraphs))
    o1 = next(o for o in with_replies if o.id == "O1")
    assert o1.reply is not None and o1.reply.authorities[0].doc_id == "DLHC-2022-1187"
    assert o1.reply.authorities[0].citation == env.tb.tools["render_citation"]("DLHC-2022-1187", 14)
    assert o1.reply.check in (ClaimCheck.SUPPORTED, ClaimCheck.REPAIRED)


def test_a_reply_citing_a_paragraph_nobody_retrieved_is_flagged(install_stores, paragraphs):
    """Plan §8.1 step 3 'no citation that wasn't retrieved' applies to replies too: the O2 reply cites DLHC-1999-0000#7, so it cannot be SUPPORTED."""
    env = make_env(install_stores)
    state = drafted(env, paragraphs)
    o2 = Objection(id="O2", against="G1", factor="parity_with_co_accused", objection=h.OBJECTIONS[1]["objection"],
                   grounds=[ObjectionGround(store="caselaw.reasoning", doc_id="DLHC-2023-0911", para=12)])
    (reply,) = env.vakeel.reply_to_objections(state, [o2])
    assert reply.check == ClaimCheck.NEEDS_REVIEW


# ---- round 2 -----------------------------------------------------------------------------------------------------
def test_verdicts_are_given_with_reasons(install_stores, paragraphs):
    env = make_env(install_stores)
    _, _, judged = round_trip(env, drafted(env, paragraphs))
    assert judged and all(o.verdict in set(SparringVerdict) and o.reason for o in judged)
    by_id = {o.id: o for o in judged}
    assert by_id["O1"].verdict == SparringVerdict.ANSWERED
    assert by_id["O4"].verdict == SparringVerdict.UNANSWERED


def test_unanswered_objection_goes_to_counsel_as_needs_review(install_stores, paragraphs):
    """Plan §9: UNANSWERED objections go to counsel as NEEDS_REVIEW; answered ones do not."""
    env = make_env(install_stores)
    round_trip(env, drafted(env, paragraphs))
    flagged = [e.model_dump_json() for e in env.log.events if "NEEDS_REVIEW" in e.model_dump_json()]
    assert any("O4" in f for f in flagged)
    assert not any('"O1"' in f or "O1:" in f for f in flagged)


def test_sparring_budget_is_two_rounds(install_stores, paragraphs):
    """Plan §9: budget two rounds; the record says so, and the objection calls are bounded."""
    env = make_env(install_stores)
    record = env.abh.spar(drafted(env, paragraphs))
    assert record.rounds == 2 and record.case_id == h.CASE_ID
    assert 1 <= len(env.allm.calls) <= 15
    assert all(o.verdict is not None for o in record.objections)


# ---- Sutradhar routes the whole loop -----------------------------------------------------------------------------
def delegate_env(install_stores, paragraphs):
    world = h.case_0007_world()
    install_stores(world.stores)
    tb = h.ScenarioToolbox(world)
    llm = h.sparring_llm()
    sut, ctx, _ = h.build_agent(SutradharAgent, llm=llm, toolbox=tb, world=world, budgets=BudgetTracker())
    state = h.make_state(world.dossier, world.rights).model_copy(update=SECRET_STATE)
    return SimpleNamespace(world=world, tb=tb, llm=llm, sut=sut, ctx=ctx, state=state, packs=packs(paragraphs))


def test_delegate_drafts_spars_and_hands_the_record_back(install_stores, paragraphs):
    """Plan §6.2 step 3: packs to Vakeel, draft to Abhiyojak, objections back to Vakeel; the state gets a brief and a sparring record."""
    env = delegate_env(install_stores, paragraphs)
    out = env.sut.delegate(env.state, env.packs)
    assert [g.id for g in out.brief.grounds] == ["G1", "G2", "G3"]
    assert out.sparring is not None and out.sparring.rounds == 2
    assert {str(getattr(e.actor, "value", e.actor)) for e in env.ctx.log.events} >= {AgentName.VAKEEL.value, AgentName.ABHIYOJAK.value}


def test_delegated_brief_cites_only_retrieved_court_reasoning(install_stores, paragraphs):
    env = delegate_env(install_stores, paragraphs)
    out = env.sut.delegate(env.state, env.packs)
    retrieved = {("DLHC-2022-1187", 14), ("SC-2014-0463", 21), ("DLHC-2021-0420", 11)}
    assert {(a.doc_id, a.para) for g in out.brief.grounds for a in g.authorities} <= retrieved
    assert all(a.citation for g in out.brief.grounds for a in g.authorities)


def test_delegated_run_keeps_vakeels_notes_away_from_abhiyojak(install_stores, paragraphs):
    env = delegate_env(install_stores, paragraphs)
    env.sut.delegate(env.state, env.packs)
    abhiyojak_calls = h.calls_of(env.llm, *h.ABHIYOJAK_KINDS)
    assert abhiyojak_calls
    assert not [c for c in abhiyojak_calls if h.VAKEEL_NOTE in c.prompt]


def test_nothing_is_dropped_silently(install_stores, paragraphs):
    """Plan §8.1: every drafted ground is in the brief, whatever its check says; every kept objection has a verdict."""
    env = delegate_env(install_stores, paragraphs)
    out = env.sut.delegate(env.state, env.packs)
    assert len(out.brief.grounds) == len(env.packs)
    assert all(g.check in set(ClaimCheck) for g in out.brief.grounds)
    assert all(o.verdict is not None for o in out.sparring.objections)
