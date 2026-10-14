"""Incremental redrafting driver and the full-regeneration baseline (plan §10 steps 3-4, §15.6 F2, §15.2 T3).

Only stale claims are redrafted; unchanged claims stay word for word; a no-op change set costs zero LLM calls;
the brief view reports what changed and why; `full_regeneration` (baseline F2) touches every claim.

ASSUMPTIONS (the skeleton's `redraft_incrementally(state, change_set)` has no LLM parameter):
* the LLM is resolved through `vakeel_sahayak.models.factory.get_llm` (patched here with a ScriptedLLM) and the NLI
  checker through `get_nli` (patched with the FakeNli); stores are the in-memory fakes;
* one LLM call redrafts one stale claim, and no other LLM call is made while redrafting (re-planning and re-sparring
  are done without extra LLM calls in this unit setting).
"""

from __future__ import annotations

import pytest

from tests.fakes.models import FakeNli, ScriptedLLM
from tests.unit.truth_maintenance._helpers import change, install_llm, make_brief, respond_like_a_drafter, states
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.enums import ClaimState
from vakeel_sahayak.truth_maintenance.redraft import diff_brief, full_regeneration, redraft_incrementally


@pytest.fixture()
def llm(monkeypatch, install_stores):
    """A ScriptedLLM installed as the only LLM; every call is recorded in `llm.calls`."""
    counter = [0]
    scripted = ScriptedLLM(default="REDRAFTED", strict=False, by_prompt=[("", respond_like_a_drafter(counter))])
    install_llm(monkeypatch, scripted, nli=FakeNli())
    install_stores()
    return scripted


@pytest.fixture()
def state(dossier, expected_rights_report):
    return CaseGraphState(case_id="case-0007", dossier=dossier, rights=expected_rights_report, brief=make_brief())


def test_only_stale_claims_are_redrafted(llm, state):
    """Plan §10 step 3: with the charge sheet changed, G2 and G3 are stale; the LLM is called exactly twice."""
    new = redraft_incrementally(state, change("charge_sheet"))
    assert len(llm.calls) == 2  # exactly the stale claims G2 and G3
    old = {g.id: g for g in make_brief().grounds}
    assert new.grounds[1].argument != old["G2"].argument
    assert new.grounds[2].argument != old["G3"].argument


def test_unchanged_claims_are_byte_identical(llm, state):
    """Plan §10 step 4: unchanged claims stay word for word (the whole ground record is identical)."""
    old = {g.id: g.model_dump() for g in make_brief().grounds}
    new = redraft_incrementally(state, change("charge_sheet"))
    got = {g.id: g.model_dump() for g in new.grounds}
    for gid in ("G1", "G4", "G5"):
        assert got[gid] == old[gid]
        assert got[gid]["argument"] == old[gid]["argument"]


def test_unrelated_claim_text_is_never_sent_to_the_llm(llm, state):
    """Plan §10 step 3: claims that are not stale are not part of any redraft prompt (tokens saved)."""
    redraft_incrementally(state, change("charge_sheet"))
    g4 = make_brief().grounds[3].argument
    g5 = make_brief().grounds[4].argument
    assert all(g4 not in p and g5 not in p for p in llm.prompts)


def test_order_and_ids_of_grounds_are_preserved(llm, state):
    """Plan §10 step 4: the brief keeps the same grounds in the same order."""
    new = redraft_incrementally(state, change("charge_sheet"))
    assert [g.id for g in new.grounds] == ["G1", "G2", "G3", "G4", "G5"]
    assert new.case_id == "case-0007"


def test_redrafted_claims_are_current_again(llm, state):
    """Plan §10: after redrafting nothing is left STALE."""
    new = redraft_incrementally(state, change("charge_sheet"))
    assert all(s is ClaimState.CURRENT for s in states(new).values())


def test_redrafting_a_root_claim_redrafts_the_whole_chain(llm, state):
    """Plan §10 step 1+3: a changed co_accused_bail stales G1, G2, G3 (transitively) and exactly three calls are made."""
    redraft_incrementally(state, change("co_accused_bail"))
    assert len(llm.calls) == 3


def test_noop_change_set_makes_zero_llm_calls_and_returns_the_same_brief(llm, state):
    """Plan §15.2 T3 control: an empty change set -> no LLM calls and an identical brief."""
    new = redraft_incrementally(state, ChangeSet(case_id="case-0007", trigger="clock"))
    assert llm.calls == []
    assert new.model_dump() == make_brief().model_dump()


def test_change_nobody_depends_on_makes_zero_llm_calls(llm, state):
    """Plan §10: a changed field no claim depends on stales nothing, so nothing is redrafted."""
    new = redraft_incrementally(state, change("custody_days"))
    assert llm.calls == []
    assert new.model_dump() == make_brief().model_dump()


# ---- diff_brief ---------------------------------------------------------------------------------------------
def _ground_id(row: dict[str, str]) -> str:
    # ASSUMPTION: a change row names its ground under 'ground_id' (or 'id') and explains it under 'reason'.
    return row.get("ground_id") or row["id"]


def test_diff_reports_changed_grounds_with_a_reason():
    """Plan §10 step 4: the brief view highlights what changed and why: one row per changed ground, with a reason."""
    old = make_brief()
    new = make_brief()
    new.grounds[1].argument = "Investigation is complete: the charge sheet was filed on 02.11.2024 [F:charge_sheet]."
    new.grounds[2].argument = "Charges are not framed; see ground G2 as redrafted."
    rows = diff_brief(old, new)
    assert {_ground_id(r) for r in rows} == {"G2", "G3"}
    assert all(r["reason"].strip() for r in rows)


def test_diff_of_identical_briefs_is_empty():
    """Plan §10 step 4 / T3: no change, no rows."""
    assert diff_brief(make_brief(), make_brief()) == []


def test_diff_does_not_report_unchanged_grounds():
    """Plan §10 step 4: unchanged claims are not highlighted."""
    old, new = make_brief(), make_brief()
    new.grounds[3].argument = "Antecedents: two earlier FIRs were found [F:antecedents]."
    assert [_ground_id(r) for r in diff_brief(old, new)] == ["G4"]


# ---- full regeneration baseline (F2) -------------------------------------------------------------------------
def test_full_regeneration_touches_every_claim(llm, state):
    """Plan §15.6 F2: the baseline regenerates all claims (every ground gets new text)."""
    new = full_regeneration(state)
    old = {g.id: g.argument for g in make_brief().grounds}
    assert len(llm.calls) >= len(old)
    assert [g.id for g in new.grounds] == list(old)
    assert all(g.argument != old[g.id] for g in new.grounds)


def test_incremental_uses_fewer_llm_calls_than_full_regeneration(llm, state, dossier, expected_rights_report):
    """Plan §10 'tokens and time saved against full regeneration' (T3): incremental < full for a one-field change."""
    redraft_incrementally(state, change("charge_sheet"))
    incremental_calls = len(llm.calls)
    llm.calls.clear()
    full_regeneration(CaseGraphState(case_id="case-0007", dossier=dossier, rights=expected_rights_report, brief=make_brief()))
    assert incremental_calls < len(llm.calls)
