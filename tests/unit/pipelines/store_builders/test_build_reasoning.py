"""Builder of `caselaw.reasoning` (plan §5.1, §5.2, §5.3, §2).

Part-aware chunking: only the court's reasoning paragraphs are stored (defense and prosecution submissions, facts and the
operative order are not), at most 400 tokens per chunk, split at sentence ends. Metadata on every row: doc_id, para, court,
date, outcome, part, sections, section_family, factors, cites, authority. Test orders and same-FIR orders are excluded.
"""

from __future__ import annotations

import pytest

from tests.unit.pipelines.store_builders._helpers import (
    CASE_DATE,
    DEFENSE_MARK,
    FACTS_MARK,
    LATE_ORDER,
    PROSECUTION_MARK,
    SAME_FIR_ORDER,
    TEST_ORDER,
    doc_ids,
    ntok,
)
from vakeel_sahayak.pipelines.store_builders.build_reasoning import build_reasoning
from vakeel_sahayak.schemas.enums import Factor, OrderPart, StoreName
from vakeel_sahayak.stores.caselaw_reasoning import ReasoningStore


@pytest.fixture()
def built(interim, excluded, tmp_path):
    out = tmp_path / "reasoning"
    n = build_reasoning(str(interim), str(out), exclude_doc_ids=excluded)
    store = ReasoningStore()
    store.open(str(out))
    yield n, store
    store.close()


def everything(store: ReasoningStore, **kw):
    return store.search("co-accused bail charge sheet gravity custody", before="2100-01-01", k=1000, **kw)


def test_store_identity():
    """The builder feeds the store named caselaw.reasoning."""
    assert ReasoningStore.name == StoreName.CASELAW_REASONING


def test_returns_the_row_count_of_the_store(built):
    """`build_reasoning` returns the rows written, which is what the store counts (build report vs plan estimates)."""
    n, store = built
    assert n == store.count() > 0


def test_only_reasoning_paragraphs_are_stored(built):
    """Every stored row has part == reasoning; no sentinel of the defense, prosecution or facts part is in any row (plan §5.2)."""
    _, store = built
    rows = everything(store)
    assert rows and all(r.part == OrderPart.REASONING for r in rows)
    blob = " ".join(r.text for r in rows)
    for mark in (DEFENSE_MARK, PROSECUTION_MARK, FACTS_MARK, "personal bond"):
        assert mark not in blob


def test_other_parts_are_not_retrievable_by_asking_for_them(built):
    """Asking for another part returns nothing: authorities are cited from reasoning paragraphs only."""
    _, store = built
    assert store.search("falsely implicated", part=OrderPart.DEFENSE, before="2100-01-01") == []
    assert store.search("flee from justice", part=OrderPart.PROSECUTION, before="2100-01-01") == []


def test_chunks_have_at_most_400_tokens(built):
    """Plan §5.2: short paragraphs merge, long ones split at sentence ends, up to 400 tokens. ASSUMPTION: whitespace tokens."""
    _, store = built
    assert max(ntok(r.text) for r in everything(store)) <= 400


def test_long_paragraph_is_split_at_sentence_ends(built):
    """DLHC-2020-0500 has a 1,200-token reasoning paragraph (4 sentences of 300 tokens): it becomes several chunks that all end at a full stop."""
    _, store = built
    chunks = [r for r in everything(store) if r.doc_id == "DLHC-2020-0500"]
    assert len(chunks) >= 3
    assert all(r.text.rstrip().endswith(".") for r in chunks)


def test_every_metadata_field_is_filled(built):
    """A parity paragraph of DLHC-2022-1187 carries the full metadata record of plan §5.2."""
    _, store = built
    row = next(r for r in everything(store) if r.doc_id == "DLHC-2022-1187" and "parity" in r.text)
    assert row.court == "Delhi High Court"
    assert row.date == "2022-06-03"
    assert row.outcome == "granted"
    assert row.part == OrderPart.REASONING
    assert row.para >= 1
    assert "IPC 420" in row.sections


def test_section_family_is_expanded_through_the_concordance(built):
    """IPC 420 in the order expands to the family {IPC 420, BNS 318(4)} (plan §5.2: section_family via the concordance)."""
    _, store = built
    row = next(r for r in everything(store) if r.doc_id == "DLHC-2022-1187")
    assert {"IPC 420", "BNS 318(4)"} <= set(row.section_family)


def test_factors_are_tagged_by_the_keyword_rules(built):
    """The parity paragraph carries parity_with_co_accused and charge_sheet_filed (cue words: co-accused, charge sheet)."""
    _, store = built
    rows = [r for r in everything(store) if r.doc_id == "DLHC-2022-1187"]
    tags = {f for r in rows for f in r.factors}
    assert {Factor.PARITY_WITH_CO_ACCUSED, Factor.CHARGE_SHEET_FILED} <= tags
    gravity = [r for r in everything(store) if r.doc_id == "DLHC-2023-0911"]
    assert any(Factor.GRAVITY_AND_PUNISHMENT in r.factors for r in gravity)


def test_cites_and_authority_come_from_the_citation_graph(built):
    """`authority` is in [0, 1]; the Supreme Court judgment cited by two High Court orders outranks the High Court order citing it."""
    _, store = built
    rows = everything(store)
    assert all(0.0 <= r.authority <= 1.0 for r in rows)
    sc = max(r.authority for r in rows if r.doc_id == "SC-2014-0463")
    hc = max(r.authority for r in rows if r.doc_id == "DLHC-2022-1187")
    assert sc > hc
    citing = [r for r in rows if r.doc_id == "DLHC-2022-1187"]
    assert any("SC-2014-0463" in r.cites for r in citing)


def test_test_orders_and_same_fir_orders_are_excluded(built):
    """Plan §2: the test order and the order with the same FIR (112/2024, PS-1) are in no row."""
    _, store = built
    ids = doc_ids(everything(store))
    assert TEST_ORDER not in ids and SAME_FIR_ORDER not in ids
    assert {"DLHC-2022-1187", "DLHC-2023-0911", "SC-2014-0463", "DLHC-2020-0500"} <= ids


def test_later_order_is_stored_but_hidden_by_the_before_filter(built):
    """DLHC-2025-0099 (2025-03-01) is a valid order, so it is stored; the run-time rule hides it from a case dated 2025-02-03."""
    _, store = built
    assert LATE_ORDER in doc_ids(everything(store))
    assert LATE_ORDER not in doc_ids(store.search("co-accused bail", before=CASE_DATE, k=1000))


def test_query_without_before_date_is_refused(built):
    """Every shared-store query needs a `before` date (plan §2)."""
    _, store = built
    with pytest.raises((ValueError, TypeError)):
        store.search("co-accused bail")


def test_without_an_exclusion_set_nothing_is_excluded(interim, tmp_path):
    """ASSUMPTION: `exclude_doc_ids=None` excludes nothing (build_all passes the leakage set), so the test order shows up."""
    out = tmp_path / "all"
    build_reasoning(str(interim), str(out))
    store = ReasoningStore()
    store.open(str(out))
    assert TEST_ORDER in doc_ids(everything(store))


def test_embeddings_go_through_the_model_client(interim, excluded, tmp_path, fake_embedder):
    """Dense vectors are computed by the embedder from `models/` (here the 32-dimension fake), not by a direct import."""
    calls: list[list[str]] = []
    original = fake_embedder.embed
    fake_embedder.embed = lambda texts: (calls.append(list(texts)), original(texts))[1]
    build_reasoning(str(interim), str(tmp_path / "r"), exclude_doc_ids=excluded)
    assert calls and sum(len(c) for c in calls) > 0
