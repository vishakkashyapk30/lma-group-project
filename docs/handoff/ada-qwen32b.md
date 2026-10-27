# Qwen3-32B-AWQ on Ada

> Checked by Vishak 2026-10-27: the plan to serve Qwen3-32B-AWQ on Ada is DROPPED (see the decision section at the end; the job was cancelled). B0L is the Sarvam-105B single pass (about INR 3 to 5 for 50 cases per `sweep-dev.md`; the 1.15 INR per case figure below is the older estimate, unverified), A5 and the teacher dossiers wait for the fine-tuning stretch. The "Uses" bullet in the first section is therefore historical.

Status 2026-10-26: the download is running on Ada (started from the laptop through the gateway). Not served yet.

- **Access:** `ssh <user>@ada-gw1` (or `ada-gw2`). The old host `ada.iiit.ac.in` no longer accepts SSH; the laptop's `~/.ssh/config` still points at it, so update it to the gateways.
- **Where:** `/share1/vishakkashyap.k/vakeel-sahayak/models/Qwen3-32B-AWQ` (19.3 GB, 14 files). Log: `/share1/vishakkashyap.k/vakeel-sahayak/logs/download_qwen32b.log` (look for `ALL_DONE`; each LFS file is sha256-verified). Script: `scripts/ada/fetch_qwen32b.sh` (resumable).
- **Limits found:** `/home2` has about 2 GB free and share1 has a 3,000-file quota (1,769 used, 100 GB space quota with about 58 GB used), so no Python venv or vLLM install fits there. Install vLLM on node-local `/scratch` inside a GPU session (about 8 to 10 GB, many files), serve from the share1 copy staged to scratch with `scripts/ada/stage_to_scratch.sh` (still a TODO stub).
- **Serving (not done):** 4 x RTX 2080 Ti node, tensor parallel 4, AWQ, `--max-model-len` about 8192, OpenAI-compatible endpoint; the project's local runtime config is `configs/models.yaml` (`teacher`, runtime vllm). Sessions are at most 6 hours, so submit with `scripts/ada/sbatch_*.sbatch` style jobs and stage weights at the start.
- **Uses:** B0L (single-pass 32B), the A5 prompted-32B extractor arm, teacher dossiers, and the bulk generative jobs that do not fit the OpenAI and Sarvam budgets (`docs/handoff/eval-jobs.md`).

## Decision 2026-10-27: stopped, not needed for the status report

Four attempts to serve Qwen3-32B-AWQ on Ada failed during the vLLM install, never in the model itself. Causes found, each fixed in `scripts/ada/serve_qwen32b.sh`: (1) PyPI is slow from the compute nodes (about 5 MB/s; torch from download.pytorch.org gives 20 MB/s, so torch and the CUDA libraries come from there); (2) `srun` without `-N 1 -n 1` starts the script once per task and the copies collide; (3) one node (gnode069) has a broken GPU, skip it with `-x`; (4) `$HOME` is NFS with about 2 GB free, so pip's cache hung: every cache and temp dir is now on node-local `/scratch`. Not confirmed: that vLLM 0.10.2 runs on Turing (compute capability 7.5, no flash attention; use `--enforce-eager` and check the attention backend).

The model is not needed for the status report: the large-model baseline B0L runs on a hosted model (`gpt-6-luna`, or Sarvam-105B at about INR 1.15 per case), and A5 (prompted 32B extractor) and the teacher dossiers belong to the fine-tuning stretch. The job was cancelled to save the allocation. To retry: `scripts/ada/serve_qwen32b.sh` inside `srun -A research --qos=medium -p u22 --constraint=2080ti -N 1 -n 1 -x gnode069 --gres=gpu:4 -c 2 --mem=48G --time=05:30:00`.

## Update 2026-10-27 (evening): retry is back on, not yet run

A teammate pointed out that AWQ-quantised Qwen3-32B with vLLM tensor parallel across the four 2080 Ti of one Ada node is the intended setup; the four failures were installs, not the model. The serve script already used that (AWQ, `--dtype half`, `--tensor-parallel-size 4`, 8192 context). What was still open is the attention backend on Turing, so the script now tries the engine default, then `VLLM_ATTENTION_BACKEND=TRITON_ATTN`, then the V0 xformers path, and prints which one answered. Nothing was launched in this update; the retry needs one interactive 4-GPU session (command above) and costs no API budget. If it comes up, B0L, A5 and the teacher dossiers can use it, and the decision above is reversed for those; the Sarvam B0L arm stays as the hosted comparison. Not started: wiring `configs/models.yaml` `teacher` to the tunnel URL for a real run.
