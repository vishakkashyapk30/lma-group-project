"""T7 safety (plan §15.2 T7, §15.8, §16): planted Faker-style names never appear in logs or Ada-bound payloads.

Synthetic names (English and Devanagari, from `tests/fakes/data.py`; no real people) are planted in the documents, in a dictation and in a chat
message. Metric: leak rate = 0 over every artefact where a leak could sit: the event log, the Python log records, every prompt of the Ada-bound
client, the case shelf, the shared stores, the API responses, the board of the batch desk and the exported application.

Real modules: Munshi's pseudonymisation step, BaseAgent (which logs pseudonymised inputs only), `privacy.boundary.assert_pseudonymised`,
`privacy.leak_check.find_leaks`, the API, the batch desk. Fakes: models, stores and tools (`Scenario`; its toolbox pseudonymises with the role
aliases Accused-1, Complainant-1, Co-accused-1, IO-1).

ASSUMPTIONS: names are replaced by role aliases before filing and before anything is logged or sent to Ada; raw files stay below
`$VS_DATA_DIR/cases/` (laptop only); an identity pseudonymiser (a failing step) still leaves no name in an Ada prompt.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from tests.fakes.data import PLANTED_NAMES, PLANTED_NAMES_HI, build_world
from tests.fakes.toolbox import leaked_names
from tests.system import _helpers as sh
from tests.system import _scripts as ss
from tests.unit.export._helpers import docx_text
from tests.unit.privacy._helpers import VIOLATION
from vakeel_sahayak.privacy.boundary import assert_pseudonymised
from vakeel_sahayak.privacy.leak_check import find_leaks
from vakeel_sahayak.schemas.enums import AgentName, DocumentType

pytestmark = pytest.mark.system

CASE = sh.CASE_ID
G2 = sh.G2
ALL_NAMES = PLANTED_NAMES + PLANTED_NAMES_HI
TABS = ("ingestion", "dossier", "dates", "rights", "brief", "spar", "prep")


def names_bundle() -> list[sh.BundlePage]:
    """The four documents of the worked example with every planted name woven into the pages (English text layer and Devanagari OCR)."""
    n0, n1, n2, n3 = PLANTED_NAMES
    h0, h1 = PLANTED_NAMES_HI
    hi = sh.HI_FIR_P1 + f"\nआरोपी {h0}\nशिकायतकर्ता {h1}"
    return [
        sh.page(hi, DocumentType.FIR, new_doc=True, lang="hi", scanned=True, ocr_text=hi, ocr_conf=0.8),
        sh.page(f"REMAND ORDER\nFIR No. 112/2024 PS-1\nThe accused {n0} was arrested on 20.08.2024 and remanded on 21.08.2024.\n"
                f"Complainant {n1}; co-accused {n2} absconding; IO {n3}.", DocumentType.REMAND_ORDER, new_doc=True),
        sh.page(sh.pdfgen.BAIL_ORDER_PAGE + f"\nThe bail application of {n0} is rejected.", DocumentType.BAIL_ORDER, new_doc=True),
        sh.page(sh.pdfgen.ORDER_SHEET_PAGE, DocumentType.BAIL_ORDER),
    ]


def with_names_run(tmp_path, monkeypatch, **kw) -> sh.Scenario:
    sc = sh.Scenario(tmp_path, monkeypatch, pages=names_bundle(), answers=[""] * 4, **kw)
    sc.through_gate1()
    sc.through_draft()
    sc.chat(f"Did {PLANTED_NAMES[0]} have any earlier bail application?")
    return sc


def artefacts(sc: sh.Scenario, client) -> list[str]:
    """Everything a leak could sit in: the log, Ada-bound prompts, the case shelf, the shared stores and the API responses."""
    api = [client.get(f"/api/cases/{CASE}/{tab}").text for tab in TABS]
    return [sh.dump_events(sc.events()), *sc.ada_prompts, sh.stores_text(sc.world, shared=False), sh.stores_text(sc.world, shared=True), *api]


# ---- the main metric ----------------------------------------------------------------------------------------------------
def test_planted_names_never_reach_logs_ada_payloads_stores_or_the_api(tmp_path, monkeypatch):
    """Leak rate 0 over every artefact; the independent scan and `privacy.leak_check.find_leaks` agree."""
    sc = with_names_run(tmp_path, monkeypatch)
    texts = artefacts(sc, sc.client())
    leaks = leaked_names(texts, ALL_NAMES)
    assert sh.leak_rate(len(leaks), len(texts)) == 0.0, leaks
    assert [n for t in texts for n in find_leaks(t, ALL_NAMES)] == []


def test_the_names_really_were_in_the_documents(tmp_path, monkeypatch):
    """Guard against a vacuous pass: the planted names are in the raw pages and the pseudonymiser turned them into aliases."""
    pages_text = " ".join(p.text for p in names_bundle())
    assert all(n in pages_text for n in ALL_NAMES)
    sc = with_names_run(tmp_path, monkeypatch)
    assert any("Accused-1" in p for p in sc.ada_prompts + [sh.dump_events(sc.events())])


def test_python_log_records_hold_no_planted_name(tmp_path, monkeypatch, caplog):
    """'Logs store only pseudonymised text' (plan §16): the application logger, at DEBUG, never saw a name."""
    caplog.set_level(logging.DEBUG)
    with_names_run(tmp_path, monkeypatch)
    assert leaked_names([caplog.text, *[r.getMessage() for r in caplog.records]], ALL_NAMES) == []


def test_every_tool_call_input_in_the_log_is_pseudonymised(tmp_path, monkeypatch):
    """Event inputs and outputs hold pseudonymised text only: no TOOL_CALL or TOOL_RESULT carries a name."""
    sc = with_names_run(tmp_path, monkeypatch)
    tool_events = [e.model_dump_json() for e in sc.events() if e.tool]
    assert tool_events and leaked_names(tool_events, ALL_NAMES) == []


# ---- the boundary -----------------------------------------------------------------------------------------------------
def test_every_ada_bound_payload_passes_the_boundary(tmp_path, monkeypatch):
    """Plan §16: only pseudonymised text may be sent to Ada: each recorded Ada prompt passes `assert_pseudonymised`."""
    sc = with_names_run(tmp_path, monkeypatch)
    assert sc.ada_prompts
    for prompt in sc.ada_prompts:
        assert assert_pseudonymised({"case_id": CASE, "prompt": prompt}) is None


def test_no_page_image_or_audio_ever_reaches_an_ada_prompt(tmp_path, monkeypatch):
    """Page images, audio and raw files stay on the laptop: no prompt carries file bytes, and raw files sit below the data directory only."""
    sc = with_names_run(tmp_path, monkeypatch)
    assert not [p for p in sc.ada_prompts if "%PDF" in p or "RIFF" in p or "\x89PNG" in p]
    raw = [p for p in tmp_path.rglob("*") if p.suffix in (".pdf", ".wav", ".png", ".jpg")]
    assert raw and all(sc.data_dir in p.parents for p in raw)


def test_a_name_typed_into_the_chat_is_pseudonymised_before_ada(tmp_path, monkeypatch):
    """Counsel types a real name in the chat: the Ada-bound prompt carries the alias (Accused-1), never the name."""
    sc = with_names_run(tmp_path, monkeypatch)
    assert any("Accused-1" in p for p in sc.ada_prompts)
    assert leaked_names(sc.ada_prompts, ALL_NAMES) == []


def test_a_devanagari_name_typed_into_the_chat_is_pseudonymised_too(tmp_path, monkeypatch):
    sc = sh.Scenario(tmp_path, monkeypatch, ada=sh.ada_client(chat=[("custody", "Custody: 167 days [date_calc]")]))
    sc.with_case_state()
    client = sc.client()
    client.post(f"/api/cases/{CASE}/chat", json={"text": f"{PLANTED_NAMES_HI[0]} कितने दिन से हिरासत में है? How many days in custody?"})
    assert leaked_names(sc.ada_prompts, ALL_NAMES) == []
    assert leaked_names([sh.dump_events(sc.events()), client.get(f"/api/cases/{CASE}/chat").text], ALL_NAMES) == []


def test_a_failing_pseudonymiser_is_caught_at_the_boundary(tmp_path, monkeypatch):
    """Defence in depth: even if the pseudonymise step does nothing (identity), no planted name reaches an Ada prompt: the run is
    stopped by the boundary (a violation error) or the text is cleaned later; either way the Ada clients see no name."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=names_bundle(), answers=[""] * 4, pseudonymiser=lambda text, case_id: text)
    try:
        sc.through_gate1()
        sc.through_draft()
    except VIOLATION:
        pass
    assert leaked_names(sc.ada_prompts, ALL_NAMES) == []


# ---- the shared stores ------------------------------------------------------------------------------------------------
def test_shared_stores_never_hold_a_case_name_and_are_not_written_by_a_run(tmp_path, monkeypatch):
    """The seven shared stores are read-only for a run: their content is the same before and after, and holds no case name."""
    sc = sh.Scenario(tmp_path, monkeypatch, pages=names_bundle(), answers=[""] * 4)
    before = sh.stores_text(sc.world, shared=True)
    sc.through_gate1()
    sc.through_draft()
    after = sh.stores_text(sc.world, shared=True)
    assert after == before and leaked_names([after], ALL_NAMES) == []


# ---- the batch desk ---------------------------------------------------------------------------------------------------
def test_names_in_a_batch_never_reach_ada_or_the_board(tmp_path, monkeypatch):
    """Three of six constructed cases carry the planted names: after stage 1 and 2, no Ada prompt, record or board entry has a name."""
    cases = sh.build_batch(n=6, planted_indexes=(3, 5), planted_days_left=(3, 1))
    for c in cases[:3]:
        c.pages.extend(ss.names_pages())
    sc = sh.Scenario(tmp_path, monkeypatch, toolbox=sh.BatchToolbox(build_world(), cases), ada=sh.ada_client())
    files = []
    for c in cases:
        f = sc.data_dir / "batch" / Path(c.path).name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4\n% stub\n")
        files.append(str(f))
    agent = sc.agent(AgentName.PAIROKAR)
    agent.stage2(agent.decide_next_steps(agent.stage1(files)), 10_000.0)
    texts = [*sc.ada_prompts, sc.client().get("/api/desk/board").text, *[sh.dump_events(sc.events(case_id=c.case_id)) for c in cases]]
    assert leaked_names(texts, ALL_NAMES) == []


# ---- the exported application -----------------------------------------------------------------------------------------
def test_the_exported_application_has_placeholders_not_names(tmp_path, monkeypatch):
    """Needs python-docx. The cause title has placeholders for real names, filled in only on counsel's machine (plan §8.2)."""
    pytest.importorskip("docx")
    sc = with_names_run(tmp_path, monkeypatch)
    sc.clear_and_approve(G2)
    paths = [Path(p) for p in sc.client().post(f"/api/cases/{CASE}/export", json={"format": "DOCX"}).json()]
    text = docx_text(next(p for p in paths if "application" in p.name.lower()))
    assert leaked_names([text], ALL_NAMES) == [] and "[" in text
