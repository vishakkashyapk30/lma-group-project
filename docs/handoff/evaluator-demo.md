# Evaluator demo

## Backend: recorded cases and pre-loading

(handoff, backend half)

Written 14 Nov 2026. An evaluator opens the site and finds six demo cases already loaded. Each has a tour: nine steps (INTAKE, DOSSIER,
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

What each recorded run produced (numbers from `demo/cases/<slug>/tour.json`; rights statuses are the Rights Radar as of 2026-11-14;
"withheld" is sentences the claim checker could not support; "spend" is Sarvam INR for that case):

| Case | Law and file | Rights Radar | Brief (grounds, withheld) | Sparring | Spend |
|---|---|---|---|---|---|
| 01 cheating, parity | IPC 420/406, 11 born-digital PDFs, co-accused on bail | default bail WINDOW_CLOSED, s.479 ELIGIBLE (977 days), Antil CHECK | 6 drafted, 6 supported; 14 withheld; 3 grounds left to counsel | 7 objections, 7 unanswered | 3.63 |
| 02 theft, default bail | BNS 303(2), 8 PDFs, no charge sheet | default bail ELIGIBLE (day 95), s.479 NOT_YET, Antil A | 3 drafted, 3 supported; 13 withheld; 3 left | 3 objections, 3 unanswered | 3.01 |
| 03 NDPS small, Hindi | NDPS 21(a), Hindi FIR plus 8 English PDFs, grounds of arrest oral | default bail CHECK, s.479 CHECK, Antil C | 3 drafted (1 repaired, 2 supported); 13 withheld; 4 left | 6 objections, 6 unanswered | 3.51 |
| 04 NDPS commercial, scanned | NDPS 21(c)/29, one image-only page read by OCR | default bail WINDOW_CLOSED, s.37 BAR_APPLIES, Antil C | 8 drafted, 8 supported; 10 withheld; 1 left | 6 objections, 6 unanswered | 3.57 |
| 05 attempt to murder, parity | BNS 109 with 3(5), 11 PDFs with the medico-legal report | default bail CHECK, s.479 CHECK, Antil CHECK | 7 drafted (1 repaired, 6 supported); 12 withheld; 1 left | 9 objections, 9 unanswered | 3.48 |
| 06 breach of trust, missing papers | BNS 316(2), 4 PDFs only; intake asked 6 questions | default bail NOT_YET, s.479 CHECK, Antil CHECK | 5 drafted, 5 supported; 6 withheld; 1 left | 10 objections, 10 unanswered | 2.92 |

Gate 2 checklist sizes: 7, 6, 7, 6, 9, 13 items (unsupported fields plus unanswered objections). The six differ in law (IPC, BNS, NDPS
small and commercial), custody (default bail open, closed, not yet open, s.37 bar), record quality (complete, Hindi, scanned, four
papers only) and parity (co-accused granted, refused, none).

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
All six recordings used the owner's Sarvam key (`sarvam-105b`), capped at INR 300 for the recording (`VS_SARVAM_CAP_INR=300`).
Per-case spend, from the recording ledger: 01 3.63, 02 3.01, 03 3.51, 04 3.57, 05 3.48, 06 2.92 INR, which is 20.12 INR for the six
recorded runs. The ledger of the whole recording (410 rows, including earlier test calls with no case id, 2.95 INR) sums to 23.07 INR.
The backend checks (pre-loading, export) made no model call; they ran with `VS_MODELS=offline`.

### Known limits seen while recording (product, not the demo)
- Gate 2 always lists unanswered objections: in all six recordings Vakeel's replies left every objection unanswered, so the tour
  approves with acknowledgements (this is what the checker could support, not a recorder fault).
- The Rights Radar leaves default bail and s.479 at CHECK where the dossier lacks a computed date (cases 03 and 05); the tour reports
  the status as recorded.
- Day counts in the case descriptions follow the Rights Radar (day 1 is the first remand): cases 01, 03, 04, 05 charge sheets on days
  55, 54, 167 and 81.
- The exported DOCX files carry the locality "Karol Bagh" (case 01), an address that is part of the synthetic file, not a person's name.
