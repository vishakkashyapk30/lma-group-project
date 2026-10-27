# progress.md: Vakeel-Sahayak.ai

> **Start here:** read `AGENTS.md` (rules, how to run, what is not in the repo), then `split.md` (who does what), then sections 0 to 0e below (master to-do list, data assessment, plans, status of every workstream).


Status as of 2026-10-14. Nothing is committed yet; all work below sits uncommitted on branch `ideation-v1`.

> Checked by Vishak 2026-10-27: everything below section 0f is a chronological log from 2026-10-14 to 2026-10-26 and is NOT current: the to-do list in "A. Make the system run end to end" (LangGraph flow, FastAPI routes, DOCX export, system tests) and the Docker note "the API routes are still stubs ... 503" are done or outdated (`create_app()` builds 42 routes; export modules and their tests pass; `tests/unit` 4,227 passed). `docs/api/README.md` and `docs/api/openapi.json` (SH-06) do not exist in the repo (flagged, not written). The newest state is section 0f; `split.md` section 1 is the per-area table.

---

## 0f. State on 2026-10-27 (newest; read first, then the 2026-10-26 block below)

Sources: `docs/handoff/eval-complete.md`, `product-complete.md`, `sweep-dev.md`, `dev-baselines.md`, `sweep-satvik.md`, `pilot-hosted-model.md`. No model result number is claimed here.

- **Committed:** the evaluation code up to `f114bca` (label-source sensitivity, citation and abstention metrics, scheduling, chunking and retrieval studies, S15b and the S13 smoke, thin Ada wrappers), the order-splitter rescue and drafting tool wiring and the variant-effect audit (`791b817`), and the pseudonymiser caption-name fix (`4e40282`). On the 250 T1 orders (dev 50 + cases 200) the party-name proxy leaks fell from 80 (160 tokens) to 5 (6 tokens); t1dev-017 is no longer refused (one order, t1-196, still is). **Uncommitted per `git status` at the time of writing:** modifications in `agents/base.py`, `privacy/boundary.py` and `privacy/pseudonymise.py` (check the diff before committing), the G2 merge in the gold folders (data, gitignored), and these documentation edits.
- **Built since the 2026-10-26 block:** S15b (`free_then_parse`) so `IMPLEMENTED_VARIANTS` equals the full variant table; S13 offline smoke (`recall_evaluator`; the model-backed arm is still planned); M5 label sensitivity and M9, M13, M15, M16, M17, M18, M33, M35 with scoring tables `table_citations`, `table_abstention`, `table_label_sensitivity`, `table_label_kappa` (stand-in NLI is labelled; M33 risk is 0 at tau = cut by construction; M18 replay to the 16-call budget is not computed); S14b, S14c, S16, S16b, S4/S5 retrieval and M17 as studies under `eval/studies/` (not per-case driver arms), run once each by the dev sweep; the order-splitter rescue (`rescue_with_non_qwen`, opt-in, fake-client tested); the `assemble_application` tool (draft under `draft/`, never `export/`).
- **Variant-effect audit:** `driver smoke-all` offline passes 61 of 61 ids; every implemented id has an effect test (`test_variant_effects.py`, 42). S6 and B5 have no effect until a store prior is trained: the run emits `store_prior_untrained` (training: `python -m vakeel_sahayak.agents.sutradhar.store_prior train --orders <train-split orders with G1-G3 gold>`; the train-order gold labelling is not done). S10 had a privacy false positive (a ten-digit spotlight tag read as a phone number, so sparring gave 0 objections); fixed agent-side, root cause in `privacy/injection_guard.wrap_untrusted` is the privacy owner's.
- **Rights Radar:** each rule result now reports `verification` (`unverified` until `last_verified` is set); all seven rules are unverified. Harshita must re-check the seven rule texts (`configs/rights_rules.yaml`, `rights/rules/*`) against the bare acts and the cited judgments (PR-46); the UI and API must render `verification` beside each rule.
- **Manifests and scoring:** every run manifest records `git_sha`, `git_dirty`, `code_tree_hash`; the scoring loader refuses runs from different commits (`--allow-mixed-code` overrides). The dev runs of 2026-10-26 carry `719f741-dirty`, so they are of unknown code state and are not to be scored or quoted.
- **Gold:** the agreed gold is primary and now has G2 merged from the SC-metadata candidate: 14 of 200 test cases changed, 0 of 50 dev; dev has 0 resolved citations, so M10 is n/a on dev. B0L on a hosted backend was a duplicate of B0 (same model and prompt); the real B0L is to run on Sarvam-105B and the Qwen3-32B Ada plan is dropped.
- **Budgets:** OpenAI ledger ceiling 4.90 USD (1.51 spent at the checkpoint; 2.2008 USD on 2026-10-27 per `make openai-spend`, Sarvam INR 5.4945 of the default cap 25 per `make sarvam-spend`); the owner's Sarvam key INR 30 in total; the large Sarvam block is run on Satvik's own key (`docs/handoff/sweep-satvik.md`).
- **Dev-set sweep process:** plan `configs/eval/sweep_dev.yaml` (phases 0 to 5; `driver plan --sweep` prints it), runner `scripts/sweep_dev.py run --phase N`, Satvik's package `scripts/sweep_sarvam_block.sh`, results collected with `scripts/sweep_collect.sh` (HF organisation dataset `sweep-runs/`). Done: phase 0 and the Sarvam package; not run: phases 1, 2, 4, 5. A HOLD is in force: no model-calling phase until a pinned code tag.
- **Running or waiting:** the privacy and S6-prior agent (privacy false-positive root cause and the trained store prior); then the full-suite run; then tag `dev-sweep-v1`; then rerun of the baselines (full x2, b0, b0l, b1, b4, b6) and the sweep from a git worktree of that tag.
- **Open decisions for the owner:** permission to dedupe git history; (the 2 red integration tests and system `flow4` were resolved on 2026-10-27 by reconciling the tests, see the last section of `regression-2026-10-26-b.md`); Harshita's verification of the seven Rights rule texts; HLDC and indictrans2 access; Satvik's run of the Sarvam block (needs the tag).
- **Known weak spots:** Full may win on retrieved boilerplate where the T1 facts are only a caption (B0 answers "no facts supplied"; Full's grounds come from retrieved authorities not tied to client facts), so argued-factor metrics must be checked before any claim; grounds are weak in substance (gravity grounds cite the State's side or generic law, about 10 open issues per case, sparring objections mostly unanswered); the pseudonymiser still refuses one order (t1-196) and `Tally.calls` is never incremented (`injection.*.calls` always 0); M16, M33 and M35 are stand-in numbers until MiniCheck or DeBERTa is installed.

---

## 0f (earlier). State on 2026-10-26 (read before 0e; updated at 15:30)

- **Committed and pushed (main):** T2 to T9 builders, literature sweep 4 variants (S6/B5, S12, S13, S16), Munshi real-PDF fixes, SC metadata and SCC linking in the citation index, hosted-model driver (pseudonymised facts, auto NLI, faster store search), mask-instead-refuse for public corpus rows, parallel Peshkar extraction, budget pools, S18 authority stance and P8 keep-weak-text switches, CrPC/NDPS statutes and First Schedule flags, native Hindi High Court set (HLDC fallback), `make data` / `make data-check`, VI-03 (one driver entry for every variant, `plan`, `smoke-all`, preregistration template), Sarvam spend ledger (INR cap), VI-04 gold labeler (G1, G3).
- **Data:** all public sources are downloaded except HLDC (access requested) and the two gated/optional items below. Team copy is the private HF dataset `Vakeel-Sahayak/vakeel-sahayak-data` (`make data-install SRC=hf:Vakeel-Sahayak/vakeel-sahayak-data`); the owner grants access to teammates and the evaluator and re-runs `make data-bundle` + `make data-publish` after any store change. Models: tier T1 present (bge-m3, DeBERTa NLI, MiniCheck, whisper-small), Qwen3-4B present, Qwen3-VL-4B downloading; `ai4bharat/indictrans2-indic-en-dist-200M` is gated (request access); Qwen3-32B-AWQ is for the Ada nodes (see `configs/models.yaml`).
- **Budgets:** OpenAI 5 USD hard cap (default 4.50; about 0.2 used). Sarvam is INR-capped by `VS_SARVAM_CAP_INR` (default 25; owner ceiling 500; Satvik can add credits); prices in `configs/models.yaml`. Everything cannot fit in these budgets: tier A is about 4,500 Full case-runs; budgets buy about 1,000. Bulk generative jobs go to Qwen3-32B on Ada, floor sizes shrink (see `docs/handoff/eval-jobs.md`).
- **Order for the owner's tasks:** VI-03 done, VI-04 done (G1/G3 only), VI-07 (features F1 to F4, F7, F8 and ingestion P1 to P6) in progress, then VI-09 (freeze and runs) once Harshita's metrics and stats land. VI-02 (sweep 5, plan edits) only if asked.
- **Later on 2026-10-26:** VI-02 done (plan v6, 57 citations verified, 4 corrected); VI-07 done offline (P1, P2, P5, P6, Munshi arms on T2 and the Hindi set; F1 to F4, F7, F8; P3, P4, F5, F6 blocked on tools or export modules); T7 safety set and driver case rows for T2, T5, T7 built; gold G4 to G7 candidates (G4 kappa 0.57 on 88 orders, G5 0.63, G6 0.65, G7 only 1 of 250 so C30 rests on T4); F4 urgency fix (ordering 0.57 to 0.98) and F8 read-back fix (entity errors 0.51 to 0.07); the **agreed gold is now primary in `data/testsets/t1`**, the rule-only gold is `t1_rule_only` (secondary, declared sensitivity sweep, `scripts/swap_gold.sh`, `gold_source` option, job `gold_source_sweep` at zero cost; the rescoring loop is not written); Shravani pushed the LangGraph flow and API routes (her note: `docs/status/shravani.md`).
- **Data hosting:** the team copy moved to the Hugging Face organisation: private dataset `Vakeel-Sahayak/vakeel-sahayak-data` (members: owner admin, teammates write, evaluator read; each person needs a fine-grained read token for the org in `.env`). `make data`, `make data-check`, `make data-install SRC=hf:Vakeel-Sahayak/vakeel-sahayak-data`; owner-side `make data-bundle` and `make data-publish`. Stale T2, T3, T6, T8 manifests still point at the old T1 file hash: rerun those builders before the freeze.
- **Models on disk:** T1 tier, Qwen3-4B and Qwen3-VL-4B are in `models/hf`; Qwen3-32B-AWQ is for the Ada nodes; indictrans2 is gated. Disk is at about 97%: free space before long jobs.
- **Next for the owner:** the Sutradhar bug behind 2 API tests (from Shravani's note), the broad regression on the combined `main`, rerun of the stale T2/T3/T6/T8 builders; VI-09 (freeze and runs) waits for Harshita's metrics and statistics and the gold-sweep rescoring loop; VI-11 only if the freeze lands early.
- **Open for people:** HLDC and indictrans2 access requests; the privacy-boundary public-corpus rule and the pseudonymiser hook-in need Shravani's review (put in the PR description); S18's paper (Wachsmuth et al., ACL 2018) was cited from memory, verify; Sarvam char-priced endpoint prices are guesses (translate, transliterate, language-id, TTS); `.env` has `VS_SARVAM=off`, so Sarvam runs must export `VS_SARVAM=pseudonymised` after loading it.
- **Known weak spots:** G1 kappa 0.60 (weak_prima_facie 0.25, gravity 0.27); G3 previous_bail 0.26; Munshi cannot read image-only files offline (needs a vision model or OCR); Hindi native set is one court and two years.
- **Handoff notes to read:** `docs/handoff/` (pilot-hosted-model, gold-labeler, eval-jobs, data-and-models, citation-sc-metadata, munshi-real-pdf-reading, testsets-t2-t9, literature-sweep-4, eval-features when VI-07 ends).

## 0e. In flight when the usage limit hit (2026-10-24, about 18:30) and what to resume

**Why this section exists:** the 5-hour usage limit was about 85% used. Four agents were running; each was told to keep the code consistent, finish one item at a time, and write a handoff note in `docs/handoff/`. A snapshot of all uncommitted work (about 150 changed files) is in the session scratchpad (`snapshot-*.tgz`); nothing from this session after the 20 commits has been committed.

**Agents running at that point, and where their notes are:**
| Agent | Task | Handoff note |
|---|---|---|
| Workspace redesign | One-step-at-a-time case workspace (stepper, "what needs you", side source panel, chat drawer, Details drawer, plain labels, privacy wording fix) | `docs/handoff/workspace-redesign.md` |
| Literature sweep 1 | Sutradhar and retrieval variants (sufficiency stopping, Self-RAG/CRAG-style critique, adaptive depth, graph expansion), each default-off, cited, in `docs/literature-to-code-map.md` | `docs/handoff/literature-sweep-1.md` |
| Eval infrastructure | EV-07 driver and `make smoke`, EV-05 baselines (B6 first), EV-03 T1 builder, EV-06a ablation wrappers | `docs/handoff/eval-infrastructure.md` |
| Data and models | Full store build (background job), CrPC/NDPS statutes, Kathbath remainder, model download script, NOTICE, HLDC check, e-SCR attempt | `docs/handoff/data-and-models.md` |

**Status updates (2026-10-24, evening):**
- **Workspace redesign: finished** and live on port 3000 (builds clean; Vitest and Playwright not run, so the old tests fail on purpose). Not yet checked by eye: mobile layout, the source panel, the chat and Details drawers, the confirm dialogs. `frontend/DESIGN.md` still lacks a "Workspace principles" section. Details: `docs/handoff/workspace-redesign.md`.
- **Literature sweep 1: partly done.** Only **S3 sufficiency stopping** is finished (switch `Switches.stopping` = `rules` (default), `rules_llm`, `llm`; `for_variant("S3")`, `"S3b"`, alias `"A11b"`; module `agents/sutradhar/sufficiency.py`; 20 new tests plus a default-off golden-output check; cited to Joren et al. ICLR 2025, Sun et al. Findings of ACL 2026, Park et al. NeurIPS 2025 workshop; those details come from the literature review and were not re-checked on the official pages). **Not started:** S1 (Self-RAG/CRAG critique), S2 (adaptive depth), S5 (graph expansion), S4 (score-skew signal). The sweep's S-numbers follow the evaluation plan; the literature review numbers the same ideas differently (its S2 = plan S5, its R1 = S3, its R2 = S4). Test status: regression 2,146 passed, 16 skipped; the 30 targeted failures are the unbuilt graph (26) and 3 registry tests with an extra `b6` module, plus one unchecked. Details: `docs/handoff/literature-sweep-1.md`.

- **Eval infrastructure: done** (EV-03, EV-05, EV-06a, EV-07, PR-12; note `docs/handoff/eval-infrastructure.md`). All four tasks work offline.
  - **Driver:** `make smoke` exits 0 (case-0007 end to end, no LangGraph, the export gate still enforced), and `make eval-smoke` runs 3 real dev cases. Shards resume, and there is a run manifest.
  - **Baselines and ablations:** baselines B0, B0L, B0S, B1, B2, B3, B4, B6 and Full; ablation wrappers A1 to A10.
  - **T1 on real data:** test 200 (80 BNS-era, 137 after 2025-04, 22 High Courts), dev 50, open 120, blind 80 (hashed ids; the blind slice opens once with `--open-blind`, which needs the `eval-freeze-v1` git tag).
  - **Weak spots:** the 8-word overlap rule drops 68% of the clean test window, so T1 skews to orders with distinctive facts text. Gold is rule-only and provisional until a non-Qwen labeler runs. Citation resolution is 0 of 80 because `oil_metadata.jsonl` is missing. Dossier fields found in the test set: sections 84.5%, charge sheet 22%, arrest date 18%, co-accused bail 12.5%, custody days 12%, trial stage 6.5%, previous bail 2.5%. G7 is nearly empty (0.5%). Dev is all IPC-era.
  - **Left:** the `Switches` fields for the new arms (EV-01: `critic_mode`, `repair_mode`, `abhiyojak_isolation`, `retrieval_policy`, `store_prior`, `munshi_gap_policy`), jobs for RQ2, F1 to F4 and the S-variants, and the failing `tests/unit/eval` files owned by others (metrics 36, stats 16, features 18, ingestion pipelines 13) and `tests/unit/testsets` (T2 to T9, 31 failures).
  - **Changes to shared data:** `data/interim/splits.json` was rewritten with the T1 labels (backup `splits.json.pre-t1`); a path bug in `pipelines/gold/g2_cited_precedents.py` was fixed.

- **EV-01 switches: done** (note `docs/handoff/ev-01-switches.md`). `Switches` now has the fields for every planned variant (`retrieval_policy`, `weak_signal`, `graph_expansion`, `store_prior`, `munshi_gap_policy`, `repair_mode`, `critic_mode`, `abhiyojak_isolation`, `draft_mode`, `topology`, `plan_cache`, `urgency_policy`, `output_format`, the three S17 flags, `munshi_image_only`, `chunking`), all defaulting to today's behaviour. `for_variant` builds full, A1 to A10, P5 to P7, B5, S1 to S17 (and extra arms) and the plan aliases. **Behaviour implemented today:** full, A1 to A10, S3, S3b, P5, P6. Everything else fails loudly via `assert_variant_implemented`; each variant task must add its id to `IMPLEMENTED_VARIANTS` in `orchestration/switches.py`. Defaults to confirm: S15 `answer_only` (`reasoning_first` is the arm), S7 `sequential` (`hierarchy` is the arm), three separate S17 booleans, the extra `chunking` field, and the A12 "prior alone" arm being B5 with alias S6b.

- **Data and models: mostly done** (note `docs/handoff/data-and-models.md`; nothing left running).
  - **Full store build finished** in about 35 minutes (hashed-ngram embedder) and `data/stores/MANIFEST.json` is written (1.76 GB). The first build (5 h 20 min, stuck) was killed. The cause was the fuzzy case-name citation matching scoring every one of about 116K titles for each cited name. The fix is `pipelines/store_builders/fast_index.py` (only titles sharing a word with the cited party are scored, with a cache) plus progress logging; a citation whose parties share no whole word with the indexed title is no longer matched.
  - **Rows:** concordance 554, citations 3,492 (plan 100–300K, far below), reasoning 161,247, arguments 70,691, objections 55,024, similar 114,544, statutes 1,411. 115,376 orders used, 612 excluded. Citation resolution is 0.19. Wiring the Supreme Court metadata (`data/raw/open_india_law/sc_metadata.jsonl`) into the citation index is still to do and needs `pipelines/citation_graph/**`.
  - **Kathbath complete:** 3,130 of 3,130 Hindi test utterances (293 MB).
  - **Models (PR-21 done):** `scripts/download_models.sh` (tier from an argument or `VS_MODELS`, `--dry-run`, disk check, licence shown, resumable, SHA-256 verified), tier table under `weights:` in `configs/models.yaml`, `make models` and `make models-dry-run`. T1 helper models downloaded: BGE-M3 (2.31 GB), DeBERTa-v3-large NLI (0.88 GB), MiniCheck-RoBERTa-Large (1.42 GB); Whisper small skipped. T2 and T3 sizes in the table are approximate.
  - **NOTICE written** at the repo root. Licences for the four T1 models and IndicTrans2 are verified. Qwen, Llama, NLLB, fonts and libraries are marked "to verify". PyMuPDF is AGPL, and the IPC2BNS-Verify repo has no LICENSE file.
  - **Disk:** 12 GB free.
  - **Blocked, needs a person:**
    - **CrPC 1973, NDPS s.37 and the First Schedule:** every Indian government host refused or timed out from here, and no statute text was typed from memory. The wiring is ready (`StatuteStore.build` merges `data/gaps/statutes/*.jsonl`, with a test). A teammate must save the CrPC and NDPS PDFs from https://indiacode.nic.in/handle/123456789/15247 into `data/gaps/raw/`, extract the sections s.41, 41A, 50, 57, 167, 436, 436A, 437, 438, 439, the First Schedule and NDPS s.37 into `crpc.jsonl` and `ndps.jsonl` with a source URL on each row, then run `scripts/build_stores.sh --only statutes`. The steps are in `data/README.md`.
    - **HLDC:** no Hugging Face login on this machine. A teammate must accept the gated terms for `Exploration-Lab/IL-TUR` (licence CC BY-NC-SA 4.0), log in, and put the `bail` folder in `data/raw/hldc/`.
    - **e-SCR Hindi translations:** no published bulk download or reuse terms; written permission from the Supreme Court Registry or NIC is needed, or a small manual sample. The fallback is IndicTrans2 or NLLB translation.

- **Literature sweep 1: complete** (S3 earlier; S1, S2, S5 and S4 now; note `docs/handoff/literature-sweep-1.md`, rows in `docs/literature-to-code-map.md`). All opt-in and default-off (the golden default-run test still passes). Regression 2,168 passed, 16 skipped; targeted 980 passed; ruff clean.
  - **S1** `retrieval_policy='self_critique'` (`agents/sutradhar/critique.py`): Self-RAG (ICLR 2024) and CRAG (arXiv 2024) style critic with corrective actions.
  - **S2** `retrieval_policy='adaptive'` (`depth.py`): Adaptive-RAG (NAACL 2024) style none/single/multi depth.
  - **S5** `graph_expansion=True` (alias A16; `pipelines/citation_graph/expansion.py`, `CitationStore.expand`): personalised PageRank in the style of HippoRAG 2 (ICML 2025) and HippoRAG (NeurIPS 2024).
  - **S4** `weak_signal='skew'` (`skew.py`): SkewRoute (Findings of EMNLP 2025) style score-skew signal; the plan's Gini and top-gap measures are the plan's choice, not necessarily the paper's.
  - **Not done / assumptions:** the S4 AUROC metric (M19) is not built; the thresholds and constants (PPR damping 0.5, expansion weight 0.3, 5 expanded documents) are untuned; no comparison on the real stores has been run (G2 recall@10, share of Supreme Court roots); CRAG's correct/ambiguous/incorrect actions come from the plan's framing, not the paper page. Case-0007 is BNS-era, so under S2 every factor is classed "multi" there.
  - **Signature changes (optional args, default False):** `search_reasoning(..., expand_graph=False, with_scores=False)`; new `ReasoningStore.search_scored`/`search_docs`, `CitationStore.expand`/`graph`. The event that carries retrieval signals is now named "retrieval variant signals".

- **Landing colour and motion pass: done** (note `docs/handoff/landing-colour-motion.md`; builds clean; Vitest and Playwright not run). Full-width bands (cream hero with a saffron offset block, saffron tint "How it works", indigo "sources" band with a highlight sweep, neem tint "What you stay in control of", maroon closing band with a faint lattice, neutral footer), contrast pairs in `frontend/DESIGN.md`. The hero product loop plays once (8.55 s, every beat 180 to 250 ms, opacity and transform only), then rests; Replay is a quiet text button; it pauses on a hidden tab; reduced motion shows the final frame. Not yet checked by eye: the later loop frames after a fix, 360/768/1920 px after the change, the reduced-motion frame, paint time. Old unit and e2e specs still describe the earlier landing.

- **Literature sweep 2: complete** (note `docs/handoff/literature-sweep-2.md`; six rows under "Sweep 2" in `docs/literature-to-code-map.md`). All off by default, each with its own tests and a default-off golden check (`tests/unit/agents/vakeel/test_variants_golden.py`).
  - **S8 / A2b** `repair_mode='self_critique'`: self-critique-only repair, no NLI or re-retrieval (CRITIC, ICLR 2024; Huang et al., ICLR 2024; Zhang et al., Findings of ACL 2024).
  - **S10 / A8c** `abhiyojak_isolation=False`: Abhiyojak also reads Vakeel's notes (Wynn et al., "Talk Isn't Always Cheap", arXiv 2025).
  - **S9 / A8b** `critic_mode='sampling'`: k samples at an equal token budget (Debate or Vote, NeurIPS 2025; Should We Be Going MAD?, ICML 2024; Du et al., ICML 2024); lives in `eval/ablations/a8b_sampling_critic.py`.
  - **S11 / A8d** `critic_mode='three_role'`: Grader, Critic, Defender, Grader (CourtEval, Findings of ACL 2025). **S11b/c** `draft_mode='debate'` and `'vote'`.
  - **S15 / A13** `output_format='reasoning_first'`: a free reasoning field before the answer fields; stored but never cited (Let Me Speak Freely, EMNLP 2024 Industry; CRANE, ICML 2025).
  - **Not done:** S15b (`free_then_parse`); S15 covers Vakeel only (Peshkar and Sutradhar prompts untouched); no `configs/eval/runs.yaml` jobs for S8 to S11 or S15.
  - **Caveats:** the offline stand-ins are weak by design (offline S8 never repairs by itself; offline S10 ignores what it reads), so real effects need a hosted model. S10's flip rate is only a proxy (`conceded_share`) because there is no withdraw action. The S11b/c draft debate and vote spend about 3x and 4x the tokens without equalising them. The S9 budget stop uses an estimated sample cost.
  - **New:** `CaseGraphState.variant_signals`; `Switches` rejects `abhiyojak_isolation=False` with `critic_mode` `sampling` or `three_role`.

- **Literature sweep 3: complete** (note `docs/handoff/literature-sweep-3.md`; six rows under "Sweep 3" in `docs/literature-to-code-map.md`; three new golden default-run files for Peshkar, Munshi and Pairokar). Final regression 3,351 passed, 16 skipped; the one failure (`models/prefix.py` missing from the helper list in `test_interfaces.py`) was fixed and re-run alone (59 passed), but the full regression was not re-run after that fix.
  - **S17 / S17b-d (alias A15)** `no_typed_handoff`, `no_spotlighting`, `no_guard`: typed hand-off (CaMeL-style data/control separation as a channel rule enforced by `ask`, not CaMeL's interpreter), spotlighting (delimiting form only), the existing detector as guard. Papers: Beurer-Kellner et al. design patterns (arXiv 2025), CaMeL (Debenedetti et al., arXiv 2025), Spotlighting (Hines et al., arXiv 2024), AgentDojo (NeurIPS 2024 D&B); StruQ and SecAlign cited as related only. The `SusceptibleLLM` stand-in models susceptibility; it is not a measurement of any real model.
  - **S7 (A11a)** `munshi_gap_policy='hierarchy'` (`ingestion/hierarchy.py`): IntrAgent (ACL 2026) style page choice from the page index; on a constructed file it re-reads 1 page against 4 for sequential. Weights untuned.
  - **P7** `munshi_image_only`: every page to the vision route (cost reference).
  - **S14 / S14b / S14c / S14d:** agentic plan caching (NeurIPS 2025; on case-0007 the second same-signature case skips all 8 planning calls and tokens fall from 30,633 to 12,836, packs byte-identical), `urgency_policy` fifo / least-work / shortest-first (under the same 3-case budget urgency misses 0 deadline cases, FIFO misses 2), and a prefix-friendly prompt layout (`prefix_layout`, SGLang, KVFlow; a lower-bound signal).
  - **Not done:** the OCR vs text-layer cross-check of S17(c); datamarking and encoding forms of spotlighting; `runs.yaml` jobs for the new variants; real-model measurements (injection success on a real model, G1 recall with the plan cache, tuning S7 weights). Open: whether a batch sets `store_version` on `plans_of` when a store is rebuilt; whether to keep S14d as a named variant.

- **Live check of the hosted backends: passed (2026-10-25)** with `make live-smoke` (`scripts/live_smoke.py`, public text only, keys read from the untracked `.env` into the process and never printed). Sarvam: language ID (`en-IN`), English to Hindi translation (Devanagari output), chat, and text-to-speech all worked. OpenAI (`gpt-6-luna`): plain chat, structured JSON output (`{'arrest_date': '2024-08-20'}`), and a repeated call served free from the cache; so the model accepts the temperature and reasoning settings the client sends. The ledger shows 0.00002 USD spent of the 4.50 cap. A small call costs about 0.000004 USD, far less than the earlier estimate for a whole case. Not yet tested live: Sarvam speech-to-text and Vision, and the agents running on a hosted model end to end.

- **Literature sweep 4: complete** (note `docs/handoff/literature-sweep-4.md`; rows under "Sweep 4" in `docs/literature-to-code-map.md`). Broad regression 3,420 passed, 16 skipped. `Switches.implemented_variants()` now covers every id in the table, so no must or should variant is unbuilt.
  - **S6 / B5** `store_prior='order'` / `'only'` (`agents/sutradhar/store_prior.py`): a count-model router over (factor, section family, era, court), trained from TRAIN orders only by `python -m vakeel_sahayak.agents.sutradhar.store_prior train --orders FILE` (no manual labels; dev, test and blind rows are refused). AgentRouter (ACL 2026), GraphRouter and RouteLLM (ICLR 2025), MasRouter (ACL 2025, related only). **Untrained on real data:** without an artefact the prior is neutral.
  - **S12 / S12b** `topology='sequential'` / `'single_agent'`: Plan-and-Act (ICML 2025), "Why Do Multi-Agent LLM Systems Fail?" (NeurIPS 2025 D&B), "Towards a Science of Scaling Agent Systems" (arXiv 2025). `single_agent` still drafts through Vakeel's unchanged `delegate`.
  - **S16 / S16b** `chunking` = `fixed`, `recursive`, `semantic`, `page`, `proposition`, `late` (`stores/chunk_strategies.py`; Dense X, EMNLP 2024; Late Chunking, arXiv 2024; "Is Semantic Chunking Worth the Computational Cost?", Findings of NAACL 2025). The proposition splitter is a rule-based stand-in for the paper's trained one; late chunking is an approximation unless the embedder gives token vectors. No store was rebuilt.
  - **S13** workflow-search harness (`eval/runners/workflow_search.py`; AFlow and ADAS, ICLR 2025; MaAS, ICML 2025): dev-only grid or random search with caps; no real search run.
  - **Not done:** `configs/eval/runs.yaml` jobs for the new arms; real-data training of the store prior; true late chunking with BGE-M3 token vectors; author lists of several papers not re-checked.

- **First real-model pilot (2026-10-25), one T1 dev case on OpenAI `gpt-6-luna`:** it used 10 calls (6,624 tokens in, 1,169 out), cost **0.0013 USD**, took 314 seconds, and exposed two harness bugs: (1) Peshkar's claim checker needs `torch` in `auto` mode, so the dossier stayed empty; (2) Vakeel's payloads were refused by the privacy boundary because the evaluation driver feeds raw T1 names instead of pseudonymising the facts as the real intake does, so no ground could be drafted (only Sutradhar's 8 calls were real). Also learned: the agent roles declare client-text data, so hosted runs need `VS_EXTERNAL=pseudonymised`, not `public`; the driver now runs cases in a public scope (`_case_scope`) but that does not override the role's own declaration. A real case uses only about 7,700 tokens so far (the plan assumed 100K to 150K), though the drafting stage did not really run.

- **Test-set builders T2 to T9: built** (VI-06; note `docs/handoff/testsets-t2-t9.md`; outputs in `data/testsets/<set>/`, gitignored; `make testsets` works; order T4, T3, T2, T6, T9, T5, T8). `tests/unit/testsets`: T2 25/25, T3 11/11, T4 12/12, T5 7/7, T6 13/13, T9 13/13, T8 1 pass and 6 skipped (need `parler_tts`); only T7 is still a stub.
  - **Numbers:** T4 500 scenarios (default bail 200, undertrial 200, notice 50, 24-hour production 50; answers derived from the rule text by `testsets/rights_spec_writer.py`, which does not import `rights/`; the Radar agrees on all 500; this is a consistency check, not a legal one). T3 240 updates over 60 open T1 cases (baseline arrest date read from G3 for only 11 of 60; the rest constructed and labelled). T6 150 questions over 79 cases. T9 2,095 strings from 500 Supreme Court judgments (1,497 true, 598 distractors). T5 300 cases with 100 planted deadlines at 1 to 7 days from 2026-11-02. T2 600 bundles (100 cases × 6 kinds), 2,300 pages, 111 MB, 192 s. T8 300 utterances (150 Kathbath with audio; 150 dictations, transcripts only).
  - **Approximations:** T9's SCC, AIR, SCC OnLine and Cri LJ numbers are constructed (the corpus only has INSC and SCR), so it tests format handling, not real reporter numbers; case-name strings resolve 142 of 247. T2 has 2,300 pages instead of about 4,800 (no HLDC, no e-SCR); its Hindi order is templated, not translated; K6 is a raster page with an invisible Kruti-Dev-style text layer, not real legacy glyphs; degradation uses Pillow and NumPy, not Augraphy. T8 dictation audio is pending (Parler-TTS missing; `--synthesize` via Sarvam not run).
  - **New dependency:** PyMuPDF (AGPL) is now installed in `.venv` and is the `testsets` extra in `pyproject.toml`, noted in `NOTICE`. The network was too slow, so the packages were copied from the uv cache and `~/.local`; `pip install .[testsets]` is the supported route.
  - **Regression:** 3,437 passed, 3 failed. The 3 failures were skipped before and now run because PyMuPDF exists: `ingestion/test_signals.py::test_compute_signals_born_digital_pdf` and two in `tools_intake/test_documents_tools.py` (`split_bundle_flow1`, `classify_document_remand_order`). **Munshi's real-PDF reading code therefore has bugs that the offline path hid**; they are being fixed (see below).
  - **Open:** a team member should review the readings in `rights_spec_writer.py` (a year counted as 365 days; unsettled law returns CHECK). The F2 to F4 jobs in `eval/runners/jobs.py` can now be fed from these sets.

**First thing after the reset:** read the four handoff notes, then run `ruff check src`, the regression test command in section 5, and `cd frontend && npx tsc --noEmit -p . && npm run lint && npm run build`. If anything is half-edited, finish or fix it before starting new work. Check on the background store build (`docs/handoff/data-and-models.md` gives the log path).

**Queued, in this order (not started):**
1. **Landing page colour and animation pass:** a wider palette (saffron/ochre, deep indigo, neem green, with colour-block bands), a short hero product loop of 8 to 10 seconds that plays once, light reveal and hover motion. No pinned scenes, no long intros, none of the AI tells.
2. **Update the frontend tests** (Vitest and Playwright) to the redesigned shell and workspace; the old expectations will fail intentionally (Cases page title and numerals, top nav, stage-rail words, agent markup, Help route, mode chip, desk rank numerals).
3. **Swagger / OpenAPI documentation:** make `create_app()` mount all routers so `/docs` and `/openapi.json` work, export `docs/api/openapi.json`, and write `docs/api/README.md` (the routes are still stubs, so it documents the contract and marks what is not implemented).
4. **Literature sweeps 2 to 5:**
   - Sweep 2: verification and adversarial variants (self-critique-only, sampling critic, no isolation, reasoning-first output).
   - Sweep 3: Munshi hierarchy re-reading, injection defences, cache-friendly prompts and plan caching.
   - Sweep 4: routing and the remaining should-priority variants.
   - Sweep 5: apply the 25 proposed edits to `docs/plan.md` and check every citation.
   - Each sweep adds a section to `docs/literature-to-code-map.md` (paper, venue, year, link, switch, module, test, status).
5. Evaluation steps that need Ada (bring-up, real runs, freeze) and the remaining items in section 0.

**Rules to keep:** one backend and one frontend agent at a time at most; agents save as they go; no Claude attribution in any commit or document; commit only with the four-teammate strategy; API keys only in the environment; OpenAI spend capped at 5 USD.

## 0d. Decision on 2026-10-24: hosted LLMs are allowed

- The team has a **Sarvam API key** (all Sarvam models) and an **OpenAI API key worth about 5 USD**. We no longer need local open-weight models to run the system. This relaxes the plan's original "open weights, no paid API at run time" rule.
- **Keys** live only in environment variables (`SARVAM_API_KEY`, `OPENAI_API_KEY`) or an untracked `.env`. Never commit them.
- **OpenAI spend is a hard cap of 5 USD.** An OpenAI adapter must keep a persisted token and cost ledger, refuse calls past the cap, use the cheapest suitable model, and cache outputs. Put the large evaluation runs on Sarvam or the offline stand-ins.
- **Privacy rules stay:** hosted APIs only see public or constructed data and pseudonymised text; raw client files need counsel's recorded consent (the existing policy gate in `models/sarvam/policy.py`).
- **Evaluation consequence:** hosted models change over time, so every run records the model name, version and date (course rule). The GPU node-hour budget in the evaluation plan becomes a token and dollar budget; the plan documents still describe the GPU budget and need updating.
- **OpenAI adapter: built** (mocked HTTP only; no live call, because `OPENAI_API_KEY` is not set in this environment).
  - **Spend cap:** a SQLite ledger records every call (tokens and cost, never prompt text). It reserves the worst-case cost before each call and refuses it before any request goes out if the total would pass the cap. Default 4.50 USD; the code clamps any config or env value to 5.00. In-flight reservations count, so parallel calls cannot overshoot. Check spend with `make openai-spend`.
  - **Model:** default `gpt-6-luna` (0.10 / 0.50 USD per million input / output tokens, verified on the OpenAI pricing page on 2026-10-24). A model missing from the price table is refused. A response cache makes repeated temperature-0 calls free.
  - **Switches:** `VS_LLM_BACKEND=offline|local|sarvam|openai` picks the backend for the agent roles, `VS_LABELER` and `VS_TEACHER` pick the labeler and teacher (public data only), and `VS_EXTERNAL=off|public|pseudonymised|consented` is the shared privacy gate for all providers. Model families (qwen, llama, sarvam, openai, offline) are exposed, and `describe_run_models()` stamps model, version and date into each evaluation run.
  - **Tests:** 63 new in `tests/unit/models/test_openai.py`, all passing.
  - **To verify live:** whether `gpt-6-luna` accepts `temperature` and `reasoning_effort: none` (the client drops a rejected parameter and retries). The families rule allows the teacher and the judged system to share a family (Qwen) but forbids it for the labeler.
- **What this changes in the plans:** `docs/evaluation-plan.md` §7 (run plan), `docs/product-readiness.md` (hardware tiers, model download tasks PR-20 to PR-23, PR-33 to PR-35) and the team plan's Ada tasks; the independence of the B0L (prompted 32B) and labeler/teacher families also needs a re-check (OpenAI and Sarvam are both non-Qwen).

## 0c. Plans written on 2026-10-24 (read these first)

| Document | What it is |
|---|---|
| [docs/evaluation-plan.md](docs/evaluation-plan.md) | How the work will be presented like a paper: 42 falsifiable claims, baselines (B0–B6, with the course's four baseline types), 17 architecture variants S1–S17 based on the literature (8 must, 7 should, 2 could), 50 metrics, statistics (McNemar, bootstrap, Wilcoxon, Holm), a sealed blind slice, empty results tables and figures, the run budget, and threats to validity. Built on the course evaluation slides (L12), the guest lecture on Indian-language models, and RAG L14. |
| [docs/product-readiness.md](docs/product-readiness.md) | What is left to be a product a lawyer can use: acceptance criteria, gaps by area, a release plan, and 86 tasks PR-01…PR-86 with priorities, effort and a critical path. Defines a "Preview v0.9" scope. |
| [split.md](split.md) | Who does what from here (2026-10-25): four independent streams with file ownership, Harshita's lighter share, the merge waves, and appendices with the PR and review rules, history-sync steps, freeze and definition of done, and the evaluation job map. It replaces the earlier team plan (the `docs/team/` folder, now removed). |

**Findings that need the team's attention:**
- **The plan does not fit the time.** Committed work is 72.5 person-days against 61 (3.5 weeks) to 70 (4 weeks) of capacity. Fine-tuning, the RQ2 ingestion study and the F1–F8 feature evaluations are stretch items. The evaluation plan itself is about 408 node-hours at full size against about 255 available.
- The evaluation freeze cannot be at the start of week 2, because the graph, evaluation driver, metrics and T1 builder do not exist yet. The team plan recommends day 14 (hard limit day 15).
- Headline factor-recall must be paired with precision (arguing all 12 factors scores recall 1.0).
- The default Docker stack runs stand-in models; real quality on a lawyer's laptop is unmeasured and Qwen3-14B does not fit an 8 GB GPU.
- The frontend silently shows case-0007 demo data on any API error; a product build must be strict.

**Decisions before Day 1:** capacity (add a fifth person, or ship the Preview), the evaluation freeze date, squash merge and branch protection, who holds the three Ada accounts, and the product and evaluation decision lists (readiness D1–D11, evaluation §9).

## 0. Everything left to do (master checklist, 2026-10-21)

Order of priority: A and B unblock a runnable system; C and D produce the research results; E to H are data, review and cleanup. Details for each item are in the sections below and in `docs/plan.md`.

### A. Make the system run end to end (highest priority)
- [ ] **LangGraph flow** in `src/vakeel_sahayak/orchestration/graph.py`: Munshi → Peshkar → Gate 1 (interrupt) → Sutradhar ⇄ Vakeel ⇄ Abhiyojak → Gate 2 (interrupt) → export; SQLite checkpointer (thread id = case id); the change-set path (new document → Peshkar diff → Gate 1 re-approval → truth maintenance → partial redraft). Tests: `tests/unit/orchestration/test_graph.py` (about 30).
- [ ] **Plain-Python fallback** in `orchestration/fallback_state_machine.py` with the same gate rules; selected when langgraph is missing or `VS_ORCHESTRATOR=plain`. Tests: `test_fallback_state_machine.py` (about 4).
- [ ] **Real FastAPI routes** (`src/vakeel_sahayak/api/routers/*`; `api/app.py` `create_app()` still raises NotImplementedError): cases, upload, chat, SSE events, gates, export, desk, library. Today `api/asgi.py` returns 503 on `/api/*` and the UI falls back to demo data. Tests: `tests/unit/api` (116 failing), `tests/integration/test_api_routes.py`. The API must pin the shapes of the rights report and the hearing-prep card, which the frontend fixtures currently tolerate loosely. Library search must enforce the required `before` date on the server and return `sc_root` and `good_law`. `CaseSummary` needs a `last_activity` field.
- [ ] **DOCX export** in `src/vakeel_sahayak/export/*`: court-ready application (§8.2), List of Dates, annexure index, hearing-prep card, PDF. Tests: `tests/unit/export` (26 failing, 9 errors).
- [ ] **System tests** `tests/system` (257 failing before): they pass once the three items above exist. Real-model variants carry `models` / `gpu` markers.
- [ ] **Integration tests** `tests/integration` (107 failing before): re-run after the graph; fix what is left.
- [ ] Settle `request_approval(...).unresolved` wording between the code and the test (the test now expects plain ids).

### B. Verify what was built (nobody has done these)
- [ ] **A person uses the frontend in a browser** (`docker compose up`, http://localhost:3000): all frontend checks so far were automated (Vitest 233/233, Playwright 69/69 on a production build). Check visuals, the landing scenes, the workspace and the mobile layout.
- [ ] Fix the Playwright setup: the tests wanted chromium-1248 but 1243 was installed (the agent symlinked it). Run `npx playwright install`, or pin `@playwright/test` to the 1.59 line.
- [ ] One landing scroll test flakes under `next dev` with 8 workers (cold chunk compiles). Use `next start` for e2e, or lower `workers`.
- [ ] Run the Playwright container (`docker compose --profile test`), whose image pull was cancelled, and the GPU profile (`--profile real`).
- [ ] **Live Sarvam test** with a real key (only mocked HTTP so far). Confirm the `json_schema` response format. Set Sarvam's dashboard data retention to the shortest option. Decide whether `agents_14b` should switch to `runtime: sarvam` (the default stays Qwen).
- [ ] Install PyMuPDF (16 ingestion tests skip without it) and the real OCR, vision, translation and speech libraries; test the non-offline paths.
- [ ] Munshi: it reads each page twice on real files in tool mode, and its in-memory shelf starts empty each run (see `agents/munshi/toolkit.py`).
- [ ] Re-check the **Rights Radar rule texts** against the bare acts (week-0 item). Open readings: a bare "10 years" counts as `CHECK`; grounds of arrest are always `FLAG` when not communicated; IPC 420 → BNS 318(4) is treated as `SAME`; the Antil category D list is an assumption; the sexual-offence decline list is deliberately broad. *Kapil Wadhawan* and *M. Ravindran* were cited from memory.

### C. Evaluation (plan §15)
- [ ] Test-set builders T1–T9 in `testsets/` (T1 court-grounded, T2 messy bundles with Augraphy, T3 change sets, T4 rights scenarios, T5 batch, T6 chat, T7 safety, T8 speech incl. Sarvam TTS in `public_scope()`, T9 citation formats). Tests: `tests/unit/testsets`.
- [ ] Baselines B0–B4, ablations A1–A10, ingestion pipelines P1–P6, feature evals F1–F8, metrics, bootstrap/Wilcoxon/Holm statistics, retrieval-only analysis, failure analysis, runners in `eval/`. Tests: `tests/unit/eval` (175 failing).
- [ ] Use a non-Qwen labeler (Llama-3.1-8B, or Sarvam as the documented independent option) for gold agreement; report agreement and rule-only coverage.
- [ ] Restrict the test pool to High Court orders: `assign_splits` drew one Supreme Court judgment into the test set.

### D. Fine-tuning (plan §3 / §12)
- [ ] Teacher dossiers, NLI span filter, OCR-noise augmentation (30% of pairs), QLoRA training of Qwen3-4B on the Ada cluster, adapter merge. Tests: `tests/unit/finetune` (70 failing).
- [ ] Week-1 teacher pilot (Qwen3-32B on Ada vs a free Mistral API); measure throughput.

### E. Data (partly done; see section 5b)
- [ ] **HLDC**: a teammate requests access on Hugging Face (the `bail` config of `Exploration-Lab/IL-TUR`, non-commercial licence), then puts the `bail` folder in `data/raw/hldc/`. Fallback: NLLB-200 translation.
- [ ] **Statutes missing from Open India Law**: CrPC 1973, NDPS s.37 and the CrPC/BNSS First Schedule (bailable/cognisable) from India Code.
- [ ] **Open India Law**: only bail-related shards were kept (1.4 GB of 53.6 GB). The Hugging Face repo is gated; the ungated mirror was used. Request access if the full release is needed.
- [ ] **Kathbath**: only the first 1,000 of 3,130 Hindi test utterances were taken.
- [ ] **e-SCR / SUVAS Hindi judgments**: not attempted (optional; no bulk download).
- [ ] **IPC2BNS-Verify**: the repo has no LICENSE file despite an MIT badge. Ask the authors before redistributing.
- [ ] **Form layouts** (FIR IIF-1, remand order, custody certificate): no national templates found; build constructed ones.
- [ ] **Model weights**: none downloaded (Qwen3-4B/14B/32B, BGE-M3, DeBERTa-v3, MiniCheck, Surya, Qwen3-VL, IndicTrans2, Whisper, Llama-3.1-8B). `scripts/download_models.sh` is still a stub.
- [ ] **Full store build** (about 2 GB, about 85 minutes, about 200K reasoning paragraphs) on a machine with more disk; this laptop had about 20 GB free after clearing Docker's cache. Only a 2,000-order sample build ran. Wire the Supreme Court metadata into the citation index.
- [ ] Data risks found in week 0 that the plan did not expect:
  - FIR numbers appear in only 12.9% of orders, so the same-FIR leakage rule is weak.
  - About 17% of citations resolve (none of the SCC/AIR ones, because the corpus has no such field).
  - Only 5.9% of orders split cleanly, and several courts have no BNS-era orders (Madhya Pradesh 0, Kerala 3).
  - The text has glued-word artefacts ("theapplicant").

### F. Literature review (written; adoption still to do)
- [x] **Written:** `docs/literature-review-and-usage.md` is complete. It has 145 papers across 14 topics (114 top-venue, 8 workshop or other, 23 preprints; 34 rated 4 or 5), plus 24 more in the "not catalogued" table. 51 were checked on an official page; the other 94 carry an official link from the earlier sweep but their venue was not re-fetched (marked S in the Check column).
- [x] **IntrAgent** exists: ACL 2026 Long Papers, pp. 674–715 (https://aclanthology.org/2026.acl-long.29/). **AgentRouter** exists: ACL 2026 Long Papers, pp. 788–809 (https://aclanthology.org/2026.acl-long.33/). Both are only moderately relevant (only their ideas transfer), and the document says so.
- [x] Venue corrections found: olmOCR, AutoGen and Mem0 have no venue on arXiv, so they are now marked unconfirmed or preprint.
- [ ] **Apply the 25 proposed edits to `docs/plan.md`** (section 7 of the review). None are applied yet, because Phase 4 was built against the current plan. Also check that each proposal's module path exists (all do except the new `agents/sutradhar/store_prior.py`).
- [ ] **Implement the adoptions.** Must-priority items:
  - Munshi gap-driven re-reading with hierarchy-ranked page choice (ablation A11a).
  - Sutradhar sufficiency and stopping variants, with stopped-too-early and over-search rates (A11b).
  - A cost-quality frontier across budgets, and cost per passed case.
  - A self-critique-only arm against Vakeel's tool-grounded repair (A2b).
  - A sampling-only critic at equal tokens, and an Abhiyojak arm without context isolation (A8b, A8c).
  - Structured-output ordering with a free reasoning field before the answer fields (A13).
  - Injection defences (typed hand-off plus spotlighting), tested on T7 (A15).
  - A null-agent audit of every metric.
  - Position the project as bail preparation, not outcome prediction.
- [ ] Should-priority items: a learned store prior against the evidence contracts (baseline B5, ablation A12); oracle regret for the ingestion ladder; proposition and late-chunking variants in B3; implicit-staleness tests for truth maintenance; citation faithfulness by removal; a text-layer vs OCR cross-check for font-injected PDFs; scheduling-policy comparison and prefix caching for Pairokar; a policy for when to ask counsel; a LoRA rank sweep. The new baselines and ablations are B5, A2b, A8b–d, A11–A16 and P7.
- [ ] Caveats: contribution lines come from abstracts, not full-paper reads; several adopted ideas rest on 2026 preprints; data availability for IL-PCSR, IBPS and the legal hallucination benchmark is unchecked; the compute estimate for the extra runs is still "not yet estimated".

### G. Documents
- [ ] Update `docs/proposal/proposal.tex` and `proposal.pdf` (they are still v4; only `proposal.md` is v5); re-render the PDF and use `figures/architecture_v5` for the diagram.
- [ ] The proposal's new references [21]–[26] (Self-RAG, Adaptive-RAG, Docling, HLDC, Augraphy, Doyle 1979) were written from memory: verify authors, venues and links.
- [ ] Plan questions from the proposal agent: is the 3-questions-per-round limit per round or per case? Is the week 6–7 run schedule too tight? Do the RQ2 vision results come from the laptop's 4B model or Ada's 8B?
- [ ] Final report and demo video (plan week 8).

### H. Git and housekeeping
- [ ] **Push** the 20 local commits (branch `ideation-v1`); nothing has been pushed.
- [ ] Eight commits from 1–2 Oct mention Claude and are already on GitHub. Removing them needs a history rewrite and a force-push, which affects teammates' clones. Decide first.
- [ ] Open design choices still on defaults: an unconfirmed "overruled" treatment from cue words still raises the good-law flag; optional `confidence`/`route`/`lang` fields exist on `SourceRef` and `CaseChunk`; Devanagari and Latin spellings of one name get two aliases; re-ingesting a file duplicates its documents and events; counsel's answers to Munshi's questions are stored but not parsed into facts.
- [ ] Disk space is tight on the laptop: prune Docker build cache (`docker builder prune`) when needed.

## 0b. Do we have enough data? (assessment, 2026-10-21)

Based on the week-0 feasibility report (`data/interim/feasibility_report.md`), which used samples and heuristics that nobody has checked by hand. **Verdict: mostly yes for the core questions, with four weak spots and two blockers that are not data.**

**Enough**
- **Main test set (RQ1):** 1,483,143 High Court bail orders remain after filtering, and 88,121 of them split cleanly. The test pool has 94 BNS-era orders against the 60 needed, so the H1c pilot fallback is not needed.
- **Fine-tuning:** the training pool is far larger than the roughly 4,000 orders needed to get about 2,000 verified pairs.
- **Precedent index, argument bank, objection bank:** the 2,000-order sample build gave 3,414 reasoning paragraphs, which extrapolates to about 200K for the full set (within the plan's range).
- **Concordance:** 544 typed IPC↔BNS edges plus the 1,140-query benchmark.
- **Hindi speech test (T8):** 1,000 Kathbath utterances against the roughly 300 needed.
- **T3, T4, T5, T7:** constructed by us, so external data does not limit them.

**Weak or missing**
1. **Citations (biggest risk):**
   - Only about 17% resolve to Open India Law records, and none of the SCC/AIR ones, because the corpus has no such field.
   - Recall@10 of court-cited precedents (the RQ2 / H1c metric) would be scored on a thin subset per order.
   - The citation graph and the good-law check will be sparse.
   - Wiring in the metadata of the 37,014 Supreme Court judgments should help, but by an unknown amount.
2. **Dossier ground truth:**
   - FIR numbers appear in 12.9% of orders and offence dates in 4.8%, so accuracy on those fields is measured on few examples.
   - The same-FIR leakage rule is also weak.
3. **Test-set skew:** only clean-splitting orders qualify. Allahabad and Madras carry most BNS-era orders, while Madhya Pradesh has 0 and Kerala 3, so results may not generalise across High Courts.
4. **Missing statutes:** no CrPC 1973, no NDPS s.37 and no bailable/cognisable table, so the statute store is incomplete. This is fixable from India Code.

**Not data, but equally blocking**
- **No model weights are downloaded.** Qwen3-4B, 14B and 32B, the labeler and the embedder total many tens of GB. They do not fit on the laptop (about 20 GB free), so they belong on the Ada cluster.
- **HLDC is blocked** (manual approval needed). The fallback, NLLB translation, works but gives weaker Hindi tests.

**To do about it**
- [ ] Add a coverage report to the citation and dossier metrics, so thin evidence is visible in the results.
- [ ] Wire the Supreme Court metadata into the citation index and re-measure the resolution rate.
- [ ] Fetch the missing statutes from India Code.
- [ ] Request HLDC access.
- [ ] Report results per court and check whether the test sample can be balanced across courts.
- [ ] Download the model weights on Ada and size the disk before the real runs.

## 1. Plan v5 (done)

**File:** [docs/plan.md](docs/plan.md), rewritten from v4 to v5 in response to the TA's feedback.

**TA feedback, and how v5 answers it** (Section 0 of the plan maps each point):

| TA feedback | Where the plan answers it |
|---|---|
| How are different kinds of PDF handled? | Munshi, the ingestion agent (§4) |
| Ingestion must be an agent | Munshi's agent loop (§4.3) |
| Use several RAG databases | Ten stores on four shelves (§5) |
| An agent must orchestrate what comes from each database | Sutradhar, with evidence contracts (§6) |
| Not novel in agentic engineering | §7–11 and §14 |
| Required baselines | B0–B4 (§15.3) |
| Frame it as an engineering problem | §1.2 |

**Decisions made in ideation:**

- **Features:** all eight new ones.
  - Agentic: prosecution sparring (Abhiyojak), incremental redrafting (truth maintenance), Rights Radar, batch triage desk (Pairokar).
  - Lawyer-facing: court-ready application, hearing-prep card, precedent explorer, Hindi and voice intake.
- **Evaluation:** every feature is evaluated fully (F1–F8), with its own baseline or ablation.
- **Agent names:** court-office names: Munshi, Peshkar, Sutradhar, Vakeel, Abhiyojak, Pairokar.
- **Frontend** (plan §13):
  - Next.js, replacing Streamlit.
  - "Manuscript" palette (maroon, cream and gold), with contrast checked.
  - The landing page combines all four concepts: Nyay ki Devi hero, a citizen's journey, geometry-of-justice transitions, a living-manuscript finale.
  - Each agent gets its own animation in the app.
  - The workspace is a stage rail above three panes.
- **Compute:** about 1,220 RTX 2080 Ti GPU-hours, about 56 Ada sessions (73 with buffer). That is about twice v4's budget, and needs all three accounts.

**To verify in week 0:**
- The Rights Radar rule texts (Appendix C). *Kapil Wadhawan* and *M. Ravindran* were cited from memory.
- Licences for HLDC, Kathbath, Surya weights and Indic Parler-TTS.

**Open questions raised by the proposal agent:**
- Is the limit of 3 questions to counsel per round or per case?
- The week 6–7 run schedule is tight.
- Do the RQ2 vision-model results come from the laptop's 4B model or Ada's 8B model?

## 2. Proposal (done)

**[docs/proposal/proposal.md](docs/proposal/proposal.md)** is rewritten to match plan v5 (≈584 lines, up from ≈477).

**New architecture diagram:**
- [docs/proposal/figures/architecture_v5.mmd](docs/proposal/figures/architecture_v5.mmd) is the Mermaid source.
- It is rendered as [.svg](docs/proposal/figures/architecture_v5.svg) and [.png](docs/proposal/figures/architecture_v5.png).
- The same diagram is embedded in §7 of proposal.md.

**Not updated (still v4):** `proposal.tex`, `proposal.pdf` and the old `figures/architecture.mmd`/`.pdf`.

**To check:** references [21]–[26] (Self-RAG, Adaptive-RAG, Docling, HLDC, Augraphy, Doyle 1979) were appended with authors and IDs written from memory. Verify them, and renumber by first appearance if wanted.

## 3. Project skeleton (done; stubs only, no logic)

**Size:** 443 files were created. `README.md` (repository layout section) and `.gitignore` were modified.

**Python package:** [src/vakeel_sahayak/](src/vakeel_sahayak/).
- **Agents:** the six agents.
- **Tools:** all 39 plan-named tools, each a function plus a `<NAME>_SPEC`.
- **Stores and contracts:** the 10 stores, and 12 evidence-contract YAMLs.
- **Rights Radar:** an engine plus 7 rules.
- **Other modules:** ingestion, orchestration (with ablation switches), truth maintenance, batch, privacy, model clients, export, FastAPI API, pipelines, fine-tuning, test-set construction, eval.
- **Stubs:** bodies are `raise NotImplementedError`. Schemas, enums and YAML files are real.
- **Import check:** all 306 modules import cleanly in `.venv`.

**Configs and scripts:**
- [configs/](configs/): YAML for models, stores, budgets, thresholds, tools and rights rules; `bail_sections.yaml` has 5 extra rows marked TODO for verification.
- [scripts/ada/](scripts/ada/): the session shard runner and the QLoRA sbatch job.
- `data/`, `Makefile`, `.env.example`.

**Frontend:** [frontend/](frontend/) is a Next.js stub with:
- routes `/`, `/cases`, `/case/[id]`, `/desk`, `/library`, `/about`;
- landing scenes 0–6, the six agent animations and the workspace tabs;
- [styles/tokens.css](frontend/styles/tokens.css) with the palette.

**Guide for coding agents:** [docs/architecture/skeleton.md](docs/architecture/skeleton.md) maps each plan section to its module and sets the conventions to follow.

**Interpretations to review:**
- 9 of the 12 factor IDs were chosen by the agent, for example `undertrial_period`.
- Contract slots beyond the parity example were inferred from plan Appendix B.

## 4. Test suite: complete (written, not run)

The suite is now written for every layer in the brief. **No test has been run**, not even `--collect-only`: the code is all stubs, and
the earlier instruction stands (run tests only after the code is implemented). Details, layout, markers and the plan-section map are in
[tests/README.md](tests/README.md).

**What exists** (about 2,130 Python test functions in 173 files, plus the frontend tests):
- **Unit tests** (`tests/unit/`, 1,834 functions in 150 files, 27 folders): schemas, record, contracts, config, tools and tool registry, intake/law/case
  tools, rights, ingestion, stores, orchestration, truth maintenance, batch, privacy, agents (all 6), models, pipelines, eval. The four
  folders that were empty are now filled:
  - `api/`: app and dependencies, and the routers for cases, upload (files and dictation), chat, SSE events, gates, export (403 before
    Gate 2), desk and library, with FastAPI `TestClient`;
  - `export/`: the application sections, List of Dates from the timeline, the DOCX application (needs python-docx), the annexure index,
    the "AI-generated draft" banner, the hearing card, the gated exporter;
  - `pipelines/concordance/`: IPC to BNS edge types (same/split/merged/reworded/new), IPC 420 to BNS 318(4), the ten-row bail table
    (CrPC 436/436A/437/438/439 to BNSS 478/479/480/482/483);
  - `pipelines/store_builders/`: one module per builder (statutes, concordance, reasoning, arguments, objections, citations, similar) plus
    `build_all`: part-aware chunking, metadata fields, reasoning-only authorities, leakage exclusions.
  - The last gaps are now closed (370 functions in 27 new files, all with fakes and no network):
    - `finetune/` (77): span-check filtering keeps only all-pass orders, noise augmentation (30% of pairs get an OCR-of-degraded-render input,
      target unchanged), the QLoRA config (r=16, 2 epochs, FP16, one GPU, the only sbatch job), the SFT dataset with test and same-FIR
      orders excluded, resumable teacher shards, and the teacher-pilot decision rule (more verified pairs per day wins; the API only if
      terms, cost and pinned-and-cached conditions all hold) with the family rule;
    - `testsets/` (108): T1-T9 sizes and composition (200 with at least 60 BNS-era and an 8-gram leakage check; T2 companions and renderers K1-K6;
      T3 three change types plus 60 no-op controls; T4 day 59/60/61, one-third vs one-half, 7 vs 10 years, first-time vs repeat; T5 deadlines
      planted in the next 7 days; T6-T9), construction-known answers and deterministic seeds;
    - `eval/` additions (82): baselines B0-B4 and what each isolates, ablations A1-A10 as runs (switches reach the Full system, per-case saving,
      resume, sharding), features F1-F8 (`score` on hand-checked run directories), ingestion pipelines P1-P6 and Munshi (backend call counts,
      per-kind breakdown), runners (resumable shards, 3 runs vs 1 run, only QLoRA is a batch job);
    - tool modules `tools_case/` (21), `tools_caselaw/` (38), `tools_advocacy/` (10), `tools_drafting/` (34): argument validation, store
      routing, reasoning-only authorities, the good-law check blocking overruled citations, `render_citation` from metadata only, `export`
      gated and never bulk.
- **Integration tests** (`tests/integration/`, 112 new functions in 8 files): Munshi to Peshkar on the 14-page bundle; Sutradhar with fake
  stores (plan, assess, relax, budget stop, missing slots as open issues); Vakeel and Abhiyojak sparring (context isolation, ungrounded
  objections discarded, UNANSWERED to NEEDS_REVIEW); the change-set flow (diff, re-approval, only affected grounds redrafted,
  no-op control); the event log (resume, trace, dependencies); gate interrupts with export blocked before Gate 2; the API end to end
  with SSE; the Pairokar queue resuming after an interrupted shard with the shared cache.
- **System tests** (`tests/system/`, 176 functions in 14 files, about 290 cases once parametrised; one file per scenario):
  - user flows 1-7 of plan §13.6: `test_flow1_messy_bundle.py` (22), `test_flow2_quick_chat.py` (15), `test_flow3_brief_spar_export.py` (19),
    `test_flow4_case_moves_on.py` (10), `test_flow5_dictated_hindi.py` (10), `test_flow6_batch_desk.py` (13, the 120-file desk is marked
    `slow`), `test_flow7_library.py` (15);
  - the T7 safety suite: `test_t7_planted_instructions.py` (11; digital, scanned, Hindi and handwritten pages, and a fooled planner),
    `test_t7_pressure.py` (10), `test_t7_bulk_export.py` (9), `test_t7_prediction_lay_advice.py` (9), `test_t7_name_leaks.py` (12),
    `test_t7_sensitive_matters.py` (11), `test_t7_draft_label.py` (10);
  - `_helpers.py` (the `Scenario` driver) and `_scripts.py` (planted instructions, pressure prompts, planted names, the fooled planner,
    the by-factor drafter). The earlier consolidated `test_user_flows.py` (22) and `test_safety_t7.py` (25) were split into these files, with
    every case carried over; copies are not kept in the repo.
  - Six real-model variants carry `@pytest.mark.models` (most also `gpu`) and are skipped by default.
- **Shared code:** `tests/conftest.py`, `tests/fakes/`, `tests/fixtures/` (case-0007, statutes, concordance, paragraphs, PDF generator).
- **Frontend:** Vitest (`frontend/tests/unit/`, 9 files: tokens, status map, stage rail, reduced motion, api client, SSE hook, brand, fixtures)
  and Playwright (`frontend/e2e/`, 11 specs, 52 tests: landing scenes 0-6, reduced-motion storyboard, the three workspace panes, Gate 1 and
  Gate 2, flows 1, 2, 3, 4, 5 and 6, library). `flow4_case_moves_on.spec.ts` (new charge-sheet order, changed fields highlighted, re-approve,
  only G2 redrafted and highlighted; plus a duplicate-document control) and `flow5_dictated_case.spec.ts` (Hindi dictation through the mic, read-back,
  USER_STATED facts, "per counsel, not on record") are new. Hooks are in `e2e/testids.ts`, the "change" and "dictation" scenarios in
  `e2e/mockBackend.ts`, and nine new JSON fixtures in `e2e/fixtures/` (guarded by `tests/unit/e2eFixtures.test.ts`).
- **Configs:** `pyproject.toml` has the pytest config (testpaths, markers unit/integration/system/gpu/models/slow, default
  `-m "not gpu and not models"`); `Makefile` has `test-unit`, `test-integration`, `test-system`, `test-frontend` (and `test-e2e`,
  `test-models`, `test-collect`).

**Static checks done** (nothing executed): `py_compile` and `ruff check --select F,E9` over all of `tests/` (the final gap-filling pass: its 27 new
Python files plus their helpers) are clean (17 unused imports
in 15 earlier files were removed; no file was found truncated); imported names were resolved against the source; `tsc --noEmit` on the frontend is clean.

**Expect all of it to fail until the modules are implemented.** Assumptions the tests make where the plan is silent are marked
`# ASSUMPTION:` (about 270; `grep -rn ASSUMPTION tests frontend/tests frontend/e2e`); things the skeleton lacks are marked `# SKELETON-GAP:`:
no API route lets counsel resolve a Gate 2 checklist item, and nothing serves the hearing card's "conditions courts impose". The gap-filling pass
added more: no function applies the teacher-pilot decision rule or the family rule (`choose_teacher`, `verified_pairs_per_day`,
`assert_family_rule` are the intended names in `finetune/teacher_dossiers.py`); no `ChangeSet` REST route (flow 4 reads it from SSE events) and no
route that confirms a dictation read-back (flow 5 uses the chat route); `check_claim(claim, refs)` has no case id, so fact support and the
transfer flag cannot be tested on the tool alone; B1 and B2 have no combined index or whole-order text store; the per-kind breakdown,
escalation-rate and questions-asked metrics, B3's best-variant choice and B4's RRF have no function yet; no TTS client for T8.

**Known gaps** (outside the brief): no unit tests yet for `tools/dossier.py` and `tools/interaction.py` (exercised through the fake toolbox, the
agent tests and `tools_intake/test_privacy_ask_user.py`); the Playwright specs need the real UI hooks from `e2e/testids.ts` before they can pass.

**Side effects of the earlier test agents to review or clean up:**
- The skeleton files `src/vakeel_sahayak/batch/queue.py` and `src/vakeel_sahayak/orchestration/switches.py` were edited after the skeleton was finished. Review those edits.
- `pyproject.toml` and `Makefile` were edited (pytest config, markers, test targets).
- pytest, pytest-asyncio and hypothesis were installed in `.venv`.
- `npm install` was run in `frontend/`, creating `node_modules/`, `package-lock.json` and `tsconfig.tsbuildinfo`.
- A stray 25 MB `pymupdf-*.whl` was downloaded into the repo root. Delete it, or add it to `.gitignore`.
- It is not confirmed whether any tests were executed before the stop.

## 5. Coding phases

Each phase works like this:
1. A coding agent implements the phase from plan.md alone, without seeing `tests/`.
2. Only that phase's tests are run.
3. A reconcile agent fixes the code by default. It changes a test only where the test contradicts the plan, and marks each such change `# RECONCILED`.

| Phase | Scope | Tests that check it | Status |
|---|---|---|---|
| 1. Foundations | config, schemas, event log and case record, contracts, tool registry with gated export, Rights Radar (7 rules), date_calc / map_section / transfer_check / statute tools, privacy (pseudonymisation, boundary, injection guard, leak check, sensitive matters), concordance pipeline | `tests/unit/{schemas,record,contracts,config,tools,tools_law_case,rights,privacy,pipelines/concordance}` | **Done** |
| 2. Stores and data pipelines | order splitter, section extraction, factor tagger, date splits and leakage, citation graph and good-law check, rule-based gold labels G1–G7, the 8 remaining stores (SQLite FTS5 + optional LanceDB/BGE-M3), store builders, store tools | `tests/unit/{stores,pipelines,tools_caselaw,tools_advocacy,tools_case}` | **Done** |
| 3. Munshi ingestion | page quality signals, the routing ladder (text layer → layout → OCR → vision → ask counsel), input kinds K1–K10, bundle splitting and document classification, filing into the case shelf, gap checklist, conflict detection, Hindi (OCR + IndicTrans2), voice intake (Whisper/IndicConformer + read-back), intake tools | `tests/unit/{ingestion,tools_intake}` | **Done.** Phase 3 unit tests: 281 passed, 16 skipped (needs PyMuPDF), 0 failed. Three tests were changed, each marked `# RECONCILED` (K5 uses the new `devanagari_share` signal; the conflict field is named `arrest_date`; the `file_item` items carry a `case_id`). |
| 4. Agents and orchestration | model clients (vLLM, local 4B, vision model, NLI, labeler), Peshkar (dossier, List of Dates, change detection), Sutradhar (evidence contracts, plans, sufficiency, budgets, chat routing), Vakeel (drafting, check and repair), Abhiyojak (sparring, context isolation), truth maintenance (incremental redrafting), Pairokar (urgency triage, queue, shared cache), LangGraph graph with gate interrupts, ablation switches | `tests/unit/{models,agents,orchestration,truth_maintenance,batch,tools_drafting}` + `tests/integration` | **Mostly done; the LangGraph flow is left for teammates.** All six agents are built and pass their unit tests: Munshi, Peshkar (10), Sutradhar (133), Vakeel (42), Abhiyojak (28), Pairokar + batch desk (83), plus truth maintenance (60) and the core (287). Phases 1–4 regression: 2,590 passed, 16 skipped (PyMuPDF), 0 failed. Each agent was run offline on case-0007 in a scratch script.

**Left for teammates:** `orchestration/graph.py` and `orchestration/fallback_state_machine.py` (about 34 unit tests plus the integration and system tests wait on them). |

**Done and green:**
- Core (model clients incl. an offline LLM and NLI, structured output, budgets, ablation switches, gates, agent base class, drafting tools, LangGraph + SQLite checkpointer): 287 tests pass.
- Peshkar: its 10 tests pass, and an offline run on case-0007 gives the full dossier (custody 167 days), the List of Dates, the Rights report, and a change set when a conflicting remand order arrives.

**To do:** Sutradhar, Vakeel, Abhiyojak, truth maintenance, Pairokar and batch, then the LangGraph graph and fallback state machine (`orchestration/graph.py`, `fallback_state_machine.py`; about 34 tests wait on them).

**Known:** 3 of Munshi's own agent tests (`tests/unit/agents/munshi/test_agent.py`) fail on `search_pages` / `ask_user` call counts, because Munshi calls the ingestion modules directly. Regression: 2,113 passed, 3 failed. |
1. a core agent (model clients, offline LLM, structured output, budgets, switches, agent base, drafting tools, langgraph install);
2. four parallel builds (Peshkar; Sutradhar; Vakeel + Abhiyojak; truth maintenance + Pairokar/batch), none of which see the tests;
3. wiring (the LangGraph graph with gate interrupts, a fallback state machine, baselines, an end-to-end offline run);
4. five parallel reconcilers, then integration;
5. up to 2 review rounds (plan fidelity, safety and privacy, robustness, test integrity) with skeptic verification, then fixes and a gate. |
| 5. API and export | FastAPI routers (cases, upload, chat, SSE events, gates, export, desk, library), the court-ready DOCX application, List of Dates, annexure index, hearing-prep card, PDF export | `tests/unit/{api,export}` + `tests/integration/test_api_routes.py` + `tests/system` | To do |
| 6. Frontend | design system (Manuscript tokens, type), landing page scenes 0–6 with GSAP, the six agent animations, the workspace (stage rail + 3 panes + tabs), cause list, desk, library, about, SSE client | `frontend/tests` (Vitest) + `frontend/e2e` (Playwright) | **Done.** All pages are built: landing (scenes 0–6, Lenis, static storyboard for reduced motion), six agent animations, the workspace (stage rail, case file with PDF highlights, chat, trace graph, gate modal, six tabs), cause list, batch desk, library (citation graph and IPC↔BNS bridge) and about. It runs in demo mode on case-0007 data when no API is reachable.

**Checks:** Vitest 233/233; Playwright 69/69 on a production server (the first run had 114 Vitest and 15 Playwright failures); `tsc`, `lint` and `build` are clean. It found and fixed real bugs: dialogs off-screen, crashes on unusual API data, first-click races, a scroll jump on the landing page, and several accessibility issues.

**Risks and open items:**
- Under `next dev` with 8 workers, one landing scroll spec flakes in most full runs (cold chunk compiles). Production runs never did.
- Playwright 1.64 wanted chromium-1248 but only 1243 was installed; the agent symlinked it. Run `npx playwright install`, or pin `@playwright/test` to the 1.59 line.
- The e2e rights and prep fixtures don't match the typed models; the UI tolerates both. The backend should pin those shapes.
- Nobody has looked at it in a browser yet. Visual polish is unreviewed.
- Library search takes only a query; the filters run in the browser, so the backend must enforce the before-date. `CaseSummary` has no `last_activity`, and search hits lack `sc_root` and `good_law`. |
1. a foundation agent;
2. six parallel tracks (landing art and scenes 0–3; scenes 4–6 and orchestrator; agent animations; workspace shell; workspace tabs; other pages);
3. integration;
4. a test reconcile pass (Vitest + Playwright);
5. up to 2 rounds of review over 5 lenses (plan fidelity, accessibility, motion/performance, data contract, visual design), with skeptic verification, then fixes and a gate.

The app runs in demo mode from case-0007 mock data until the backend (Phases 4–5) exists. |
| 7. Evaluation and training | test-set construction T1–T9 (rendering + Augraphy, change sets, rights scenarios, speech), baselines B0–B4, ablations A1–A10, ingestion pipelines P1–P6, feature evals F1–F8, metrics and statistics, teacher dossiers + QLoRA fine-tuning, Ada shard scripts | `tests/unit/{eval,finetune,testsets}` | To do |

**Test isolation (2026-10-15):**
- `tests/conftest.py` has an autouse fixture that gives every test its own `VS_DATA_DIR`. Before this, tests wrote case event logs into `data/cases/`, and stale questions there broke later runs.
- `test_load_config_paths_section` clears the override, because it checks the default paths.
- After the change, Phases 1–3 together give **1,894 passed, 20 skipped, 0 failed**, and `data/cases/` stays empty.

**How Phases 1 and 2 were checked:**
- Phase 1 + 2 unit tests: **1,613 passed, 4 skipped, 0 failed**. The 4 skipped need langgraph (Phase 4).
- No test file has been changed to make the code pass; there are no `# RECONCILED` markers.
- `ruff check src` is clean.
- Phase 2 history:
  1. The first run gave 482 passed, 103 failed.
  2. The reconcile agent fixed most of them before it hit the usage limit, leaving 14.
  3. Those last 14 were all in the case-shelf tools (`get_timeline`, `get_fact`, `search_case_docs`). They now read from the case stores through `open_store` instead of re-folding the event log, and `get_timeline` rejects malformed or inverted date windows.
- `assign_splits` no longer takes 17–34 s per test; all Phase 2 tests run in about 12 s.

**Phase 2 decisions to review:**
- Every shared-store search needs a `before` date, to block leakage. Analysis code passes `9999-12-31` for no limit.
- Until the Llama labeler is connected, citation treatments come from cue words only, so an unagreed "overruled" still triggers the good-law flag.
- Orders with the same FIR are grouped across courts. This can over-group same-named police stations in different districts.
- Authority weights are court 0.35, bench 0.15, citations 0.35, recency 0.15. They are to be tuned on dev.
- Store files are `<shelf>/<name>.sqlite`. An unbuilt shared store opens empty, so a search on it returns no results.
- `pipelines/oil_ingest.py` (downloading Open India Law) is still a stub, until the data is pulled in week 1.

**Phase 1 choices to confirm in week 0:**
- A bare "10 years" maximum is treated as `CHECK`, the same as "may extend to ten years".
- Missing communication of the grounds of arrest is always `FLAG`; the retroactivity question is noted in the detail text.
- IPC 420 → BNS 318(4) is treated as `SAME`, and 436A → 479 as `REWORDED`.
- The Antil category D list of economic-offence sections is an assumption.
- The sexual-offence decline list is deliberately broad.
- The IPC2BNS-Verify file format is guessed.

**Known outside Phase 1:** `tests/unit/tools_drafting/test_export_and_approval_tools.py` expects `unresolved == ["antecedents"]`, but the code gives `["UNSUPPORTED:antecedents"]`. This is to be settled in Phase 5.

**Phase 3 open questions:**
- Should `SourceRef` and `CaseChunk` gain optional `confidence`, `route` and `lang` fields? Today confidence is stored only in the event log.
- Re-reading a document files new `-r1` chunks beside the old ones, because `case.docs` has no supersede.
- The same person written in Devanagari and in Latin gets two aliases until a transliteration step is added.
- Ingesting the same file twice creates duplicate documents and events.
- Counsel's answers to Munshi's questions are stored but not yet parsed into facts. This is to be wired with the Phase 4 gate interrupts.
- The offline translator is a word glossary, not IndicTrans2. The real models are written against the library APIs but not yet tested.

**Defaults chosen on 2026-10-15 (change any of these if you disagree):**
- An "overruled" treatment taken from cue words alone still raises the good-law flag, labelled "unconfirmed", until the Llama labeler is connected.
- Optional `confidence`, `route` and `lang` fields are to be added to `SourceRef` and `CaseChunk` in Phase 4.
- Transliteration-based alias merging (Devanagari vs Latin names) is deferred.
- Your two reference screenshots no longer exist on disk, so the frontend follows plan §13.2's description of the Hugh James and LawStatu elements.

## 5b. Cross-cutting work added on 2026-10-19

**Sarvam API integration (done; checked against mocked HTTP only)**
- Package `models/sarvam/`: HTTP client with retries, typed wrappers, a privacy policy gate, and adapters for vision/OCR, translation, speech-to-text (Saaras), LLM (Sarvam-105B), text-to-speech (Bulbul) and language ID.
- **Off by default.** `VS_SARVAM=off|public|pseudonymised|consented` and the env var `SARVAM_API_KEY` (read only from the environment, never from files).
  - `public`: public or constructed data only.
  - `pseudonymised`: also client text, after the privacy boundary check.
  - `consented`: also raw pages and audio, only for cases with a counsel-recorded consent event.
- Falls back to the local model whenever Sarvam is off, blocked, or fails.
- Tests: 60 new in `tests/unit/models/test_sarvam.py`; all pass. Three small `# RECONCILED` edits in `test_interfaces.py`.
- **No live call has been made, because no key was set in this environment.** The `json_schema` response format is an assumption (the client retries in `json_object` mode on a 400/422).
- Open: retention is a workspace setting in the Sarvam dashboard and cannot be enforced from code, so someone must set it to the shortest option. `agents_14b` is still Qwen; switch with `runtime: sarvam` if wanted. No test-set code calls Sarvam TTS yet (needed for T8).

**Docker (done)**
- `docker compose up` starts a healthy backend and frontend: http://localhost:3000 (UI), :8000 (API), bound to 127.0.0.1. Data lives in the `vs_data` volume.
- Backend image 381 MB, frontend image 245 MB. Cold build about 16 minutes; warm start about 12 seconds.
- Optional profiles: `real` (vLLM + heavy extras, needs the NVIDIA toolkit), `test` (pytest, Vitest, Playwright e2e), `data` (dataset job). Guide: `DOCKER.md`.
- The API routes are still stubs, so the container serves `/healthz` and answers `/api/*` with 503; the frontend then uses its demo mode.
- Not verified: the Playwright e2e container (the image pull was cancelled) and the GPU profile.

**Datasets (week-0, done in part)**
- Open India Law v2026.08.1: the Hugging Face repo is gated, so the ungated mirror named in its README was used. About 1.4 GB of bail-related shards were kept out of 53.6 GB scanned. 1,483,143 High Court bail orders after removing sexual-offence, POCSO and juvenile matters (about 235K were filtered out); 662 Supreme Court judgments discuss bail.
- Statutes: 1,411 rows (IPC, BNSS, BNS, UAPA s.43D, PMLA s.45). **Gaps:** no CrPC 1973, no NDPS s.37, and no CrPC/BNSS First Schedule (so "bailable" and "cognisable" are unset). Get these from India Code.
- IPC2BNS-Verify (commit 8d3e770): 544 typed edges and the 1,140-query benchmark. The repo has no LICENSE file despite an MIT badge; ask the authors before redistributing.
- Kathbath: first 1,000 of 3,130 Hindi test utterances.
- **HLDC: blocked.** It needs manual access approval on Hugging Face (the `bail` config of `Exploration-Lab/IL-TUR`, a non-commercial licence). A teammate must request access, then put the `bail` folder in `data/raw/hldc/`. Fallback: NLLB-200 translation. The e-SCR Hindi set was not attempted (optional).
- Interim files in `data/interim/`: `orders.jsonl` (115,988-order sample), `statutes.jsonl`, `concordance_edges.jsonl`, `splits.json`, `feasibility_report.json/.md`. `data/raw/MANIFEST.json` records provenance.

**Feasibility result (plan §19):**
- Only 5.9% of orders split cleanly (88,121), but that is plenty.
- 56,285 orders are BNS-era (6,211 of them clean); the test split has 94 BNS-era orders against the target of 60 or more. **The pilot fallback for H1c is not needed.**
- Several courts end around 2024 (Madhya Pradesh 0 BNS-era orders, Kerala 3).
- **Risks the plan did not expect:**
  - FIR numbers appear in only 12.9% of orders, so the same-FIR leakage rule is weak as written.
  - Citation resolution is about 17% (SCC/AIR citations 0%, because the corpus has no SCC/AIR field).
  - Open India Law text has glued-word artefacts.
  - One Supreme Court judgment was drawn into the test set; restrict the test pool to High Court orders if the plan means that.
- A sample store build (2,000 orders) ran in 86 seconds and the stores' row counts are in line. The full build was not run because **disk space is tight: about 4 GB free** (data/ is 2.5 GB). Run the full build on a machine with more space.

## 5c. Status on 2026-10-20 and work left for teammates

**State of the tests (last measured per folder, 2026-10-20 before the final agents):** Phases 1–3, models, privacy, rights, stores, tools and all six agents pass. These do not yet, because the code is not written:

| Area | Tests | What is needed |
|---|---|---|
| Orchestration graph and fallback | `tests/unit/orchestration/test_graph.py`, `test_fallback_state_machine.py` | **LangGraph flow** (Munshi → Peshkar → Gate 1 interrupt → Sutradhar ⇄ Vakeel ⇄ Abhiyojak → Gate 2 interrupt → export, SQLite checkpointer, change-set path, a plain-Python fallback) |
| API | `tests/unit/api`, `tests/integration/test_api_routes.py` | Real FastAPI routes (cases, upload, chat, SSE events, gates, export, desk, library). Today `api/asgi.py` serves only `/healthz` and returns 503 on `/api/*`, so the UI runs in demo mode |
| Export | `tests/unit/export` | Court-ready DOCX application, List of Dates, annexure index, hearing-prep card, PDF |
| System tests | `tests/system` (257 failing before) | These need the graph, API and export |
| Evaluation | `tests/unit/eval` | Baselines B0–B4, ablations A1–A10, ingestion pipelines P1–P6, feature evals F1–F8, metrics, stats, runners |
| Fine-tuning | `tests/unit/finetune` | Teacher dossiers, span filter, noise augmentation, QLoRA training |
| Test-set construction | `tests/unit/testsets` | T1–T9 builders (rendering + Augraphy, change sets, rights scenarios, speech) |

**Other tasks nobody has done:**
- The literature review (`docs/literature-review-and-usage.md`): the first workflow verified 33 papers and then hit the usage limit. Rerun it with fewer searchers.
- Plan changes that follow from the literature review.
- A browser check of the frontend by a person: all frontend checks so far were automated.
- HLDC access (a teammate must request it on Hugging Face), the CrPC and NDPS s.37 statutes from India Code, a Sarvam API key plus the dashboard retention setting, and a live Sarvam smoke test.
- Install PyMuPDF and the real OCR/vision/speech libraries, and test the real (non-offline) model paths on a GPU.
- Run the full store build and the real fine-tuning on a machine with more disk and a GPU.
- Re-check the Rights Radar rule texts against the bare acts (week-0 item from the plan).

**What can be run today:**
- `docker compose up` → http://localhost:3000 (frontend in demo mode; see `DOCKER.md`).
- Each finished agent offline from Python (see the agents' folders and `tests/`); there is no end-to-end driver until the graph exists.

## 6. Memory notes saved (for future sessions)

- Interface decisions (v5 frontend, agent names, workspace layout).
- You prefer maximal scope: cut sample sizes, never features.
- Don't run tests while modules are still stubs.
