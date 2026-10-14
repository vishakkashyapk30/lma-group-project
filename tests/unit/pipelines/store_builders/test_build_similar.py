"""Builder of `caselaw.similar` (plan §5.1): one vector per order's facts section, plus a fact signature (sections, custody
band, charge-sheet status, co-accused outcome). Test and same-FIR orders are excluded (plan §2)."""

from __future__ import annotations

import pytest

from tests.unit.pipelines.store_builders._helpers import CASE_DATE, LATE_ORDER, SAME_FIR_ORDER, TEST_ORDER, doc_ids
from vakeel_sahayak.pipelines.store_builders.build_similar import build_similar
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.schemas.store_rows import FactSignature
from vakeel_sahayak.stores.caselaw_similar import SimilarStore

FACTS_OF_CASE = "applicant induced the complainant to part with money; arrested; charge sheet filed; co-accused granted bail"


@pytest.fixture()
def built(interim, excluded, tmp_path):
    out = tmp_path / "similar"
    n = build_similar(str(interim), str(out), exclude_doc_ids=excluded)
    store = SimilarStore()
    store.open(str(out))
    yield n, store
    store.close()


def test_store_identity():
    assert SimilarStore.name == StoreName.CASELAW_SIMILAR


def test_one_row_per_included_order(built):
    """Whole-order vectors: one row per order, not per paragraph. 7 orders minus the test and same-FIR orders = 5."""
    n, store = built
    assert n == store.count() == 5


def test_excluded_orders_are_not_retrievable(built):
    _, store = built
    ids = doc_ids(store.similar(FACTS_OF_CASE, before="2100-01-01", k=100))
    assert TEST_ORDER not in ids and SAME_FIR_ORDER not in ids
    assert {"DLHC-2022-1187", "DLHC-2023-0911", "SC-2014-0463"} <= ids


def test_rows_carry_court_date_and_signature(built):
    """The signature holds the sections of the order (IPC 420), the charge-sheet status and the co-accused outcome."""
    _, store = built
    row = next(r for r in store.similar(FACTS_OF_CASE, before="2100-01-01", k=100) if r.doc_id == "DLHC-2022-1187")
    assert row.court == "Delhi High Court" and row.date == "2022-06-03"
    sig = row.signature
    assert isinstance(sig, FactSignature)
    assert "IPC 420" in sig.sections
    assert sig.charge_sheet_status == "filed"
    assert sig.co_accused_outcome == "granted"
    assert sig.custody_band  # the facts say 'about four months': a band is assigned


def test_only_the_facts_part_is_embedded(interim, excluded, tmp_path, fake_embedder):
    """Plan §5.1: the vector is of the facts section; reasoning, submissions and the operative order never reach the embedder."""
    texts: list[str] = []
    original = fake_embedder.embed
    fake_embedder.embed = lambda t: (texts.extend(t), original(t))[1]
    build_similar(str(interim), str(tmp_path / "s2"), exclude_doc_ids=excluded)
    blob = " ".join(texts)
    assert "induced the complainant" in blob
    for mark in ("falsely implicated", "flee from justice", "perused the record", "personal bond"):
        assert mark not in blob


def test_before_filter_hides_later_orders(built):
    """DLHC-2025-0099 is stored but invisible for a case dated 2025-02-03."""
    _, store = built
    assert LATE_ORDER in doc_ids(store.similar(FACTS_OF_CASE, before="2100-01-01", k=100))
    assert LATE_ORDER not in doc_ids(store.similar(FACTS_OF_CASE, before=CASE_DATE, k=100))


def test_query_without_before_date_is_refused(built):
    _, store = built
    with pytest.raises((ValueError, TypeError)):
        store.similar(FACTS_OF_CASE)


def test_signature_filter_prefers_matching_sections(built):
    """With a signature naming IPC 420 every returned order is one whose signature contains IPC 420 (all synthetic orders cite it)."""
    _, store = built
    sig = FactSignature(sections=["IPC 420"], charge_sheet_status="filed", co_accused_outcome="granted")
    rows = store.similar(FACTS_OF_CASE, signature=sig, before="2100-01-01", k=100)
    assert rows and all("IPC 420" in r.signature.sections for r in rows[:3])
