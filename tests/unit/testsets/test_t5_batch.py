"""T5 batch set (plan §15.2, §11, F4): the 200 T1 cases plus 100 T4 scenarios with deadlines planted in the NEXT 7 DAYS; 300 cases.
Answers by construction: the planted deadlines are recorded as truth, so 'every case with a near deadline ranks ahead of the rest' is
checkable without any labelling.

# ASSUMPTION: out_dir/cases.jsonl rows {"case_id", "source": "T1" | "T4", "as_of", "deadline": <ISO date or None>, "deadline_kind"}.
# ASSUMPTION: a T1 case has no deadline inside the 7-day window; only the 100 T4 scenarios carry a planted one.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from tests.unit.testsets._helpers import assert_manifest, read_manifest, read_rows, write_t1_dir, write_t4_dir
from vakeel_sahayak.testsets.t5_batch import build_t5


def build(tmp_path, n_t4: int = 120):
    t1, t4 = write_t1_dir(tmp_path), write_t4_dir(tmp_path, n_t4)
    out = tmp_path / "t5"
    m = build_t5(str(t1), str(t4), str(out))
    return m, read_rows(out / "cases.jsonl"), out


def test_three_hundred_cases_two_hundred_t1_and_one_hundred_t4(tmp_path):
    m, rows, out = build(tmp_path)
    assert_manifest(m, "T5", 300)
    assert len(rows) == 300 and m.used_for == ["F4"]
    assert sum(r["source"] == "T1" for r in rows) == 200 and sum(r["source"] == "T4" for r in rows) == 100
    assert len({r["case_id"] for r in rows}) == 300
    assert read_manifest(out)["size"] == 300


def test_every_planted_deadline_falls_in_the_next_seven_days(tmp_path):
    """Planted deadlines satisfy as_of < deadline <= as_of + 7 days (plan §15.2)."""
    _, rows, _ = build(tmp_path)
    planted = [r for r in rows if r["deadline"]]
    assert len(planted) == 100 and all(r["source"] == "T4" for r in planted)
    for r in planted:
        as_of, deadline = date.fromisoformat(r["as_of"]), date.fromisoformat(r["deadline"])
        assert as_of < deadline <= as_of + timedelta(days=7), r


def test_deadlines_are_spread_over_the_week_so_that_ranking_is_not_trivial(tmp_path):
    """# ASSUMPTION: at least five distinct days are used, so pairwise ranking accuracy (F4) measures ordering, not just a flag."""
    _, rows, _ = build(tmp_path)
    assert len({r["deadline"] for r in rows if r["deadline"]}) >= 5


def test_t1_cases_have_no_deadline_in_the_window(tmp_path):
    _, rows, _ = build(tmp_path)
    for r in rows:
        if r["source"] == "T1":
            assert not r["deadline"] or date.fromisoformat(r["deadline"]) > date.fromisoformat(r["as_of"]) + timedelta(days=7)


def test_all_cases_share_one_as_of_date(tmp_path):
    """One 'today' for the whole desk, so urgency is comparable across cases."""
    _, rows, _ = build(tmp_path)
    assert len({r["as_of"] for r in rows}) == 1


def test_build_is_deterministic(tmp_path):
    t1, t4 = write_t1_dir(tmp_path), write_t4_dir(tmp_path)
    build_t5(str(t1), str(t4), str(tmp_path / "a"))
    build_t5(str(t1), str(t4), str(tmp_path / "b"))
    assert (tmp_path / "a" / "cases.jsonl").read_bytes() == (tmp_path / "b" / "cases.jsonl").read_bytes()


def test_fewer_than_one_hundred_t4_scenarios_is_an_error(tmp_path):
    t1, t4 = write_t1_dir(tmp_path), write_t4_dir(tmp_path, 60)
    with pytest.raises(ValueError):
        build_t5(str(t1), str(t4), str(tmp_path / "t5"))
