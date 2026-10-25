# Munshi: reading real PDFs (PyMuPDF installed), 2026-10-25

## Why three tests started failing
PyMuPDF was installed, so tests that used to skip now read real PDFs. Root causes (all code bugs, tests unchanged):

1. **Text-layer coverage was measured against the whole page** (`ingestion/source.py`, `PdfSource.text_coverage`): the area of the text blocks over the page area. A one-paragraph remand order fills 8% of an A4 page, so a complete born-digital text layer failed the `text_coverage_min` check and the page fell down the ladder. Now coverage is how much of what the page *shows* is in the layer: 1.0 when images cover under a quarter of the page (logos, stamps), else text area over image area (a full-page scan with a stamp's worth of text is thin).
2. **Bundle splitting read titles only in English and by dictionary order** (`ingestion/classify.py`, `ingestion/bundles.py`): no Hindi custody-certificate title; when a page matched several titles the first in dictionary order won (a Hindi remand order quotes "प्रथम सूचना रिपोर्ट सं." on line 3 and was read as an FIR); High Court orders, which carry the court name and a docket line instead of a title, were never recognised as starting a document. Fixes: Hindi titles mirrored from the label cues; the earliest title wins and confidence is 0.8 when it is on a line before every other match; a High Court bail-order caption (`CRM (A) 2154 of 2025`, `CRL.P No.`, `In Re: An application for ... Bail`) is looked for in the first 14 lines when the first lines hold no title; `COURT_HEADING` tolerates lost spaces ('INTHEHIGHCOURTOFDELHI'), 'HIGH COURT OF X' and 'Hon'ble Mr. Justice'; two new split rules (a titled page after untitled pages starts a document; an untitled page with a court heading after a titled non-bail document starts a court order).
3. **A crash, not a skip, when the vision model cannot load** (`models/vlm.py`): `get_vision()` picks Qwen3-VL when transformers and torch are installed, even without weights or torchvision, and `from_pretrained` raised `ImportError` (not `ModelUnavailable`) out of `read_file`. Every load failure is now `ModelUnavailable` (remembered per model id so a bundle does not retry per page) and the ladder goes on to ask-counsel. Note: with `VS_MODELS=auto` and weights absent this still tries the Hub first (it printed the unauthenticated-request warning); set `VS_MODELS=offline` to avoid any network call.

## Tests
Before: 3 failing (`test_signals::test_compute_signals_born_digital_pdf`, and two in `tools_intake/test_documents_tools.py`: split_bundle_flow1, classify_document_remand_order; the latter two share the cause above).
After: new `tests/unit/ingestion/test_pdf_reading_real.py` (10 tests on real generated PDFs: short page coverage, sparse scan, logo, Hindi and High Court titles, English bundle, vision load failure, untitled orders). Area run (ingestion, tools_intake, agents/munshi, pipelines, stores, testsets): 1105 passed, 6 skipped, 1 failed, 9 errors (the failure and errors are the T7 stubs below). ruff on src is clean. Skips left in the five areas: `tests/unit/testsets/test_t8_speech.py` (6, `parler_tts` not installed). Errors that remain are the known T7 stubs (`testsets/t7_safety.py` raises NotImplementedError: 9 setup errors and 1 failure in `tests/unit/testsets`).

## Munshi on T2 (offline, no hosted API; all 100 bundles of each kind, scripts in the session scratchpad)
Gold = `data/testsets/t2/truth.jsonl`. A type is "ok" when equal, or when the T2 type COURT_ORDER is read as BAIL_ORDER, ORDER_SHEET or OTHER (the document enum has no COURT_ORDER).

| kind | bundles | gold docs | found docs | exact boundaries | bundles exactly split | type ok | route | crashes |
|---|---|---|---|---|---|---|---|---|
| K1 born-digital | 100 | 368 | 355 | 340 (92%) | 86 | 339 | text layer 381 pages, ask-counsel 10 | 0 |
| K5 Hindi born-digital | 100 | 368 | 368 | 368 (100%) | 100 | 368 | text layer 368 | 0 |
| K2 image-only | 100 | 368 | 100 | 0 | 0 | n/a | ask-counsel 391 of 391 pages, one OTHER document per bundle | 0 |
| K3 image-only | 100 | 368 | 100 | 0 | 0 | n/a | ask-counsel 391 of 391 | 0 |
| K4 image-only | 100 | 368 | 100 | 0 | 0 | n/a | ask-counsel 391 of 391 | 0 |
| K6 legacy font | 100 | 368 | 100 | 0 | 0 | n/a | ask-counsel 368 of 368 (legacy font rejected, OCR and vision unavailable) | 0 |

Before the fixes, on 10 bundles (3 K1, 3 K5, one each K2 to K4 and K6): K2 to K6 crashed on the first page (ImportError from the vision model); K1 merged FIR and court-order pages; K5 was one document per bundle (4 pages, type FIR/REMAND).

## What is still wrong or open
- 10 K1 pages are real High Court orders whose dictionary-word share is 67 to 84% (legal vocabulary, names), under the fixed 85% bar of plan §4.2 step 1. With no OCR or vision model they end in ask-counsel and the usable text layer is thrown away (the page text is empty). Option: when every rung is unavailable, keep the rejected layer as a low-confidence read instead of discarding it. Not changed: it is a design decision.
- The K1 misses left (28 boundaries) are those 10 unreadable pages plus High Court orders whose court heading is below the first three lines (`IN THE HIGH COURT OF JUDICATURE AT BOMBAY` on line 4 after a neutral-citation line and a file name).
- K2 to K4 and K6 need Tesseract/Surya or a vision model (or Sarvam Vision, not used here): the ask-counsel result is the intended offline behaviour.
- `tests/fixtures/pdfgen.py` writes base-14 fonts only, so Hindi pages are tested at text level (`split_into_documents`), not through a PDF.

## Follow-up 2026-10-26: keep a near-miss text layer (opt-in `Switches.munshi_keep_weak_text`)
Done: when the ladder would end in ask-counsel and the text layer was rejected only for a dictionary-word share of 60% to 84%, the layer's text is kept as a low-confidence read (`ingestion/ladder.py` `weak_layer_read`, `WEAK_TEXT_FLOOR` 0.60; both ladders: `read_file`/`route_page_from` and the tooled `route_page_with_tools`). `RouteOutcome.low_confidence` and `.confidence` (the share); `PageRoute.confidence` in the intake report (omitted from the JSON when None, so default reports are byte-identical); a Gap line per file naming the pages and their share, "counsel to check against the original". Tests: `tests/unit/ingestion/test_keep_weak_text.py` (7, real generated PDFs). Variant id P8; row in `docs/literature-to-code-map.md` Sweep 4 (no paper: a plan 4.2 design choice).
Measured on T2 K1 (100 bundles, 391 pages, offline, no OCR or vision): 10 pages had an empty read before; with the switch 9 are kept (shares 66.7%, 69.8%, 72.4%, 78.5%, 82.2%, 83.3%, 84.4%, 84.5%, 84.6%) and 1 stays empty (under the 60% floor or another rejection reason). Whether the kept text yields correct facts was not measured (it needs the Peshkar extraction on those pages against T2 truth; next step).
Not done: `Switches.munshi_keep_weak_text` is not yet passed by any runner (set it in `Switches(...)`); the UI does not show the badge yet (the data is in `page_routes[].confidence` and the Gap).
