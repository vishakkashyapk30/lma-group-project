"""Builder of `advocacy.arguments` (plan §5.1): defense-submission paragraphs, tagged by factor and outcome.

The bank is used for coverage and phrasing only and is never cited as authority; the argument bank also holds gold labels
(G1), so the leakage exclusion matters most here (plan §2).
"""

from __future__ import annotations

import pytest

from tests.unit.pipelines.store_builders._helpers import (
    DEFENSE_MARK,
    PROSECUTION_MARK,
    SAME_FIR_ORDER,
    TEST_ORDER,
    doc_ids,
    ntok,
)
from vakeel_sahayak.pipelines.store_builders.build_arguments import build_arguments
from vakeel_sahayak.schemas.enums import Factor, OrderPart, StoreName
from vakeel_sahayak.stores.advocacy_arguments import ArgumentStore


@pytest.fixture()
def built(interim, excluded, tmp_path):
    out = tmp_path / "arguments"
    n = build_arguments(str(interim), str(out), exclude_doc_ids=excluded)
    store = ArgumentStore()
    store.open(str(out))
    yield n, store
    store.close()


def everything(store: ArgumentStore, **kw):
    return store.search("co-accused released bail innocent falsely implicated", before="2100-01-01", k=1000, **kw)


def test_store_identity():
    assert ArgumentStore.name == StoreName.ADVOCACY_ARGUMENTS


def test_returns_the_row_count_of_the_store(built):
    n, store = built
    assert n == store.count() > 0


def test_only_defense_submissions_are_stored(built):
    """Every row is a defense-submission paragraph; no reasoning, prosecution or facts text is in the bank."""
    _, store = built
    rows = everything(store)
    assert rows and all(r.part == OrderPart.DEFENSE for r in rows)
    blob = " ".join(r.text for r in rows)
    assert DEFENSE_MARK in blob
    assert PROSECUTION_MARK not in blob and "perused the record" not in blob


def test_one_defense_paragraph_per_included_order(built):
    """The synthetic orders have one defense paragraph each: 5 non-excluded orders (7 minus the test and same-FIR orders)."""
    _, store = built
    assert len(everything(store)) == 5


def test_rows_carry_factor_and_outcome_tags(built):
    """Plan §5.1: tagged by factor and outcome. The parity submission of DLHC-2022-1187 is tagged parity and 'granted'."""
    _, store = built
    row = next(r for r in everything(store) if r.doc_id == "DLHC-2022-1187")
    assert row.outcome == "granted"
    assert Factor.PARITY_WITH_CO_ACCUSED in row.factors
    rejected = next(r for r in everything(store) if r.doc_id == "DLHC-2023-0911")
    assert rejected.outcome == "rejected"


def test_outcome_filter_selects_rows(built):
    """`outcome='rejected'` returns only the submission made in an order that refused bail."""
    _, store = built
    assert doc_ids(everything(store, outcome="rejected")) == {"DLHC-2023-0911"}


def test_chunks_respect_the_400_token_limit(built):
    _, store = built
    assert max(ntok(r.text) for r in everything(store)) <= 400


def test_test_orders_and_same_fir_orders_are_excluded(built):
    """Plan §2: the exclusion matters most in the argument bank, which holds gold labels."""
    _, store = built
    ids = doc_ids(everything(store))
    assert TEST_ORDER not in ids and SAME_FIR_ORDER not in ids


def test_store_offers_no_authority_citation_path(built):
    """Never cited as authority (plan §5.1): the store has no `get_paragraph`-style fetch that Vakeel could cite from."""
    _, store = built
    assert not hasattr(store, "get_paragraph")


def test_query_without_before_date_is_refused(built):
    _, store = built
    with pytest.raises((ValueError, TypeError)):
        store.search("bail")
