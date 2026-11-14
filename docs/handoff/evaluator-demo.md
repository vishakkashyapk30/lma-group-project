# Evaluator demo (guided tours)

An evaluator of the project opens the site, finds six recorded demo cases on the Cases page, picks one and presses Next after every step. Every field is already filled; the walk goes from the papers to the exported application. The demos differ by offence and law, custody and rights, record quality, and parity and history. The backend half (recorded cases, the `/api/demo/tours` routes, pre-loading at startup) comes first, then the tour interface.

## Backend: recorded cases and pre-loading

(handoff, backend half)

Written 14 Nov 2026, re-recorded 15 Nov 2026 (see "What changed since the first recording"). An evaluator opens the site and finds six demo cases already loaded. Each has a tour: nine steps (INTAKE, DOSSIER,
GATE_1, RIGHTS, BRIEF, SPAR, HEARING_PREP, GATE_2, FILE) whose captions say what each agent did in that recorded run, with the run's own
numbers. Every case was run end to end through the real API on Sarvam-105B (the owner's key), exactly as the web interface calls it.
Gate 2 is left open in every snapshot: the evaluator approves it in the tour, which shows that export is impossible before counsel's
approval, then downloads the DOCX. The frontend tour is a separate piece of work (it codes against the contract below).

### What was built
| Piece | Where |
|---|---|
| Six synthetic cases, their PDFs and counsel's scripted answers | `src/vakeel_sahayak/demo/cases.py` |
| Recorder (drive the API, snapshot, build the tour, check) | `scripts/demo/record_demos.py` |
| The recordings | `demo/cases/<slug>/` (`case/`, `events.jsonl`, `tour.json`) |
| Pre-loading at API start-up, the tour contract | `src/vakeel_sahayak/demo/preload.py`, called from `api.app.create_app` |
| Tour routes | `src/vakeel_sahayak/api/routers/demo.py`: `GET /api/demo/tours`, `GET /api/demo/tours/{slug}`, `POST /api/demo/tours/{slug}/reset` |
| A chosen case id on creation (the recorder uses `demo-01` ... `demo-06`) | `POST /api/cases {"title", "case_id"}`: optional; 409 when taken, 422 when invalid |
| Tests (offline, a tiny fixture snapshot) | `tests/unit/demo/test_preload.py` |
| Docker | `docker/backend.Dockerfile` copies `demo/`; `.dockerignore` keeps `demo/**`; `compose.yaml` passes `VS_DEMO_CASES` |

`scripts/seed_complete_bail_demo.py` (Satvik's complete file) now takes its documents from case 01, so there is one copy of that file.

### The six cases
All invented: role pseudonyms only (Accused-1, Co-accused-2, Complainant-1, IO-1), police stations PS-<n>, FIR numbers of no real case.
Every page carries the image stamp "SYNTHETIC DEMONSTRATION DOCUMENT - NOT A COURT RECORD OR LEGAL EVIDENCE" at top and foot. The
custody certificates are dated 10.11.2026 and their day counts were checked by date arithmetic.

Re-recorded 15 Nov 2026 (second recording; the first, 14 Nov, is described under "What changed since the first recording" below). What each recorded run
produced (numbers from `demo/cases/<slug>/tour.json`; rights statuses are the Rights Radar as of 2026-11-15; "withheld" is sentences the claim checker
could not support; "spend" is Sarvam INR for that case; sparring: objections raised, then how many Abhiyojak judged ANSWERED / PARTLY / UNANSWERED, and how many were not
judged because the sparring token budget was spent):

| Case | Law and file | Rights Radar | Brief (grounds, withheld) | Sparring | Spend |
|---|---|---|---|---|---|
| 01 cheating, parity | IPC 420/406, 11 born-digital PDFs, co-accused on bail | default bail WINDOW_CLOSED, s.479 ELIGIBLE (978 days against 852), Antil CHECK | 7 drafted (1 repaired, 6 supported); 16 withheld; 3 grounds left to counsel | 13 raised; 0 judged, 13 not judged | 4.92 |
| 02 theft, default bail | BNS 303(2), 8 PDFs, no charge sheet | default bail ELIGIBLE (day 96), s.479 NOT_YET, Antil A | 4 drafted (1 repaired, 3 supported); 4 withheld; 2 left | 9 raised; 0 judged, 9 not judged | 3.86 |
| 03 NDPS small, Hindi | NDPS 21(a), Hindi FIR plus 8 English PDFs, grounds of arrest oral | default bail WINDOW_CLOSED (day 54 of 60), s.479 ELIGIBLE (136 days against 122), Antil C | 3 drafted, 3 supported; 14 withheld; 5 left | 5 raised; 0 judged, 5 not judged | 7.70 |
| 04 NDPS commercial, scanned | NDPS 21(c)/29, one image-only page read by OCR | default bail WINDOW_CLOSED, s.479 CHECK (the charge names no clause), s.37 BAR_APPLIES, Antil C | 6 drafted (2 repaired, 4 supported); 15 withheld; 3 left | 15 raised; 0 judged, 15 not judged | 4.75 |
| 05 attempt to murder, parity | BNS 109 with 3(5), 11 PDFs with the medico-legal report | default bail WINDOW_CLOSED (90-day limit, maximum death, day 81), s.479 NOT_APPLICABLE (death), Antil B | 6 drafted (1 repaired, 5 supported); 5 withheld; 1 left | 14 raised; 0 judged, 14 not judged | 4.19 |
| 06 breach of trust, missing papers | BNS 316(2), 4 PDFs only; intake asked 6 questions | default bail NOT_YET (day 41), s.479 CHECK (antecedents unknown), Antil CHECK | 4 drafted (2 repaired, 2 supported); 6 withheld; 2 left | 11 raised; 8 judged: 2 ANSWERED, 3 PARTLY, 3 UNANSWERED; 3 not judged | 6.77 |

Not judged means the reply or judge call was refused with `BudgetExhausted`; Abhiyojak then records UNANSWERED with the reason "The reply could not be judged; counsel to read it."
The tour's SPAR caption says so in each case.

Gate 2 checklist sizes: 13, 11, 6, 15, 15, 9 items (unsupported fields plus unanswered objections). The six differ in law (IPC, BNS, NDPS
small and commercial), custody (default bail open, closed, not yet open, s.37 bar), record quality (complete, Hindi, scanned, four
papers only) and parity (co-accused granted, refused, none).

#### What changed since the first recording (14 Nov to 15 Nov 2026)
- Rights Radar: the maximum punishment is found for BNS 109 with 3(5) and NDPS 21(a), so cases 03 and 05 now show real statuses (default bail WINDOW_CLOSED,
  s.479 ELIGIBLE in 03 and NOT_APPLICABLE in 05) instead of CHECK for a missing maximum; the story and variant lines of 01, 03, 04, 05, 06 in `demo/cases.py` were rewritten to match.
- Sparring reserve on in the product configuration (60000 at first, 120000 for the final recording): objection raising no longer fails (objections per case: 3 to 10 in the first recording,
  now 5 to 15), but judging is still starved, see Known limits. Old (first recording, no reserve): 41 objections, 1 judged. New: 67 raised, 8 judged (all in case 06).
- The SPAR caption now states what happened in the run: objections raised, how many judged, answered, partly answered, unanswered, how many not judged for lack of the sparring token budget, and that counsel answers what stays open before Gate 2 (`record_demos.py`, `build_tour`).
- Tour contract: optional `hi` text; `translate_tours_hi.py` was run on these recordings (see Hindi tours).
- A radar crash on dossiers with no sections was fixed in the product; no `rights_check_failed` event is in any recording.

### Tour contract (`demo/cases/<slug>/tour.json`; pydantic model `demo.preload.Tour`, also in `docs/api/openapi.json`)
`{slug, case_id, title, story, variant{offence, custody, record, parity}, recorded{date, backend, model, cost_inr}, steps[9]}`; each
step `{stage, tab (dossier|rights|brief|spar|prep), title, caption, agent (MUNSHI|PESHKAR|SUTRADHAR|VAKEEL|ABHIYOJAK|null), filled[{label, value}], action}`.
`action` is `"approve_gate_2"` on the GATE_2 step only.

**Gate 2 needs acknowledgements.** The Gate 2 checklist of most cases is not empty (unsupported fields, grounds that need review,
unanswered objections). `POST /api/cases/{id}/gates/GATE_2_EXPORT/approve` answers 409 unless `acknowledged_fields` lists them. The
GATE_2 step's `filled[].label`s are exactly the strings to send (a field name such as `previous_bail`, `NEEDS_REVIEW:G2`,
`UNANSWERED:O3`), and `GET /api/cases/{id}/gates/GATE_2_EXPORT` gives the same list live. The workspace's own Gate 2 modal already sends
them this way.

**Repeating the tour.** After an evaluator approves Gate 2 the case stays approved. `POST /api/demo/tours/{slug}/reset` puts the case
back as recorded (record rows and folder replaced), for the next evaluator.

### Pre-loading
On API start-up (`create_app()`), unless `VS_DEMO_CASES` is `off` (also `0`, `false`, `no`; default on), every
`demo/cases/<slug>/` is imported when its case id is not in the record, has no folder under `<VS_DATA_DIR>/cases/` and is not in
`<VS_DATA_DIR>/cases/.demo_imported.json` (so a demo case counsel deletes stays deleted). Import = copy `case/` to
`<VS_DATA_DIR>/cases/<case_id>/` and append `events.jsonl` to `record.sqlite` with the recorded event ids and times. It never
overwrites and is idempotent; a broken snapshot is skipped with a warning and never stops the API. `VS_DEMO_DIR` points at another
`demo/` folder. Switch it off: `VS_DEMO_CASES=off` (compose: `VS_DEMO_CASES=off docker compose up`). The test suite sets it off in
`tests/conftest.py`; `tests/unit/demo` turns it on with a fixture.

The tours list only cases present in the record, so with the demo off `GET /api/demo/tours` is `[]`.

### How to re-record (one case or all)
Everything heavy under `systemd-run` with a memory cap; the key stays in the main checkout's untracked `.env` and is never printed.
```bash
WT=<worktree or repo root>; M=<main checkout (has .venv and .env)>; D=<scratch data dir>
mkdir -p $D && ln -sfn $M/data/stores $D/stores          # stores read-only from the main checkout
ln -sfn $M/models $WT/models                              # helper models for VS_MODELS=auto (gitignored)
systemd-run --user --unit=demo-api -p MemoryMax=6G --working-directory=$WT /bin/bash -c "set -a; . $M/.env; set +a; \
  export PYTHONPATH=$WT/src VS_DATA_DIR=$D VS_CONFIG_DIR=$WT/configs VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_ALLOW_PAID=sarvam \
  VS_EXTERNAL=consented VS_SARVAM=consented VS_GEMINI=off VS_SARVAM_CAP_INR=300 VS_SARVAM_RUN_ID=evaluator-demo VS_DEMO_CASES=off; \
  unset GEMINI_API_KEY GEMINI_API_KEYS OPENAI_API_KEY VS_API_TOKEN; \
  exec $M/.venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --host 127.0.0.1 --port 8020"
$M/.venv/bin/python scripts/demo/record_demos.py run --api http://127.0.0.1:8020 --data-dir $D --cases 01-cheating-parity [--reset]
$M/.venv/bin/python scripts/demo/record_demos.py check     # key-like strings, machine paths, size of demo/
systemctl --user stop demo-api
```
The scratch data dir has its own Sarvam ledger (`$D/sarvam/ledger.sqlite`), so `VS_SARVAM_CAP_INR=300` caps this recording alone
(the code refuses the call that would pass it). `record_demos.py tour` rebuilds the tour files from the raw API answers kept in
`$TMPDIR/vs-demo-work/<slug>/raw.json` (not committed) without calling any model. The recorder fails a case, rather than guessing, when
intake asks a question no scripted answer matches: add a pattern to that case in `demo/cases.py`.

VS_EXTERNAL=consented with counsel's consent recorded per case (`POST /consent`, provider sarvam, note "counsel's consent for the
synthetic evaluator-demo case"): the cases are synthetic, so raw pages may go to Sarvam; nothing of a real client is involved.

### Spend
Second recording, 15 Nov 2026: the owner's Sarvam key (`sarvam-105b`), capped at INR 300 for the recording (`VS_SARVAM_CAP_INR=300`, a scratch data
dir with its own ledger). Per-case spend, from the ledger: 01 4.92, 02 3.86, 03 7.70, 04 4.75, 05 4.19, 06 6.77 INR, which is 32.19 INR for the six
recorded runs (75 to 126 hosted calls each). The ledger of that recording (550 calls, a fresh directory) sums to 29.23 INR (it counts each call once; the per-case figures overlap in time). Earlier work on the same day, not in these numbers: the 60000-token
recording (about INR 30, six cases, replaced) and one aborted case 05 run. The first recording (14 Nov) cost 20.12 INR for six cases.
The backend checks (pre-loading, export) made no model call; they ran with `VS_MODELS=offline`. Hindi captions: Gemma on the Gemini free tier, no cost.

### Known limits seen while recording (product, not the demo)
- **Sparring is still starved (the main thing to know).** The product now has a 120000-token sparring reserve (`PRODUCT_SPARRING_RESERVE_TOKENS`;
  it was 60000 in the first re-recording of this day, with the same outcome). With Sarvam-105B it is spent before Abhiyojak judges: in cases 01 to 05
  none of 13, 9, 5, 15 and 14 objections was judged (all UNANSWERED with "The reply could not be judged"), only case 06 judged 8 of 11 (2 answered, 3 partly,
  3 unanswered). Why (case 05, events.jsonl): raising the objections costs about 5K tokens per factor plus about 10K for the general round (about 40K);
  then every objection takes two Vakeel calls (reply and repair, 3.4K to 3.9K each, one factor made 13 calls); judging runs after all replies, so it is
  last in line and finds the pool empty (`BUDGET_HIT` spent 121127 of 120000). Roughly 8K to 12K per objection in all, so a reserve for 14 objections
  needs 150K to 180K, or the judge should run per factor, or objection numbers should be capped. Before the reserve (first recording): 40 of 41 objections
  not judged; now (120000): 56 of 56 in cases 01 to 05 and 3 of 11 in case 06, so 59 of 67 in all (88%). The captions state this plainly. Gate 2 therefore
  lists the unanswered objections of every case, and the tour approves with acknowledgements.
- The Rights Radar fixes of 15 Nov show in the new recordings: case 03 default bail WINDOW_CLOSED and s.479 ELIGIBLE (maximum 1 year read from NDPS 21(a)),
  case 05 default bail WINDOW_CLOSED on a 90-day limit and s.479 NOT_APPLICABLE (maximum death for BNS 109 with 3(5); BNS 109's own maximum is not death in the
  statute for every clause, the radar takes the highest). Still CHECK for s.479 in case 04 (NDPS 21(c)/29: the charge names no clause, so the radar has no
  maximum) and case 06 (antecedents unknown). No `rights_check_failed` event in any of the six recordings.
- NDPS case 03's "Notice of appearance" row reads "Offence punishable up to 7 years" (the NDPS 21(a) maximum is 1 year); left as recorded.
- Seen in the recorded output, left as recorded: case 06's "Notice of appearance" reads "Offence punishable up to 7 years. No arrest memo or
  notice in the file" although an arrest memo is in the file; intake names a "bail order" document type in cases 02, 03 and 06 whose dossier
  lists no earlier bail order.
- Live walk (15 Nov 2026, real backend on offline models, real tour files, `frontend/e2e/tour_live.spec.ts`, reruns with
  `E2E_LIVE_API=1 E2E_LIVE_API_BASE=<api> E2E_PORT=<web> E2E_TOURLIVE_SHOTS=<dir>`; skipped otherwise): tours 01 and 04 from the Cases page to
  Export with Next only, real Gate 2 approval, DOCX downloaded (a zip, over 2 KB), titles, captions and filled values equal to tour.json at
  all nine steps, no console errors. Defect found and fixed: at 1440x900 a long "Filled in at this step" list spilled out of the tour bar
  over the workspace (the step column was never height-limited in the wide layout); it now scrolls inside the bar
  (`lg:max-h-[calc(42dvh-1.5rem)]`), with a layout check in `tour.spec.ts` and `tour_live.spec.ts` (`expectStepInsideBar`).
  Fixed on 15 Nov 2026: the "Exported 4 files" toast no longer covers the export button (toasts now sit bottom-left; during a demo, above the
  bar on wide screens and at the top of the screen below lg); layouts under 1024 px were walked at 768x1024 and 390x844 and the bar folds there.
  Hindi captions: translated on 15 Nov 2026 for the current recordings (see Hindi tours); 9 texts remain English.
  The 768 px breadcrumb overlap and the cut-off stepper on a phone are the workspace header, not the tour (not fixed).
- Day counts in the case descriptions follow the Rights Radar (day 1 is the first remand): cases 01, 03, 04, 05 charge sheets on days
  55, 54, 167 and 81.
- The exported DOCX files carry the locality "Karol Bagh" (case 01), an address that is part of the synthetic file, not a person's name.

## Tour interface (frontend)

### What the evaluator sees
- **Cases page** (`/cases`): a "Guided demos" section above the matters, one row per tour with its title, its story and the four facets as plain text ("Offence and law: ...", "Custody and rights: ...", "Record quality: ...", "Parity and history: ..."), and a "Start the guided demo" button. It opens `/case/<case_id>?tour=<slug>`. With no tours (the server answers 404 or `[]`, or the request fails) the section is not rendered at all.
- **Tour bar** in the workspace: docked under the step (above nothing else, never over it), white panel with a hairline top border. It shows "Guided demo · Step k of n · Done by <agent>, <subtitle>", the step's title (serif) and caption (read out through `aria-live="polite"`), and the step's `filled` list as read-only filled fields (label above, value in a field-like box). The Gate 1 and Gate 2 steps add the gate's status ("Gate 1 is approved.", "Gate 2 is open. Next approves the draft for export.") and the gate's note from `GATE_LABELS`. The first step shows the recording line (date, backend, model). Buttons: Exit the demo, Back, Next (the primary). On the Gate 2 step Next reads "Approve and continue"; on the last step it reads "Finish" and leaves tour mode, staying on Export.
- **Next** moves the workspace with its own navigation (`ws.setStage`), so the stepper, the step slide and the breadcrumb behave as for counsel. GATE_1 opens Review facts, GATE_2 and FILE open Export, SPAR opens Draft grounds and scrolls to "Likely objections". The case is past Gate 1, so no step is locked; if a tour ever points at a locked step the bar says "This step is not open in this case yet..." instead of failing.
- **Gate 2**: Next on the GATE_2 step calls `POST /api/cases/{id}/gates/GATE_2_EXPORT/approve` once, sending every item on the Gate 2 checklist as reviewed (field names for UNSUPPORTED, `NEEDS_REVIEW:<id>` and `UNANSWERED:<id>` keys otherwise, the same shape the confirm dialog sends), then refreshes the summary and gates. If the gate is already approved (a second evaluator) it just moves on; if the approve call fails it asks `GET /gates/GATE_2_EXPORT` again and moves on when the gate turned out approved, else it stays on the step and shows the server's message, and Next tries again. A double press never sends two approvals.
- **Keyboard**: the bar is a labelled region, focus starts on Next, Right arrow or Enter = Next, Left arrow = Back, Escape = leave the demo. The keys act only when focus is on the page or inside the bar, never while typing in a field or with a dialog open; Enter on a focused button presses that button.
- **Language**: every interface string of the bar and the list is wrapped in `t()` and translated in `hi.json` (28 new strings, Gemma on the Gemini free tier with `scripts/translate_ui_hi.py`, as for the rest of the interface). The recorded text has its own optional Hindi, see "Hindi tours" below; the fold control below lg reuses the existing strings "Hide" and "Read".
- **Toasts** (`components/ui/toast.tsx`) sit bottom-left, away from the primary buttons at the right end of a step's footer, with the 200 ms rise-in fade. While a tour runs, the bar sets `--tour-bar-h` and `html[data-tour]`: from lg up the toast stays above the bar; below lg it moves to the top of the screen (it would span the whole width and cover the step's footer otherwise). Checked by `tour.spec.ts` (bounding boxes against the export button, its link, Next and the bar, at 1440x900 and 390x844).
- **Below 1024 px** the bar stays in the page flow under the step (never over it), at most 42% of the screen height; the filled list scrolls inside it. A "Hide" / "Read" control (`tour-fold`, `aria-expanded`) folds it to the title, progress and the three buttons. Exit, Back, Next, the fold control and the demo's start button are at least 44 px high; nothing scrolls sideways at 768 or 390 px (`tour.spec.ts`).

- **Read-only** (`lib/tourMode.ts`): while `?tour=<slug>` is on a case page the recorded case is shared by every evaluator, so the workspace cannot change it. The tour bar says "This is a recorded demo; fields are read-only." First layer: `useTourMode()` disables the Edit/Add and "Mark unknown" buttons of Review facts, the date edit, the Reword/Accept/Resolve controls of the grounds and objections, the drop zone, both file inputs, dictation and "Upload audio", the chat box, Send, attach and dictation, and the "Draft the grounds" button (the title of a disabled button carries the note). Second layer: `refuseInTour` in `lib/api.ts` (inside `http` and, through the third argument of `call`, in the in-browser demo backend too) throws an `ApiError` 423 with a plain message ("This is a recorded demo, so this change was not made. Exit the demo to work on a case of your own.") for every POST, PUT, PATCH and DELETE except `POST /api/cases/{id}/gates/GATE_2_EXPORT/approve` (the tour's Next on the GATE_2 step) and `POST /api/cases/{id}/export` (the export button on the FILE step). The tour itself makes no other write (no consent call). The message reaches the page through the workspace's error banner (`actionError`). Outside a tour nothing is blocked. `WorkspaceShell` keeps the flag in step with the URL; `isTourMode()` also reads the URL, so the guard works before any component mounted. New writes added to `lib/api.ts` must pass `{ method, path }` as the last argument of `call`.
- **One primary button**: in tour mode the tour's Next is the only maroon button. The step footer's own button ("Continue to Draft grounds" and the like, "Export as Word file") and the top bar's New case are drawn secondary, and Send in the chat is disabled and secondary. The gate buttons ("Confirm facts and continue", "Approve this draft for export") are not drawn; a line says "In this demo, Next approves the draft for export." (Gate 1: "...Next moves on; counsel confirmed these facts when the case was recorded."). The new strings are English only until `scripts/translate_ui_hi.py` is run (the interface falls back to English).
- **Workspace header** (not only in tours): below 1024 px the six steps are one control, "Step k of 6: <name>", that opens the list (44 px rows, `nav` "Case steps", the states still read as words, arrows and Escape work, choosing a step closes it); from 1024 px the row of steps is as before. The search box shows from lg; below lg it is an icon button (Ctrl K still opens the palette). The breadcrumb truncates inside its box and "Stage: ..." shows from xl (the step control says it below). Walked at 390, 768, 820, 1024, 1280 and 1440 px in `e2e/header_layout.spec.ts`; set `E2E_HEADER_SHOTS=<dir>` to write the header on every step.

### Hindi tours (recorded text)
- Contract (optional, backward compatible; `Tour`, `TourStep` in `demo/preload.py`, `docs/api/openapi.json` regenerated): `hi` on the tour `{title, story, variant{offence,custody,record,parity}, src}` and on each step `{title, caption, filled[{label,value}], src}`. `src` maps each field (`title`, `caption`, `variant.offence`, `filled.0.label`) to a hash of the English it was made from. A tour without `hi` is served as before (`"hi": null`).
- Frontend: `lib/tour.ts` parses `hi` (`localizedTour`, `localizedStep`); `TourBar` and `GuidedDemos` show the Hindi when the interface language is Hindi, field by field, with the English where a field has none. Vitest: `tests/unit/tourLang.test.tsx`.
- `scripts/demo/translate_tours_hi.py` fills `hi` through the repo's hosted client (Gemma on the Gemini free tier, data class PUBLIC under `public_scope`, the same gate as `scripts/translate_ui_hi.py`; the demo text is invented, role pseudonyms only). It keeps numbers, section references, role pseudonyms, PS and case numbers, file names, stage terms, Rights Radar statuses and every other upper-case abbreviation as written, rejects an answer that loses one or changes a digit (3 tries, then the field stays English), skips text whose English hash is unchanged, copies text with nothing to translate (file names, keys such as `UNANSWERED:O7`), and saves after every request. `--dry-run` lists strings and requests and writes nothing; `--check` exits 1 for missing or stale Hindi. Tests: `tests/unit/scripts/test_translate_tours_hi.py` (fake translator).
- State on 15 Nov 2026 (after the final recording): Hindi is in all six tours, 1,031 of 1,040 strings (the rest are copies of text with nothing to translate). Gemma on the Gemini free tier (`gemma-4-31b-it`, then `gemma-4-26b-a4b-it`) only returned `ReadTimeout` for about 40 minutes, so the run used `--model gemini-3.5-flash-lite` (same free tier, public synthetic text only): `--batch 10`, then two passes of `--batch 5` and `--batch 1` over what failed. `--check` still exits 1 for 9 texts (3 distinct): the step title "Rights Radar" in four tours and the label `fir` (a field key) never came back in Devanagari, and one ground value starting "SUPPORTED:" lost its status word in three tries; the interface shows the English for them. 20 captions were read: numbers, section references (BNS, NDPS, s.479), role pseudonyms and status words kept; "Gate 2" is rendered "GATE_2" in some captions; "counsel" is rendered both "अधिवक्ता" and left as the English word for stage terms. Rerun after any re-recording: `set -a; . ./.env; set +a; VS_MODELS=auto VS_GEMINI=public .venv/bin/python scripts/demo/translate_tours_hi.py` (add `--model gemini-3.5-flash-lite` when Gemma times out), then `--check`; it resumes from what is saved.

### Files
- `frontend/lib/tour.ts`: types, the parser for `GET /api/demo/tours[/slug]` (steps sorted into INTAKE ... FILE order, unknown stages dropped, the approve action allowed on GATE_2 only), the stage map, and the step machine (`createTourMachine`: bounds, the single-flight Gate 2 action).
- `frontend/lib/api.ts`: `listTours()` (404 -> `[]`) and `getTour(slug)` (404 -> `null`).
- `frontend/components/tour/GuidedDemos.tsx` (in `components/cases/CauseList.tsx`) and `frontend/components/tour/TourBar.tsx` (in `components/workspace/WorkspaceShell.tsx` when `?tour=` is present).
- Demo build (`NEXT_PUBLIC_API_MODE=demo`, or `auto` with the API unreachable): `frontend/lib/mock/tours.ts` serves one tour, `00-sample-cheating-parity`, over the sample case-0007 through `lib/mock/server.ts` (`listTours`, `getTour`). The sample case is at Gate 1 approved and Gate 2 open, so the tour's Gate 2 step really approves it in the browser's demo state (sessionStorage; a new tab starts fresh).
- `frontend/e2e/mockBackend.ts` answers `/api/demo/tours` with `[]` (and 404 for a slug), so the other specs see a server with demos off.

### Tests
- Vitest: `tests/unit/tour.test.ts` (parser, order, bounds, Gate 2 once, already approved, approval refused then retried, approved by someone else meanwhile), `tests/unit/tourApi.test.ts` (routes, 404 handling, the demo build's tour), `tests/unit/tourUi.test.tsx` (the list, the bar walking all nine steps, Gate 2 once with the right keys, unknown slug, wrong case, keyboard).
- Playwright: `e2e/tour.spec.ts`, offline (aborts `localhost:8000`, so the client falls back to the demo backend): starts from the cases page, presses only Next through all nine steps, checks the stepper at each, ends at Export with the draft approved and downloads the Word file link; axe on the cases page, the Review facts step and Export; keyboard and Escape; unknown slug.
- `e2e/tour.spec.ts` also holds the toast check (1440x900, 390x844) and the layout walks at 768x1024 and 390x844.
- Run: `cd frontend && E2E_PORT=3030 npx playwright test e2e/tour.spec.ts --project=chromium` (any free port; Playwright reuses whatever answers on it).
- `tests/unit/tourMode.test.ts` (Vitest): which calls the guard lets through, 423 and no request for every other write (live and in the demo backend), nothing blocked outside a tour. `e2e/tour_readonly.spec.ts`: controls disabled, a forced click or typing sends no request. `e2e/tour_one_primary.spec.ts`: exactly one visible maroon button, `tour-next`, at each of the nine steps at 1440x900 and 390x844. Both run against `next dev` or a `NEXT_PUBLIC_API_MODE=demo` build.

### Also changed here
- `ink-muted` darkened from `#675D54` to `#615850` (6.4:1 on canvas, 6.9:1 on white, 5.85:1 on parchment-deep, 5.2:1 on the hairline colour), DESIGN.md table updated. The reported 4.32:1 failure (6 muted nodes and the Gaps tab count on Review facts) did not reproduce here (dev and production demo builds, 1x to 8x CPU throttling, Hindi on); the measurement looks like a frame of the 200 ms step fade, so `e2e/helpers.ts` `seriousAxeViolations` now waits (up to 2 s) for running finite animations to end before axe runs, and the darker token gives the muted text more headroom.

### Not done / next steps
- Not checked against the backend agent's real tour files yet; the parser is defensive (unknown stages and agents ignored, missing tabs defaulted) but the field names must match the API described above.
