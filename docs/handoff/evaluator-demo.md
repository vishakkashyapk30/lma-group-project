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

Re-recorded 15 Nov 2026 (third recording of that day, with the interleaved sparring step and a 200000-token reserve; the history is under "What changed since the first recording"). What each recorded run
produced (numbers from `demo/cases/<slug>/tour.json`; rights statuses are the Rights Radar as of 2026-11-15; "withheld" is sentences the claim checker
could not support; "spend" is Sarvam INR for that case; sparring: objections raised, how many got a reply that Abhiyojak judged (ANSWERED / PARTLY / UNANSWERED), and how many were left
for counsel as NOT_REPLIED_BUDGET because the sparring reserve could not cover another reply):

| Case | Law and file | Rights Radar | Brief (grounds, withheld) | Sparring | Spend |
|---|---|---|---|---|---|
| 01 cheating, parity | IPC 420/406, 11 born-digital PDFs, co-accused on bail | default bail WINDOW_CLOSED, s.479 NOT_YET (978 days in custody; the radar applies the half threshold, 1,278 days), Antil CHECK | 8 drafted, 8 supported; 15 withheld; 1 left to counsel | 16 raised; 5 replied and judged (0 / 3 / 2); 11 not replied (budget) | 5.58 |
| 02 theft, default bail | BNS 303(2), 8 PDFs, no charge sheet | default bail ELIGIBLE (day 96), s.479 NOT_YET, Antil A | 3 drafted, 3 supported; 8 withheld; 3 left | 7 raised; 7 replied and judged (2 / 4 / 1); 0 not replied | 3.97 |
| 03 NDPS small, Hindi | NDPS 21(a), Hindi FIR plus 8 English PDFs, grounds of arrest oral | default bail WINDOW_CLOSED (day 54 of 60), s.479 ELIGIBLE (136 days against 122), Antil C | 4 drafted, 4 supported; 18 withheld; 4 left | 9 raised; 9 replied and judged (2 / 4 / 3); 0 not replied | 8.42 |
| 04 NDPS commercial, scanned | NDPS 21(c)/29, one image-only page read by OCR | default bail WINDOW_CLOSED, s.479 CHECK (the charge names no clause), s.37 BAR_APPLIES, Antil C | 5 drafted, 5 supported; 11 withheld; 4 left | 12 raised; 11 replied and judged (2 / 5 / 4); 1 not replied (one judge call also failed) | 6.28 |
| 05 attempt to murder, parity | BNS 109 with 3(5), 11 PDFs with the medico-legal report | default bail WINDOW_CLOSED (90-day limit, maximum death, day 81), s.479 NOT_APPLICABLE (death), Antil B | 6 drafted, 6 supported; 13 withheld; 1 left | 14 raised; 12 replied and judged (2 / 5 / 5); 2 not replied (budget) | 5.85 |
| 06 breach of trust, missing papers | BNS 316(2), 4 PDFs only; intake asked 6 questions | default bail NOT_YET (day 41), s.479 CHECK (antecedents unknown), Antil CHECK | 4 drafted (2 repaired, 2 supported); 7 withheld; 2 left | 10 raised; 9 replied and judged (1 / 3 / 5); 1 not replied | 6.57 |

In all, 68 objections raised, 53 replied and judged (9 ANSWERED, 24 PARTLY, 20 UNANSWERED) and 15 left for counsel. An objection left for counsel carries the verdict UNANSWERED with a reason starting `NOT_REPLIED_BUDGET:`; the tour's SPAR caption states the counts for each case.

Gate 2 checklist sizes: 14, 3, 5, 6, 9, 8 items (unsupported fields plus unanswered objections). The six differ in law (IPC, BNS, NDPS
small and commercial), custody (default bail open, closed, not yet open, s.37 bar), record quality (complete, Hindi, scanned, four
papers only) and parity (co-accused granted, refused, none).

#### What changed since the first recording (14 Nov to 15 Nov 2026)
- Rights Radar: the maximum punishment is found for BNS 109 with 3(5) and NDPS 21(a), so cases 03 and 05 now show real statuses (default bail WINDOW_CLOSED,
  s.479 ELIGIBLE in 03 and NOT_APPLICABLE in 05) instead of CHECK for a missing maximum; the story and variant lines of 01, 03, 04, 05, 06 in `demo/cases.py` were rewritten to match.
- Sparring step, three recordings the same day. (1) First recording, 14 Nov, no reserve: 41 objections, 1 judged. (2) Reserve 60000 and then 120000 (judging last, after every reply):
  55 raised and 7 judged at 60000; 67 raised and 8 judged at 120000 (59 never judged; the raise cost about 40K and every reply about 7K, so the pool was empty when judging started).
  (3) Final: the judge runs right after each reply is drafted, an objection the reserve cannot cover becomes NOT_REPLIED_BUDGET with a plain reason, and the product reserve is 200000
  (`PRODUCT_SPARRING_RESERVE_TOKENS`): 68 raised, 53 replied and judged, 15 left for counsel. Check on the record: `round_2` event with `"interleaved": true` (the Sutradhar peer path the API
  uses took the interleaved route in all six cases), `not_replied_budget` events, and one `sparring_reserve` event per case (case 05: 197,679 of 200,000 spent; case 01: 178,017, the 11 left
  over each needed an estimated 26K against 22K left; case 05 needed 13K against 2K).
- The SPAR caption now states what happened in the run: objections raised, how many got a reply that Abhiyojak judged, the verdict counts, how many were left for counsel because the sparring token budget ran out, and that counsel answers what stays open before Gate 2 (`record_demos.py`, `build_tour`).
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
Third recording, 15 Nov 2026 (the final one): the owner's Sarvam key (`sarvam-105b`), capped at INR 300 for the recording (`VS_SARVAM_CAP_INR=300`, a scratch data dir with its own ledger). Per-case spend, from
the ledger: 01 5.58, 02 3.97, 03 8.42, 04 6.28, 05 5.85, 06 6.57 INR, which is 36.67 INR for the six recorded runs (85 to 139 hosted calls each; the ledger of the whole recording, 666 calls, sums to 33.72 INR because
runs overlapped in time). Earlier recordings of the same day, replaced: 60000 reserve about INR 30, 120000 reserve about INR 32, plus one aborted run; the first recording (14 Nov) cost 20.12 INR. Case runs took 15 to 27 minutes
each (two recorder processes at once). The backend checks (pre-loading, export) made no model call; they ran with `VS_MODELS=offline`. Hindi captions: Gemini free tier, no cost.

### Known limits seen while recording (product, not the demo)
- **Sparring is budget-limited, no longer starved.** With the 200000-token reserve and the interleaved judge, 53 of 68 objections got a judged reply. Cases with 14 and 16 objections still leave some for counsel
  (05: 2, 01: 11, because the reserve check estimates a worst case of 26K for a reply, repair and judge (22K was left in case 01) and the 16 objections need more than 200K); the Gate 2 list carries them and the tour approves with acknowledgements.
  The verdict mix is mostly PARTLY and UNANSWERED: 9 answered, 24 partly, 20 unanswered. A raise of the reserve (to about 250K) or fewer objections per case would remove the leftovers.
- The Rights Radar fixes of 15 Nov show in the new recordings: case 03 default bail WINDOW_CLOSED and s.479 ELIGIBLE (maximum 1 year read from NDPS 21(a)),
  case 05 default bail WINDOW_CLOSED on a 90-day limit and s.479 NOT_APPLICABLE (maximum death for BNS 109 with 3(5); BNS 109's own maximum is not death in the
  statute for every clause, the radar takes the highest). Still CHECK for s.479 in case 04 (NDPS 21(c)/29: the charge names no clause, so the radar has no
  maximum) and case 06 (antecedents unknown). No `rights_check_failed` event in any of the six recordings.
- Case 03's "Notice of appearance" row reads "Offence punishable up to 7 years" although NDPS 21(a) has a maximum of one year. Not a bug in the input path: the rule reads the same maximum as the other rules (1 year, from the section text);
  "up to 7 years" is the rule's own wording for its band (seven years or less), and a one-year offence is inside it. The case 03 tour text says so (variant, custody line).
- Case 01's s.479 now shows NOT_YET (978 days in custody; the radar applied the half threshold of 1,278 days, not the one-third threshold of 852 for a first-time offender); in the 14 Nov and the first 15 Nov recordings it showed ELIGIBLE. The dossier, antecedents "none (verified)", is the same; the tour text states the NOT_YET result as recorded.
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
- State on 15 Nov 2026 (after the final recording): Hindi is in all six tours and `--check` passes ("all Hindi texts are current in 6 tours"; 1,010 strings, 131 copied unchanged, the rest translated). Gemma on the Gemini free tier timed out all morning (`ReadTimeout` on `gemma-4-31b-it` and `gemma-4-26b-a4b-it`), so the run used `--model gemini-3.5-flash-lite` (same free tier, public synthetic text only): `--batch 10`, then passes of `--batch 5`, `3`, `2` over what failed. Three kinds of text used to fail and are now handled by design, with tests: (1) `ENGLISH_BY_DESIGN` ("Rights Radar", the tab name) and dossier field keys such as `fir` or `previous_bail` (`FIELD_KEY`) are copied, never sent to the model, and `--check` accepts them; (2) a value that starts with a status word or an id ("SUPPORTED: ...", "G4 · antecedents") is split by `split_prefix`, so the model sees only the sentence and the prefix is put back as written. About 20 captions were read: numbers, section references, role pseudonyms and status words kept; some stage terms stay English ("Gate 2", "List of Dates", "counsel" in one caption). Rerun after any re-recording: `set -a; . ./.env; set +a; VS_MODELS=auto VS_GEMINI=public .venv/bin/python scripts/demo/translate_tours_hi.py` (add `--model gemini-3.5-flash-lite --batch 5` when Gemma times out), then `--check`; it resumes from what is saved.

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
