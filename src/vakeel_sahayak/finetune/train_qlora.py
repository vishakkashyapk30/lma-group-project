"""Step 5: QLoRA on Qwen3-4B (r=16, 2 epochs, one 2080 Ti, FP16), checkpoint every epoch. Launched by scripts/ada/sbatch_qlora.sbatch (plan §12, §17).

QLoRA (Dettmers et al., NeurIPS 2023): the frozen base is 4-bit NF4, LoRA adapters train in FP16 (a Turing 2080 Ti has no bf16, so any other
precision is refused before a model loads). The loss is on the assistant turn only (the dossier JSON), the facts and system turns are masked.
`alpha`, `dropout` and `target_modules` are null in the config until tuned on dev; the documented fallbacks below apply until then.

torch, transformers, peft and bitsandbytes are imported inside `train`, so the package imports on a bare install; a missing one raises
`TrainingDependencyError` naming what to install, only when training is actually invoked.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

DEFAULT_ALPHA = 32  # fallback while `lora.alpha` is null (TODO: tune on dev)
DEFAULT_DROPOUT = 0.05
DEFAULT_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
MAX_LEN = 4096
SEED = 42


class TrainingDependencyError(RuntimeError):
    """A library needed for training is not installed (install with `pip install torch transformers peft bitsandbytes accelerate`)."""


def load_config(config_path: str) -> dict[str, Any]:
    """Read and validate the QLoRA config; FileNotFoundError for a missing file, ValueError for a setting the 2080 Ti cannot run."""
    import yaml

    path = Path(config_path)
    if not path.is_file():
        raise FileNotFoundError(f"QLoRA config not found: {config_path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if cfg.get("precision") != "fp16":
        raise ValueError(f"precision must be 'fp16' (the 2080 Ti has no bf16), got {cfg.get('precision')!r}")
    quant = cfg.get("quantization") or {}
    if quant.get("bits") != 4 or quant.get("type") != "nf4":
        raise ValueError(f"QLoRA needs 4-bit NF4 quantisation, got {quant!r}")
    return cfg


def lora_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    """LoRA arguments with the documented fallbacks for the settings still null in the config."""
    lora = cfg.get("lora") or {}
    return {
        "r": int(lora.get("r", 16)),
        "lora_alpha": lora["alpha"] if lora.get("alpha") is not None else DEFAULT_ALPHA,
        "lora_dropout": lora["dropout"] if lora.get("dropout") is not None else DEFAULT_DROPOUT,
        "target_modules": lora.get("target_modules") or list(DEFAULT_TARGETS),
        "bias": "none",
        "task_type": "CAUSAL_LM",
    }


def output_dir(cfg: dict[str, Any], run: int | None) -> Path:
    """The adapter folder: `output` itself, or `<output>/run<k>` when one of the `runs` repeated trainings is named."""
    base = Path(cfg["output"])
    if run is None:
        return base
    if not 0 <= run < int(cfg.get("runs", 1)):
        raise ValueError(f"run {run} is outside 0..{int(cfg.get('runs', 1)) - 1}")
    return base / f"run{run}"


def mask_prompt(prompt_ids: list[int], full_ids: list[int], ignore: int = -100) -> list[int]:
    """Labels for one chat example: the prompt tokens are ignored, the assistant turn is learned."""
    n = min(len(prompt_ids), len(full_ids))
    return [ignore] * n + list(full_ids[n:])


def _require(*names: str) -> None:
    import importlib.util

    missing = [n for n in names if importlib.util.find_spec(n) is None]
    if missing:
        raise TrainingDependencyError(
            f"training needs {', '.join(missing)}: pip install torch transformers peft bitsandbytes accelerate"
        )


def _encode(tokenizer: Any, messages: list[dict[str, str]]) -> dict[str, list[int]]:
    """Tokenise one conversation (thinking off); only the final assistant turn carries labels."""
    kw = {"enable_thinking": False}
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=True, add_generation_prompt=True, **kw)
    full = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=False, **kw)
    prompt, full = (
        list(prompt["input_ids"] if hasattr(prompt, "keys") else prompt),
        list(full["input_ids"] if hasattr(full, "keys") else full),
    )
    full = full[:MAX_LEN]
    return {"input_ids": full, "attention_mask": [1] * len(full), "labels": mask_prompt(prompt, full)[:MAX_LEN]}


def train(config_path: str = "configs/finetune/qlora.yaml", run: int | None = None) -> str:
    """Train and return the adapter directory.

    Args:
        config_path: the QLoRA YAML (base model, LoRA, epochs, data, output)
        run: which of the `runs` repeated trainings this is (seed = 42 + run, folder `<output>/run<run>`); None for a single run into `output`

    Returns:
        Adapter path.
    """
    cfg = load_config(config_path)
    out = output_dir(cfg, run)
    for key in ("train", "dev"):
        if not Path(cfg["data"][key]).is_file():
            raise FileNotFoundError(f"{key} data not found: {cfg['data'][key]} (build it with finetune.build_dataset)")
    _require("torch", "transformers", "peft", "bitsandbytes", "accelerate")

    import json

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    seed = SEED + (run or 0)
    set_seed(seed)
    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"], quantization_config=bnb, torch_dtype=torch.float16, device_map={"": 0}
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(**lora_settings(cfg)))
    model.print_trainable_parameters()

    def rows(path: str) -> list[dict[str, list[int]]]:
        with open(path, encoding="utf-8") as fh:
            return [_encode(tok, json.loads(line)["messages"]) for line in fh if line.strip()]

    args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=int(cfg["epochs"]),
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        fp16=True,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        report_to=[],
        seed=seed,
        data_seed=seed,
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=rows(cfg["data"]["train"]),
        eval_dataset=rows(cfg["data"]["dev"]),
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
    )
    ckpts = sorted((out / "checkpoints").glob("checkpoint-*")) if (out / "checkpoints").is_dir() else []
    trainer.train(
        resume_from_checkpoint=str(ckpts[-1]) if ckpts else None
    )  # a run killed after epoch 1 resumes from it
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    return str(out)


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m vakeel_sahayak.finetune.train_qlora [CONFIG] [--run K] (K also from the RUN environment variable)."""
    import argparse

    ap = argparse.ArgumentParser(description="QLoRA training of the Qwen3-4B extractor")
    ap.add_argument("config", nargs="?", default="configs/finetune/qlora.yaml")
    ap.add_argument("--run", type=int, default=int(os.environ["RUN"]) if os.environ.get("RUN") else None)
    ns = ap.parse_args(argv)
    print(train(ns.config, ns.run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
