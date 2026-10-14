"""`search_reasoning` and `get_paragraph` (plan §5.1 caselaw.reasoning, §5.2, §2 leakage, §8.1).

Fixture world (tests/fixtures/caselaw/paragraphs.json), for case-0007 decided 2025-02-03:
  reasoning paragraphs: DLHC-2022-1187#14 (parity, charge sheet), DLHC-2021-0420#11 (custody), DLHC-2023-0911#12 (gravity), SC-2014-0463#21
  (charge sheet), BOMHC-2024-0355#8 (trial delay); DLHC-2025-0099#5 is dated AFTER the case, TESTORD-2024-0001#3 is a test-split order
  (and was removed from the in-memory store like the real build does). Defense paragraph DLHC-2022-1187#9 and prosecution paragraph
  DLHC-2023-0911#6 live in the advocacy stores' parts, not in the authority set.

The authorities rule (plan §5.1, skeleton.md): authorities are cited from REASONING paragraphs only. The tool returns reasoning paragraphs
and never defense or prosecution submissions. Tools validate argument values even though calls are schema-constrained.
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.tools_case._helpers import assert_tool_error, install_recording_stores, stores_touched
from vakeel_sahayak.schemas.enums import Factor, OrderPart, StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.tools.caselaw.reasoning import GET_PARAGRAPH_SPEC, SEARCH_REASONING_SPEC, get_paragraph, search_reasoning

BEFORE = "2025-02-03"
FORBIDDEN = {"TESTORD-2024-0001", "SAMEFIR-2024-0002", "DLHC-2025-0099"}


def ids(hits: list[ParagraphRecord]) -> list[str]:
    return [f"{h.doc_id}#{h.para}" for h in hits]


# ---------------------------------------------------------------- search_reasoning
def test_returns_reasoning_paragraphs_only(world, install_stores):
    """Authorities come from reasoning only: no returned paragraph is a defense or prosecution submission, even for a query that matches them
    word for word ('Counsel for the petitioner submits that co-accused was granted bail')."""
    install_stores()
    hits = search_reasoning("Counsel for the petitioner submits that co-accused was granted bail", before=BEFORE, k=20)
    assert hits and all(isinstance(h, ParagraphRecord) and h.part == OrderPart.REASONING for h in hits)
    assert "DLHC-2022-1187#9" not in ids(hits) and "DLHC-2023-0911#6" not in ids(hits)


def test_the_store_is_asked_for_the_reasoning_part(world, install_stores):
    """Even if a store implementation accepted other parts, the tool pins `part` to reasoning (plan §5.2 'reasoning-only paragraphs')."""
    install_stores()
    search_reasoning("parity", before=BEFORE)
    (method, kw), = world.stores[StoreName.CASELAW_REASONING].calls
    assert method == "search" and kw.get("part", OrderPart.REASONING) == OrderPart.REASONING


def test_before_date_excludes_later_orders(world, install_stores):
    """Leakage rule: nothing dated on or after `before` comes back (DLHC-2025-0099 is dated 2025-03-01); test and same-FIR orders are
    absent from the store."""
    install_stores()
    hits = search_reasoning("co-accused parity bail", before=BEFORE, k=50)
    assert not FORBIDDEN & {h.doc_id for h in hits}
    assert all(h.date < BEFORE for h in hits)
    earlier = search_reasoning("co-accused parity bail", before="2022-01-01", k=50)
    assert {h.doc_id for h in earlier} <= {"DLHC-2021-0420", "SC-2014-0463"}


def test_a_missing_before_date_is_refused(world, install_stores):
    """Plan §2: every shared-store query takes a `before` date. # ASSUMPTION: the tool raises (ValueError) or returns a ToolError."""
    install_stores()
    assert_tool_error(lambda: search_reasoning("parity"))


@pytest.mark.parametrize("before", ["", "03/02/2025", "2025-13-01", "yesterday"])
def test_a_malformed_before_date_is_refused(world, install_stores, before):
    install_stores()
    assert_tool_error(lambda: search_reasoning("parity", before=before))


def test_factor_filter(world, install_stores):
    install_stores()
    hits = search_reasoning("charge sheet", factor=Factor.CHARGE_SHEET_FILED, before=BEFORE, k=20)
    assert ids(hits) and all(Factor.CHARGE_SHEET_FILED in h.factors for h in hits)
    assert set(ids(hits)) == {"DLHC-2022-1187#14", "SC-2014-0463#21"}


def test_factor_accepts_the_enum_value_string(world, install_stores):
    """Calls are schema-constrained JSON, so the factor may arrive as its string value."""
    install_stores()
    assert ids(search_reasoning("trial delay", factor="trial_delay", before=BEFORE)) == ["BOMHC-2024-0355#8"]


def test_unknown_factor_is_refused(world, install_stores):
    install_stores()
    assert_tool_error(lambda: search_reasoning("bail", factor="grant_probability", before=BEFORE))


def test_section_family_filter_matches_ipc_and_bns_wording(world, install_stores):
    """Plan §5.4: a BNS 318(4) case also retrieves IPC 420 precedents: the family filter takes both refs."""
    install_stores()
    hits = search_reasoning("bail", section_family=["BNS 318(4)", "IPC 420"], before=BEFORE, k=20)
    assert "SC-2014-0463#21" not in ids(hits)  # the SC paragraph carries no section family
    assert {"DLHC-2022-1187#14", "DLHC-2021-0420#11", "DLHC-2023-0911#12"} <= set(ids(hits))


def test_court_and_outcome_filters(world, install_stores):
    install_stores()
    assert {h.court for h in search_reasoning("bail", court="Bombay", before=BEFORE, k=20)} == {"Bombay HC"}
    assert {h.outcome for h in search_reasoning("bail", outcome="rejected", before=BEFORE, k=20)} == {"rejected"}


def test_k_limits_the_results_and_must_be_positive(world, install_stores):
    install_stores()
    assert len(search_reasoning("bail custody charge sheet", before=BEFORE, k=2)) == 2
    for k in (0, -1):
        assert_tool_error(lambda k=k: search_reasoning("bail", before=BEFORE, k=k))


def test_empty_query_is_refused(world, install_stores):
    install_stores()
    assert_tool_error(lambda: search_reasoning("  ", before=BEFORE))


def test_search_touches_only_the_reasoning_store(world, monkeypatch):
    opened = install_recording_stores(monkeypatch, world)
    search_reasoning("parity", before=BEFORE)
    assert {n for n, _ in opened} == {StoreName.CASELAW_REASONING}
    assert stores_touched(world) == {StoreName.CASELAW_REASONING}


def test_signature_defaults_follow_the_plan():
    p = inspect.signature(search_reasoning).parameters
    assert p["k"].default == 10 and p["before"].default is None and SEARCH_REASONING_SPEC.stores == [StoreName.CASELAW_REASONING]


# ---------------------------------------------------------------- get_paragraph
def test_get_paragraph_fetches_by_id(world, monkeypatch):
    opened = install_recording_stores(monkeypatch, world)
    p = get_paragraph("DLHC-2022-1187", 14)
    assert isinstance(p, ParagraphRecord) and (p.doc_id, p.para, p.part) == ("DLHC-2022-1187", 14, OrderPart.REASONING)
    assert "enlarged on bail" in p.text
    assert {n for n, _ in opened} == {StoreName.CASELAW_REASONING}


@pytest.mark.parametrize(("doc_id", "para"), [("NOPE-1999-0001", 1), ("DLHC-2022-1187", 999), ("", 14), ("DLHC-2022-1187", 0), ("DLHC-2022-1187", -4)])
def test_get_paragraph_unknown_or_invalid_ids_are_errors(world, install_stores, doc_id, para):
    """No invented paragraph, ever: an unknown id (or invalid number) is an error."""
    install_stores()
    assert_tool_error(lambda: get_paragraph(doc_id, para))


@pytest.mark.parametrize(("doc_id", "para"), [("DLHC-2022-1187", 9), ("DLHC-2023-0911", 6)])
def test_get_paragraph_refuses_submissions_as_authority(world, install_stores, doc_id, para):
    """DLHC-2022-1187#9 is a defense submission and DLHC-2023-0911#6 a prosecution submission: they exist, but cannot be fetched as a citable
    paragraph (plan §5.1: argument-bank content is for coverage and phrasing only; authorities are cited from reasoning only).
    # ASSUMPTION: refused with an error."""
    install_stores()
    assert_tool_error(lambda: get_paragraph(doc_id, para))


def test_get_paragraph_is_vakeel_only_and_reads_the_reasoning_store():
    from vakeel_sahayak.schemas.enums import AgentName

    assert GET_PARAGRAPH_SPEC.agents == [AgentName.VAKEEL] and GET_PARAGRAPH_SPEC.stores == [StoreName.CASELAW_REASONING]
