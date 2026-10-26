# Pre-freeze dev-set sweep: operator checkpoints

Plan: `configs/eval/sweep_dev.yaml` (`driver plan --sweep` prints it); runner: `scripts/sweep_dev.py run --phase N [--arms a,b] [--shards 4] [--parallel 2]` (resumable shards, env per backend from the yaml, applied after `.env`; set `VS_OPENAI_CAP_USD=4.90` and `VS_SARVAM_CAP_INR` in the shell). Dev cases only.

## Checkpoint 2026-10-27 (hold in force)
- Budgets (owner correction): OpenAI ledger ceiling 4.90 USD (1.51 spent); owner's Sarvam key INR 30 in total (5.49 of the 25-INR code default shown, i.e. about 0.7 INR used by an aborted smoke); the big Sarvam block is Satvik's: `docs/handoff/sweep-satvik.md`, `scripts/sweep_sarvam_block.sh`, `scripts/sweep_collect.sh`.
- HOLD from the coordinator: no model-calling phase until a pinned code tag; then ALL model arms, including a rerun of full x2, b0, b0l, b1, b4, b6, run from a git worktree of the tag.
- Done: phase 0 (config and plan table); Sarvam package and collect script (tests `tests/unit/scripts/test_sweep_collect.py`); driver manifest now records `git_sha`, `git_dirty`, `code_tree_hash`; the scoring loader refuses runs from different commits (`--allow-mixed-code` overrides; tests in `test_scoring_pipeline.py`, `test_manifest_code_stamp.py`).
- Aborted, outputs discarded: a 3-case Sarvam smoke (killed on the hold after 132 calls in case 1; the path works: calls were made and settled) and the first offline phase-1 batch (stopped; the unpinned tree makes it unusable). Offline Full costs about 85 s of CPU per case (real BGE-M3 retrieval, 480% CPU), so phase 1 is a few hours of laptop time.
- Not run yet: phases 1, 2, 4, 5.
