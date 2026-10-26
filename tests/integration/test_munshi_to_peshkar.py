"""Munshi -> case shelf -> Peshkar on the constructed 14-page bundle (plan §4.2-§4.6, §7.1-§7.3, §13.6 flow 1).

Real modules: MunshiAgent, PeshkarAgent, BaseAgent.call_tool, the event log mirror, the Rights Radar and
`compute_change_set` (through the scenario toolbox). Fakes: models (ScriptedLLM), page back-ends and the three case-shelf
stores (tests/fakes). The bundle: pages 1-3 scanned Hindi FIR (p.2 handwriting needing the vision model, p.3 unreadable),
4-5 and 6-7 two remand orders, 8-14 the Sessions Court bail rejection with the order sheet on p.14. No custody certificate and no
co-accused order are in the bundle.

ASSUMPTIONS: tool kwargs are `file_path` / `page` as in the tool signatures; a PageRoute's `route` entries start with the route
name ('text_layer', 'ocr', 'vision'); `IngestionReport.questions` carries what counsel was asked; Peshkar puts a conflict between
documents to counsel through `ask_user` and marks the field AMBIGUOUS.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.fakes.toolbox import leaked_names
from tests.integration import _helpers as h
from vakeel_sahayak.agents.munshi.agent import MunshiAgent
from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.orchestration.gates import await_gate
from vakeel_sahayak.schemas.enums import AgentName, DocumentType, EventKind, FieldStatus, GateId, PageStatus, Stage
from vakeel_sahayak.schemas.events import Event


def pipeline(install_stores, *, second_arrest_date: str | None = None, answers: list[str] | None = None, peshkar: bool = False):
    """Run Munshi (and optionally Peshkar) on the bundle. Returns everything a test may look at."""
    world = h.fresh_case_world()
    install_stores(world.stores)
    tb = h.ScenarioToolbox(world, pages=h.build_bundle(second_arrest_date), boundaries=h.BUNDLE_BOUNDARIES, answers=answers or [""] * 6)
    laptop = h.make_llm(where="laptop", events=h.munshi_events_responder(), free="")
    munshi, mctx, _ = h.build_agent(MunshiAgent, llm=laptop, toolbox=tb, world=world)
    state = munshi.run(h.seed_state())
    out = SimpleNamespace(world=world, tb=tb, llm=laptop, log=mctx.log, state=state, munshi=munshi, report=state.ingestion)
    if peshkar:
        agent, pctx, _ = h.build_agent(PeshkarAgent, llm=laptop, toolbox=tb, world=world, log=mctx.log)
        out.peshkar = agent
        # what the graph does around Peshkar (orchestration/graph.py): dossier_node advances the stage, gate1_node opens Gate 1 and holds
        advanced = agent.run(state).model_copy(update={"stage": Stage.DOSSIER})
        out.state = await_gate(advanced, GateId.GATE_1_DOSSIER, log=mctx.log, interrupt=False)
    return out


def pages_of(tb: h.ScenarioToolbox, tool: str) -> list[int]:
    return [c.kwargs["page"] for c in tb.calls if c.name == tool]


# ---- Munshi ------------------------------------------------------------------------------------------------------
def test_bundle_is_split_and_labelled_into_four_documents(install_stores):
    """K8: FIR (pp.1-3, Hindi), two remand orders (4-5, 6-7), bail order with the order sheet (8-14)."""
    r = pipeline(install_stores)
    got = [(d.type, d.pages, d.lang) for d in r.report.documents]
    assert got == [(t, [a, b], lang) for a, b, t, lang in h.BUNDLE_BOUNDARIES]
    assert [d.doc_id for d in r.report.documents] == ["d1", "d2", "d3", "d4"]


def test_every_page_climbs_the_ladder_only_as_far_as_needed(install_stores):
    """Plan §4.2: the vision model sees only p.2 (handwriting) and p.3 (OCR failed); OCR only the scanned FIR pages; the 11
    born-digital pages are read from the text layer and never OCR'd."""
    r = pipeline(install_stores)
    assert pages_of(r.tb, "vision_read_page") == [2, 3]
    assert sorted(set(pages_of(r.tb, "ocr_page"))) == [1, 2, 3]
    assert sorted(set(pages_of(r.tb, "read_text_layer"))) == list(range(4, 15))
    # RECONCILED: the page count is not known up front, so Munshi probes one page past the end (15), which fails and ends the file
    assert sorted(set(pages_of(r.tb, "inspect_page"))) == list(range(1, 16))


def test_report_records_the_route_and_status_of_each_page(install_stores):
    """IngestionReport page_routes (plan §4.6): p.1 ocr, p.2 ocr then vision, p.3 UNREADABLE, digital pages text_layer."""
    r = pipeline(install_stores)
    routes = {pr.page: pr for d in r.report.documents for pr in d.page_routes}
    assert any(step.startswith("ocr") for step in routes[1].route) and not any(step.startswith("vision") for step in routes[1].route)
    assert any(step.startswith("vision") for step in routes[2].route)
    assert routes[3].status == PageStatus.UNREADABLE
    assert routes[4].route[0].startswith("text_layer") and routes[4].status == PageStatus.OK
    assert [routes[p].status for p in (1, 2, 4, 9)] == [PageStatus.OK] * 4


def test_unreadable_page_becomes_one_question_to_counsel(install_stores):
    """Plan §4.6: 'Page 3 of the FIR is unreadable. Can you upload a clearer copy?'; unreadable pages are grouped into one question."""
    r = pipeline(install_stores)
    asked = [q for batch in r.tb.questions for q in batch]
    page3 = [q for q in asked if "page 3" in q.lower()]
    assert len(page3) == 1 and "unreadable" in page3[0].lower()
    assert any("page 3" in q.lower() for q in r.report.questions)


def test_munshi_asks_at_most_three_questions_per_round(install_stores):
    """Plan §4.3: the limit is 3 per round (shared with Peshkar); the bundle has more gaps than that."""
    r = pipeline(install_stores)
    assert r.tb.questions and all(len(batch) <= 3 for batch in r.tb.questions)


def test_hindi_pages_are_translated_and_both_texts_are_kept(install_stores):
    """K5 (plan §4.5): Hindi pages are translated; the filed chunk keeps the original and its English translation."""
    r = pipeline(install_stores)
    # RECONCILED: Munshi translates through the model facade inside the privacy-boundary scope (ingestion.hindi.translate_keeping_original),
    # not through the `translate` tool, so the evidence that a page was translated is its route entry in the ingestion report.
    assert any(step.startswith("translate") for d in r.report.documents for pr in d.page_routes for step in pr.route)
    fir_chunks = [c for c in r.tb.docs_store.chunks if c.doc_id == "d1"]
    assert fir_chunks and all(c.text and c.text_en for c in fir_chunks)
    assert all(c.doc_type == DocumentType.FIR for c in fir_chunks)


def test_dated_events_are_filed_on_the_timeline_with_their_sources(install_stores):
    """Plan §4.4: arrest 2024-08-20 (d2, p.4), first remand 2024-08-21, Sessions Court rejection 2024-09-30, charge sheet 2024-11-02 (d4, p.14)."""
    r = pipeline(install_stores)
    events = {e.date: e for e in r.tb.timeline_store.events}
    assert set(events) >= {"2024-08-20", "2024-08-21", "2024-09-30", "2024-11-02"}
    assert (events["2024-08-20"].source.doc.startswith("d2"), events["2024-08-20"].source.page) == (True, 4)
    assert events["2024-11-02"].source.doc.startswith("d4") and events["2024-11-02"].source.page == 14
    assert all(e.source and e.source.doc and e.source.page for e in events.values())


def test_report_counts_match_what_was_filed(install_stores):
    r = pipeline(install_stores)
    assert r.report.filed.timeline_events == r.tb.timeline_store.count() >= 4
    assert r.report.filed.chunks == r.tb.docs_store.count() > 0


def test_names_are_pseudonymised_before_filing_and_never_logged(install_stores):
    """Plan §4.3 step 3, §16: no planted name (English or Devanagari) in any shelf row or in the event log."""
    r = pipeline(install_stores)
    assert h.planted_in_stores(r.tb) == []
    assert leaked_names([r.log.as_text()], h.PLANTED_NAMES + h.PLANTED_NAMES_HI) == []
    assert any("Accused-1" in c.text for c in r.tb.docs_store.chunks)


def test_gap_check_finds_the_missing_custody_certificate_and_acts(install_stores):
    """Plan §4.3 step 4: the checklist item is reported with the action taken; the charge-sheet status (p.14) is not a gap."""
    r = pipeline(install_stores)
    items = [g.item.lower() for g in r.report.gaps]
    assert any("custody certificate" in i for i in items)
    assert not any("charge" in i for i in items)
    assert all(g.action for g in r.report.gaps)
    assert r.tb.count("search_pages") + r.tb.count("ask_user") >= 1


def test_every_tool_call_is_logged_as_call_then_result_by_munshi(install_stores):
    """Plan §3.3: every agent action appends an event; tools are called only through call_tool."""
    r = pipeline(install_stores)
    calls = [e for e in r.log.events if e.kind == EventKind.TOOL_CALL]
    results = [e for e in r.log.events if e.kind == EventKind.TOOL_RESULT]
    # RECONCILED: page reads and the pseudonymiser handle client text before it is pseudonymised, so Munshi calls them with `_raw_tool` and the
    # log holds no event for them (plan §16: the log holds pseudonymised text only); every other tool call is an event pair.
    raw = {"inspect_page", "read_text_layer", "ocr_page", "vision_read_page", "pseudonymise"}
    # The log also holds one logical `route_page` pair per page (the route the ladder took, without the page text).
    assert len(calls) == len(results) and {c.name for c in r.tb.calls if c.name not in raw} <= {e.tool for e in calls}
    assert {str(getattr(e.actor, "value", e.actor)) for e in calls} == {AgentName.MUNSHI.value}


def test_two_documents_that_disagree_keep_both_values(install_stores):
    """Plan §4.3 step 5: the second remand order recites arrest on 22.08.2024: both dates are filed and marked as in conflict."""
    r = pipeline(install_stores, second_arrest_date="22.08.2024")
    arrests = [e for e in r.tb.timeline_store.events if e.label == "Arrest"]
    assert {e.date for e in arrests} == {"2024-08-20", "2024-08-22"}
    assert all(e.status == FieldStatus.AMBIGUOUS for e in arrests)
    by_id = {e.event_id: e for e in arrests}
    assert all(set(e.conflicts_with) == set(by_id) - {e.event_id} for e in arrests)


# ---- Peshkar -----------------------------------------------------------------------------------------------------
def test_dossier_statuses_after_peshkar(install_stores):
    """Plan §7.1 example: arrest and first remand VERIFIED from their quotes, custody COMPUTED by date_calc, antecedents UNSUPPORTED."""
    f = pipeline(install_stores, peshkar=True).state.dossier.fields
    assert (f.arrest_date.value, f.arrest_date.status) == ("2024-08-20", FieldStatus.VERIFIED)
    assert (f.first_remand.value, f.first_remand.status) == ("2024-08-21", FieldStatus.VERIFIED)
    assert f.custody_days.status == FieldStatus.COMPUTED and f.custody_days.source.tool == "date_calc"
    # ASSUMPTION: the fake date_calc counts inclusively (168); the plan's figure is 167 (tests/unit/agents/sutradhar accepts both).
    assert f.custody_days.value in (167, 168)
    assert f.antecedents.status == FieldStatus.UNSUPPORTED and f.antecedents.value is None
    assert f.charge_sheet.value.filed is True and f.charge_sheet.value.date == "2024-11-02"


def test_every_verified_field_has_a_source_quote_that_supports_it(install_stores):
    """VERIFIED means 'the quote supports the value': each such field has a source with a quote (span_check ran on it)."""
    r = pipeline(install_stores, peshkar=True)
    fields = r.state.dossier.fields
    verified = [n for n in type(fields).model_fields if getattr(fields, n).status == FieldStatus.VERIFIED]
    assert {"arrest_date", "first_remand"} <= set(verified)
    assert all(getattr(fields, n).source and getattr(fields, n).source.quote for n in verified)
    assert r.tb.count("span_check") >= len(verified)


def test_rights_radar_runs_on_the_filed_timeline(install_stores, case_meta):
    """Plan §7.3 for case-0007: default bail WINDOW_CLOSED (charge sheet on day 74), s.479 CHECK (antecedents unknown), no statutory bar."""
    r = pipeline(install_stores, peshkar=True)
    assert {c.check.value: c.status.value for c in r.state.rights.checks} == case_meta["expected"]["rights_statuses"]
    assert r.tb.count("rights_check") >= 1


def test_list_of_dates_is_built_from_the_timeline_not_invented(install_stores):
    """Plan §7.2: rows sorted by date with their sources; nothing beyond what Munshi filed."""
    r = pipeline(install_stores, peshkar=True)
    rows = r.peshkar.build_list_of_dates(r.state)
    assert [e.date for e in rows] == sorted(e.date for e in rows)
    assert {e.event_id for e in rows} == {e.event_id for e in r.tb.timeline_store.events}
    assert all(e.source and e.source.page for e in rows)


def test_peshkar_stops_at_gate_1_and_nothing_is_approved(install_stores):
    """Plan §3.1: the dossier waits for counsel (Gate 1); no agent approves, no brief exists yet."""
    r = pipeline(install_stores, peshkar=True)
    assert r.state.pending_gate == GateId.GATE_1_DOSSIER
    assert r.state.stage in (Stage.DOSSIER, Stage.RIGHTS)
    assert r.state.brief is None
    assert not [e for e in r.log.events if e.kind == EventKind.GATE_APPROVED]


def test_conflicting_dates_are_put_to_counsel_and_marked_ambiguous(install_stores):
    """Plan §7.1: Peshkar decides which conflicts to put to counsel; the arrest date is AMBIGUOUS and the question names both dates."""
    r = pipeline(install_stores, second_arrest_date="22.08.2024", peshkar=True)
    assert r.state.dossier.fields.arrest_date.status == FieldStatus.AMBIGUOUS
    asked = " ".join(q for batch in r.tb.questions for q in batch)
    assert "20.08.2024" in asked and "22.08.2024" in asked
    assert all(len(batch) <= 3 for batch in r.tb.questions)


def test_unsupported_fields_are_left_for_counsel_not_filled_in(install_stores):
    """Antecedents are never guessed: the field stays UNSUPPORTED and appears as an open question (plan §7.1 'open_questions')."""
    r = pipeline(install_stores, peshkar=True)
    assert r.state.dossier.fields.antecedents.status == FieldStatus.UNSUPPORTED
    assert any("antecedents" in q.lower() or "pending cases" in q.lower() for q in r.state.dossier.open_questions)


def test_shelf_is_the_only_input_peshkar_needs(install_stores):
    """The dossier is derived from the case shelf, not from the raw pages: once Peshkar starts, no page-reading tool is called."""
    r = pipeline(install_stores, peshkar=True)
    page_tools = {"inspect_page", "read_text_layer", "parse_layout", "ocr_page", "vision_read_page", "split_bundle"}
    names = [c.name for c in r.tb.calls]
    first_peshkar = min(names.index(n) for n in ("extract_dossier", "rights_check", "span_check") if n in names)
    assert not [n for n in names[first_peshkar:] if n in page_tools]


def test_a_dictated_fact_is_user_stated_and_never_verified(install_stores):
    """Plan §4.5, §7.1: a fact counsel dictated is USER_STATED with a chat source; the brief later labels it 'per counsel, not on record'."""
    world = h.fresh_case_world()
    install_stores(world.stores)
    tb = h.ScenarioToolbox(world, pages=h.build_bundle(), boundaries=h.BUNDLE_BOUNDARIES, answers=[""] * 6)
    laptop = h.make_llm(where="laptop", events=h.munshi_events_responder(), free="")
    munshi, mctx, _ = h.build_agent(MunshiAgent, llm=laptop, toolbox=tb, world=world)
    state = munshi.run(h.seed_state())
    # RECONCILED: Peshkar reads the papers; what counsel dictated reaches the record as counsel's own `state_field` action (the audio route writes it),
    # and the dossier built over it keeps it USER_STATED with its chat source
    mctx.log.append(Event(event_id="", case_id=h.CASE_ID, ts="", kind=EventKind.USER_ACTION, actor="counsel",
                          inputs={"action": "state_field", "field": "personal", "value": ["sole earning member"], "chat": "turn 3"}))
    agent, _, _ = h.build_agent(PeshkarAgent, llm=laptop, toolbox=tb, world=world, log=mctx.log)
    personal = agent.run(state).dossier.fields.personal
    assert (personal.value, personal.status) == (["sole earning member"], FieldStatus.USER_STATED)
    assert personal.source.chat == "turn 3"
