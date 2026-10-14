"""The case moves on (plan §7.4, §10, §13.6 flow 4, §15.2 T3): a new charge-sheet document arrives, Peshkar diffs the case state,
counsel re-approves, and only the affected grounds are redrafted; unchanged claims stay word for word; a duplicate document is a
no-op.

Real modules: PeshkarAgent.detect_changes, `compute_change_set`, `mark_stale`, `factors_to_reopen`, `redraft_incrementally`,
`diff_brief`, `full_regeneration`, `collect_dependencies` / `hash_value`, the Rights Radar engine, SutradharAgent.reopen_after_change.
Fakes: stores, tools (scenario toolbox) and the scripted LLM.

The approved state: charge sheet not yet filed (default-bail window open: first remand 2024-08-21, 166 days at 2025-02-03), a brief of
three grounds built with the real dependency collector: G1 parity (co_accused_bail, sections), G2 charge sheet (charge_sheet), G3
custody (custody_days). T3 change types: (a) the charge sheet is filed, (b) a co-accused is granted bail, (c) time crosses a
threshold (the s.479 date), plus the no-op control (a duplicate document).

ASSUMPTION (documented in `ChangeToolbox`): the fake `diff_case_state` compares the approved dossier with the case shelf as the
extractor would read it now; only the fields whose source documents changed (`touched`) differ.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.fakes.models import FakeNli
from tests.fakes.stores import InMemoryFactsStore
from tests.integration import _helpers as h
from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.rights.engine import RightsEngine
from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, Ground
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import CoAccusedBail
from vakeel_sahayak.schemas.enums import ClaimCheck, ClaimState, Factor, FactorStance, FieldStatus, StoreName
from vakeel_sahayak.truth_maintenance.dependencies import collect_dependencies, hash_value
from vakeel_sahayak.truth_maintenance.redraft import diff_brief, full_regeneration, redraft_incrementally
from vakeel_sahayak.truth_maintenance.staleness import compute_change_set, factors_to_reopen, mark_stale

CS_ORDER = SourceRef(doc="d6 (order sheet)", page=1, lang="en", route="text_layer", quote="Charge sheet filed on 02.11.2024.")
G2_UNFILED = "No charge sheet has been filed against the applicant yet [F:charge_sheet]; the investigation continues."
G2_FILED_REDRAFT = h.G2_TEXT
G4_CITES_G2 = "As argued in ground G2, the investigation is over, so a long trial is likely [F:trial_stage]."


class ChangeToolbox(h.ScenarioToolbox):
    """ScenarioToolbox whose `diff_case_state` reads the shelf as the extractor would now: the approved dossier with the `touched`
    fields re-extracted (and the shelf's dossier updated accordingly), then the real `compute_change_set` against the approved state."""

    touched: tuple[str, ...] = ("charge_sheet",)

    def t_diff_case_state(self, case_id: str, since_hash: str | None = None):
        raw = self._raw_extraction()
        current = self.approved_dossier.model_copy(deep=True)
        for name in self.touched:
            setattr(current.fields, name, getattr(raw.fields, name))
        current.as_of = self.as_of
        self.facts_store._dossier = current
        return compute_change_set(self.approved_dossier, current, self.approved_rights, self.t_rights_check(case_id))


def ground(gid: str, factor: Factor, text: str, dossier, rights, authority: tuple[str, int] | None = None, **depends) -> Ground:
    auths = [Authority(doc_id=authority[0], para=authority[1])] if authority else []
    g = Ground(id=gid, factor=factor, stance=FactorStance.FAVOURABLE, argument=text, authorities=auths, check=ClaimCheck.SUPPORTED,
               state=ClaimState.CURRENT, depends_on=collect_dependencies(text, dossier, rights, auths))
    for key, value in depends.items():
        setattr(g.depends_on, key, value)
    return g


def approved_state(world, *, with_g4: bool = False):
    """(approved dossier, approved rights, brief, timeline without the charge-sheet event)."""
    d0 = h.with_charge_sheet(world.dossier, filed=False)
    timeline0 = h.timeline_without(world, "e6")
    r0 = RightsEngine().run(d0, timeline0, h.AS_OF)
    grounds = [
        ground("G1", Factor.PARITY_WITH_CO_ACCUSED, h.G1_TEXT, d0, r0, ("DLHC-2022-1187", 14)),
        ground("G2", Factor.CHARGE_SHEET_FILED, G2_UNFILED, d0, r0),
        ground("G3", Factor.CUSTODY_PERIOD, h.G3_TEXT, d0, r0, ("DLHC-2021-0420", 11)),
    ]
    if with_g4:
        grounds.append(ground("G4", Factor.TRIAL_DELAY, G4_CITES_G2, d0, r0, claims=["G2"]))
    return d0, r0, BailBrief(case_id=h.CASE_ID, grounds=grounds), timeline0


def make_env(install_stores, monkeypatch, *, touched: tuple[str, ...] = ("charge_sheet",), with_g4: bool = False):
    world = h.case_0007_world()
    d0, r0, brief, timeline0 = approved_state(world, with_g4=with_g4)
    world.stores[StoreName.CASE_TIMELINE].events = list(timeline0)
    world.stores[StoreName.CASE_FACTS] = InMemoryFactsStore(d0.model_copy(deep=True))
    install_stores(world.stores)
    tb = ChangeToolbox(world, approved_dossier=d0, approved_rights=r0)
    tb.touched = touched
    llm = h.full_pipeline_llm(plan=h.plan_responder(authority_court=None))
    h.install_llm(monkeypatch, llm, nli=FakeNli())
    state = CaseGraphState(case_id=h.CASE_ID, dossier=d0, rights=r0, brief=brief)
    peshkar, ctx, _ = h.build_agent(PeshkarAgent, llm=llm, toolbox=tb, world=world)
    return SimpleNamespace(world=world, tb=tb, llm=llm, d0=d0, r0=r0, brief=brief, state=state, peshkar=peshkar, ctx=ctx)


def file_charge_sheet_order(env) -> None:
    """Counsel uploads the order; Munshi files its dated event on the shelf (plan §13.6 flow 4 step 1)."""
    env.tb.tools["file_item"](StoreName.CASE_TIMELINE, {"event_id": "e6", "date": "2024-11-02", "label": "Charge sheet filed"}, CS_ORDER)


def after_approval(env, change_set: ChangeSet) -> CaseGraphState:
    """The state after counsel re-approved: the new dossier and rights are current, the change set is pending redrafting."""
    new_dossier = h.with_charge_sheet(env.d0, filed=True, date="2024-11-02")
    new_rights = RightsEngine().run(new_dossier, env.world.stores[StoreName.CASE_TIMELINE].get(), h.AS_OF)
    return env.state.model_copy(update={"dossier": new_dossier, "rights": new_rights, "pending_change_set": change_set})


# ---- Peshkar: new document -> diff -------------------------------------------------------------------------------
def test_new_charge_sheet_document_changes_one_field_and_the_default_bail_check(install_stores, monkeypatch):
    """Plan §7.4: re-extract only the fields the document touches, diff, re-run the Rights Radar. Filing the charge sheet changes
    `charge_sheet` and turns default bail from an open window into WINDOW_CLOSED."""
    env = make_env(install_stores, monkeypatch)
    assert {c.check.value: c.status.value for c in env.r0.checks}["default_bail"] == "ELIGIBLE"
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    assert cs.trigger == "new_document"
    assert [f.field for f in cs.fields] == ["charge_sheet"]
    assert cs.fields[0].old_hash != cs.fields[0].new_hash
    assert cs.rights_changed == ["default_bail"]
    assert env.tb.count("rights_check") >= 1


def test_only_the_touched_field_is_re_extracted(install_stores, monkeypatch):
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    env.peshkar.detect_changes(env.state)
    calls = [c for c in env.tb.calls if c.name == "extract_dossier" and c.kwargs.get("fields")]
    assert calls and all(c.kwargs["fields"] == ["charge_sheet"] for c in calls)


def test_duplicate_document_is_a_no_op_for_peshkar(install_stores, monkeypatch):
    """T3 control: a duplicate document changes nothing: an empty change set (no fields, no events, no rights)."""
    env = make_env(install_stores, monkeypatch, touched=())
    cs = env.peshkar.detect_changes(env.state)
    assert cs.fields == [] and cs.new_event_ids == [] and cs.rights_changed == []


# ---- staleness ---------------------------------------------------------------------------------------------------
def test_only_the_claim_that_depends_on_the_charge_sheet_goes_stale(install_stores, monkeypatch):
    """Plan §10 step 1: G2 depends on `charge_sheet`; G1 (co_accused_bail, sections) and G3 (custody_days) do not."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    assert mark_stale(env.brief, cs) == ["G2"]


def test_claims_that_cite_a_stale_claim_go_stale_too(install_stores, monkeypatch):
    """Plan §10 step 1: G4 cites G2, so it is stale as well; G1 and G3 are not."""
    env = make_env(install_stores, monkeypatch, with_g4=True)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    assert sorted(mark_stale(env.brief, cs)) == ["G2", "G4"]


def test_charge_sheet_filed_reopens_its_factor_and_nothing_else_needs_replanning(install_stores, monkeypatch):
    """Plan §10 step 2: 'a factor may become available (charge sheet filed -> investigation complete)'. Sutradhar re-plans that factor, not parity."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    assert Factor.CHARGE_SHEET_FILED in factors_to_reopen(env.brief, cs)
    sut, _, _ = h.build_agent(SutradharAgent, llm=env.llm, toolbox=env.tb, world=env.world, budgets=BudgetTracker())
    reopened = sut.reopen_after_change(after_approval(env, cs), cs)
    assert Factor.CHARGE_SHEET_FILED in reopened
    assert Factor.PARITY_WITH_CO_ACCUSED not in reopened and Factor.CUSTODY_PERIOD not in reopened


# ---- incremental redrafting --------------------------------------------------------------------------------------
def redraft(env, cs: ChangeSet):
    state = after_approval(env, cs)
    return state, redraft_incrementally(state, cs)


def test_only_the_stale_ground_is_redrafted_and_the_rest_stay_word_for_word(install_stores, monkeypatch):
    """Plan §10 step 3-4 (flow 4): G2 is redrafted; G1 and G3 are identical to the approved text, including their dependencies."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    _, new = redraft(env, cs)
    old = {g.id: g for g in env.brief.grounds}
    cur = {g.id: g for g in new.grounds}
    assert [g.id for g in new.grounds] == ["G1", "G2", "G3"]
    assert cur["G1"].model_dump() == old["G1"].model_dump() and cur["G3"].model_dump() == old["G3"].model_dump()
    assert cur["G2"].argument != old["G2"].argument and "02.11.2024" in cur["G2"].argument
    assert len(h.calls_of(env.llm, "ground")) == 1


def test_redrafted_ground_depends_on_the_new_value_and_is_current(install_stores, monkeypatch):
    """The redrafted claim's dependency hash is that of the new charge-sheet value, and nothing is left STALE."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    state, new = redraft(env, cs)
    g2 = next(g for g in new.grounds if g.id == "G2")
    assert g2.depends_on.facts["charge_sheet"] == hash_value(state.dossier.fields.charge_sheet.value)
    assert g2.depends_on.facts["charge_sheet"] != next(g for g in env.brief.grounds if g.id == "G2").depends_on.facts["charge_sheet"]
    assert all(g.state == ClaimState.CURRENT for g in new.grounds)


def test_redrafted_ground_is_checked_again(install_stores, monkeypatch):
    """Checks re-run on changed claims only (plan §10 step 3): the redrafted G2 has a check result, other grounds keep theirs."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    _, new = redraft(env, cs)
    g2 = next(g for g in new.grounds if g.id == "G2")
    assert g2.check in set(ClaimCheck)
    assert all(a.citation for a in g2.authorities)


def test_chained_claims_are_both_redrafted(install_stores, monkeypatch):
    """G4 cites G2 (stale by propagation): two ground drafts, G1 and G3 untouched."""
    env = make_env(install_stores, monkeypatch, with_g4=True)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    _, new = redraft(env, cs)
    assert len(h.calls_of(env.llm, "ground")) == 2
    old = {g.id: g for g in env.brief.grounds}
    assert all(g.model_dump() == old[g.id].model_dump() for g in new.grounds if g.id in ("G1", "G3"))


def test_replanning_and_sparring_are_limited_to_what_changed(install_stores, monkeypatch):
    """Plan §10 step 3: Sutradhar re-plans only the reopened factor, Abhiyojak re-spars only on the changed ground; unchanged grounds' text is not sent."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    redraft(env, cs)
    planned = {h.detect_factor(c.prompt, default=Factor.CHARGE_SHEET_FILED) for c in h.calls_of(env.llm, "plan")}
    assert planned <= {Factor.CHARGE_SHEET_FILED}
    for call in h.calls_of(env.llm, *h.ABHIYOJAK_KINDS):
        assert h.G1_TEXT not in call.prompt and h.G3_TEXT not in call.prompt


def test_brief_view_highlights_what_changed_and_why(install_stores, monkeypatch):
    """Plan §10 step 4: one row, for G2, with a reason."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    _, new = redraft(env, cs)
    rows = diff_brief(env.brief, new)
    assert [(r.get("ground_id") or r["id"]) for r in rows] == ["G2"]
    assert rows[0]["reason"].strip()


def test_incremental_costs_less_than_full_regeneration(install_stores, monkeypatch):
    """Plan §10 / F2: 'tokens and time saved against full regeneration': one ground call against one per ground."""
    env = make_env(install_stores, monkeypatch)
    file_charge_sheet_order(env)
    cs = env.peshkar.detect_changes(env.state)
    state, _ = redraft(env, cs)
    incremental_calls, incremental_tokens = len(env.llm.calls), env.llm.total_tokens
    full_llm = h.full_pipeline_llm(plan=h.plan_responder(authority_court=None))
    h.install_llm(monkeypatch, full_llm, nli=FakeNli())
    full_regeneration(state)
    assert len(h.calls_of(full_llm, "ground")) >= len(env.brief.grounds) > len(h.calls_of(env.llm, "ground"))
    assert incremental_calls < len(full_llm.calls) and incremental_tokens < full_llm.total_tokens


# ---- the no-op control -------------------------------------------------------------------------------------------
def test_duplicate_document_leaves_the_brief_untouched_and_costs_no_model_call(install_stores, monkeypatch):
    """T3 control (F2: 'no edits on no-op controls'): empty change set -> nothing stale, nothing re-planned, nothing redrafted."""
    env = make_env(install_stores, monkeypatch, touched=())
    cs = env.peshkar.detect_changes(env.state)
    assert mark_stale(env.brief, cs) == []
    sut, _, _ = h.build_agent(SutradharAgent, llm=env.llm, toolbox=env.tb, world=env.world, budgets=BudgetTracker())
    assert sut.reopen_after_change(env.state, cs) == []
    new = redraft_incrementally(env.state, cs)
    assert new.model_dump() == env.brief.model_dump()
    assert env.llm.calls == []


# ---- the other two T3 change types ---------------------------------------------------------------------------------
def test_new_co_accused_bail_redrafts_only_the_parity_ground(install_stores, monkeypatch):
    """T3 change (b): a second co-accused is granted bail: `co_accused_bail` changes, only G1 (parity) is stale."""
    env = make_env(install_stores, monkeypatch)
    d1 = env.d0.model_copy(deep=True)
    d1.fields.co_accused_bail = TrackedField[list[CoAccusedBail]](
        value=[*env.d0.fields.co_accused_bail.value, CoAccusedBail(id="Co-accused-2", outcome="granted", date="2025-01-20")],
        source=env.d0.fields.co_accused_bail.source, status=FieldStatus.VERIFIED)
    cs = compute_change_set(env.d0, d1, env.r0, env.r0)
    assert [f.field for f in cs.fields] == ["co_accused_bail"] and cs.rights_changed == []
    assert mark_stale(env.brief, cs) == ["G1"]
    assert factors_to_reopen(env.brief, cs) == [Factor.PARITY_WITH_CO_ACCUSED]


def test_time_crossing_the_s479_threshold_creates_a_clock_change_set(install_stores, monkeypatch):
    """T3 change (c), plan §7.4: 'the radar also runs on a clock'. With antecedents known to be none, custody past 852 days turns the
    undertrial check from NOT_YET (2026-12-20) to ELIGIBLE; the crossing creates a change set and stales the claim that depends on it.

    ASSUMPTION: the engine reads `custody_days` from the dossier, so the later state carries 853 days (arrest 2024-08-20 to 2026-12-21)."""
    env = make_env(install_stores, monkeypatch)
    none_known = TrackedField[list[str]](value=[], source=SourceRef(chat="turn 5"), status=FieldStatus.USER_STATED)
    early, late = env.d0.model_copy(deep=True), env.d0.model_copy(deep=True)
    for d in (early, late):
        d.fields.antecedents = none_known
    late.fields.custody_days = TrackedField[int](value=853, source=SourceRef(tool="date_calc"), status=FieldStatus.COMPUTED)
    timeline = env.world.stores[StoreName.CASE_TIMELINE].get()
    engine = RightsEngine()
    r_early, r_late = engine.run(early, timeline, h.AS_OF), engine.run(late, timeline, "2026-12-21")
    assert engine.clock_crossings(r_early, r_late) == ["undertrial_limit"]
    cs = compute_change_set(early, late, r_early, r_late)
    assert "undertrial_limit" in cs.rights_changed
    g5 = ground("G5", Factor.UNDERTRIAL_PERIOD, "The applicant has crossed the s.479 period.", early, r_early, rights=["undertrial_limit"])
    brief = BailBrief(case_id=h.CASE_ID, grounds=[*env.brief.grounds, g5])
    assert "G5" in mark_stale(brief, cs)
    assert "G1" not in mark_stale(brief, cs)
