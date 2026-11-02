# Arms A5, A10 and S13 on Sarvam-105B (2 November 2026)

## Finding: they were already dispatchable, as `ID:ARG`
No `src/` change was needed. `driver run --system` accepts A5, A10 and S13 only with an argument (`src/vakeel_sahayak/eval/runners/systems.py`, `system_switches`):
`A5:base_4b` (or `A5:prompted_32b`), `A10:<store>` (one of the seven shared stores, e.g. `A10:caselaw.reasoning`) and `S13:<field>=<value>[,...]` (e.g. `S13:stopping=llm`).
The Sarvam queue script (`scripts/midsub/sweep-v3-sarvam-queue.sh`) passed bare `A5`, `A10`, `S13`, which are refused with exit 2; those three arms are the ones missing from `sarvam_block_v3/outputs`. Code is unchanged from `dev-sweep-v3`, so the code stamp is identical and the new arms are paired with the existing block.

Added: `tests/unit/eval/test_arg_systems_dispatch.py` (bare ids refused with the `ID:ARG` hint, one A10 arm per store, A5 and S13 fields), a dispatch table at the end of `docs/literature-to-code-map.md`, and the run script `scripts/midsub/sweep-v3-arms-a5-a10-s13.sh`.

## S13
S13 is not a single arm: the repo defines it as a grid point of other switches (`Switches.for_variant('S13', **fields)`) plus the search harness `eval/runners/workflow_search.py`, whose model-backed arm raises `NotImplementedError` (a real search needs G1 recall on dev with a hosted model; docs/literature-to-code-map.md). No grid winner exists in the docs. I ran the repo's default smoke grid point, `S13:stopping=llm` (same as S3b). This is not a search result; a real S13 needs the search run on dev with a hosted model and a chosen point.

## A5 caveat
Under `VS_LLM_BACKEND=sarvam` every agent role (`agents_14b`, `munshi_4b`, `extractor_4b`) goes to the same hosted model, so `A5:base_4b` differs from Full only by role name. Expect it to equal Full up to sampling noise. The fine-tuned vs base contrast needs the local 4B (laptop/Ada). `A5:prompted_32b` was not run (the `teacher` role is not served by Sarvam).

## Runs
Sarvam-105B, first 10 dev cases (`data/testsets/t1/dev.jsonl`), env as the queue script (`VS_ALLOW_PAID=sarvam`, run cap raised to 90). Nine arms, all 10 cases completed with no case or stage errors:
`A10:law.statutes`, `law.concordance`, `caselaw.reasoning`, `caselaw.citations`, `caselaw.similar`, `advocacy.arguments`, `advocacy.objections`, `S13:stopping=llm`, `A5:base_4b`.
Outputs: `/home/vishak/IIITH-IV-I/lma/sweep-v3/data/eval/dev_runs/sarvam_block_v3/outputs/{a10_<store>,s13_stopping_llm,a5_base_4b}`; logs next to them in `logs/`, driver log `arms-a5-a10-s13.log`.
Spend: ledger 224.89 to 238.26 INR, so INR 13.4 (limit 400; the response cache served most calls because the prompts repeat Full's). Total after: about INR 238.3 of 5000 (the ledger also holds earlier work). OpenAI stayed locked.
Not scored yet. Score with `scoring score --runs <dir> --slice dev --gold-source agreed` on a directory holding these arms plus `full` (symlinks work); A10 outputs are retrieval and slot fill only, so only retrieval and slot metrics apply.
