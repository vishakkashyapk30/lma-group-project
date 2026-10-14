"""Date-based splits (plan §2 'Splits by date', configs/splits.yaml).

Train: orders before 2024. Dev: early 2024 (2024-01-01..2024-04-01), 50 orders. Test: mid-2024 to 2025
(2024-06-01..2025-12-31), 200 orders sampled across High Courts, of which at least 60 are BNS-era (offence on or after 1 July 2024).
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.unit.pipelines._helpers import COURTS, order_row, read_json, spread_dates, write_jsonl
from vakeel_sahayak.pipelines.splits import assign_splits, is_bns_era

BNS_START = date(2024, 7, 1)


# ---- config facts (pass today) -----------------------------------------------------------------------------------
def test_splits_yaml_matches_plan(load_yaml):
    """configs/splits.yaml encodes the plan §2 table: boundaries, 50 dev, 200 test, >=60 BNS-era, BNS start 2024-07-01."""
    cfg = load_yaml("splits.yaml")
    assert cfg["train"] == {"before": "2024-01-01"}
    assert cfg["dev"] == {"from": "2024-01-01", "to": "2024-04-01", "n": 50}
    assert cfg["test"] == {"from": "2024-06-01", "to": "2025-12-31", "n": 200, "min_bns_era": 60}
    assert cfg["bns_era_offence_on_or_after"] == "2024-07-01"


# ---- is_bns_era --------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("offence", "expected"),
    [("2024-06-30", False), ("2024-07-01", True), ("2024-07-02", True), ("2023-12-31", False), ("2025-01-01", True),
     ("2019-01-01", False)],
)
def test_is_bns_era_boundary(offence, expected):
    """The BNS applies to offences on or after 1 July 2024: 30 June is IPC-era, 1 July is BNS-era."""
    assert is_bns_era(offence) is expected


@given(st.integers(min_value=-400, max_value=400))
def test_is_bns_era_property_around_boundary(delta):
    """Property: for any day within a year of 2024-07-01, is_bns_era is exactly `date >= 2024-07-01`."""
    d = BNS_START + timedelta(days=delta)
    assert is_bns_era(d.isoformat()) is (d >= BNS_START)


# ---- assign_splits -----------------------------------------------------------------------------------------------
def _big_orders() -> list[dict]:
    rows = []
    # 400 train orders in 2019-2023
    for i, d in enumerate(spread_dates("2019-01-01", 400, 4)):
        rows.append(order_row(f"TR-{i:04d}", d, COURTS[i % 4], fir=str(i), fir_year=2018 + i % 5))
    # 80 dev candidates in 2024-01-01..2024-04-01 (91 days)
    for i in range(80):
        d = date(2024, 1, 1) + timedelta(days=int(i * 90 / 79))
        rows.append(order_row(f"DV-{i:04d}", d.isoformat(), COURTS[i % 4], fir=f"d{i}", fir_year=2023))
    # a gap between dev and test: 2024-04-02..2024-05-31
    for i in range(10):
        rows.append(order_row(f"GP-{i:04d}", (date(2024, 4, 5) + timedelta(days=i * 5)).isoformat(), fir=f"g{i}", fir_year=2024))
    # 300 test candidates: 100 BNS-era offences, 200 IPC-era offences, orders 2024-06-01..2025-12-31
    for i, d in enumerate(spread_dates("2024-06-01", 300, 1)):
        bns = i < 100
        rows.append(order_row(f"TS-{i:04d}", d, COURTS[i % 4], offence_date="2024-07-15" if bns else "2023-06-15",
                              fir=f"t{i}", fir_year=2024 if bns else 2023))
    return rows


def _ids(split_map: dict, name: str) -> set[str]:
    return {k for k, v in split_map.items() if v == name}


def test_assign_splits_counts_and_caps(tmp_path):
    """Train takes every pre-2024 order; dev is capped at 50 and test at 200."""
    orders = write_jsonl(tmp_path / "orders.jsonl", _big_orders())
    out = tmp_path / "splits.json"
    counts = assign_splits(str(orders), str(out), seed=0)
    assert counts == {"train": 400, "dev": 50, "test": 200}
    split_map = read_json(out)  # ASSUMPTION: out_path is a JSON object {doc_id: split}
    assert len(_ids(split_map, "train")) == 400 and len(_ids(split_map, "dev")) == 50 and len(_ids(split_map, "test")) == 200


def test_assign_splits_respects_date_windows(tmp_path):
    """Every dev order is dated in the dev window, every test order in the test window, train before 2024."""
    rows = _big_orders()
    by_id = {r["doc_id"]: r for r in rows}
    orders = write_jsonl(tmp_path / "orders.jsonl", rows)
    out = tmp_path / "splits.json"
    assign_splits(str(orders), str(out), seed=0)
    split_map = read_json(out)
    assert all(by_id[i]["date"] < "2024-01-01" for i in _ids(split_map, "train"))
    assert all("2024-01-01" <= by_id[i]["date"] <= "2024-04-01" for i in _ids(split_map, "dev"))
    assert all("2024-06-01" <= by_id[i]["date"] <= "2025-12-31" for i in _ids(split_map, "test"))


def test_gap_orders_are_in_no_split(tmp_path):
    """Orders between 2024-04-02 and 2024-05-31 belong to no split (ASSUMPTION: omitted or marked 'unused')."""
    rows = _big_orders()
    orders = write_jsonl(tmp_path / "orders.jsonl", rows)
    out = tmp_path / "splits.json"
    assign_splits(str(orders), str(out), seed=0)
    split_map = read_json(out)
    for r in rows:
        if r["doc_id"].startswith("GP-"):
            assert split_map.get(r["doc_id"]) not in {"train", "dev", "test"}


def test_test_split_has_at_least_sixty_bns_era_orders(tmp_path):
    """Plan §2: of the 200 test orders at least 60 have an offence on or after 1 July 2024 (100 are available out of 300)."""
    rows = _big_orders()
    by_id = {r["doc_id"]: r for r in rows}
    orders = write_jsonl(tmp_path / "orders.jsonl", rows)
    out = tmp_path / "splits.json"
    assign_splits(str(orders), str(out), seed=0)
    test_ids = _ids(read_json(out), "test")
    assert sum(by_id[i]["offence_date"] >= "2024-07-01" for i in test_ids) >= 60


def test_dev_and_test_are_sampled_across_high_courts(tmp_path):
    """Plan §2 'sampled across High Courts': each of the four courts appears in dev and in test."""
    rows = _big_orders()
    by_id = {r["doc_id"]: r for r in rows}
    orders = write_jsonl(tmp_path / "orders.jsonl", rows)
    out = tmp_path / "splits.json"
    assign_splits(str(orders), str(out), seed=0)
    split_map = read_json(out)
    for name in ("dev", "test"):
        assert {by_id[i]["court"] for i in _ids(split_map, name)} == set(COURTS)


def test_splits_are_disjoint_by_construction(tmp_path):
    """Each order has exactly one split label (the output maps a doc id to a single split)."""
    orders = write_jsonl(tmp_path / "orders.jsonl", _big_orders())
    out = tmp_path / "splits.json"
    assign_splits(str(orders), str(out), seed=0)
    split_map = read_json(out)
    assert isinstance(split_map, dict) and set(split_map.values()) >= {"train", "dev", "test"}


def test_same_seed_gives_identical_splits(tmp_path):
    """Sampling is deterministic for the same seed."""
    orders = write_jsonl(tmp_path / "orders.jsonl", _big_orders())
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert assign_splits(str(orders), str(a), seed=7) == assign_splits(str(orders), str(b), seed=7)
    assert a.read_text() == b.read_text()


def test_different_seed_changes_the_sample(tmp_path):
    """A different seed draws a different dev sample (50 of 80) so seeds are not ignored."""
    orders = write_jsonl(tmp_path / "orders.jsonl", _big_orders())
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assign_splits(str(orders), str(a), seed=1)
    assign_splits(str(orders), str(b), seed=2)
    assert _ids(read_json(a), "dev") != _ids(read_json(b), "dev")


def test_window_boundaries_are_inclusive_where_the_config_says(tmp_path):
    """2023-12-31 is train; 2024-01-01 and 2024-04-01 are dev; 2024-06-01 and 2025-12-31 are test; the days just outside are unused."""
    rows = [
        order_row("B-train", "2023-12-31"), order_row("B-dev-first", "2024-01-01"), order_row("B-dev-last", "2024-04-01"),
        order_row("B-gap-1", "2024-04-02"), order_row("B-gap-2", "2024-05-31"),
        order_row("B-test-first", "2024-06-01", offence_date="2024-07-15"), order_row("B-test-last", "2025-12-31", offence_date="2024-09-01"),
        order_row("B-after", "2026-01-01"),
    ]
    # enough BNS-era test orders (62 in total, under the 200 cap) so the >=60 requirement is satisfiable without sampling loss
    rows += [order_row(f"F-{i:03d}", d, offence_date="2024-08-01", fir=f"f{i}", fir_year=2024)
             for i, d in enumerate(spread_dates("2024-08-01", 60, 3))]
    orders = write_jsonl(tmp_path / "orders.jsonl", rows)
    out = tmp_path / "splits.json"
    assign_splits(str(orders), str(out), seed=0)
    m = read_json(out)
    assert m["B-train"] == "train"
    assert m["B-dev-first"] == "dev" and m["B-dev-last"] == "dev"
    assert m["B-test-first"] == "test" and m["B-test-last"] == "test"
    for unused in ("B-gap-1", "B-gap-2", "B-after"):
        assert m.get(unused) not in {"train", "dev", "test"}
