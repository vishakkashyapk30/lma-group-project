"""QLoRA training (plan §12 step 5, §17): Qwen3-4B, r=16, 2 epochs, one 2080 Ti, FP16, checkpoint every epoch; the only `sbatch` job.

Config and script facts pass on the skeleton; the `train` tests fail until it is implemented. The 2080 Ti is a Turing card with no
bf16 support, which is why precision is FP16 (ASSUMPTION: `train` refuses any other precision before it loads a model).
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest
import yaml

from vakeel_sahayak.finetune import train_qlora
from vakeel_sahayak.finetune.merge_adapter import export_for_laptop

REPO = Path(__file__).resolve().parents[3]
FINETUNE_DIR = REPO / "src" / "vakeel_sahayak" / "finetune"
HEAVY = {"torch", "transformers", "peft", "bitsandbytes", "trl", "vllm", "accelerate", "datasets"}


@pytest.fixture()
def qlora(load_yaml):
    return load_yaml("finetune/qlora.yaml")


def test_base_model_is_qwen3_4b_the_same_weights_as_munshi(qlora, load_yaml):
    """The extractor is an adapter on the Munshi 4B weights (plan §12): same base model id."""
    models = load_yaml("models.yaml")["llm"]
    assert qlora["base_model"] == "Qwen/Qwen3-4B" == models["munshi_4b"]["model"] == models["extractor_4b"]["model"]


def test_lora_rank_is_16_and_epochs_are_2(qlora):
    """Plan §12 step 5: r=16, 2 epochs."""
    assert qlora["lora"]["r"] == 16
    assert qlora["epochs"] == 2


def test_precision_is_fp16(qlora):
    assert qlora["precision"] == "fp16"


def test_four_bit_nf4_quantisation(qlora):
    """QLoRA: the frozen base is 4-bit NF4."""
    assert qlora["quantization"] == {"bits": 4, "type": "nf4"}


def test_checkpoint_every_epoch_so_a_failed_run_resumes(qlora):
    """Plan §17: checkpoints every epoch (a batch job that dies after epoch 1 keeps epoch 1)."""
    assert qlora["checkpoint_every"] == "epoch"


def test_thirty_percent_of_inputs_are_noisy(qlora):
    """The config's noisy fraction is the plan's 30%, the same default as `augment_pairs`."""
    from vakeel_sahayak.finetune.noise_augment import augment_pairs

    assert qlora["data"]["noisy_fraction"] == 0.3
    assert inspect.signature(augment_pairs).parameters["fraction"].default == qlora["data"]["noisy_fraction"]


def test_three_runs_and_the_adapter_path_matches_models_yaml(qlora, load_yaml):
    """Three training runs (plan §17: ~100 GPU-h for 3 runs); the output dir is where `extractor_4b` loads its adapter from."""
    assert qlora["runs"] == 3
    assert qlora["output"] == load_yaml("models.yaml")["llm"]["extractor_4b"]["adapter"]


def test_unset_lora_hyperparameters_are_marked_for_dev_tuning(qlora):
    """alpha, dropout and target modules are not fixed by the plan: they stay null with a TODO until tuned on dev."""
    assert qlora["lora"]["alpha"] is None and qlora["lora"]["dropout"] is None and qlora["lora"]["target_modules"] is None
    assert "TODO" in (REPO / "configs/finetune/qlora.yaml").read_text(encoding="utf-8")


def test_train_default_config_path_is_the_qlora_yaml():
    params = inspect.signature(train_qlora.train).parameters
    assert params["config_path"].default == "configs/finetune/qlora.yaml"
    assert (REPO / params["config_path"].default).exists()


SBATCH = REPO / "scripts/ada/sbatch_qlora.sbatch"


def _directives() -> dict[str, str]:
    return dict(re.findall(r"^#SBATCH --([\w-]+)=(\S+)", SBATCH.read_text(encoding="utf-8"), re.M))


# RECONCILED: owner decision 2026-10-27, 4 GPUs for DDP QLoRA; plan section 17 said one
def test_sbatch_script_asks_for_four_gpus_one_task_and_at_most_one_and_a_half_days():
    """One node, one task (torchrun starts the 4 processes), exactly 4 x 2080 Ti, at most 1.5 days, modest CPUs and memory."""
    d = _directives()
    assert d["gres"] == "gpu:4" and d["constraint"] == "2080ti"
    assert d["nodes"] == "1" and d["ntasks"] == "1"
    assert d["account"] == "research" and d["qos"] == "medium" and d["partition"] == "u22"
    assert int(d["cpus-per-task"]) <= 8 and d["mem"] == "64G"
    t = d["time"]
    days, hms = (int(t.split("-")[0]), t.split("-")[1]) if "-" in t else (0, t)
    hh, mm, ss = (int(x) for x in hms.split(":"))
    assert days * 24 + hh + mm / 60 + ss / 3600 <= 36, "at most 1.5 days"


def test_sbatch_script_excludes_the_broken_node_and_uses_scratch_not_home_caches():
    text = SBATCH.read_text(encoding="utf-8")
    assert _directives()["exclude"] == "gnode069"
    assert _directives()["output"].startswith("slurm_logs/")
    assert 'W="/scratch/$USER/vs-qlora' in text
    for var in ("PIP_CACHE_DIR", "TMPDIR", "HF_HOME", "TRITON_CACHE_DIR", "TORCHINDUCTOR_CACHE_DIR"):
        assert re.search(rf'{var}="\$W/', text), var
    assert "PIP_NO_CACHE_DIR=1" in text
    assert "$HOME/.cache" not in text and "~/.cache" not in text
    assert "trap cleanup EXIT" in text and 'rm -rf "$W"' in text


def test_sbatch_script_runs_torchrun_with_four_processes_and_installs_from_the_pytorch_index_first():
    text = SBATCH.read_text(encoding="utf-8")
    assert "--nproc_per_node=4" in text and "torchrun" in text and "vakeel_sahayak.finetune.train_qlora" in text
    assert text.index("download.pytorch.org/whl/cu128") < text.index("qlora_requirements.txt")
    assert "--export-dir" in text and "sha256sum" in text and "git clone" not in text  # the code arrives as a staged tarball
    reqs = (REPO / "scripts/ada/qlora_requirements.txt").read_text(encoding="utf-8")
    for lib in ("transformers", "peft", "bitsandbytes", "accelerate", "trl", "datasets"):
        assert re.search(rf"^{lib}==\d", reqs, re.M), f"{lib} is not pinned"
    assert not re.search(r"^torch\b", reqs, re.M), "torch comes from the PyTorch index, not this file"


def test_config_world_size_matches_the_sbatch_and_keeps_the_effective_batch_of_16(qlora):
    assert qlora["world_size"] == 4 == int(_directives()["gres"].split(":")[1])
    assert qlora["effective_batch_size"] == 16 and qlora["per_device_batch_size"] == 1


def test_qlora_is_the_only_sbatch_job():
    """Plan §17: inference runs in interactive sessions only; the one sbatch job is training."""
    offenders = [p.name for p in (REPO / "scripts").rglob("*") if p.is_file() and "#SBATCH" in p.read_text(encoding="utf-8", errors="ignore")]
    assert offenders == ["sbatch_qlora.sbatch"]  # the stage and fetch scripts only mention the word in prose, never as a directive


@pytest.mark.parametrize("path", sorted(FINETUNE_DIR.glob("*.py")), ids=lambda p: p.name)
def test_finetune_modules_import_no_heavy_library_at_top_level(path):
    """Skeleton convention: torch, transformers, peft ... are imported inside functions so the package imports on a bare install."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & HEAVY


@pytest.mark.parametrize("override", [{"precision": "bf16"}, {"precision": "fp32"}])
def test_train_refuses_a_precision_other_than_fp16(tmp_path, qlora, override):
    """ASSUMPTION: bf16 is rejected up front (a 2080 Ti cannot do it) rather than failing after the model has loaded."""
    cfg = tmp_path / "qlora.yaml"
    cfg.write_text(yaml.safe_dump({**qlora, **override}), encoding="utf-8")
    with pytest.raises(ValueError):
        train_qlora.train(str(cfg))


def test_train_refuses_a_missing_config(tmp_path):
    with pytest.raises(FileNotFoundError):
        train_qlora.train(str(tmp_path / "nope.yaml"))


def test_export_for_laptop_needs_an_existing_adapter(tmp_path):
    """merge_adapter.export_for_laptop(adapter_dir, out_dir) packages the adapter for the local_llm client: no adapter, no package."""
    with pytest.raises(FileNotFoundError):
        export_for_laptop(str(tmp_path / "missing"), str(tmp_path / "out"))
