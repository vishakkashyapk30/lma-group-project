# Status — Harshita

## 14 Nov 2026: items 2 and 3 done
- **Item 2, live end to end: done.** `frontend/e2e/live_flow.spec.ts` with `E2E_LIVE_API=1` against `docker compose up -d --build` on `main` at 74c6b06 (after `./install.sh` seeded the data volume): passed 3 times in a row (about 17 s each), through export and the application download. Found and fixed on the way: `.docx` was served as `application/octet-stream` (explicit media types in `api/routers/export.py`, test added), and the Docker build failed on a bare apostrophe in `AboutPage.tsx`. One earlier run on the freshly rebuilt backend got a 500 on the draft call (39.7 s in); it did not repeat, the backend logged no traceback, and calling the draft endpoint directly gave 200. Cause not found; if it shows again, check the first draft after a rebuild. Run guide: `docs/handoff/run-and-live-test.md`. Playwright reuses whatever answers on the port: stop Docker or set `E2E_PORT` when running the mocked specs.
- **Item 3, Hindi interface labels: done as a first pass (PR #11, merged).** Translated with Gemma (`gemma-4-31b-it`) on the Gemini free tier through the repo's client, not Sarvam: the strings are public interface text, nothing was paid and the paid lock was not touched. 300 strings, none reviewed by hand (`hi.meta.json`). Language toggle in the top bar, choice saved, `<html lang>` set; shell, stepper, status badges, every step's title, intro and footer button, and the gate list are translated. Not done: text inside the tabs, the cases, library, desk, settings, help and about pages, and sentences with counts. How it works, how to regenerate and the limits: `docs/handoff/hindi-labels.md`.
- **Also merged:** PR #10 (gaps by factor, objections grouped by ground, brief read by sentence; the objections test reconciled with a RECONCILED note) and PR #9 (run guide).
- **Still open:** a person's look in a browser at the Hindi toggle and the Draft grounds step; the AC-0 to AC-7 walk-through with Shravani. The axe colour-contrast check fails on `main` (muted text colour, Satvik's design-token call).

## 13 Nov 2026: machine-checkable frontend items run (by a session on Vishak's request)
What was run, in a fresh worktree of `arch-report` (2953422), offline models, own data dir, ports 8010 and 3010 only:
- `npm ci`: done (about 10 minutes; it stalled on the optional `canvas` native download, a peer of `jsdom`, which is not needed; the stalled download was killed and npm finished without it). `motion` is installed; `npx tsc --noEmit`: clean.
- Vitest, whole suite: 19 files, 319 tests, all passed. (Run with at most 4 workers; with 16 workers under a 4 GB memory cap the workers were killed.)
- Playwright, non-live specs (both projects, mocked backend): 167 passed, 1 skipped (the live spec). No code change was needed.
- Production build: `next build` failed on a lint error (`react/no-unescaped-entities`, `components/about/AboutPage.tsx` line 140, a bare apostrophe). Fixed with `&apos;` (rendered text unchanged); build then passed.
- Live end to end: `frontend/e2e/live_flow.spec.ts` with `E2E_LIVE_API=1` against the production build and a backend from this tree: passed (1.5 to 2.1 min): upload, facts, Gate 1, rights, draft, resolve, hearing card, Gate 2, export, download of the application. The spec reads the bundle from `E2E_LIVE_PDF` when the worktree has no `data/` (the default path is `<checkout>/data/testsets/t2/bundles/t1-003_K1.pdf`); it now also reads `E2E_LIVE_API_BASE` (default http://localhost:8000).
- Withheld-sentence view, in a real browser against the live offline case: the offline draft does withhold sentences (7 grounds, 4 with one withheld sentence each: G1, G3, G4, G7; reasons such as "could not be checked", "the cited paragraph does not say this"). Each ground shows a closed "Removed from the argument (1 sentence)" line; opening it lists the sentence and its reason in plain words. No console errors or page errors. A style probe over the withheld subtree found no gradients, shadows, uppercase or letter-spaced labels, no animation, and no transition over 300 ms; there is no dot or pill. "Grounds left for you to draft" did not appear in this case (no ground lost every sentence); it is covered by `frontend/tests/unit/withheld.test.tsx` and the demo case. New assertion in the live spec: the number of lists under grounds and of left-for-counsel grounds equals what the API's `withheld` reports, the list is closed until opened, and opening it shows every sentence.
- Seen in the offline output, not a frontend defect: one withheld reason reads "(payload is not safe to send to Ada: args.claim: un-pseudonymised personal name)" in the API; the screen drops the bracket and shows "Could not be checked." One withheld sentence is cut mid-sentence ("... cannot be a decisive") because the offline extractor truncates it.

Still for Harshita:
- A person's look in a browser (judgement on spacing, wording and the feel of the Draft grounds step; the checks above are automated).
- Hindi interface labels. There is no i18n mechanism: `<html lang="en">` is fixed in `app/layout.tsx`, no dictionary, no language switch. Only the Hindi text of documents is handled (`lang="hi"` on quoted text, Devanagari fonts and `.hindi-body` classes in `app/globals.css`). Rough size (a regex count over `app/`, `components/`, `lib/`, mock data excluded): about 540 distinct interface strings, about 2,600 words, in 127 files; the biggest blocks are `lib/labels.ts` (78), the landing page, the Brief tab and the settings, trace, help and about pages. Plan without a framework: a flat `lib/i18n/hi.ts` dictionary keyed by the English string, a `t()` helper and a `lang` value in the shell context (stored in `localStorage`, also set on `document.documentElement.lang`), a language switch in Settings, and `t()` wrapped around the strings. Translate with Sarvam only the public interface strings (never case text, drafted sentences or quotes), one batch call, after the owner unlocks the paid lock. Keep statute and case names and "Gate 1/2" untranslated. Needs the Devanagari font stack already in place. No paid call was made in this session.

## Current assignment (13 Nov 2026)
- **Item 1 done by Vishak on 13 Nov (commit bc2709e):** what c1457 withholds, per ground, and every Abhiyojak objection in the workspace.
  - Backend: `GET /api/cases/{id}/brief` adds `withheld: [{ground, factor, sentences: [{sentence, reason}], dropped}]`, folded from Vakeel's X4 `abstain` events (only the latest draft of each ground counts; replies are skipped). API-only: the stored brief, the export and the export hash are unchanged. `src/vakeel_sahayak/api/{models,service}.py`, `api/routers/cases.py`, `docs/api/openapi.json` regenerated.
  - Frontend: under each ground a closed "Removed from the argument (n sentences)" list, each sentence with its reason in plain words (`frontend/lib/withheld.ts`: "not supported by the record", "the record is silent on trial delay", ...; scores dropped); a "Grounds left for you to draft" section for grounds that lost every sentence (`components/workspace/tabs/Withheld.tsx`). "Likely objections" lists every objection whatever its verdict and its summary now also counts "not judged yet". Demo case-0007 has sample withheld sentences (G1, G5, and G8 dropped).
  - Tests: `tests/unit/api/test_brief_withheld.py` (4), `frontend/tests/unit/withheld.test.tsx` (11), `frontend/tests/unit/objections.test.tsx` (3), all passing.
- **Done by Harshita on 14 Nov (see above):** item 2, the live end-to-end run (`frontend/e2e/live_flow.spec.ts` with `E2E_LIVE_API=1` against `docker compose up` on `main`, plus Vitest and Playwright; fix what breaks); item 3, Hindi interface labels (done with Gemma instead of Sarvam, first pass). The Gemini open-slice shard is dropped.
Full list: `docs/handoff/team-todo-2026-11-02.md`, section "What each person does next (13 November)".

## Earlier assignment (2 Nov 2026, to the freeze on 10 Nov)
Swapped with Satvik on 2 Nov. Frontend of the chosen architecture, live end-to-end tests, a Gemini key in the pool and a shard of the 5 to 7 Nov Gemini runs, Hindi labels translated with Sarvam and wired in (no review by hand).
Full list, dates and rules: `docs/handoff/team-todo-2026-11-02.md`. The tables below are the earlier state.

Assigned (owner's day-1 message §7): **metrics & statistics, the statutes, the Rights Radar verification, and the proposal PDF + README/QA docs.**

## Metrics & statistics  ← DONE (implemented 2026-10-26)
The code with failing unit tests encoding the spec. All of `tests/unit/eval/test_metrics.py` + `test_stats.py` now pass (**52 passed**, was 52 failed). `ruff` clean.

- **Statistics** (`eval/stats/`): `holm_bonferroni` (step-down, pure Python), `paired_bootstrap_ci` (seeded percentile CI, numpy), `wilcoxon_signed_rank` (scipy exact, 1.0 when all diffs zero).
- **Metrics** (`eval/metrics/`): `recall_at_k` + `slot_fill_rate` (retrieval), `factor_recall_precision` (answerable-only), `character_error_rate` (Levenshtein) + `boundary_f1` + `field_accuracy` (ingestion), `pass_hat_k` + `stale_claim_rate` (agentic), `map_section_accuracy` + `tool_call_accuracy` (tool-calling), `rights_accuracy` (rights), `export_violations` + `injection_success_rate` + `refusal_rate` + `leak_rate` (safety), `average_over_runs` (stats_helpers).
- **Dependency:** installed `numpy` + `scipy` into `.venv` (the full `.[eval]` extra pulls minicheck→torch, too heavy for this disk; only numpy/scipy are needed for the stats).
- **Left as a stub (outdated, Checked by Vishak 2026-10-27: it was implemented afterwards, see `docs/handoff/regression-2026-10-26-b.md`):** `eval/metrics/unsupported_fact.py` — no test references it, so not implemented (implementing untested code risks the wrong spec).

### HA-01 completed (2026-10-27, Harshita)
- Vishak's 2026-10-27 commit `f114bca` added the unsupported-fact rate, `validate_checker` and the ingestion helpers (`by_kind`, `escalation_rate`, `questions_asked`); his versions are kept.
- **Added here:** `mean_reciprocal_rank` and `ndcg_at_k` in `eval/metrics/retrieval.py` (document-level like `recall_at_k`; tests in `tests/unit/eval/test_ranking_metrics.py`), and the **null-agent audit** of plan 5.7 as a unit test (`tests/unit/eval/test_null_agent_audit.py`: empty brief, copy-the-facts, copy-the-checklist, argue-all-twelve, random citations, export without approval).
- **Audit finding (xfail, strict):** `unsupported_fact_rate` returns 0.0 for a brief with no sentences; plan 5.7 says "no claims", not 0. For Vishak; the test flips when it is fixed.
- **McNemar:** in Vishak's `eval/scoring/stats_extra.py` (`mcnemar_exact`); not duplicated into `eval/stats/`.
- Not covered: the all-stores-removed abstention check (needs a real run).
- Tests: `test_metrics`, `test_stats`, `test_null_agent_audit`, `test_ranking_metrics`: 62 passed, 1 xfailed; `ruff check src` clean.
- **Open for Vishak:** `tool_call_accuracy.args_valid` requires an exact match to gold args (plan says "argument validity"); `false_eligible_rate` divides by all checks; empty-input conventions (recall/precision 1.0, slot fill 0.0); MiniCheck threshold to fix on dev.

## Still to do (not yet started)
- **Statutes (HA-02):** the extraction was done by Vishak on 2026-10-26 (`scripts/extract_gap_statutes.py`, from official government PDFs; rows in the team data bundle under `data/gaps/statutes/`; see `data/README.md` "Gap-filling status"). Still missing (listed there): BNS/BNSS First Schedule flags, UAPA 43D(5) / PMLA 45 / BNS 318(4) text.

### HA-02 review (2026-10-27, Harshita)
- Installed the bundle (`RAW=0 make data-install`). Fixed `scripts/data_install.sh`: `sed -i` without a suffix fails on macOS (Vishak to review). The install's sanity check reports `gaps/: 14 files, manifest says 15` (about 4.6 KB missing, not one of the statute files); asked Vishak which file.
- **Rows load:** `StatuteStore().open()` returns all 10 CrPC sections (41, 41A, 50, 57, 167, 436, 436A, 437, 438, 439) and NDPS 19, 24, 27A, 31A, 37; IPC 352/533 rows carry First Schedule flags. Spot checks right: IPC 302, 379, 420 and NDPS 37 cognisable and non-bailable.
- **Tests:** `tests/unit/stores` + `tests/unit/tools_law_case` 221 passed.
- **Text vs PDF:** every row has `source_url` and `retrieved`; 85-100% of each row's 8-word windows occur verbatim in `pdftotext` of its source PDF. The misses are the script's documented edits (footnote markers such as `1[may, and shall,` in CrPC 436, joined lines and list items), not changed wording.
- **Rights Radar verification**: re-check the rule texts against the bare acts (review, not code).
- **Proposal PDF + README/QA docs**: writing.

*Note: this work was done by Shravani's session at the user's request; Harshita should review before it goes in under her task id.*
