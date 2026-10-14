"""Change sets and staleness propagation (plan §7.4 change detection, §10 steps 1-2, §15.2 T3 constructed change sets).

`compute_change_set` diffs two approved states; `mark_stale` marks claims with a changed dependency STALE and
propagates through claims that cite a stale claim; `factors_to_reopen` says which factors may newly apply or drop out.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.unit.truth_maintenance._helpers import change, ground, make_brief, states, with_charge_sheet
from vakeel_sahayak.schemas.bail_brief import BailBrief, DependsOn
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.enums import ClaimState, Factor, RightsStatus
from vakeel_sahayak.truth_maintenance.dependencies import hash_value
from vakeel_sahayak.truth_maintenance.staleness import compute_change_set, factors_to_reopen, mark_stale

CURRENT, STALE = ClaimState.CURRENT, ClaimState.STALE
TRIGGERS = {"new_document", "clock", "counsel_edit"}


# ---- compute_change_set -------------------------------------------------------------------------------------
def test_charge_sheet_filed_changes_exactly_the_charge_sheet_field(dossier, expected_rights_report):
    """Plan §7.4/T3: a charge sheet filed on 2024-11-02 (vs not filed) changes exactly one field, with old/new hashes."""
    old = with_charge_sheet(dossier, filed=False, date=None)
    cs = compute_change_set(old, dossier, expected_rights_report, expected_rights_report)
    assert [f.field for f in cs.fields] == ["charge_sheet"]
    fc = cs.fields[0]
    assert fc.old_hash == hash_value(old.fields.charge_sheet.value)
    assert fc.new_hash == hash_value(dossier.fields.charge_sheet.value)
    assert fc.old_hash != fc.new_hash
    assert cs.rights_changed == []
    assert cs.case_id == "case-0007"
    assert cs.trigger in TRIGGERS


def test_identical_dossiers_give_an_empty_change_set(dossier, expected_rights_report):
    """Plan §15.2 T3: the no-op control: nothing changed -> empty ChangeSet."""
    cs = compute_change_set(dossier, dossier.model_copy(deep=True), expected_rights_report, expected_rights_report)
    assert cs.fields == [] and cs.rights_changed == [] and cs.new_event_ids == []


def test_two_changed_fields_are_both_reported_and_nothing_else(dossier, expected_rights_report):
    """Plan §7.4: the diff lists every changed field (here custody_days and trial_stage) and only those."""
    new = dossier.model_copy(deep=True)
    new.fields.custody_days.value = 168
    new.fields.trial_stage.value = "charges framed"
    cs = compute_change_set(dossier, new, expected_rights_report, expected_rights_report)
    assert {f.field for f in cs.fields} == {"custody_days", "trial_stage"}
    by_field = {f.field: f for f in cs.fields}
    assert by_field["custody_days"].old_hash == hash_value(167)
    assert by_field["custody_days"].new_hash == hash_value(168)


def test_field_filled_for_the_first_time_has_no_old_hash(dossier, expected_rights_report):
    """ASSUMPTION: a previously empty field (antecedents None) has old_hash None and a real new hash."""
    new = dossier.model_copy(deep=True)
    new.fields.antecedents.value = ["none pending"]
    cs = compute_change_set(dossier, new, expected_rights_report, expected_rights_report)
    assert [f.field for f in cs.fields] == ["antecedents"]
    assert cs.fields[0].old_hash is None
    assert cs.fields[0].new_hash == hash_value(["none pending"])


def test_source_only_change_is_not_a_value_change(dossier, expected_rights_report):
    """ASSUMPTION: only values are diffed; a different quote or status with the same value changes nothing."""
    new = dossier.model_copy(deep=True)
    new.fields.trial_stage.source.quote = "Charges not framed (re-read)"
    cs = compute_change_set(dossier, new, expected_rights_report, expected_rights_report)
    assert cs.fields == []


def test_rights_status_change_is_listed_in_rights_changed(dossier, expected_rights_report):
    """Plan §7.4: a Rights Radar status change (default_bail WINDOW_CLOSED -> ELIGIBLE) is reported by check name."""
    new_rights = expected_rights_report.model_copy(deep=True)
    for check in new_rights.checks:
        if check.check.value == "default_bail":
            check.status = RightsStatus.ELIGIBLE
    cs = compute_change_set(dossier, dossier.model_copy(deep=True), expected_rights_report, new_rights)
    assert cs.rights_changed == ["default_bail"]
    assert cs.fields == []


# ---- mark_stale ---------------------------------------------------------------------------------------------
def test_direct_dependency_change_marks_the_claim_stale():
    """Plan §10 step 1: a claim whose dependency hash changed becomes STALE."""
    brief = make_brief()
    stale = mark_stale(brief, change("trial_stage"))
    assert stale == ["G3"]
    assert states(brief)["G3"] is STALE


def test_claim_citing_a_stale_claim_becomes_stale_transitively():
    """Plan §10 step 1: the chain G1 <- G2 <- G3 goes stale from its root."""
    brief = make_brief()
    stale = mark_stale(brief, change("co_accused_bail"))
    assert set(stale) == {"G1", "G2", "G3"}
    assert states(brief) == {"G1": STALE, "G2": STALE, "G3": STALE, "G4": CURRENT, "G5": CURRENT}


def test_middle_of_chain_staleness_reaches_downstream_only():
    """Plan §10 step 1: staleness flows to claims that cite the stale one, not back to the claims it cites."""
    brief = make_brief()
    stale = mark_stale(brief, change("charge_sheet"))
    assert set(stale) == {"G2", "G3"}
    assert states(brief)["G1"] is CURRENT


def test_unrelated_claims_stay_current():
    """Plan §10 step 4: claims without a changed dependency are untouched."""
    brief = make_brief()
    mark_stale(brief, change("charge_sheet"))
    st_ = states(brief)
    assert st_["G1"] is CURRENT and st_["G4"] is CURRENT and st_["G5"] is CURRENT


def test_change_to_a_field_nobody_uses_marks_nothing():
    """Plan §10: a changed field that no claim depends on leaves every claim CURRENT."""
    brief = make_brief()
    assert mark_stale(brief, change("custody_days")) == []
    assert all(s is CURRENT for s in states(brief).values())


def test_rights_dependency_marks_the_claim_stale():
    """Plan §10: claims depending on a RightsReport entry go stale when that check changes."""
    brief = make_brief()
    assert mark_stale(brief, change(rights=["undertrial_limit"])) == ["G5"]
    assert states(brief)["G5"] is STALE


def test_noop_change_set_marks_nothing_stale():
    """Plan §15.2 T3 control: an empty change set returns [] and leaves every claim CURRENT."""
    brief = make_brief()
    empty = ChangeSet(case_id="case-0007", trigger="clock")
    assert mark_stale(brief, empty) == []
    assert all(s is CURRENT for s in states(brief).values())


def test_two_changes_union_their_stale_sets():
    """Plan §10: several changed fields stale the union of their dependants."""
    brief = make_brief()
    stale = mark_stale(brief, change("antecedents", "trial_stage"))
    assert set(stale) == {"G3", "G4"}


@given(
    n=st.integers(2, 9),
    cites=st.data(),
    changed=st.sets(st.integers(0, 8), max_size=4),
)
def test_property_stale_set_is_the_downstream_closure(n, cites, changed):
    """Plan §10: stale = claims with a changed fact plus everything that (transitively) cites them.

    Oracle: a plain fixed-point closure over the constructed citation edges.
    """
    names = [f"f{i}" for i in range(n)]
    grounds = []
    edges: dict[str, list[str]] = {}
    for i in range(n):
        cited = cites.draw(st.lists(st.integers(0, max(i - 1, 0)), max_size=2, unique=True)) if i else []
        edges[f"G{i}"] = [f"G{j}" for j in cited if j < i]
        g = ground(f"G{i}", Factor.ANTECEDENTS, f"claim {i}", claims=edges[f"G{i}"])
        g.depends_on = DependsOn(facts={names[i]: f"h:{i:04x}"}, claims=edges[f"G{i}"])
        grounds.append(g)
    brief = BailBrief(case_id="case-0007", grounds=grounds)
    changed_names = {names[i] for i in changed if i < n}
    cs = ChangeSet(
        case_id="case-0007",
        trigger="new_document",
        fields=[FieldChange(field=f, old_hash=f"h:{names.index(f):04x}", new_hash="h:ffff") for f in sorted(changed_names)],
    )
    expected = {f"G{names.index(f)}" for f in changed_names}
    grew = True
    while grew:
        grew = False
        for gid, cited in edges.items():
            if gid not in expected and any(c in expected for c in cited):
                expected.add(gid)
                grew = True
    assert set(mark_stale(brief, cs)) == expected
    assert {g.id for g in brief.grounds if g.state is STALE} == expected


# ---- factors_to_reopen --------------------------------------------------------------------------------------
def test_charge_sheet_filed_reopens_the_charge_sheet_factor():
    """Plan §10 step 2: a filed charge sheet makes 'investigation complete' available (charge_sheet_filed reopens)."""
    brief = BailBrief(case_id="case-0007", grounds=[make_brief().grounds[0]])  # brief has only a parity ground
    assert Factor.CHARGE_SHEET_FILED in factors_to_reopen(brief, change("charge_sheet"))


def test_charge_sheet_change_reopens_an_existing_charge_sheet_ground_too():
    """Plan §10 step 2: a factor may also drop out; an existing charge_sheet_filed ground is reopened for re-check."""
    assert Factor.CHARGE_SHEET_FILED in factors_to_reopen(make_brief(), change("charge_sheet"))


def test_co_accused_change_reopens_parity():
    """ASSUMPTION: a changed co_accused_bail field reopens parity_with_co_accused and not charge_sheet_filed."""
    reopened = factors_to_reopen(make_brief(), change("co_accused_bail"))
    assert Factor.PARITY_WITH_CO_ACCUSED in reopened
    assert Factor.CHARGE_SHEET_FILED not in reopened


def test_noop_change_set_reopens_no_factor():
    """Plan §15.2 T3 control: nothing changed -> no factor is re-planned."""
    assert factors_to_reopen(make_brief(), ChangeSet(case_id="case-0007", trigger="clock")) == []


def test_reopened_factors_are_factor_enums_without_duplicates():
    """Plan §10 step 2: the result is a list of Factor, each once."""
    reopened = factors_to_reopen(make_brief(), change("charge_sheet", "trial_stage", "co_accused_bail"))
    assert all(isinstance(f, Factor) for f in reopened)
    assert len(reopened) == len(set(reopened))
