# Sarvam block of the dev-set sweep: instructions for Satvik (self-contained)

The owner's Sarvam key may spend only about INR 30 in total, so the Sarvam-105B part of the pre-freeze dev-set sweep is run by you, with YOUR key, on your machine. It is preliminary dev-set work for the status report (50 dev orders, no blind or test slice). Your results come back as one small tarball.

## What the block is
Arms on Sarvam-105B over the 50 T1 dev cases (25 for the last three), in priority order. Every arm is only comparable with Full on the same backend, so the block carries its own Full and B0. Estimated spend (INR, at the dashboard prices of 2026-10-26, token counts measured on gpt-6-luna; the real figure is in `make sarvam-spend` after the first arm):

| Arm | Cases | INR | Claim |
|---|---|---|---|
| full (reference) | 50 | 58 | all |
| b0 (single pass) | 50 | 4 | C1 |
| S3 (rules then LLM rater) | 50 | 58 | C6 |
| S3b (LLM rater alone) | 50 | 58 | C6 |
| S8 (self-critique only) | 50 | 48 | C13 |
| S9 (sampling-only critic) | 50 | 48 | C7 |
| S10 (no Abhiyojak isolation) | 50 | 48 | C8 |
| S1 (retrieval self-critique) | 25 | 34 | C10 |
| S15 (reasoning-first output) | 25 | 29 | C26, C27 |
| S15b (free text then parse) | 25 | 29 | C26, C27 (could) |
| S11 (three-role review) | 25 | 29 | C7 (could) |
| total | | about 440 | |

You decide how much to spend. Full + b0 + S3 is about INR 120, the first seven rows about INR 320. An arm that does not fit the cap is stopped by the ledger (it refuses the call that would pass your cap), and the arm stays partial: run it again later or leave it. `scripts/sweep_sarvam_block.sh plan` prints this table from the config.

## Steps
1. `git fetch --tags && git checkout dev-sweep-v1`. The pinned code tag is **`dev-sweep-v1`** (commit efd0ce4; all runs must come from exactly this code: every manifest records `git_sha` and `git_dirty`, and the collect step refuses a different commit). Use a clean checkout: `git checkout dev-sweep-v1` with no local edits to `src/` or `configs/` (the run records `git_dirty`).
2. `make setup`, then `make data` (you need `data/testsets/t1` and `data/stores`; `RAW=0 make data` skips the raw 1.8 GB). For the real DeBERTa claim checker, which the owner's runs use: `.venv/bin/pip install -e '.[nli]'` (needs torch; without it the run falls back to an offline NLI and records that, and the unsupported-fact rates are then not comparable: say so when you send the results).
3. Put your key in your own untracked `.env`: `SARVAM_API_KEY=...` (never commit or print it). Do not copy the owner's `.env`.
4. Choose your cap and run (resumable: Ctrl-C any time and run the same command again; finished cases are skipped):
   `VS_SARVAM_CAP_INR=150 scripts/sweep_sarvam_block.sh run`
   Options: `ARMS=full,b0,S3` to pick arms, `SHARDS=3` for the parallel processes per arm (default 3; fewer if the machine is small). The script sets `VS_MODELS=auto VS_LLM_BACKEND=sarvam VS_EXTERNAL=pseudonymised VS_SARVAM=pseudonymised` and your cap; it uses your own local ledger (`data/sarvam/ledger.sqlite`, nothing shared); `make sarvam-spend` shows the spend.
   Outputs go to `data/eval/dev_runs/sarvam_block/outputs/<arm>/` (one JSON per case, `MANIFEST.json` per arm, logs under `.../logs/`). Each case takes a few minutes; an arm of 50 cases with 3 shards takes roughly 1 to 1.5 hours.
5. Package: `scripts/sweep_sarvam_block.sh pack` writes `data/eval/dev_runs/sweep-sarvam-<date>.tar.gz` holding only the per-case result JSON, the manifests, the case lists and a `PACK_INFO.json` (cap, spend, commit). It leaves out the event logs, the logs, `.env` and anything key-like, and refuses to pack if a key-like string is found.
6. Send it back (default path, Hugging Face): `hf upload Vakeel-Sahayak/vakeel-sahayak-data data/eval/dev_runs/sweep-sarvam-<date>.tar.gz sweep-runs/sweep-sarvam-<date>.tar.gz --repo-type dataset`. You are a member of the organisation with the write role. If you use a fine-grained token: huggingface.co/settings/tokens -> Create new token -> Fine-grained -> under Permissions add the organisation Vakeel-Sahayak -> "Write access to contents/settings of all repos under Vakeel-Sahayak" (or the single repo vakeel-sahayak-data) -> put it in `.env` as `HF_TOKEN=...` or run `hf auth login`. If that is not possible, send the file to the owner directly. Then tell the owner the file name.

## Owner side
`scripts/sweep_collect.sh --hf sweep-sarvam-<date>.tar.gz` (or a local path) downloads, checks and unpacks into `data/eval/dev_runs/sarvam_block/`: only regular files with the names the packer writes, no absolute or `..` paths or links, no key-like strings, `gold_source` agreed, the same `prompt_hash` and `git_sha` as the owner's Full runs (`EXPECT_PROMPT_HASH`, `ALLOW_CODE_MISMATCH=1` override), `llm_backend` sarvam; a differing NLI backend only warns. Score with `python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs/sarvam_block/outputs --slice dev --gold-source both --out <dir>` (its own Full is the reference).
`make data-publish` never touches `sweep-runs/` on the dataset (the upload has no delete; see the note in `scripts/data_publish.sh`) and `make data` / `data_install` exclude `sweep-runs/*` from the download.

## Caveats
Preliminary dev-slice results, small n, wide intervals. Sarvam-105B is a reasoning model: the output tokens per case may be higher than the gpt-6-luna measurement, so check the ledger after the first arm and adjust the plan. Hosted text is pseudonymised before it leaves the machine (`VS_EXTERNAL=pseudonymised`); do not change that.
