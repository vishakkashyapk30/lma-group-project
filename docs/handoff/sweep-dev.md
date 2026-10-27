# Pre-freeze dev-set sweep: operator checkpoints

Plan: `configs/eval/sweep_dev.yaml` (`driver plan --sweep` prints it); runner: `scripts/sweep_dev.py run --phase N [--arms a,b] [--shards 4] [--parallel 2]` (resumable shards, env per backend from the yaml, applied after `.env`; set `VS_OPENAI_CAP_USD=4.90` and `VS_SARVAM_CAP_INR` in the shell). Dev cases only.

## Checkpoint 2026-10-27 (hold in force)
- Budgets (owner correction): OpenAI ledger ceiling 4.90 USD (1.51 spent); owner's Sarvam key INR 30 in total (5.49 of the 25-INR code default shown, i.e. about 0.7 INR used by an aborted smoke); the big Sarvam block is Satvik's: `docs/handoff/sweep-satvik.md`, `scripts/sweep_sarvam_block.sh`, `scripts/sweep_collect.sh`.
- HOLD from the coordinator: no model-calling phase until a pinned code tag; then ALL model arms, including a rerun of full x2, b0, b0l, b1, b4, b6, run from a git worktree of the tag.
- Done: phase 0 (config and plan table); Sarvam package and collect script (tests `tests/unit/scripts/test_sweep_collect.py`); driver manifest now records `git_sha`, `git_dirty`, `code_tree_hash`; the scoring loader refuses runs from different commits (`--allow-mixed-code` overrides; tests in `test_scoring_pipeline.py`, `test_manifest_code_stamp.py`).
- Aborted, outputs discarded: a 3-case Sarvam smoke (killed on the hold after 132 calls in case 1; the path works: calls were made and settled) and the first offline phase-1 batch (stopped; the unpinned tree makes it unusable). Offline Full costs about 85 s of CPU per case (real BGE-M3 retrieval, 480% CPU), so phase 1 is a few hours of laptop time.
- Not run yet: phases 1, 2, 4, 5.

## State after the cut-off on 2026-10-27 (about 05:30)

- **Rerun on the pinned tag, mostly done.** The baselines were rerun from a clean worktree of `dev-sweep-v1` (every manifest: `git_sha` efd0ce49fa41..., `git_dirty` false, code-tree hash d8cf147bd5...). All 50 dev cases are on disk for `b0`, `b1`, `b4`, `b6` and `full`; `full__run2` has 50 files of which 47 are error-free (3 cases errored and were not retried). The old runs are in `data/eval/dev_runs_superseded/` and must not be scored. The real B0L (Sarvam-105B single pass, about INR 3 to 5) was not run, and the hosted `b0l` stand-in is a duplicate of `b0` and is not rerun.
- **Spend at the cut-off:** OpenAI 2.20 USD of the 4.50 default cap (the rerun cost about 0.69 USD: full +0.39, b4 +0.26, b0 +0.02, b1 +0.03); Sarvam INR 5.49 of the INR 30 allowed on the owner's key (unchanged).
- **Nothing has been scored yet.** Scoring needs no paid call: `.venv/bin/python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs --slice dev --gold-source both --out data/eval/dev_scores` then `... report --scores data/eval/dev_scores` (it took more than 25 minutes with the real DeBERTa claim checker the last time).
- **Owner decision (2026-10-27):** no new paid runs until the API-key arrangement with the teammates is settled. Phase 1 (free offline arms), phase 2 (OpenAI ablations), the Sarvam block (Satvik) and phase 4 (Ada) are all still to run. The runner is `scripts/sweep_dev.py`; the plan is `configs/eval/sweep_dev.yaml`.
- **To finish the 3 errored cases of `full__run2`:** `scripts/sweep_dev.py run --phase 0 --arms full --include-done` from the worktree (resumable, about 0.02 USD).
