# OpenAI block of the dev-set sweep: instructions for a teammate with their own OpenAI key (self-contained)

Same idea as `sweep-satvik.md` (read its steps 1, 2 and 6 for checkout, data and upload). The phase-2 OpenAI ablation arms (A2, A8, A9, A3, A1, A6, A7, b2, b3; 50 dev orders each, gpt-6-luna) can be run on YOUR key and YOUR ledger, so the owner's 5 USD ledger is not the limit. Preliminary dev-set work, no blind or test slice.

1. `git fetch --tags && git checkout dev-sweep-v2` (pinned tag, clean `src/` and `configs/`; the script refuses otherwise, `ALLOW_OTHER_CODE=1` overrides and the owner will then refuse the results).
2. `make setup`, `make data`; for the real DeBERTa checker `.venv/bin/pip install -e '.[nli]'` (as in `sweep-satvik.md`).
3. Your key in your own untracked `.env`: `OPENAI_API_KEY=...`. Never the owner's, never committed or printed.
4. `scripts/sweep_openai_block.sh plan` prints the arms and estimated USD (no key, no calls; the whole phase is under 3 USD).
5. `VS_OPENAI_CAP_USD=2.50 scripts/sweep_openai_block.sh run`. Options: `ARMS=A2,A8`, `SHARDS=2` (default 3). The script sets `VS_MODELS=auto VS_LLM_BACKEND=openai VS_EXTERNAL=pseudonymised` and your cap. The ledger is the local file `data/openai/ledger.sqlite` (`make openai-spend` shows it); the code refuses a call that would pass the cap, and clamps every cap to 5 USD per ledger file. Optional soft per-run cap: `VS_OPENAI_RUN_CAP_USD`. Resumable: Ctrl-C and rerun; finished cases and arms are skipped, and arms marked `done` in `configs/eval/sweep_dev.yaml` are not in the list.
   Outputs: `data/eval/dev_runs/outputs/<arm>/` (logs in `data/eval/dev_runs/logs/`).
6. `scripts/sweep_openai_block.sh pack` writes `data/eval/dev_runs/sweep-openai-<date>.tar.gz` (per-case JSON, manifests, case lists, `PACK_INFO.json`; no events, logs, `.env`; refuses a key-like string) and prints the `hf upload ... sweep-runs/sweep-openai-<date>.tar.gz` command. Send the file name to the owner.

## Owner side
`scripts/sweep_collect.sh --hf sweep-openai-<date>.tar.gz` (or a local path): same checks as for the Sarvam package (names, no links, no keys, `gold_source` agreed, same `prompt_hash` and `git_sha` as the owner's Full) with `llm_backend` openai; unpacks into `data/eval/dev_runs/openai_block/`. Score against the owner's Full:
`python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs/openai_block/outputs --slice dev --gold-source both --out <dir>` (copy or link `outputs/full` next to them if the scorer needs the reference in the same directory).
