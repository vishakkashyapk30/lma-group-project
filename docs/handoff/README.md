# Handoff notes: index

Each note records a decision, a measurement or the working steps of a live workflow. Read the note for an area before editing it, and update or add one when you stop.

Notes that only logged finished work ("built X in file Y"), old status and to-do files, and design reviews were removed on 23 Nov 2026. They stay in git history: `git show af58a17:docs/handoff/<file>.md` (list them with `git show --stat af58a17..HEAD`).

| Area | Notes |
|---|---|
| Where everything lives, and how to restore a deleted working copy | `archive-2026-11-21.md` |
| What was decided and measured in the 27 to 29 Oct sessions (owner decisions, Gemini free tier, limits) | `session-2026-10-29.md` |
| Models, providers, privacy boundary, budgets | `pilot-hosted-model.md`, `gemini-free-tier.md`, `adding-an-llm-provider.md`, `privacy-hardening-2026-10-27.md`, `python-and-defaults.md` |
| Data, intake, citations, vectors, test sets | `data-and-models.md`, `munshi-real-pdf-reading.md`, `citation-sc-metadata.md`, `bge-vectors-2026-10-28.md`, `testsets-t2-t9.md`, `first-schedule.md` |
| Evaluation harness: switches, runners, scoring | `eval-infrastructure.md`, `eval-scoring.md`, `eval-complete.md` |
| Evaluation runs: the sweeps, spend and ledgers, baselines | `sweep-dev.md`, `sweep-satvik.md`, `dev-baselines.md`, `literature-sweeps.md`, `prereg.md` |
| Gold labels | `gold-labeler.md`, `gold-source-sweep.md` |
| The final method: failure analysis, the four fixes, results | `architecture-search-2026-11-01.md`, `arch-search-results.md` |
| Sparring reserve (post-freeze fix for unjudged objections) | `objections-unanswered-2026-11-15.md`, `sparring-reserve-measurement.md` |
| Rights Radar and statute tables | `rights-fixes.md`, `first-schedule.md`, `../qa/rights-verification.md` |
| Frontend, Hindi interface, evaluator demo | `workspace-redesign.md`, `landing-colour-motion.md`, `hindi-labels.md`, `evaluator-demo.md` |
| Fine-tuning pipeline (not run; the "train on the verifier" direction) | `finetune.md` |

Report: `../technical-report/` (build with `build.sh`). Result tables: `../results/`. Poster material: `../assets/poster/`, `../results/poster/`, `../Vakeel-Sahayak.ai_Final_Poster_Digital.pdf`.
