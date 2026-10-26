# Fine-tuning pipeline (VI-11, plan §12, §17)

## Done (offline, `tests/unit/finetune`: 110 passed, 0 skipped)
Row shape everywhere: JSON lines `{"doc_id", "facts", "dossier"}`. Helpers in `finetune/_io.py`.
- `teacher_dossiers.py`: `run_shard` (shard = positions i with i % n == shard, one line appended and flushed per order, resume from the output file), `teacher_pilot` (same first n orders to both arms, keys `<arm>/<metric>`), `verified_pairs_per_day`, `choose_teacher` (more pairs/day wins; the API only if all three conditions are recorded True; tie, missing API arm or unrecorded condition goes to Qwen on Ada), `assert_family_rule`. CLI: `python -m vakeel_sahayak.finetune.teacher_dossiers shard|pilot ...`.
- `span_filter.py`: keeps an order only if every valued field has a quote and `tools.dossier.span_check` supports it (fields with no value are not checked).
- `noise_augment.py`: seeded sample of round(fraction*n) rows; facts rendered to a page (`testsets.rendering`), degraded (`testsets.degrade.degrade_page`, own seed per row), read back with `models.factory.get_ocr()`. Needs PyMuPDF. A row whose OCR returns nothing stays clean (not counted).
- `build_dataset.py`: drops ids from `pipelines.leakage.excluded_doc_ids(<interim>/splits.json, <interim>/orders.jsonl)` (a missing splits file raises, never silently keeps everything), hash split about 10% dev, writes chat rows (system, user = facts, assistant = dossier JSON) to `train.jsonl`, `dev.jsonl`.
- `train_qlora.py`: config validated first (missing file -> FileNotFoundError; precision other than fp16 or non NF4 4-bit -> ValueError), then data check, then lazy torch/transformers/peft/bitsandbytes (`TrainingDependencyError` if absent). Plain HF Trainer, loss on the assistant turn only, fp16, paged 8-bit AdamW, grad accumulation 16, checkpoint and eval each epoch, resume from the last checkpoint. `--run K` (or env `RUN`) gives seed 42+K and output `<output>/run<K>`.
- `merge_adapter.export_for_laptop`: needs an existing adapter (FileNotFoundError otherwise); copies adapter and tokenizer files, writes `manifest.json` with sha256. No merged int4 weights are shipped: the laptop quantises the Qwen3-4B base at load.
- Scripts: `scripts/ada/sbatch_qlora.sbatch` (only sbatch job, 1 GPU, 36 h; node-local venv, torch from the PyTorch index), `scripts/ada/run_teacher_dossiers.sh SHARD N` (interactive 4-GPU session, in-process vLLM, copies output back every 10 minutes, resumes).
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
