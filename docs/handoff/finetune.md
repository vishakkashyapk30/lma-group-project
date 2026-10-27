# Fine-tuning pipeline (VI-11, plan §12, §17)

## Done (offline, `tests/unit/finetune`: 110 passed, 0 skipped)
Row shape everywhere: JSON lines `{"doc_id", "facts", "dossier"}`. Helpers in `finetune/_io.py`.
- `teacher_dossiers.py`: `run_shard` (shard = positions i with i % n == shard, one line appended and flushed per order, resume from the output file), `teacher_pilot` (same first n orders to both arms, keys `<arm>/<metric>`), `verified_pairs_per_day`, `choose_teacher` (more pairs/day wins; the API only if all three conditions are recorded True; tie, missing API arm or unrecorded condition goes to Qwen on Ada), `assert_family_rule`. CLI: `python -m vakeel_sahayak.finetune.teacher_dossiers shard|pilot ...`.
- `span_filter.py`: keeps an order only if every valued field has a quote and `tools.dossier.span_check` supports it (fields with no value are not checked).
- `noise_augment.py`: seeded sample of round(fraction*n) rows; facts rendered to a page (`testsets.rendering`), degraded (`testsets.degrade.degrade_page`, own seed per row), read back with `models.factory.get_ocr()`. Needs PyMuPDF. A row whose OCR returns nothing stays clean (not counted).
- `build_dataset.py`: drops ids from `pipelines.leakage.excluded_doc_ids(<interim>/splits.json, <interim>/orders.jsonl)` (a missing splits file raises, never silently keeps everything), hash split about 10% dev, writes chat rows (system, user = facts, assistant = dossier JSON) to `train.jsonl`, `dev.jsonl`.
- `train_qlora.py`: config validated first (missing file -> FileNotFoundError; precision other than fp16 or non NF4 4-bit -> ValueError), then data check, then lazy torch/transformers/peft/bitsandbytes (`TrainingDependencyError` if absent). Plain HF Trainer, loss on the assistant turn only, fp16, paged 8-bit AdamW, effective batch 16 (per device 1 x accumulation 16/world size), checkpoint and eval each epoch, resume from the last checkpoint. `--run K` (or env `RUN`) gives seed 42+K and output `<output>/run<K>`.
- `merge_adapter.export_for_laptop`: needs an existing adapter (FileNotFoundError otherwise); copies adapter and tokenizer files, writes `manifest.json` with sha256. No merged int4 weights are shipped: the laptop quantises the Qwen3-4B base at load.
- Scripts: `scripts/ada/sbatch_qlora.sbatch` (only sbatch job; since 2026-10-27 4 GPUs, 12 h limit, see the section below), `scripts/ada/run_teacher_dossiers.sh SHARD N` (interactive 4-GPU session, in-process vLLM, copies output back every 10 minutes, resumes).
- Test change: `tests/unit/finetune/_helpers.py` `teacher_dossier` now sets status UNSUPPORTED on the fields it empties (`# RECONCILED`: the schema rejects COMPUTED/USER_STATED with no value).

## Not done / needs a GPU, key or person
- No training, teacher run or pilot was executed here (no GPU; the Mistral arm needs `MISTRAL_API_KEY`; the pilot's three API conditions are facts a person must check and record).
- `train_qlora.train` is untested against real torch/peft: library API drift (`eval_strategy`, chat template return type) is the likely first failure. `lora.alpha/dropout/target_modules` are still null (fallbacks 32, 0.05, all linear layers); tune on dev.
- `span_filter` uses the real NLI (`pip install .[nli]` or on Ada); with offline stand-ins the kept share is meaningless.
- `sbatch_qlora.sbatch` account/partition/qos flags were copied from the interactive command in `serve_qwen32b.sh`; confirm the batch QoS allows 36 h on `u22`.
- Inputs not built here: `data/interim/finetune/train_orders.jsonl` (public train orders with a facts section; the facts extraction is not part of this package) and `data/interim/splits.json`, `orders.jsonl`.

## Commands for Ada
```bash
# 0. teacher pilot (laptop or session): both arms on 50 orders, then decide
python -m vakeel_sahayak.finetune.teacher_dossiers pilot data/interim/finetune/train_orders.jsonl 50
# 1. teacher dossiers, three accounts in parallel (interactive 4-GPU sessions)
bash scripts/ada/run_teacher_dossiers.sh 0 3        # and 1 3, 2 3
cat data/interim/finetune/dossiers.shard*.jsonl > data/interim/finetune/dossiers.jsonl
# 2-4. filter, noise, dataset
python -m vakeel_sahayak.finetune.span_filter data/interim/finetune/dossiers.jsonl data/interim/finetune/pairs.jsonl
python -m vakeel_sahayak.finetune.noise_augment data/interim/finetune/pairs.jsonl data/interim/finetune/pairs_noisy.jsonl 0.3
python -m vakeel_sahayak.finetune.build_dataset data/interim/finetune/pairs_noisy.jsonl data/interim/finetune
# 5. training, three runs
mkdir -p logs; for r in 0 1 2; do sbatch --export=ALL,RUN=$r scripts/ada/sbatch_qlora.sbatch; done
# 6. package for the laptop
python -m vakeel_sahayak.finetune.merge_adapter models/extractor-qlora <out_dir>
```
Check a background job: `squeue -u $USER`, `tail -f logs/qlora_<jobid>.out`.

## Running QLoRA on Ada (4 GPUs): prepared 2026-10-27, NOTHING HAS BEEN RUN
Owner decision 2026-10-27: one batch job on 4 x RTX 2080 Ti (DDP with `torchrun`, one process per GPU), using `/scratch` for everything big and `/share1` only as the archive. Written and unit-tested offline; no GPU, no install, no download, no hosted call has happened. Expect first-run failures in the install, bitsandbytes on sm_75, or `Trainer` API drift.

**Prerequisites that do not exist yet**
- Training data. `data/interim/finetune/train.jsonl` and `dev.jsonl` are written by `finetune.build_dataset` (chat rows) from teacher dossiers (steps 0 to 4 above). No teacher dossier exists yet. Qwen3-32B-AWQ on Ada as teacher was dropped on 2026-10-27 (see `ada-qwen32b.md`: the vLLM install failed four times, never the model). Options: (a) hosted teacher on a non-Qwen family, about 0.005 USD per dossier on `gpt-6-luna`, so a 300-dossier pilot is about 1.5 USD and 2,000 pairs about 10 USD (inside the 5 USD OpenAI cap only for the pilot; the cap and the privacy boundary apply, public orders only); (b) Mistral API arm of the teacher pilot; (c) retry the 32B on Ada later. The teacher choice is `choose_teacher` on the pilot.
- A git tag on the code to train with (the nodes have no repo; the job unpacks `git archive` of the tag). Commit first, then `git tag qlora-v1`.

**Commands, in order (laptop unless marked)**
```bash
make hooks && git tag qlora-v1                                   # the tag is the code that trains
.venv/bin/python -m vakeel_sahayak.finetune.train_qlora --dry-run --world-size 4    # laptop: config, data files, batch arithmetic, no torch
bash scripts/ada/stage_qlora_inputs.sh qlora-v1                  # sends code, train/dev jsonl, config, sbatch script to ada:~/vakeel_qlora/in/; refuses client data, keys, a full /home2
ssh ada 'cd ~ && mkdir -p slurm_logs && sbatch --export=ALL,RUN=0 vakeel_qlora/in/sbatch_qlora.sbatch'   # run 0; RUN=1 and RUN=2 after it ends (the QOS allows 4 GPUs at once)
ssh ada 'squeue -u $USER; tail -n 40 ~/slurm_logs/qlora_*.out'   # watch: "bnb smoke ok on 4 GPUs", "[plan]", "[mem]", "[gpu]", "[export] epoch 1 adapter ..."
bash scripts/ada/fetch_qlora_outputs.sh                          # adapters to models/adapters/run<K>/, checksums verified, copy archived to /share1/$USER/vakeel-sahayak/adapters/, ~/vakeel_qlora/out freed (KEEP_HOME=1 to keep)
```
What the job does: caches, venv, tarball and the 8 GB Qwen3-4B weights (curl, sha256 against the LFS oid, pinned to the commit it read) all on `/scratch/$USER/vs-qlora/run<K>`; torch 2.8.0 from the PyTorch cu128 index first, then `scripts/ada/qlora_requirements.txt` from PyPI; a bitsandbytes NF4 smoke test on each GPU before the download; dry run; `torchrun --standalone --nproc_per_node=4`. Directives: `-A research --qos=medium -p u22 --constraint=2080ti -N 1 -n 1 --gres=gpu:4 -c 8 --mem=64G --exclude=gnode069 --time=12:00:00` (the one place to change the limit; the test caps it at 36 h). `/scratch` is wiped by the EXIT trap.

**Batch size:** effective batch 16 as before (config keys `world_size: 4`, `per_device_batch_size: 1`, `effective_batch_size: 16`): per device 1, accumulation 4. A GPU count that does not divide 16 is refused (`--dry-run` shows it).

**What is written where, and resume.** Rank 0 alone writes the checkpoint, manifest and logs. After every epoch only `adapter_model.safetensors` and `adapter_config.json` (about 130 MB) replace `~/vakeel_qlora/out/run<K>/adapter` (written to a temp folder and renamed, with `epoch.json` holding epoch, step, `final` and sha256); the copy is refused with a printed message when `$HOME` would have less than 500 MB free (training goes on, the adapter then lives only on /scratch). `manifest.json` (code tag and commit, seed 42+K, config hash, train/dev hashes, base model revision, torch/peft/transformers/bitsandbytes versions, GPU names, capability, peer-access matrix, NCCL variables and version) is written beside it. Resubmitting the same command after a kill resumes: it restores the adapter weights and the finished-epoch counter only. The optimizer state, the LR schedule position and the RNG live only in the /scratch checkpoint, which the trap deletes, so a resumed epoch restarts the cosine schedule at the peak rate and uses new data order (seed + epochs done). That is an approximation, not a bit-exact resume; a job that is not killed is unaffected.

**DDP details in `train_qlora.py`:** `torch.cuda.set_device(LOCAL_RANK)` and `device_map={"": LOCAL_RANK}` per process; model init and data order use the same seed on every rank (DDP needs it), dropout streams are re-seeded per rank (`seed + 1000*rank`); `ddp_find_unused_parameters=False`; gradient checkpointing with `use_reentrant=False`; if any GPU pair lacks peer access (typical on PCIe 2080 Ti nodes) `NCCL_P2P_DISABLE=1` and `NCCL_IB_DISABLE=1` are set before the first collective (never overriding values you export).

**Expected wall time (an estimate from tokens, not a measurement).** About 2,000 pairs of about 2.5K tokens is about 5M tokens per epoch, 10M for 2 epochs. A 4B NF4 model with gradient checkpointing on one 2080 Ti is guessed at 500 to 1,000 tokens/s, so 4 GPUs give 2,000 to 4,000 tokens/s: about 1 to 1.5 h of training per run, plus about 25 to 40 min of setup (venv, 8 GB at about 15 MB/s). Budget 2 to 6 h per run, 6 to 18 h for three. The plan's earlier "about 100 GPU-h for 3 runs" is the conservative figure; the 12 h limit covers the estimate with margin and must be raised if the first run shows more than 4x slower throughput.

**Risks and unknowns:** (1) bitsandbytes on sm_75: 0.47.0 is pinned for its CUDA 12.8 build; the smoke test fails fast if kernels are missing; none of the pins was installed here. (2) 4-bit plus DDP: the usual QLoRA-on-DDP recipe, but untested on this stack; if the Trainer complains about a quantized model, fall back to `--nproc_per_node=1` (accumulation then 16, same effective batch). (3) /home2 has about 2 GB free: inputs are about 10 to 100 MB, adapters 130 MB each; stage and the job both check, and fetch frees the copy after archiving. (4) The pins in `qlora_requirements.txt` and `TORCH_SPEC` are from knowledge, not tested. (5) Unknown: real throughput, whether NCCL P2P exists on these nodes, the real pair count and token length, whether `medium` QOS has free 4-GPU nodes quickly, lora alpha/dropout (still null, fallbacks apply).
