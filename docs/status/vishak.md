# Status: Vishak

Tasks from `split.md` (stream C and shared files). Updated 2026-10-27. Details are in the handoff notes under `docs/handoff/`.

| Task | State | Note |
|---|---|---|
| VI-01 literature sweep 4 | done | `literature-sweep-4.md` |
| VI-02 sweep 5, plan v6, citation check | done | `sweep-5.md` |
| VI-03 jobs, driver dispatch, preregistration template | done | `eval-jobs.md` |
| VI-04 non-Qwen gold labeler (G1, G3; then G4 to G7) | done | `gold-labeler.md` |
| VI-05 SC metadata in the citation index, stores rebuilt | done | `citation-sc-metadata.md` |
| VI-06 test sets T2 to T9 (+ T7, driver rows, native Hindi) | done | `testsets-t2-t9.md`, `eval-unblocked.md` |
| VI-07 features F1 to F4, F7, F8 and ingestion P1 to P6 | done offline | `eval-features.md`; P3, P4, F5, F6 blocked |
| VI-08 hosted-model pilot | done | `pilot-hosted-model.md` |
| VI-10 hook, PR template | done | |
| Gold-source sweep (agreed primary, rule-only secondary) | set up | `gold-source-sweep.md`; rescoring loop not written |
| Eval completion (M5, M9 to M18, M33, M35, S15b, S13 smoke, studies S14b/c, S16/b, S4/S5, Ada wrappers) | done offline | `eval-complete.md`; stand-in NLI labelled; M18 replay and S13 model arm open |
| Product completion and variant-effect audit (splitter rescue, drafting tool, Rights `verification`) | done offline | `product-complete.md`; Harshita to verify the 7 rule texts |
| Dev-set sweep | on hold | `sweep-dev.md`: waits for tag `dev-sweep-v1`, then reruns baselines and sweep from a worktree of the tag; Sarvam block with Satvik (`sweep-satvik.md`) |
| VI-09 freeze and real runs | blocked | scoring and the rescoring loop now exist; waits for the pinned tag, real runs, Harshita's checks and preregistration hashes |
| VI-11 fine-tuning | stretch | only if the freeze lands early |

Budgets (2026-10-27): OpenAI ledger ceiling 4.90 USD (1.51 spent at the checkpoint; 2.2008 USD per `make openai-spend` later on 2026-10-27, Sarvam INR 5.4945 per `make sarvam-spend`); the "Dev-set sweep: on hold" row above is outdated: the baselines were rerun from the pinned tag `dev-sweep-v1` (`docs/handoff/sweep-dev.md`); the owner's Sarvam key INR 30 in total; the large Sarvam block runs on Satvik's key. Data: private organisation dataset `Vakeel-Sahayak/vakeel-sahayak-data`.


## 2026-10-30
Mid-submission: OpenAI queue and Gemini blocks run (tag `dev-sweep-v3`), scoring in progress, report on branch `midsub-report`. Split with Shravani: `docs/handoff/midsub-split-2026-10-30.md`. Mine: scoring, tables, results text, final PDF and push by 23:00.
