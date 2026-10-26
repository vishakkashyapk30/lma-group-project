# Qwen3-32B-AWQ on Ada

Status 2026-10-26: the download is running on Ada (started from the laptop through the gateway). Not served yet.

- **Access:** `ssh <user>@ada-gw1` (or `ada-gw2`). The old host `ada.iiit.ac.in` no longer accepts SSH; the laptop's `~/.ssh/config` still points at it, so update it to the gateways.
- **Where:** `/share1/vishakkashyap.k/vakeel-sahayak/models/Qwen3-32B-AWQ` (19.3 GB, 14 files). Log: `/share1/vishakkashyap.k/vakeel-sahayak/logs/download_qwen32b.log` (look for `ALL_DONE`; each LFS file is sha256-verified). Script: `scripts/ada/fetch_qwen32b.sh` (resumable).
- **Limits found:** `/home2` has about 2 GB free and share1 has a 3,000-file quota (1,769 used, 100 GB space quota with about 58 GB used), so no Python venv or vLLM install fits there. Install vLLM on node-local `/scratch` inside a GPU session (about 8 to 10 GB, many files), serve from the share1 copy staged to scratch with `scripts/ada/stage_to_scratch.sh` (still a TODO stub).
- **Serving (not done):** 4 x RTX 2080 Ti node, tensor parallel 4, AWQ, `--max-model-len` about 8192, OpenAI-compatible endpoint; the project's local runtime config is `configs/models.yaml` (`teacher`, runtime vllm). Sessions are at most 6 hours, so submit with `scripts/ada/sbatch_*.sbatch` style jobs and stage weights at the start.
- **Uses:** B0L (single-pass 32B), the A5 prompted-32B extractor arm, teacher dossiers, and the bulk generative jobs that do not fit the OpenAI and Sarvam budgets (`docs/handoff/eval-jobs.md`).
