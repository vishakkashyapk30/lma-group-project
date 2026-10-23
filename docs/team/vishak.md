# Vishak: evaluation lead, models on Ada, data and infrastructure

Part of the team plan in `docs/team/README.md` (read its sections 2 to 8 first: ownership, shared files, PR rules, waves, freeze). This file is the only place you update your own status. Do not edit `progress.md`.

Calendar: Day 1 (D1) is the Monday after the history sync; weeks are D1 to D5, D6 to D10, D11 to D15, D16 to D20. Effort is in person-days (estimates).

## 1. Role summary

You carry the evaluation (switches, test sets, baselines, driver, runners, preregistration, the freeze, the Ada runs) so that GPU queue time is used from week 1, and the model and data plumbing it shares with the product (weights, tiers, the full store build, licences). You also run the history sync and author the day-0 contract PR. You are the Ada session captain.

Committed: **21.5 person-days** (W1 5.5, W2 5.5, W3 5.0, W4 5.5). Stretch queue: 52.5 days, in rank order (section 5). Capacity: 17.5 days at 3.5 weeks, 20 at 4 weeks (the plan is sized to 4 weeks; tail tasks are marked T).

## 2. Owned paths

Under `src/vakeel_sahayak/` unless stated.

| Path | Notes |
|---|---|
| `eval/` (everything except `eval/metrics/` and `eval/stats/`, which Harshita owns) | baselines, ablations, features, ingestion pipelines, runners, report, retrieval-only, failure analysis |
| `testsets/` | T1 to T9 builders, rendering, degrade, specs |
| `finetune/` | teacher dossiers, span filter, noise, QLoRA, merge |
| `models/` | factory, tiers, vLLM and local clients, Sarvam |
| `ingestion/`, `agents/munshi/`, `agents/peshkar/`, `tools/intake/` | Munshi and Peshkar |
| `agents/sutradhar/`, `agents/pairokar/`, `batch/` | Sutradhar, Pairokar, batch desk |
| `pipelines/`, `stores/` | data pipelines and the ten stores (Harshita adds data under `data/gaps/` only) |
| `configs/eval/`, `configs/models.yaml`, `configs/stores.yaml`, `configs/splits.yaml`, `configs/thresholds.yaml`, `configs/paths.yaml`, `configs/finetune/` | per-file owner rule |
| `scripts/ada/`, `scripts/download_models.sh`, `scripts/build_stores.sh`, `scripts/build_testsets.sh`, `scripts/download_datasets.sh`, `scripts/build_interim.sh`, `scripts/laptop_overnight.sh`, `scripts/setup_dev.sh` | |
| `docker/`, `DOCKER.md`, `data/` (except `data/gaps/`), `NOTICE` | |
| `docs/evaluation-plan.md`, `docs/preregistration.md` (new), `docs/product-readiness.md`, `docs/literature-review-and-usage.md` | |
| Tests that follow your packages: `tests/unit/{eval (except test_metrics.py, test_stats.py), testsets, finetune, models, ingestion, pipelines, stores, batch, tools_intake}`, `tests/unit/agents/{munshi,peshkar,sutradhar,pairokar}`, `tests/integration/{test_munshi_to_peshkar,test_sutradhar_with_fakes,test_batch_queue_resume}.py` | |

Shared files you steward: `src/vakeel_sahayak/orchestration/switches.py` (you own it; others add nothing without a request), `compose.yaml`, `pyproject.toml`, `configs/*.yaml` in the per-file table of README section 2.

## 3. Week-by-week tasks (committed)

Test names are the tests that must go green for the task. PR branch names are suggestions; the target day is the day the squash merge should happen.

### Week 1 (D1 to D5): 5.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| TM-01 | History sync (you force-push `main`, `ideation-v1`, `ideation-proposal`) and the day-0 contract PR (README section 3) | All four people report `git log origin/main..` empty or only their backups; the contract PR is merged with the frozen shapes | `make test-collect` stays clean; `tests/unit/orchestration/test_switches.py` and `tests/unit/api/test_app_and_deps.py` still collect | Reviews from Shravani, Satvik (Harshita acknowledges) | `feat/contracts-day0`, D1 | 1.0 |
| EV-01 | `Switches` fields of evaluation plan 3.4 with defaults, `variant()` and `for_variant()` entries for A11a, A11b, A12 to A16, A2b, A8b to A8d, B5, P7; update the registry tests deliberately | Defaults leave `variant()` equal to `full`; every new field belongs to a named variant | `tests/unit/orchestration/test_switches.py`, `tests/unit/eval/test_registries.py` (each edited test line carries `# RECONCILED: <reason>`) | Contract PR | `feat/eval-switch-variants`, D2 | 1.0 |
| PR-21 | Replace the stub `scripts/download_models.sh`: resumable, checksums, disk check, licences shown, tier from `VS_MODELS`; update `DOCKER.md` with the three-step manual install used by PR-81 | One command fetches the tier's weights into a volume on your laptop and on Ada; a second run is a no-op | `make test-collect`; manual: second run prints "nothing to do" | PR-20 only softly (roles already in `configs/models.yaml`) | `feat/models-download`, D5 | 2.0 |
| EV-09 (part 1) | Ada bring-up: weights staged on Ada scratch, a real-model smoke of two agents through the existing scripts (not yet the driver) | One 14B and one 4B call return on Ada; session recipe written in `scripts/ada/README` section of `ada.md` | none (operational); `make test-models` subset on the laptop | PR-21 | `docs/ada-bringup`, D5 | 1.0 |
| PR-69 (part 1) | Email the IPC2BNS-Verify authors (decision P-D4); start `NOTICE` with Open India Law CC BY 4.0, models and fonts | Email sent D2; `NOTICE` draft exists | none | none | `docs/notice-draft`, D5 | 0.5 |

### Week 2 (D6 to D10): 5.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| EV-09 (part 2) | Token-per-case measurement on 10 dev cases, teacher pilot decision data (API versus 32B), throughput numbers; record in `data/eval/token_measure.json` | The mean tokens per case of Full is known; evaluation plan 7.2 floors are recomputed | none (measurement) | EV-07 (first cut of the driver), EV-03 | `feat/ada-token-measure`, D9 | 0.5 |
| EV-03 | T1 court-grounded builder with the dev (50), open-test (120) and blind (80) manifests, hashed blind ids, High-Court-only pool (progress.md C) | `build_t1()` writes manifests with hashes under the contract paths | `tests/unit/testsets/test_t1_court_grounded.py`, `tests/unit/testsets/test_common.py` | Contract PR (paths) | `feat/testset-t1`, D8 | 1.5 |
| EV-07 | Thin evaluation driver `eval/runners/driver.py` (agents in sequence, scripted counsel approves a gate only when the scenario says so; unapproved export still blocked by `GateGuard`), `shard_runner`, `run_rq1`, `run_ablations`, `run_safety` entry points, the new jobs in `configs/eval/runs.yaml`, the blind-slice lock; `make smoke` exits 0 and prints the export path (this is PR-12) | A scripted run of case-0007 completes on offline stand-ins and on Ada with real models; scoring a blind id without the freeze tag refuses | `tests/unit/eval/test_runners.py`, `tests/unit/eval/test_registries.py::test_run_registry_matches_plan` (edited deliberately and marked) | EV-01; EV-02 for scoring | `feat/eval-driver-runners`, D10 | 3.0 |
| PR-12 | Smoke driver CLI (same code as the evaluation driver) | `make smoke` exits 0 | covered by EV-07 | EV-07 | inside `feat/eval-driver-runners`, D10 | 0 (inside EV-07) |
| PR-29 (part 1) | Start the full store build on Ada scratch or a big-disk machine (about 85 minutes); wire the Supreme Court metadata if time allows | Build completes, row counts logged | `tests/unit/stores`, `tests/unit/pipelines` stay green | PR-28 for the statute store only (not for the case-law stores) | `feat/stores-full-build`, D10 | 0.5 |

### Week 3 (D11 to D15): 5.0 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| PR-29 (part 2) | Build report and manifest (row counts, sizes, data-cut date), citation resolution re-measured; statutes store rebuilt once Harshita's PR-28 lands | `data/stores/MANIFEST.json` exists and lists the cut date | `tests/unit/stores`, `tests/unit/pipelines/test_citation*` | PR-28 (Harshita, D10) | `feat/stores-manifest`, D12 | 0.5 |
| EV-05 | Baselines B0, B0L, B0S (model argument), B1, B4, B6 (no model, never imports the factor tagger) and the Full wrapper | B6 calls no model; B0L uses the teacher role | `tests/unit/eval/test_baselines.py`, `tests/unit/eval/test_chunking_variants.py` | EV-07, EV-02 | `feat/eval-baselines`, D13 | 1.5 |
| EV-06a | Ablation wrappers for the sparring 2x2: A2, A8, A9 | Each wrapper builds its context from `Switches.for_variant` and writes outputs to the contract path | `tests/unit/eval/test_ablation_runs.py` (A2, A8, A9 cases) | EV-01, EV-07 | `feat/eval-ablations-sparring`, D13 | 1.0 |
| EV-10 | `docs/preregistration.md` (evaluation plan 2.7 outline), tags `prereg-v1` and `eval-freeze-v1`, blind ids hashed, dev-fixed thresholds from job 3 | Freeze checklist (README section 8) is green and tags are pushed | `tests/unit/eval/test_registries.py` | EV-03, EV-05, EV-07, EV-11 (job 3), EV-02 | `docs/preregistration`, D14 (hard limit D15) | 1.0 |
| EV-11 (part 1) | Ada operator: failure discovery and dev tuning on 50 dev orders and 10 bundles (job 3 of the job map, README section 9) | δ, ε, the pass^3 bar and the answerable-factor rule are written down | none (operational) | EV-07, EV-02, EV-03 | no PR; result file `data/eval/dev_tuning.json`, D13 | 1.0 |

### Week 4 (D16 to D20): 5.5 days

| ID | Task | Acceptance (one line) | Tests to go green | Depends on | PR branch, target day | Days |
|---|---|---|---|---|---|---|
| EV-13 | Sampling-only critic arm (S9, A8b): k samples at the same token budget as Abhiyojak, in `eval/ablations/a8b_sampling_critic.py` (the agent code is not touched; the driver dispatches on `critic_mode`) | The arm spends the same token budget; the default Full path is unchanged (prompt hash test) | `tests/unit/eval/test_ablation_runs.py` (new case) | EV-01, EV-06a | `feat/eval-arm-sampling-critic`, D16 | 1.0 |
| EV-11 (part 2) | Ada operator after the freeze: RQ1 main (Full, B4, B0, B1, floor sizes after the token measurement), B0L, B0S, B6, sparring 2x2 (A2, A8, A9, S8, S9, S10) | Saved outputs for the 200 T1 cases (or the floor), manifests with seeds and budgets | none (operational); `tests/unit/eval/test_runners.py` stays green | EV-10 freeze; EV-12 (Satvik) arms; EV-13 | no PR; manifests under `data/eval/runs/`, D16 to D20 | 1.0 (operator time, GPU time is separate) |
| PR-20 (T) | Model tiers: T0 to T3 table in `configs/models.yaml`, `VS_MODELS=auto` picks a tier and says so | The chosen tier and its roles are printed at start-up and exposed for the API | `tests/unit/models/test_factory.py` | none | `feat/models-tiers`, D17 | 1.0 |
| PR-23 (T) | Real-model paths on case-0007 on your 4060: OCR, NLI, BGE-M3 and Whisper loaded in turn; install PyMuPDF; scope: vision and IndicTrans2 go to known issues if they do not fit | case-0007 runs with `VS_MODELS=real` for the intake and dossier stages; the 16 skipped ingestion tests run | `tests/unit/ingestion` (the 16 PyMuPDF tests), `make test-models` subset | PR-21 | `feat/real-model-paths`, D18 | 2.0 |
| PR-69 (part 2, T) | Finish `NOTICE` and the licence list for the About page content (the Licences page itself is Satvik's stretch); IPC2BNS decision (P-D4) recorded | Every shipped dataset, model and font is listed with licence and attribution | none | Authors' reply or the week-3 deadline | `docs/notice`, D17 | 0.5 |

Total committed: 5.5 + 5.5 + 5.0 + 5.5 = **21.5**. PR-69 is 1.0 in total (0.5 + 0.5), EV-09 1.5, PR-29 1.0, EV-11 2.0, EV-07 3.0 (PR-12 inside it).

## 4. Evaluation job map (all 24 must jobs of evaluation plan 7.2; you run all of them)

Code owner means who writes the arm or the set; you operate the Ada session for every job. "C" means committed in this plan, "S" means stretch (promote in the order of section 5).

| Job | What | EV task | Code owner | Tier here |
|---|---|---|---|---|
| 1 | Teacher dossiers | EV-08 | you | S (rank 2); the pilot (E-D3) is in EV-09 |
| 2 | QLoRA, Qwen3-4B, batch job | EV-08 | you | S (rank 2) |
| 3 | Failure-mode discovery and dev tuning | EV-11 part 1 | you | C, D12 to D13 |
| 4 | RQ1 main (Full, B0, B1, B4; B2, B3 once) | EV-05, EV-07, EV-11 part 2 | you; metrics Harshita (EV-02) | C, floor sizes |
| 5 | B0L, B0S, B6 | EV-05, EV-11 part 2 | you | C |
| 6 | Ablations A1, A3, A4, A6, A7 | EV-06b | you | S (rank 3) |
| 7 | Sparring 2x2: A2, A8, A9 | EV-06a, EV-11 part 2 | you | C |
| 8 | A5 extractors | EV-08 | you | S (rank 2) |
| 9 | RQ2 vision pages and full system | EV-19 | you | S |
| 10 | F2 change sets | EV-20 (with T3 in EV-18) | you | S |
| 11 | F1, F5, F6 baselines and assembly | EV-20 | you; needs PR-13 and PR-14 (Satvik) | S |
| 12 | F3 baselines | EV-20 (T4 builder) | you | S |
| 13 | F4 no-cache | EV-20 (T5 builder) | you | S |
| 14 | T6 tool calling and T7 safety, 3 runs | EV-04, EV-11 | you (builders); the existing `tests/system` T7 scripts are the fallback set | S (rank 1; never cut, so promote at the D5 velocity check) |
| 15 | S8 self-critique repair arm | EV-12 (Satvik writes the arm), EV-11 part 2 | Satvik | C |
| 16 | S9 sampling-only critic arm | EV-13, EV-11 part 2 | you | C |
| 17 | S10 no-isolation arm | EV-12 (Satvik), EV-11 part 2 | Satvik | C |
| 18 | S1 self-critique retrieval | EV-15 | you | S (rank 4) |
| 19 | S3 stopping variants (A11b) | EV-15 | you | S (rank 4) |
| 20 | S7 gap re-reading (A11a) | EV-16 | you | S (rank 5) |
| 21 | S15 output formats (A13) | EV-14 (Shravani writes it), EV-11 | Shravani | C code (W4 tail), run S |
| 22 | S17 defences (A15) | EV-17 | Shravani | S |
| 23 | Budget sweep for the cost-quality frontier | EV-11 (needs Full, A7, B4) | you | S (after job 6 provides A7) |
| 24 | Citation faithfulness by removal | EV-21 (Harshita writes the metric), EV-11 | Harshita | S |

Tier B and C jobs (25 to 33) and variants S2, S4, S5, S6, S11, S12, S13, S14, S16 are **deferred** (EV-22): they are should and could in the evaluation plan, and its own cut order (section 7.4) drops them first. Reconsider at the D12 decision (E-D5).

Compute note: with the freeze at D14 the usable Ada window after the freeze is D15 to D20 (about 75 nominal node-hours, about 52 usable after the 30% buffer). The committed jobs (4 at floor, 5, 7, 15 to 17) need about 85 node-hours at the plan's floor sizes, so job 4 runs at 150 cases and 2 runs for Full and B4, and the sparring 2x2 at 100 cases. Say so in the preregistration.

## 5. Stretch queue (not committed; take the next one when a committed task is done early or after the velocity checks at D5 and D10)

| Rank | ID | Task | Days |
|---|---|---|---|
| 1 | EV-04 | T6 (chat questions) and T7 (safety) builders; job 14 | 2.0 |
| 2 | EV-08 | Fine-tuning: teacher dossiers, span filter, noise augmentation, dataset, QLoRA, merge, A5 extractors (jobs 1, 2, 8) | 4.0 |
| 3 | EV-06b | Ablation wrappers A1, A3, A4, A6, A7; job 6 | 1.0 |
| 4 | EV-15 | S1 and S3 Sutradhar variants (jobs 18, 19) | 3.0 |
| 5 | EV-16 | S7 gap re-reading (job 20) | 1.0 |
| 6 | PR-22 | Serving container for the `real` profile fitted to 8 GB (scoped to the local runtime) | 2.5 |
| 7 | PR-33 | Ingestion hardening (encrypted and corrupt PDFs first) | 1.5 |
| 8 | PR-62 | One-command install (`install.sh`, preflight) | 2.5 |
| 9 | PR-27 | Latency and memory table per tier | 2.5 |
| 10 | PR-30 | Store distribution: release artefact, checksum, sample fallback | 2.5 |
| 11 | EV-23 | `eval/report/` table and figure writers (evaluation plan section 6) | 2.0 |
| 12 | EV-18 | T2, T3, T8, T9 builders | 5.0 |
| 13 | EV-19 | RQ2 ingestion pipelines P1 to P6 and `munshi_full` (job 9) | 3.0 |
| 14 | EV-20 | Features F1 to F8 plus T4 and T5 builders (jobs 10 to 13) | 5.0 |
| 15 | PR-24 | CPU-only path and banner | 2.5 |
| 16 | PR-34 | Low-confidence, Hindi and handwriting prompts | 2.5 |
| 17 | PR-35 | Real-file sweep | 2.5 |
| 18 | PR-63 | Publish images to GHCR | 2.5 |
| 19 | PR-67 | Resource limits per tier, offline egress test | 2.5 |
| 20 | PR-83 | Admin guide | 2.5 |

## 6. Deferred or cut (with the reason)

| ID | Reason |
|---|---|
| PR-26 | P2, needs a Sarvam key; Sarvam stays off by default and the mocked tests stand |
| PR-31 | P2, store update path; not needed before the first release |
| EV-22 | Should and could variants and jobs 25 to 33 of the evaluation plan; cut first by plan section 7.4 |

## 7. What you need from others

| From | What | Needed by |
|---|---|---|
| Shravani | TM-02: the shared commit-msg hook, `make hooks`, the PR template and `scripts/check_commits.sh` | D1 |
| Shravani | EV-14 (S15 output formats) merged, so the arm can be run | D19 (tail) |
| Shravani | The frozen graph interface (reference only: the thin driver does not call the graph) and a stable `GateGuard` | D2; she must not change `GateGuard` semantics without telling you |
| Satvik | Review of every PR of yours, turnaround one working day | continuous |
| Satvik | EV-12 (S8 `repair_mode`, S10 `abhiyojak_isolation`) merged | D10 |
| Satvik | PR-13 and PR-14 (export builders) for the F5 and F6 stretch jobs | D17 |
| Harshita | EV-02 stats (`eval/stats/*`, `tests/unit/eval/test_stats.py`) | D3 |
| Harshita | EV-02 metrics (`eval/metrics/factor_scores.py`, `unsupported_fact.py`, `retrieval.py`, `agentic.py`) and the null-agent audit | D8 |
| Harshita | PR-28 statute data under `data/gaps/statutes/` | D10 (statutes store rebuild D12) |

## 8. What others need from you

| To | What | Date |
|---|---|---|
| All | History sync done and the day-0 contract PR merged | D1 |
| Shravani, Satvik | EV-01: `Switches` fields and variant table (S15 needs `output_format`; S8 and S10 need `repair_mode` and `abhiyojak_isolation`) | D2 (fields frozen in the contract PR on D1) |
| Shravani | Review of her PRs (rotation: you review Shravani) | continuous, one working day |
| Satvik | Eval output paths and the manifest layout in the contract PR | D1 |
| Satvik | PR-23 and PR-20 (model tier statement for the API settings and for the Preview) | D18 |
| Harshita | The statutes builder glob over `data/gaps/statutes/*.jsonl` (part of the contract PR) | D1 |
| Harshita | PR-21 install steps in `DOCKER.md` for the README quick-start (PR-81) | D14 |
| Harshita | Reviews of her EV-02, PR-28, PR-46 and PR-47 PRs | one working day |
| All | The freeze: `prereg-v1` and `eval-freeze-v1` tags, and the post-freeze label rule | D14 (hard limit D15) |

## 9. Status table (update this, nothing else, when a state changes)

States: todo, doing, review, merged, blocked, dropped.

| ID | State | PR link | Merged on (Day) | Notes |
|---|---|---|---|---|
| TM-01 | todo | | | |
| EV-01 | todo | | | |
| PR-21 | todo | | | |
| EV-09 | todo | | | |
| PR-69 | todo | | | |
| EV-03 | todo | | | |
| EV-07 (PR-12 inside) | todo | | | |
| PR-29 | todo | | | |
| EV-05 | todo | | | |
| EV-06a | todo | | | |
| EV-10 | todo | | | |
| EV-11 | todo | | | |
| EV-13 | todo | | | |
| PR-20 | todo | | | |
| PR-23 | todo | | | |
| Stretch taken (list IDs) | | | | |

Task index for this file (every ID that is yours): committed TM-01, EV-01, PR-12, PR-20, PR-21, PR-23, PR-29, PR-69, EV-03, EV-05, EV-06a, EV-07, EV-09, EV-10, EV-11, EV-13; stretch PR-22, PR-24, PR-27, PR-30, PR-33, PR-34, PR-35, PR-62, PR-63, PR-67, PR-83, EV-04, EV-06b, EV-08, EV-15, EV-16, EV-18, EV-19, EV-20, EV-23; deferred PR-26, PR-31, EV-22.
