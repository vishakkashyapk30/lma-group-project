"""Step 5: QLoRA on Qwen3-4B (r=16, 2 epochs, FP16), checkpoint every epoch. Launched by scripts/ada/sbatch_qlora.sbatch (plan §12, §17).

Owner decision 2026-10-27: one batch job on four 2080 Ti with `torchrun` (DDP, one process per GPU). The effective batch of the config
(`effective_batch_size`, 16) is kept: the per-device batch is 1 and the gradient accumulation is effective / (per-device * world size), so 4 GPUs
accumulate 4 steps. Only rank 0 writes checkpoints, manifests and logs. `--dry-run` validates everything and prints the plan without importing torch.

QLoRA (Dettmers et al., NeurIPS 2023): the frozen base is 4-bit NF4, LoRA adapters train in FP16 (a Turing 2080 Ti has no bf16, so any other
precision is refused before a model loads). The loss is on the assistant turn only (the dossier JSON), the facts and system turns are masked.
`alpha`, `dropout` and `target_modules` are null in the config until tuned on dev; the documented fallbacks below apply until then.

torch, transformers, peft and bitsandbytes are imported inside `train`, so the package imports on a bare install; a missing one raises
`TrainingDependencyError` naming what to install, only when training is actually invoked.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

DEFAULT_ALPHA = 32  # fallback while `lora.alpha` is null (TODO: tune on dev)
DEFAULT_DROPOUT = 0.05
DEFAULT_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]
MAX_LEN = 4096
SEED = 42
DEFAULT_EFFECTIVE_BATCH = 16
MIN_FREE_MB = 500  # the copy to $HOME (NFS, about 2 GB free) is refused below this much free space
ADAPTER_FILES = ("adapter_model.safetensors", "adapter_config.json")


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
    ws = cfg.get("world_size", 1)
    if not isinstance(ws, int) or ws < 1:
        raise ValueError(f"world_size must be a positive integer, got {ws!r}")
    return cfg


def dist_env(environ: dict[str, str] | None = None) -> tuple[int, int, int]:
    """(rank, local_rank, world_size) as set by torchrun; (0, 0, 1) outside it."""
    e = os.environ if environ is None else environ
    return int(e.get("RANK", 0)), int(e.get("LOCAL_RANK", 0)), int(e.get("WORLD_SIZE", 1))


def batch_plan(cfg: dict[str, Any], world_size: int) -> dict[str, int]:
    """Per-device batch and gradient accumulation so that per_device * accumulation * world_size == the config's effective batch (ValueError if not exact)."""
    effective = int(cfg.get("effective_batch_size", DEFAULT_EFFECTIVE_BATCH))
    per_device = int(cfg.get("per_device_batch_size", 1))
    if world_size < 1 or per_device < 1 or effective < 1:
        raise ValueError("world size, per-device batch and effective batch must be positive")
    if effective % (per_device * world_size):
        raise ValueError(
            f"effective batch {effective} is not divisible by per-device batch {per_device} x world size {world_size}: "
            "change the number of GPUs or effective_batch_size"
        )
    return {
        "world_size": world_size,
        "per_device_batch_size": per_device,
        "gradient_accumulation_steps": effective // (per_device * world_size),
        "effective_batch_size": effective,
    }


def rank_seed(seed: int, rank: int) -> int:
    """Seed of the random streams that may differ between ranks (dropout); model init and data order use `seed` itself on every rank."""
    return seed + 1000 * rank


def nccl_env_hints(peer_access: list[list[bool]]) -> dict[str, str]:
    """NCCL settings for a node whose GPUs sit on PCIe: if any GPU pair cannot access each other's memory, peer-to-peer transport must be off
    (otherwise NCCL can hang) and InfiniBand is irrelevant on one node. With full peer access nothing is forced."""
    n = len(peer_access)
    if all(peer_access[i][j] for i in range(n) for j in range(n) if i != j):
        return {}
    return {"NCCL_P2P_DISABLE": "1", "NCCL_IB_DISABLE": "1"}


def resume_plan(export_dir: Path | None, epochs: int) -> tuple[int, Path | None]:
    """(epochs already done, adapter folder to restore) from the last adapter copied to $HOME, (0, None) for a fresh run.
    Restores adapter weights and the epoch counter only: optimizer, LR schedule and RNG state are not saved there."""
    if export_dir is None:
        return 0, None
    meta, adapter = export_dir / "epoch.json", export_dir / "adapter"
    if not (meta.is_file() and (adapter / ADAPTER_FILES[0]).is_file()):
        return 0, None
    done = int(json.loads(meta.read_text(encoding="utf-8")).get("epoch", 0))
    return (min(done, epochs), adapter) if done > 0 else (0, None)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def export_adapter(src: Path, export_dir: Path, epoch: int, step: int, final: bool = False, min_free_mb: int = MIN_FREE_MB) -> bool:
    """Copy ONLY the adapter files (about 130 MB) of a checkpoint to `export_dir/adapter` (the latest epoch replaces the previous one) and write epoch.json.
    Refuses, with a message, when the folder's disk has less than `min_free_mb` free: returns False and training goes on."""
    files = [src / n for n in ADAPTER_FILES if (src / n).is_file()]
    if len(files) != len(ADAPTER_FILES):
        print(f"[export] {src} has no adapter files, nothing copied")
        return False
    export_dir.mkdir(parents=True, exist_ok=True)
    free_mb = shutil.disk_usage(export_dir).free / 1e6
    need_mb = sum(f.stat().st_size for f in files) / 1e6
    if free_mb < min_free_mb + need_mb:
        print(f"[export] REFUSED: {export_dir} has {free_mb:.0f} MB free, need {min_free_mb} MB spare plus {need_mb:.0f} MB; nothing copied")
        return False
    tmp = export_dir / "adapter.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for f in files:
        shutil.copy2(f, tmp / f.name)
    old = export_dir / "adapter"
    shutil.rmtree(old, ignore_errors=True)
    tmp.rename(old)
    meta = {"epoch": epoch, "global_step": step, "final": final, "sha256": {f.name: file_sha256(old / f.name) for f in files}}
    (export_dir / "epoch.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[export] epoch {epoch} adapter ({need_mb:.0f} MB) copied to {old}")
    return True


def finalize(is_main: bool, model: Any, tok: Any, out: Path) -> bool:
    """Rank 0 alone writes the final adapter and tokenizer; every other rank writes nothing."""
    if not is_main:
        return False
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tok.save_pretrained(str(out))
    return True


def build_manifest(cfg_path: str, cfg: dict[str, Any], run: int | None, seed: int, plan: dict[str, int], gpus: dict[str, Any], env: dict[str, str] | None = None) -> dict[str, Any]:
    """Small JSON describing one run: code tag and sha (from VS_CODE_TAG / VS_CODE_SHA, set by the sbatch script), seed, config and data hashes, library versions, GPUs."""
    from importlib import metadata

    e = os.environ if env is None else env
    versions = {}
    for name in ("torch", "transformers", "peft", "bitsandbytes", "accelerate", "trl", "datasets"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "code_tag": e.get("VS_CODE_TAG"),
        "code_sha": e.get("VS_CODE_SHA"),
        "run": run,
        "seed": seed,
        "config_sha256": file_sha256(Path(cfg_path)),
        "data_sha256": {k: file_sha256(Path(cfg["data"][k])) for k in ("train", "dev") if Path(cfg["data"][k]).is_file()},
        "base_model": cfg["base_model"],
        "base_model_revision": e.get("VS_BASE_REVISION"),
        "plan": plan,
        "versions": versions,
        "gpus": gpus,
        "slurm_job_id": e.get("SLURM_JOB_ID"),
        "node": e.get("SLURMD_NODENAME") or e.get("HOSTNAME"),
    }


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


def _count_rows(path: str) -> int:
    n = 0
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            msgs = json.loads(line).get("messages")
            if not isinstance(msgs, list) or len(msgs) < 2 or msgs[-1].get("role") != "assistant":
                raise ValueError(f"{path} line {i}: expected chat 'messages' ending with an assistant turn")
            n += 1
    if n == 0:
        raise ValueError(f"{path} has no rows")
    return n


def make_plan(config_path: str, run: int | None, world_size: int | None = None, export_dir: str | None = None) -> dict[str, Any]:
    """Validate the config, the data files and the world-size arithmetic; no torch is imported. Raises ValueError/FileNotFoundError."""
    cfg = load_config(config_path)
    out = output_dir(cfg, run)
    rows: dict[str, int] = {}
    for key in ("train", "dev"):
        if not Path(cfg["data"][key]).is_file():
            raise FileNotFoundError(f"{key} data not found: {cfg['data'][key]} (build it with finetune.build_dataset)")
        rows[key] = _count_rows(cfg["data"][key])
    world = world_size or int(cfg.get("world_size", 1))
    batch = batch_plan(cfg, world)
    done, adapter = resume_plan(Path(export_dir) if export_dir else None, int(cfg["epochs"]))
    steps_per_epoch = -(-rows["train"] // batch["effective_batch_size"])
    return {
        "base_model": cfg["base_model"],
        "run": run,
        "seed": SEED + (run or 0),
        "output": str(out),
        "rows": rows,
        "epochs": int(cfg["epochs"]),
        "epochs_already_done": done,
        "resume_adapter": str(adapter) if adapter else None,
        "optimizer_steps_per_epoch": steps_per_epoch,
        **batch,
    }


def train(
    config_path: str = "configs/finetune/qlora.yaml",
    run: int | None = None,
    export_dir: str | None = None,
    base_model: str | None = None,
) -> str:
    """Train (under torchrun: one process per GPU) and return the adapter directory.

    Args:
        config_path: the QLoRA YAML (base model, LoRA, epochs, data, output, world size)
        run: which of the `runs` repeated trainings this is (seed = 42 + run, folder `<output>/run<run>`); None for a single run into `output`
        export_dir: folder (on $HOME) that receives only the adapter files after every epoch; a non-empty one is the resume point
        base_model: local folder with the base weights, used instead of the Hugging Face id of the config

    Returns:
        Adapter path.
    """
    cfg = load_config(config_path)
    rank, local_rank, world = dist_env()
    plan = make_plan(config_path, run, world, export_dir)
    out = output_dir(cfg, run)
    is_main = rank == 0
    _require("torch", "transformers", "peft", "bitsandbytes", "accelerate")

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainerCallback,
        TrainingArguments,
        set_seed,
    )

    n_gpu = torch.cuda.device_count()
    if local_rank >= n_gpu:
        raise RuntimeError(f"LOCAL_RANK {local_rank} but only {n_gpu} CUDA device(s) are visible")
    torch.cuda.set_device(local_rank)  # before any NCCL call: each process owns the GPU of its local rank
    peers = [[i == j or bool(torch.cuda.can_device_access_peer(i, j)) for j in range(n_gpu)] for i in range(n_gpu)]
    # PCIe 2080 Ti nodes often have no peer access between cards; NCCL then may hang on P2P. Detect it and switch P2P (and the irrelevant IB) off,
    # unless the caller set the variables already. Must happen before the first collective (the process group is created by TrainingArguments).
    for k, v in nccl_env_hints(peers).items():
        os.environ.setdefault(k, v)
    gpus = {
        "names": [torch.cuda.get_device_name(i) for i in range(n_gpu)],
        "capability": [list(torch.cuda.get_device_capability(i)) for i in range(n_gpu)],
        "peer_access": peers,
        "nccl_env": {k: os.environ[k] for k in os.environ if k.startswith("NCCL_")},
        "nccl_version": ".".join(map(str, torch.cuda.nccl.version())) if hasattr(torch.cuda, "nccl") else None,
        "torch_cuda": torch.version.cuda,
    }

    seed = SEED + (run or 0)
    set_seed(seed)  # the same seed on every rank: identical LoRA init and identical data order; dropout streams are re-seeded per rank below
    src = base_model or cfg["base_model"]
    tok = AutoTokenizer.from_pretrained(src)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        src, quantization_config=bnb, torch_dtype=torch.float16, device_map={"": local_rank}
    )
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=True, gradient_checkpointing_kwargs={"use_reentrant": False}
    )
    model = get_peft_model(model, LoraConfig(**lora_settings(cfg)))
    exp = Path(export_dir) if export_dir else None
    done, adapter = resume_plan(exp, int(cfg["epochs"]))
    if adapter is not None:
        from peft import set_peft_model_state_dict
        from safetensors.torch import load_file

        set_peft_model_state_dict(model, load_file(str(adapter / ADAPTER_FILES[0])))
    if is_main:
        model.print_trainable_parameters()
        out.mkdir(parents=True, exist_ok=True)
        manifest = build_manifest(config_path, cfg, run, seed, plan, gpus)
        manifest["resumed_from_epoch"] = done
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        if exp is not None:
            exp.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out / "manifest.json", exp / "manifest.json")
        print(f"[plan] {json.dumps(plan)}")
    remaining = int(cfg["epochs"]) - done
    if remaining <= 0:
        print("[resume] all epochs are already done; finalising the saved adapter")
        finalize(is_main, model, tok, out)
        return str(out)

    def rows(path: str) -> list[dict[str, list[int]]]:
        with open(path, encoding="utf-8") as fh:
            return [_encode(tok, json.loads(line)["messages"]) for line in fh if line.strip()]

    class Hooks(TrainerCallback):
        """Per-rank dropout seed, GPU memory in the log, and the adapter copy to $HOME after each epoch (rank 0 only)."""

        def on_train_begin(self, args, state, control, **kw):
            torch.manual_seed(rank_seed(seed + done, rank))

        def on_log(self, args, state, control, logs=None, **kw):
            if is_main and logs and "loss" in logs:
                print(f"[mem] step {state.global_step} max_alloc_gb={torch.cuda.max_memory_allocated() / 2**30:.2f}")

        def on_save(self, args, state, control, **kw):
            if is_main and exp is not None:
                export_adapter(Path(args.output_dir) / f"checkpoint-{state.global_step}", exp, done + round(state.epoch or 0), state.global_step)

    args = TrainingArguments(
        output_dir=str(out / "checkpoints"),
        num_train_epochs=remaining,
        per_device_train_batch_size=plan["per_device_batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=plan["gradient_accumulation_steps"],
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.03,
        fp16=True,
        optim="paged_adamw_8bit",
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},  # reentrant checkpointing breaks DDP with frozen base weights
        ddp_find_unused_parameters=False,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        save_only_model=False,
        report_to=[],
        seed=seed + done,
        data_seed=seed + done,
        log_level_replica="warning",
    )
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=rows(cfg["data"]["train"]),
        eval_dataset=rows(cfg["data"]["dev"]),
        data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100),
        callbacks=[Hooks()],
    )
    ckpts = sorted((out / "checkpoints").glob("checkpoint-*")) if (out / "checkpoints").is_dir() else []
    trainer.train(resume_from_checkpoint=str(ckpts[-1]) if ckpts else None)  # same-job scratch checkpoint: full restore, optimizer included
    if finalize(is_main, trainer.model, tok, out) and exp is not None:
        export_adapter(out, exp, int(cfg["epochs"]), int(trainer.state.global_step), final=True)
    return str(out)


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m vakeel_sahayak.finetune.train_qlora [CONFIG] [--run K] [--dry-run] [--export-dir D] [--base-model P] [--world-size N] (K also from RUN)."""
    import argparse

    ap = argparse.ArgumentParser(description="QLoRA training of the Qwen3-4B extractor (torchrun DDP)")
    ap.add_argument("config", nargs="?", default="configs/finetune/qlora.yaml")
    ap.add_argument("--run", type=int, default=int(os.environ["RUN"]) if os.environ.get("RUN") else None)
    ap.add_argument("--dry-run", action="store_true", help="validate config, data and world-size arithmetic, print the plan, import no torch")
    ap.add_argument("--export-dir", default=os.environ.get("VS_EXPORT_DIR"), help="copy only the adapter here after every epoch; resume from it")
    ap.add_argument("--base-model", default=None, help="local folder with the base weights")
    ap.add_argument("--world-size", type=int, default=None, help="dry run only: GPUs to plan for (default: WORLD_SIZE, else the config)")
    ns = ap.parse_args(argv)
    if ns.dry_run:
        try:
            world = ns.world_size or (dist_env()[2] if "WORLD_SIZE" in os.environ else None)
            plan = make_plan(ns.config, ns.run, world, ns.export_dir)
        except (FileNotFoundError, ValueError) as err:
            print(f"dry-run FAILED: {err}")
            return 1
        print(json.dumps(plan, indent=1))
        return 0
    print(train(ns.config, ns.run, ns.export_dir, ns.base_model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
