# Harshita: metrics and statistics, legal content, data gaps, small UI items, QA and docs

Part of the team plan in `docs/team/README.md` (read sections 2 to 8 first). This file is the only place you update your own status. Do not edit `progress.md`.

Calendar: Day 1 (D1) is the Monday after the history sync; weeks are D1 to D5, D6 to D10, D11 to D15, D16 to D20. Effort is in person-days (estimates).

## 1. Role summary

Your share is deliberately about half of the others': well-scoped tasks with few dependencies and low risk, none on the critical path. Four groups:

1. **Metrics and statistics for the evaluation** (EV-02): pure functions with tests that already exist (`tests/unit/eval/test_stats.py` 16 tests, `tests/unit/eval/test_metrics.py` 27 tests). You make them pass and add the null-agent audit.
2. **Legal content and data gaps**: re-verify the seven Rights Radar rules (PR-46) and the cases cited from memory (PR-47); fetch the missing statutes (PR-28).
3. **Small UI items** in files you create or in hook-ins of at most 30 lines: the draft label and terms (PR-37), the strict demo guard (PR-45).
4. **QA and docs**: the browser check with a written fix list (PR-75), the manual QA script (PR-77), the README quick-start (PR-81); then a stretch queue of documents (proposal `.tex` and `.pdf`, `docs/plan.md` edits, FAQ, demo script).

Committed: **11.0 person-days** (W1 2.5, W2 2.5, W3 2.5, W4 3.5). That is about half of the three others (19.5 to 21.5). Capacity at your half-time rate: 8.75 days at 3.5 weeks, 10 at 4 weeks. Week 4 is heavier because the browser check can only happen once the API is live.

## 2. Owned paths

| Path | Notes |
|---|---|
| `src/vakeel_sahayak/eval/metrics/`, `src/vakeel_sahayak/eval/stats/` | EV-02 |
| `tests/unit/eval/test_metrics.py`, `tests/unit/eval/test_stats.py` | file-level carve-out inside Vishak's `tests/unit/eval/`; every edit to an existing test line needs `# RECONCILED: <reason>` and Vishak's review |
| `src/vakeel_sahayak/rights/`, `tests/unit/rights/` | the seven rules |
| `configs/rights_rules.yaml`, `configs/bail_sections.yaml` | per-file owner rule |
| `data/gaps/` (new directory: `statutes/`, `README.md`, fetch notes) | statute data that Vishak's builder reads |
| `docs/` except the files Vishak owns (`evaluation-plan.md`, `preregistration.md`, `product-readiness.md`, `literature-review-and-usage.md`) and except the other three people's files in `docs/team/` | includes `docs/plan.md`, `docs/proposal/`, `docs/architecture/`, new `docs/qa/` |
| `README.md` (repository root), `CHANGELOG.md` | |
| `frontend/components/landing/`, `components/about/`, `components/workspace/tabs/`, `components/legal/` (new), `components/onboarding/` (new), `app/about/`, `app/help/` (new), `app/welcome/` (new), `lib/i18n/` (new), `messages/` (new) | Satvik owns the rest of `frontend/` |

Hook-in rule: a feature that must appear inside a file of another owner lives in your own new component; the hook-in edit into the other owner's file is at most 30 changed lines and that owner reviews it.

## 3. Week-by-week tasks (committed)

Test names are the tests that must go green for the task. PR branch names are suggestions; the target day is the day of the squash merge.

### Week 1 (D1 to D5): 2.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| TM-05 | Request HLDC access on Hugging Face (evaluation decision E-D9); put the `bail` folder in `data/raw/hldc/` when it arrives | Request sent on D1 | none | none | no PR | 0 (under one hour) |
| EV-02 (part 1) | Statistics: bootstrap (10,000 resamples, seeded), Wilcoxon, Holm, McNemar (exact below 25 discordant pairs, asymptotic above), cluster bootstrap that keeps cases together | Textbook 2x2 tables give the textbook answers | `tests/unit/eval/test_stats.py` (16 existing tests plus new cases for McNemar and cluster bootstrap) | contract PR (output paths, D1) | `feat/eval-stats`, D3 | 1.5 |
| EV-02 (part 2) | Metrics, first group: factor recall, precision and F1 on answerable factors, unsupported-fact rate (MiniCheck with the verbatim-span check) | Deterministic metrics, no judge scores | `tests/unit/eval/test_metrics.py` (factor and grounding cases) | EV-02 part 1 not needed; metric definitions in evaluation plan section 4 | `feat/eval-metrics-factor-grounding`, D5 | 1.0 |

### Week 2 (D6 to D10): 2.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| EV-02 (part 3) | Metrics, second group: retrieval (recall@10 with coverage), agentic (tokens and store calls per case, cost per passed case, stopped-too-early and over-search), the null-agent audit as a parameterised test over every metric | An empty brief, a copied-facts brief and an "argue all twelve" brief score near zero on every metric that must reject them (factor precision, unsupported-fact, citation) | `tests/unit/eval/test_metrics.py` (all 27 plus one table-driven test per new metric plus the null-agent audit) | EV-02 parts 1 and 2 | `feat/eval-metrics-retrieval-agentic`, D8 | 0.5 |
| PR-28 | Fetch from India Code the CrPC 1973 sections 437 to 439 (and the sections that `bail_sections.yaml` names), NDPS section 37, and the CrPC and BNSS First Schedule rows for the bail offences (bailable, cognisable); write `data/gaps/statutes/*.jsonl` in the row format of `data/interim/statutes.jsonl`; fill the five TODO rows of `configs/bail_sections.yaml` | `get_statute("CrPC 439")` resolves and `bailable` is set for the ten bail sections once Vishak's builder reads `data/gaps/statutes/` (contract PR) | the statute-store and statute-tool tests under `tests/unit/stores` and `tests/unit/tools_law_case`, `tests/unit/pipelines/concordance/test_crpc_bnss_table.py` (edits marked `# RECONCILED: <reason>`) | contract PR (builder glob, D1) | `feat/data-statute-gaps`, D10 | 1.5 (scoped to the bail sections) |
| PR-45 (part 1) | Demo-mode guard: in a product build the UI never falls back silently to demo data; strict mode by default; visible banner and clear error | With the backend down the UI shows an error, not case-0007; demo is opt-in | Vitest (`frontend/tests/unit` api client tests), `npm run typecheck`, `npm run lint` | none; `frontend/lib/api.ts` is a shared file (Satvik reviews) | `feat/ui-demo-guard-strict`, D10 | 0.5 (of 1.0) |

### Week 3 (D11 to D15): 2.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-45 (part 2) | Compose and Docker build argument so the default stack is strict; keep an opt-in demo setting for the landing page and the e2e suite | `docker compose up` default is strict; `frontend/e2e` still passes on the demo setting | `npm run build && npm run e2e` | PR-45 part 1; `compose.yaml` is shared (Vishak reviews) | `feat/ui-demo-guard-compose`, D11 | 0.5 |
| PR-37 | "AI-generated draft. Not legal advice." label on every UI view of a brief and the first-run terms accepted once: new `components/legal/DraftLabel.tsx` and `TermsGate.tsx`; hook-ins of at most 30 lines into `RightPane.tsx` and `app/layout.tsx` (Satvik reviews); the exact text is the constant frozen in the contract PR; the export banner itself is built in PR-13 and PR-14 (Satvik) | The label is on every brief view; the terms dialog appears once per browser profile | Vitest, `npm run typecheck`, `frontend/e2e/workspace.spec.ts` | contract PR (label text), Satvik for the hook-in review | `feat/ui-draft-label-terms`, D13 | 1.0 |
| PR-47 | Verify the cases cited from memory (*Kapil Wadhawan*, *M. Ravindran*) and check every other case name in `configs/`, UI text, `frontend/lib/mock/*` and `tests/fixtures`; remove what cannot be checked | Every reference has a checked citation or is removed | `tests/unit/rights`, `tests/unit/config`, Vitest | none | `docs/verify-case-references`, D14 | 0.5 |
| PR-46 (part 1) | Re-verify the first four rules against the bare acts (default bail, undertrial limit, notice of appearance, grounds of arrest): source link, version and `last_verified` per rule | Each of the four has a verified source, version and date in `configs/rights_rules.yaml` | `tests/unit/rights` (all), `tests/unit/config` | none | `feat/rights-verify-1`, D15 | 0.5 (of 2.0) |

### Week 4 (D16 to D20): 3.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-46 (part 2) | Remaining three rules (production within 24 hours, Antil category, statutory bar); record the open legal readings with the choice made; if a rule cannot be verified it is switched off | All seven rules have source, version and date; no rule reads `last_verified: null` | `tests/unit/rights`, `tests/unit/config` | PR-46 part 1 | `feat/rights-verify-2`, D17 | 1.5 |
| PR-75 | A person uses the frontend in a browser with the real backend (`docker compose up`, strict guard): landing, cause list, upload, dossier, chat, brief, Gate 1 and Gate 2; the written fix list in `docs/qa/browser-check.md` with a severity per item | A list of visual and flow defects, each assigned to an owner; the list is delivered on D17 so Satvik and Shravani fix on D18 and D19 | none (the deliverable is the list); the Playwright suite still passes on the build you checked | PR-05 (Satvik, D10), PR-06 (Shravani, D13), PR-37, PR-45 | `docs/qa-browser-check`, D17 | 1.0 (scoped to one structured pass; the second pass is stretch) |
| PR-77 | Manual QA script of the 15 most important cases (install and restart, flow 1 with the 14-page bundle and an encrypted PDF, flow 2 with a prediction request, flow 3 with an open NEEDS_REVIEW, export before and after Gate 2, a POCSO upload, a planted instruction, Sarvam off, backend stopped mid-run) in `docs/qa/manual-qa.md`; each case has steps, expected result and a pass or fail box | A teammate who did not write the code can follow every case; the run on a clean machine is the v1.0 step | none | none (draft); PR-75 for the case list | `docs/qa-manual-script`, D18 | 0.5 |
| PR-81 | README quick-start: clone, `make hooks`, start the stack, the three-step manual install (Vishak's notes in `DOCKER.md`), how to run the tests per area | Shravani follows it on a clean clone and reaches the UI | none | PR-21 install steps in `DOCKER.md` (Vishak, D14) | `docs/readme-quickstart`, D18 | 0.5 |

Total committed: 2.5 + 2.5 + 2.5 + 3.5 = **11.0**. Per task: EV-02 3.0, PR-28 1.5, PR-45 1.0, PR-37 1.0, PR-47 0.5, PR-46 2.0, PR-75 1.0, PR-77 0.5, PR-81 0.5, TM-05 0.

## 4. Stretch queue (not committed; rank order; take the next one only when the committed list is on time)

| Rank | ID | Task | Days |
|---|---|---|---|
| 1 | TM-03 | Update `docs/proposal/proposal.tex` and `proposal.pdf` to v5 (they are still v4), re-render the PDF with `figures/architecture_v5`, verify the proposal's new references [21] to [26] (authors, venues, links) | 2.0 |
| 2 | TM-04 | Apply the 25 proposed edits of section 7 of `docs/literature-review-and-usage.md` to `docs/plan.md`; check that each proposal's module path exists (all do except `agents/sutradhar/store_prior.py`) | 2.5 |
| 3 | PR-86 | FAQ on limits (ten questions a lawyer asks first) | 1.0 |
| 4 | PR-48 | Decide the open legal readings and write the UI wording; decision log | 1.0 |
| 5 | PR-79 | Demo script, 6-minute video plan, demo-environment runbook (Ada tunnel and a recorded fallback) | 2.5 |
| 6 | PR-80 | Known-issues list and stated limits (after the PR-77 run) | 1.0 |
| 7 | EV-21 | Citation faithfulness by removal and the remaining new metrics (M-list of evaluation plan 8.3) in `eval/metrics/` | 2.0 |
| 8 | PR-85 | "How it was evaluated" page and document tied to the evaluation results | 1.0 |
| 9 | PR-82 | Lawyer user guide, flows 1 to 7 with screenshots | 2.5 |
| 10 | PR-50 | Sources and dates panel: rule `last_verified` dates and the store data-cut date in the tabs | 1.0 |
| 11 | PR-18 | Editor UI for the brief (needs PR-17, Shravani's stretch) | 2.5 |
| 12 | PR-55 | Accessibility audit with axe on live data and a keyboard-only walk; fixes in your files, hook-ins elsewhere | 2.5 |
| 13 | PR-61 | Help page and glossary | 1.0 |
| 14 | PR-51 | First-run onboarding (needs PR-32 and PR-52, Satvik's stretch) | 2.5 |
| 15 | PR-64 | Windows (Docker Desktop and WSL2) and macOS notes and one real test | 2.0 |
| 16 | PR-68 | Versioning, `CHANGELOG.md`, release checklist | 1.0 |
| 17 | PR-78 | Performance budgets and measurement (needs PR-27, Vishak's stretch) | 1.0 |
| 18 | PR-84 | Architecture guide (two pages from `docs/architecture/skeleton.md`) | 1.0 |
| 19 | PR-58 | Hindi UI strings for key screens and Devanagari input checks | 2.5 |

## 5. Deferred or cut

None: every ID you own is either committed or in the stretch queue above.

## 6. What you need from others

| From | What | Needed by |
|---|---|---|
| Vishak | Contract PR merged (eval output paths, statutes builder glob over `data/gaps/statutes/*.jsonl`, the label text constant) | D1 |
| Vishak | Review of EV-02, PR-28, PR-46 and PR-47 PRs (rotation: your PRs go to the owner of the area), turnaround one working day | continuous |
| Vishak | The three-step manual install in `DOCKER.md` for PR-81 | D14 |
| Shravani | TM-02: shared hook (`make hooks`), PR template, `scripts/check_commits.sh` | D1 |
| Satvik | Review of PR-37 and PR-45 (hook-ins into his files) | D13 |
| Satvik | PR-04 and PR-05 live (reads, upload, SSE) so the browser check can start | D10 |
| Satvik | A way to start the stack in live mode on the offline stand-ins | D14 |
| Shravani | PR-06 chat, brief and spar routes live | D13 |
| Shravani | Review of your docs PRs (PR-75, PR-77, PR-81): she follows the README on a clean clone | D18 |

## 7. What others need from you

| To | What | Date |
|---|---|---|
| Vishak | EV-02 stats (`eval/stats/*`) | D3 |
| Vishak | EV-02 metrics (`eval/metrics/*`) and the null-agent audit | D8 |
| Vishak | PR-28 statute data under `data/gaps/statutes/`, so the statutes store can be rebuilt | D10 |
| Satvik | PR-28 bailable and cognisable data for the DOCX statutory position | D10 |
| Satvik | The exact text of the label and the terms (the contract constant, then PR-37) so his DOCX and card banner match the UI | D13 |
| Satvik | `last_verified`, `source` and `version` per rule in `configs/rights_rules.yaml`, for the rights read route and the sources panel (the pinned shape allows null until then) | D17 |
| Shravani | PR-37 and PR-45 merged, so the system and browser checks are consistent | D13 |
| Shravani and Satvik | The PR-75 defect list, each item assigned to an owner and a severity | D17 (fix window D18 to D19) |
| Shravani | The PR-77 manual QA script for the final clean-machine run | D18 |

## 8. Status table (update this, nothing else, when a state changes)

States: todo, doing, review, merged, blocked, dropped.

| ID | State | PR link | Merged on (Day) | Notes |
|---|---|---|---|---|
| TM-05 | todo | | | |
| EV-02 (part 1) | todo | | | |
| EV-02 (part 2) | todo | | | |
| EV-02 (part 3) | todo | | | |
| PR-28 | todo | | | |
| PR-45 | todo | | | |
| PR-37 | todo | | | |
| PR-47 | todo | | | |
| PR-46 | todo | | | |
| PR-75 | todo | | | |
| PR-77 | todo | | | |
| PR-81 | todo | | | |
| Stretch taken (list IDs) | | | | |

Task index for this file (every ID that is yours): committed TM-05, EV-02, PR-28, PR-37, PR-45, PR-46, PR-47, PR-75, PR-77, PR-81; stretch TM-03, TM-04, PR-18, PR-48, PR-50, PR-51, PR-55, PR-58, PR-61, PR-64, PR-68, PR-78, PR-79, PR-80, PR-82, PR-84, PR-85, PR-86, EV-21; deferred none.
