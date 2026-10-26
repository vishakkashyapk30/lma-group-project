# Dev-set baseline runs on gpt-6-luna (operator note, 2026-10-26/27)

Status: the runs exist on disk but are of UNKNOWN CODE STATE (manifests say `719f741-dirty`, another agent was editing the working tree). No tables were copied to `docs/results/`; no numbers are claimed. The sweep operator reruns on a pinned commit. Nothing committed.

## G2 merge (done)
- Candidate G2 (`data/testsets/t1_candidate`, `data/interim/t1_work_candidate/gold/g2.jsonl`, built with the SC-metadata citation index) merged into the agreed T1 gold. The candidate differs from `t1` only in `gold.G2` (G1, G3-G7 of the candidate are the old rule-only ones), so only `G2` was copied, matched by (case_id, doc_id).
- Applied to `t1/`, `t1_gold_candidate/` (source of the agreed swap; otherwise `swap_t1` would undo the merge) and `t1_rule_only/` (G2 is rule-extracted from the order text, no labeler, so one G2 serves both golds). Changed cases: 14 of 200 test cases per folder, 0 of 50 dev. Previous cases/dev files are backed up in `data/eval/dev_runs/_g2_backup/<folder>/`.
- Interim: `data/interim/t1_work/gold/g2.jsonl` replaced by the candidate's; the old file moved to `data/interim/t1_work/gold/rule_only/g2.jsonl`.
- New hashes: agreed `cases_sha256` 2262383a77f3a7b0e4d0a429ec897b6ce84a491a2cff683751a06b25b978412b, `dev_sha256` 9a22f359b9f4c5ba8337384aed1fc9ed86bee16ce1f05582960df5d73384618c (unchanged), `gold_sha256` 5583690e3754dacd8f2ebd4e27987ae7cfa0c3df9eb2fd9e8bc9a879d86c05be. Rule-only: cases 0c440657ff99e885e3049978134de7c506f7388b322fe5ddfe2abf5327a08ee7, dev 7853c3cb... (unchanged), gold_sha256 4cde34517adda55e5f174d9ae21a390253a32c89eecd14a468811eff38cb8ab0. Blind-set hash 9185e1cc...ebe32 and md5 of manifest_blind/dev/open and blind_sealed unchanged. Manifests refreshed.
- Dev orders with a resolved court citation: 0 of 50 (6 have a raw citation, none resolves); of 200 test orders 14 resolve (12 inside the stores per the VI-05 note). So citation recall@10 on dev stays n/a; the gain only shows on the test slice.
- Code: `testsets/gold_source.py` gained `merge_g2_rows`, `merge_g2`, `merge_g2_interim` and CLI `python -m vakeel_sahayak.testsets.gold_source merge-g2 --donor DIR [--donor-interim F] [--backup DIR]`; test `test_merge_g2_changes_only_g2_in_all_three_folders_and_is_idempotent` in `tests/unit/testsets/test_gold_source.py` (6 pass). Note: T2/T3/T6/T8 manifests that hash `t1/cases.jsonl` are stale again.

## Code changes made for the hosted baseline runs
- `eval/baselines/common.py`: baselines sent RAW T1 facts, so the privacy boundary refused every hosted call and the run silently fell back to a vLLM that is not running (empty brief, 0 tokens, `ModelUnavailable`). Added `hosted_backend()` and, only when `VS_LLM_BACKEND` is openai/sarvam and models are not offline, `draft()` now sends the same pseudonymised facts as Full (`driver.file_facts(..., shelve=False)`) and masks PII in the evidence rows (`agents.outbound.mask_public`). Offline behaviour is unchanged.
- `eval/baselines/b0_single_pass.py`: `b0l` resolves the `teacher` role, which has no hosted client (`VS_TEACHER` only affects `models/teacher.py`). Under a hosted backend `b0l` now uses the hosted agent model, so "b0l-hosted" is the same model and prompt as b0 (a stand-in; it carries no information beyond b0 and should be reported as such). Real B0L needs Qwen3-32B on Ada.
- I did not edit `eval/runners/driver.py` (it shows as modified in `git status`; that is another agent's work).
- Launcher scripts were only in the scratchpad: command `bash -c 'set -a; . ./.env; set +a; export VS_DATA_DIR=$PWD/data VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised VS_OPENAI_RUN_CAP_USD=<0.3-0.5> VS_NLI=auto OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2; .venv/bin/python -m vakeel_sahayak.eval.runners.driver run --system <id> --cases data/testsets/t1/dev.jsonl --run-index <k> --shard <i> --n-shards <n> --out data/eval/dev_runs/outputs/<id>[__run2]'`. Without the thread limits 6 processes pushed load to 40 and a case took over 10 minutes.

## What was run (all 50 dev cases, outputs in `data/eval/dev_runs/outputs/`, gitignored)
full (2 runs, 4 shards each), b0, b0l (stand-in), b1, b4, b6; real DeBERTa NLI in every manifest (`deberta-v3-nli`); gold_source agreed; prompt hash f4e2c690b94aaad3. Sharding was changed mid-run for full run 2 (2 to 4 shards) and b4 (2 to 6): resumable, so no case was run twice, but the manifest `n_shards` is the last value. Scoring was started (`scoring score --gold-source both`) and finished, but nothing from it was read or published.

## Measured cost (OpenAI ledger purposes; this task about 1.3 USD, ledger total 1.51 of 4.50 at the end)
| system | cases | USD | USD/case | tokens/case (in+out) | notes |
|---|---|---|---|---|---|
| full (2 runs) | 100 | 0.7715 | 0.0077 | about 94,000 | 15,500 s summed per run under heavy CPU contention (about 310 s/case; 172 s unloaded) |
| b4 | 50 | 0.4181 | 0.0084 | about 119,000 | as expensive as Full; the plan's 1.0 ratio was right |
| b1 | 50 | 0.0433 | 0.0009 | about 7,200 | |
| b0 | 50 | 0.0248 | 0.0005 | about 3,800 | |
| b0l (= b0 model) | 50 | 0.0203 | 0.0004 | about 3,900 | |
| b6 | 50 | 0 | 0 | 0 | no model |
The plan's 0.07 token ratio for B0/B1 is about right for B0 (0.04) and lower for B1 (0.08).

## Failure modes seen in the outputs
1. Pseudonymiser misses names. t1dev-017 ("Sadhna Kushwaha" survives pseudonymisation in a repeated caption), so the boundary refuses the case and B0, B0L and B1 return an empty brief with `ModelUnavailable` (one of 50 each; Full handled it via its own path and shows no error). This case would be scored as a zero for the baselines, an artefact of the privacy layer, not of the method. Fix: repeated-caption and `W/o` name learning in `learn_caption_names`, or exclude the case in all arms identically.
2. Thin facts. T1 `facts_text` is often only a court caption; B0 correctly answers "no facts supplied" with zero grounds (t1dev-000), while Full produces grounds from retrieved authorities (all REPAIRED) that are not tied to client facts. Full's 48/50 first outputs show 91 REPAIRED, 72 SUPPORTED and 58 NEEDS_REVIEW grounds, no empty briefs; so Full's recall advantage over B0 on dev may come from retrieved boilerplate, which the argued-factor metrics must be checked against before any claim.
3. Grounds weak in substance: gravity grounds cite decisions that state the State's side or generic law ("Gravity alone cannot be decisive"), open issues repeat "no authority for flight risk / witness tampering" for most cases (about 10 open issues per case), and sparring objections are mostly unanswered.
Also: baselines' `describe` in the manifest reads "Munshi -> Peshkar ..." (default Switches) for b0/b1/b4; misleading, scope says baseline.

## What I would run differently
- Pin the commit (clean tree, record git sha without `-dirty`), then run; one process per shard with `OMP_NUM_THREADS=2` and at most 8 processes (16 cores, 22 GB).
- Do not run b0l on a hosted backend as a separate arm; it duplicates b0. Run it on Ada.
- Fix failure mode 1 before the run, or report with and without t1dev-017.
- Plan the wall time: about 2 to 3 hours for this set with 8 processes (b4 is the slowest, a case takes as long as Full).
- Read the scoring outputs only after checking `MANIFEST.json` code_version on every arm.
