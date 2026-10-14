"""The fixed urgency rule (plan §11).

Order: (1) legal deadlines (default-bail window open or opening soon; s.479 threshold crossed); (2) days past a
threshold (more days past first); (3) custody length (longer first). Ties go to cases with no missing documents.

ASSUMPTIONS: `urgency_key` sorts ascending, most urgent first (so `rank` can use `sorted`); days-past / days-left are
read from the RightsCheckResult.detail text ("N days past", "opens in N days"); `rank` works from what
`make_card` put on the card (reasons / flags / missing_docs), because TriageCard carries no RightsReport; ties between
fully equal cards are broken by case_id so ranking is deterministic.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tests.unit.batch._helpers import (
    DEFAULT_CLOSED,
    DEFAULT_NONE,
    DEFAULT_OPEN,
    DEFAULT_SOON,
    S479_CROSSED_5,
    S479_CROSSED_48,
    S479_NONE,
    card,
    rights,
)
from vakeel_sahayak.batch.urgency import rank, urgency_key


def key(default_bail=DEFAULT_NONE, undertrial=S479_NONE, custody=100, missing=()):
    return urgency_key(rights(default_bail, undertrial), custody, list(missing))


# ---- urgency_key --------------------------------------------------------------------------------------------
def test_key_is_a_tuple():
    """Plan §11: the key is a sortable tuple."""
    assert isinstance(key(), tuple)


def test_default_bail_open_beats_window_closed_beats_no_flag():
    """Plan §11 (1): an open default-bail window outranks a closed one, which outranks a case with no flag."""
    open_ = key(DEFAULT_OPEN, custody=10)
    closed = key(DEFAULT_CLOSED, custody=500)
    none = key(DEFAULT_NONE, custody=2000)
    assert open_ < closed < none


def test_window_opening_soon_outranks_no_flag():
    """Plan §11 (1): 'opening soon' (3 days left) is a legal deadline; it outranks a longer-custody case with no flag."""
    assert key(DEFAULT_SOON, custody=30) < key(DEFAULT_NONE, custody=3000)


def test_s479_threshold_crossed_outranks_no_flag():
    """Plan §11 (1): s.479 threshold crossed is a legal deadline."""
    assert key(undertrial=S479_CROSSED_5, custody=900) < key(custody=3000)


def test_legal_deadline_outranks_longer_custody():
    """Plan §11: criterion (1) beats criterion (3) however long the other custody is."""
    assert key(DEFAULT_OPEN, custody=5) < key(DEFAULT_NONE, custody=5000)


def test_more_days_past_threshold_ranks_first():
    """Plan §11 (2): between two s.479-crossed cases the one further past ranks first."""
    assert key(undertrial=S479_CROSSED_48, custody=900) < key(undertrial=S479_CROSSED_5, custody=900)


def test_days_past_outranks_custody_length():
    """Plan §11: criterion (2) beats (3): fewer days in custody but more days past the threshold ranks first."""
    assert key(undertrial=S479_CROSSED_48, custody=900) < key(undertrial=S479_CROSSED_5, custody=1000)


def test_longer_custody_ranks_first_when_nothing_else_differs():
    """Plan §11 (3): custody length decides next."""
    assert key(custody=300) < key(custody=100)


def test_unknown_custody_ranks_after_known_custody_without_error():
    """ASSUMPTION: custody_days None (not on record) sorts last and never raises on comparison."""
    assert key(custody=1) < key(custody=None)
    assert sorted([key(custody=None), key(custody=50)])[0] == key(custody=50)


def test_tie_goes_to_the_case_with_no_missing_documents():
    """Plan §11: with everything else equal the case with no missing documents ranks first."""
    assert key(custody=100, missing=[]) < key(custody=100, missing=["custody certificate"])


def test_missing_documents_do_not_outweigh_custody():
    """Plan §11: missing documents only break ties; longer custody with a missing document still ranks first."""
    assert key(custody=300, missing=["custody certificate"]) < key(custody=100, missing=[])


def test_equal_inputs_give_equal_keys():
    """Plan §11: fixed and explainable: same inputs, same key."""
    assert key(DEFAULT_CLOSED, S479_CROSSED_5, 250, ["x"]) == key(DEFAULT_CLOSED, S479_CROSSED_5, 250, ["x"])


@given(a=st.integers(0, 4000), b=st.integers(0, 4000))
def test_property_custody_is_monotone(a, b):
    """Plan §11 (3): all else equal, strictly longer custody sorts strictly earlier."""
    if a > b:
        assert key(custody=a) < key(custody=b)
    elif a == b:
        assert key(custody=a) == key(custody=b)


# ---- rank ---------------------------------------------------------------------------------------------------
def _ids(cards):
    return [c.case_id for c in cards]


def test_rank_orders_by_the_plan_rule():
    """Plan §11: legal deadline first, then window-closed, then custody length."""
    cards = [
        card("c-long-custody", custody=2000),
        card("c-closed", DEFAULT_CLOSED, custody=500),
        card("c-open", DEFAULT_OPEN, custody=10),
        card("c-short", custody=30),
    ]
    ranked = rank(cards)
    assert _ids(ranked) == ["c-open", "c-closed", "c-long-custody", "c-short"]


def test_rank_assigns_one_to_n_without_gaps():
    """Plan §11: urgency_rank is 1..n in order."""
    ranked = rank([card(f"c{i}", custody=100 * i) for i in range(1, 6)])
    assert [c.urgency_rank for c in ranked] == [1, 2, 3, 4, 5]


def test_rank_agrees_with_urgency_key():
    """Plan §11: rank is exactly the sort by `urgency_key` (distinct keys)."""
    specs = {
        "a": dict(default_bail=DEFAULT_OPEN, custody=40),
        "b": dict(undertrial=S479_CROSSED_48, custody=900),
        "c": dict(undertrial=S479_CROSSED_5, custody=950),
        "d": dict(default_bail=DEFAULT_CLOSED, custody=300),
        "e": dict(custody=700),
        "f": dict(custody=200),
    }
    keyed = {cid: urgency_key(rights(s.get("default_bail", DEFAULT_NONE), s.get("undertrial", S479_NONE)), s["custody"], []) for cid, s in specs.items()}
    expected = sorted(specs, key=lambda cid: keyed[cid])
    assert _ids(rank([card(cid, **s) for cid, s in specs.items()])) == expected


def test_rank_puts_no_missing_documents_first_on_a_tie():
    """Plan §11: identical cases except for a missing document -> the complete file first."""
    ranked = rank([card("c-missing", custody=100, missing=["custody certificate"]), card("c-complete", custody=100)])
    assert _ids(ranked) == ["c-complete", "c-missing"]


def test_rank_is_independent_of_input_order():
    """Plan §11: deterministic; equal cards are ordered by case_id (ASSUMPTION), so input order never matters."""
    cards = [card("c2", custody=100), card("c1", custody=100), card("c3", DEFAULT_OPEN, custody=5)]
    assert _ids(rank(cards)) == _ids(rank(list(reversed(cards)))) == ["c3", "c1", "c2"]


def test_rank_of_empty_list_is_empty():
    """Plan §11: nothing to rank."""
    assert rank([]) == []


_levels = st.sampled_from([DEFAULT_OPEN, DEFAULT_SOON, DEFAULT_CLOSED, DEFAULT_NONE])
_ut = st.sampled_from([S479_CROSSED_48, S479_CROSSED_5, S479_NONE])


@given(
    specs=st.lists(
        st.tuples(_levels, _ut, st.one_of(st.none(), st.integers(0, 3000)), st.booleans()), min_size=1, max_size=8
    )
)
def test_property_rank_is_a_gapless_permutation_and_stable(specs):
    """Plan §11 hypothesis: rank is a permutation of 1..n and re-ranking a ranked list changes nothing."""
    cards = [card(f"c{i:02d}", d, u, cu, ["custody certificate"] if m else []) for i, (d, u, cu, m) in enumerate(specs)]
    ranked = rank(cards)
    assert sorted(_ids(ranked)) == sorted(_ids(cards))
    assert [c.urgency_rank for c in ranked] == list(range(1, len(cards) + 1))
    again = rank(ranked)
    assert _ids(again) == _ids(ranked)
    assert [c.urgency_rank for c in again] == [c.urgency_rank for c in ranked]
