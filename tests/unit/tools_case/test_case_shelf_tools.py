"""Case-shelf tools `get_timeline`, `get_fact`, `search_case_docs` (plan §5.1 'The stores' rows case.timeline / case.facts / case.docs, §4.4).

Case-0007 (tests/fixtures/case_0007): seven timeline events e1-e7 (offence 2024-08-10 ... co-accused bail 2024-12-05), thirteen dossier
fields. These are the client's own record, so unlike the shared stores the tools take no `before` date. `date_calc` is covered in
tests/unit/tools_law_case/test_date_calc.py. Specs and registry entries are covered in tests/unit/tools/.

Tests fail until the tools are implemented; they use the in-memory stores through `open_store`, and read `world.stores[...].calls` to see
which store a tool touched.
"""

from __future__ import annotations

import pytest

from tests.unit.tools_case._helpers import assert_tool_error, install_recording_stores, stores_touched
from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.dossier import DossierFields
from vakeel_sahayak.schemas.enums import DocumentType, FieldStatus, StoreName
from vakeel_sahayak.schemas.store_rows import CaseChunk, TimelineEvent
from vakeel_sahayak.tools.case.docs import SEARCH_CASE_DOCS_SPEC, search_case_docs
from vakeel_sahayak.tools.case.facts import GET_FACT_SPEC, get_fact
from vakeel_sahayak.tools.case.timeline import GET_TIMELINE_SPEC, get_timeline

CASE = "case-0007"


# ---------------------------------------------------------------- get_timeline
def test_get_timeline_returns_every_event_in_date_order(world, monkeypatch):
    opened = install_recording_stores(monkeypatch, world)
    events = get_timeline(CASE)
    assert all(isinstance(e, TimelineEvent) for e in events)
    assert [e.event_id for e in events] == ["e1", "e2", "e3", "e4", "e5", "e6", "e7"]
    assert [e.date for e in events] == sorted(e.date for e in events)
    assert opened == [(StoreName.CASE_TIMELINE, CASE)]


def test_get_timeline_window_is_inclusive_at_both_ends(world, monkeypatch):
    """arrest 2024-08-20 and first remand 2024-08-21 are both inside the window [2024-08-20, 2024-08-21]."""
    install_recording_stores(monkeypatch, world)
    assert [e.event_id for e in get_timeline(CASE, start="2024-08-20", end="2024-08-21")] == ["e3", "e4"]


def test_get_timeline_open_ended_windows(world, monkeypatch):
    install_recording_stores(monkeypatch, world)
    assert [e.event_id for e in get_timeline(CASE, start="2024-11-02")] == ["e6", "e7"]
    assert [e.event_id for e in get_timeline(CASE, end="2024-08-14")] == ["e1", "e2"]


def test_get_timeline_empty_window_is_an_empty_list_not_an_error(world, monkeypatch):
    install_recording_stores(monkeypatch, world)
    assert get_timeline(CASE, start="2025-01-01", end="2025-01-31") == []


def test_get_timeline_events_keep_their_source_and_status(world, monkeypatch):
    """Dated events come back with the source reference and status the store holds (plan §4.4, §7.2: every date has a source)."""
    install_recording_stores(monkeypatch, world)
    for e in get_timeline(CASE):
        assert e.status == FieldStatus.VERIFIED


@pytest.mark.parametrize("kwargs", [{"start": "03/02/2025"}, {"end": "2024-13-45"}, {"start": "2024-12-01", "end": "2024-08-01"}, {"start": ""}])
def test_get_timeline_rejects_malformed_or_inverted_windows(world, monkeypatch, kwargs):
    """Plan §15.8 'malformed date' recovery: a bad window is an error, not a silent empty answer. # ASSUMPTION: an empty string is malformed."""
    install_recording_stores(monkeypatch, world)
    assert_tool_error(lambda: get_timeline(CASE, **kwargs))


def test_get_timeline_rejects_an_empty_case_id(world, monkeypatch):
    install_recording_stores(monkeypatch, world)
    assert_tool_error(lambda: get_timeline(""))


def test_get_timeline_touches_only_the_timeline_store(world, install_stores):
    install_stores()
    get_timeline(CASE)
    assert stores_touched(world) == {StoreName.CASE_TIMELINE}


def test_get_timeline_has_no_before_parameter_it_is_the_clients_own_record():
    import inspect

    assert "before" not in inspect.signature(get_timeline).parameters
    assert GET_TIMELINE_SPEC.stores == [StoreName.CASE_TIMELINE]


# ---------------------------------------------------------------- get_fact
def test_get_fact_returns_value_source_and_status(world, monkeypatch):
    """A verified field: value, status VERIFIED and the quoted source (page 4 of the remand order)."""
    opened = install_recording_stores(monkeypatch, world)
    f = get_fact(CASE, "arrest_date")
    assert isinstance(f, TrackedField) and f.value == "2024-08-20" and f.status == FieldStatus.VERIFIED
    assert f.source is not None and f.source.page == 4 and "20.08.2024" in (f.source.quote or "")
    assert opened == [(StoreName.CASE_FACTS, CASE)]


def test_get_fact_computed_field_names_the_tool_that_computed_it(world, install_stores):
    install_stores()
    f = get_fact(CASE, "custody_days")
    assert f.value == 167 and f.status == FieldStatus.COMPUTED and f.source.tool == "date_calc"


def test_get_fact_never_guesses_an_unsupported_field(world, install_stores):
    """antecedents is UNSUPPORTED in case-0007: the tool returns it as such (value empty), it does not fill it in."""
    install_stores()
    f = get_fact(CASE, "antecedents")
    assert f.status == FieldStatus.UNSUPPORTED and f.value is None


def test_get_fact_user_stated_keeps_its_chat_source(world, install_stores):
    install_stores()
    f = get_fact(CASE, "personal")
    assert f.status == FieldStatus.USER_STATED and f.source.chat


@pytest.mark.parametrize("field", sorted(DossierFields.model_fields))
def test_get_fact_answers_every_dossier_field(world, install_stores, field):
    install_stores()
    assert isinstance(get_fact(CASE, field), TrackedField)


@pytest.mark.parametrize("bad", ["", "grant_probability", "ARREST_DATE ", "arrest-date"])
def test_get_fact_rejects_names_that_are_not_dossier_fields(world, install_stores, bad):
    """Exact lookup: only the thirteen dossier field names exist (no outcome predictions or free-form keys). # ASSUMPTION: exact match."""
    install_stores()
    assert_tool_error(lambda: get_fact(CASE, bad))


def test_get_fact_touches_only_the_facts_store(world, install_stores):
    install_stores()
    get_fact(CASE, "fir")
    assert stores_touched(world) == {StoreName.CASE_FACTS}
    assert GET_FACT_SPEC.stores == [StoreName.CASE_FACTS]


# ---------------------------------------------------------------- search_case_docs
CHUNKS = [
    CaseChunk(chunk_id="c1", doc_id="d2", doc_type=DocumentType.REMAND_ORDER, page=4, box=[64, 120, 540, 152],
              text="The accused was arrested on 20.08.2024 and produced before the Magistrate on 21.08.2024."),
    CaseChunk(chunk_id="c2", doc_id="d3", doc_type=DocumentType.BAIL_ORDER, page=7, box=[60, 200, 540, 260],
              text="The Sessions Court observed that antecedents of the applicant are not disclosed and rejected bail."),
    CaseChunk(chunk_id="c3", doc_id="d1", doc_type=DocumentType.FIR, page=1, box=None,
              text="FIR registered on 14.08.2024 under Section 318(4) BNS."),
]


@pytest.fixture()
def with_docs(world):
    world.stores[StoreName.CASE_DOCS].add_chunks(CHUNKS)
    world.stores[StoreName.CASE_DOCS].calls.clear()
    return world


def test_search_case_docs_returns_chunks_with_page_and_box(with_docs, monkeypatch):
    """'Chunks with page and box' (the UI draws the highlight from the box): the best match for the antecedents question is the bail order."""
    opened = install_recording_stores(monkeypatch, with_docs)
    hits = search_case_docs(CASE, "what did the Sessions Court say about antecedents")
    assert hits and hits[0].chunk_id == "c2" and hits[0].page == 7 and hits[0].box == [60, 200, 540, 260]
    assert opened == [(StoreName.CASE_DOCS, CASE)]


def test_search_case_docs_filters_by_document_type(with_docs, install_stores):
    install_stores()
    hits = search_case_docs(CASE, "accused", doc_types=[DocumentType.REMAND_ORDER])
    assert {h.doc_type for h in hits} == {DocumentType.REMAND_ORDER}


def test_search_case_docs_respects_k(with_docs, install_stores):
    install_stores()
    assert len(search_case_docs(CASE, "accused arrested bail FIR", k=2)) == 2
    assert len(search_case_docs(CASE, "accused arrested bail FIR")) <= 5  # default k=5


@pytest.mark.parametrize("kwargs", [{"k": 0}, {"k": -3}, {"query": ""}, {"query": "   "}])
def test_search_case_docs_rejects_bad_arguments(with_docs, install_stores, kwargs):
    install_stores()
    args = {"query": "bail", **kwargs}
    assert_tool_error(lambda: search_case_docs(CASE, **args))


def test_search_case_docs_touches_only_case_docs_and_takes_no_before(with_docs, install_stores):
    import inspect

    install_stores()
    search_case_docs(CASE, "arrest")
    assert stores_touched(with_docs) == {StoreName.CASE_DOCS}
    assert "before" not in inspect.signature(search_case_docs).parameters
    assert SEARCH_CASE_DOCS_SPEC.stores == [StoreName.CASE_DOCS]
