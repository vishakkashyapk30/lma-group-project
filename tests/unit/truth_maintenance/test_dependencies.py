"""Dependency records and value hashing (plan §10 'Dependencies', §8.1 [F:field] / [A:doc#para] tags).

`hash_value` gives a stable short hash 'h:xxxx' of a dossier value; `collect_dependencies` builds a claim's
`depends_on` from the tags in its text: facts map field -> hash of the field's value, authorities are 'doc_id#para'.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vakeel_sahayak.schemas.bail_brief import Authority, DependsOn
from vakeel_sahayak.schemas.dossier import ChargeSheetValue
from vakeel_sahayak.truth_maintenance.dependencies import collect_dependencies, hash_value

# ASSUMPTION: format is 'h:' followed by at least 4 lowercase hex digits (plan example 'h:3f2a').
HASH_RE = re.compile(r"h:[0-9a-f]{4,}")

json_scalars = st.one_of(st.none(), st.booleans(), st.integers(-10**6, 10**6), st.text(max_size=20))
json_values = st.recursive(
    json_scalars,
    lambda inner: st.one_of(st.lists(inner, max_size=4), st.dictionaries(st.text(min_size=1, max_size=6), inner, max_size=4)),
    max_leaves=10,
)


# ---- hash_value ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [167, "2024-11-02", None, True, [1, 2, 3], {"filed": True, "date": "2024-11-02"}, ["Accused-1", "Co-accused-1"], "रमेश"],
)
def test_hash_has_the_h_prefix_hex_format(value):
    """Plan §10: hashes look like 'h:3f2a'."""
    assert HASH_RE.fullmatch(hash_value(value))


def test_same_value_same_hash():
    """Plan §10: stable and deterministic."""
    value = {"filed": True, "date": "2024-11-02"}
    assert hash_value(value) == hash_value({"filed": True, "date": "2024-11-02"}) == hash_value(value)


@pytest.mark.parametrize(
    ("a", "b"),
    [
        (167, 168),
        ("2024-11-02", "2024-11-03"),
        ({"filed": True, "date": "2024-11-02"}, {"filed": False, "date": None}),
        (True, False),
        ("granted", "rejected"),
        ([1, 2], [1, 2, 3]),
        ("1", 1),
    ],
)
def test_different_values_different_hash(a, b):
    """Plan §10: a changed value changes the hash (these pairs must not collide)."""
    assert hash_value(a) != hash_value(b)


def test_dict_key_order_is_irrelevant():
    """Plan §10: value equality, not serialisation order, decides the hash."""
    assert hash_value({"a": 1, "b": {"x": 1, "y": 2}}) == hash_value({"b": {"y": 2, "x": 1}, "a": 1})


def test_list_order_matters():
    """Plan §10: a reordered list is a different value (e.g. the order of charged sections)."""
    assert hash_value(["BNS 318(4)", "BNS 61"]) != hash_value(["BNS 61", "BNS 318(4)"])


def test_pydantic_value_hashes_like_its_dump():
    """ASSUMPTION: dossier values are pydantic models; hashing a model equals hashing its dict form."""
    cs = ChargeSheetValue(filed=True, date="2024-11-02")
    assert hash_value(cs) == hash_value(cs.model_dump())


@given(json_values)
def test_property_deterministic_and_well_formed(value):
    """Plan §10: any value hashes the same every time, in the 'h:' format."""
    first = hash_value(value)
    assert first == hash_value(value)
    assert HASH_RE.fullmatch(first)


@given(st.dictionaries(st.text(min_size=1, max_size=5), st.integers(), min_size=2, max_size=6), st.randoms())
def test_property_dict_order_never_matters(d, rnd):
    """Plan §10: shuffling dict key order never changes the hash."""
    items = list(d.items())
    rnd.shuffle(items)
    assert hash_value(dict(items)) == hash_value(d)


# ---- collect_dependencies -----------------------------------------------------------------------------------
CLAIM = (
    "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail], so parity applies "
    "[A:DLHC-2022-1187#14]."
)
AUTHORITIES = [Authority(doc_id="DLHC-2022-1187", para=14), Authority(doc_id="DLHC-2021-0420", para=3)]


def test_facts_and_authorities_from_tags(dossier, expected_rights_report):
    """Plan §8.1/§10: [F:co_accused_bail] and [A:DLHC-2022-1187#14] become the claim's dependencies."""
    deps = collect_dependencies(CLAIM, dossier, expected_rights_report, AUTHORITIES)
    assert isinstance(deps, DependsOn)
    assert deps.facts == {"co_accused_bail": hash_value(dossier.fields.co_accused_bail.value)}
    assert deps.authorities == ["DLHC-2022-1187#14"]


def test_uncited_authority_is_not_a_dependency(dossier, expected_rights_report):
    """Plan §10: only authorities tagged in the text count, not every retrieved one."""
    deps = collect_dependencies(CLAIM, dossier, expected_rights_report, AUTHORITIES)
    assert "DLHC-2021-0420#3" not in deps.authorities


def test_several_fact_tags_each_hash_their_own_field(dossier, expected_rights_report):
    """Plan §10: one hash per [F:field] tag, from that field's current value."""
    text = "Charge sheet filed [F:charge_sheet]; custody is 167 days [F:custody_days]; charges not framed [F:trial_stage]."
    deps = collect_dependencies(text, dossier, expected_rights_report, [])
    assert deps.facts == {
        "charge_sheet": hash_value(dossier.fields.charge_sheet.value),
        "custody_days": hash_value(dossier.fields.custody_days.value),
        "trial_stage": hash_value(dossier.fields.trial_stage.value),
    }
    assert deps.authorities == []


def test_repeated_tag_counts_once(dossier, expected_rights_report):
    """Plan §10: a field tagged twice is one dependency and a citation tagged twice is listed once."""
    text = "Bail to co-accused [F:co_accused_bail] [A:DLHC-2022-1187#14]. Again [F:co_accused_bail] [A:DLHC-2022-1187#14]."
    deps = collect_dependencies(text, dossier, expected_rights_report, AUTHORITIES)
    assert list(deps.facts) == ["co_accused_bail"]
    assert deps.authorities == ["DLHC-2022-1187#14"]


def test_claim_without_tags_has_no_dependencies(dossier, expected_rights_report):
    """Plan §10: an untagged sentence depends on nothing."""
    deps = collect_dependencies("Bail is a right, jail the exception.", dossier, expected_rights_report, AUTHORITIES)
    assert deps.facts == {} and deps.authorities == []


def test_fact_hash_changes_when_the_field_value_changes(dossier, expected_rights_report):
    """Plan §10: the stored hash follows the dossier value, so a later change is detectable."""
    changed = dossier.model_copy(deep=True)
    changed.fields.co_accused_bail.value = []
    old = collect_dependencies(CLAIM, dossier, expected_rights_report, AUTHORITIES)
    new = collect_dependencies(CLAIM, changed, expected_rights_report, AUTHORITIES)
    assert old.facts["co_accused_bail"] != new.facts["co_accused_bail"]
