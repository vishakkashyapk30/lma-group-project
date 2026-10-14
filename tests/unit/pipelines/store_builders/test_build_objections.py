"""Builder of `advocacy.objections` (plan §5.1): prosecution-submission paragraphs, tagged by factor.

Used by Abhiyojak and the hearing-prep card; also gold (G4), so test and same-FIR orders are excluded (plan §2).
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
from vakeel_sahayak.pipelines.store_builders.build_objections import build_objections
from vakeel_sahayak.schemas.enums import OrderPart, StoreName
from vakeel_sahayak.stores.advocacy_objections import ObjectionStore


@pytest.fixture()
def built(interim, excluded, tmp_path):
    out = tmp_path / "objections"
    n = build_objections(str(interim), str(out), exclude_doc_ids=excluded)
    store = ObjectionStore()
    store.open(str(out))
    yield n, store
    store.close()


def everything(store: ObjectionStore, **kw):
    return store.search("offence serious flee from justice investigation role", before="2100-01-01", k=1000, **kw)


def test_store_identity():
    assert ObjectionStore.name == StoreName.ADVOCACY_OBJECTIONS


def test_returns_the_row_count_of_the_store(built):
    n, store = built
    assert n == store.count() > 0


def test_only_prosecution_submissions_are_stored(built):
    """Every row is a prosecution-submission paragraph; defense and reasoning text is not in the bank."""
    _, store = built
    rows = everything(store)
    assert rows and all(r.part == OrderPart.PROSECUTION for r in rows)
    blob = " ".join(r.text for r in rows)
    assert PROSECUTION_MARK in blob
    assert DEFENSE_MARK not in blob and "perused the record" not in blob


def test_one_prosecution_paragraph_per_included_order(built):
    _, store = built
    assert len(everything(store)) == 5


def test_rows_have_provenance_and_factor_tags(built):
    """Abhiyojak cites an objection by (doc_id, para): both must be present, and factors are a list of Factor (possibly empty)."""
    _, store = built
    for row in everything(store):
        assert row.doc_id and row.para >= 1
        assert isinstance(row.factors, list)


def test_chunks_respect_the_400_token_limit(built):
    _, store = built
    assert max(ntok(r.text) for r in everything(store)) <= 400


def test_test_orders_and_same_fir_orders_are_excluded(built):
    _, store = built
    ids = doc_ids(everything(store))
    assert TEST_ORDER not in ids and SAME_FIR_ORDER not in ids


def test_query_without_before_date_is_refused(built):
    """Plan §2: every shared-store query needs a `before` date."""
    _, store = built
    with pytest.raises((ValueError, TypeError)):
        store.search("flight risk")


def test_before_filter_hides_later_orders(built):
    """An objection from DLHC-2025-0099 (2025-03-01) is invisible to a case dated 2025-02-03."""
    _, store = built
    ids = doc_ids(store.search("offence serious flee from justice", before="2025-02-03", k=1000))
    assert "DLHC-2025-0099" not in ids
