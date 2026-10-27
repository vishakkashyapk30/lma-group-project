"""QLoRA under torchrun DDP (owner decision 2026-10-27, 4 x 2080 Ti): world-size arithmetic, rank-0-only writes, the adapter copy guard, resume, dry run.

Nothing here imports torch: the training function itself needs a GPU and is untested until the first job.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from vakeel_sahayak.finetune import train_qlora as tq

REPO = Path(__file__).resolve().parents[3]


def _chat(n: int) -> str:
    row = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "f"}, {"role": "assistant", "content": "{}"}]}
    return "\n".join(json.dumps(row) for _ in range(n)) + "\n"


@pytest.fixture()
def cfg_file(tmp_path, load_yaml):
    cfg = load_yaml("finetune/qlora.yaml")
    (tmp_path / "train.jsonl").write_text(_chat(40), encoding="utf-8")
    (tmp_path / "dev.jsonl").write_text(_chat(4), encoding="utf-8")
    cfg["data"]["train"], cfg["data"]["dev"] = str(tmp_path / "train.jsonl"), str(tmp_path / "dev.jsonl")
    cfg["output"] = str(tmp_path / "out")
    p = tmp_path / "qlora.yaml"
    p.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return p


@pytest.mark.parametrize("world,accum", [(1, 16), (2, 8), (4, 4), (8, 2), (16, 1)])
def test_world_size_arithmetic_keeps_the_effective_batch(load_yaml, world, accum):
    plan = tq.batch_plan(load_yaml("finetune/qlora.yaml"), world)
    assert plan["gradient_accumulation_steps"] == accum
    assert plan["per_device_batch_size"] * plan["gradient_accumulation_steps"] * world == 16


@pytest.mark.parametrize("world", [3, 5, 32])
def test_world_size_that_does_not_divide_the_batch_is_refused(load_yaml, world):
    with pytest.raises(ValueError, match="not divisible"):
        tq.batch_plan(load_yaml("finetune/qlora.yaml"), world)


def test_dist_env_reads_torchrun_variables_and_defaults_to_single_process():
    assert tq.dist_env({"RANK": "3", "LOCAL_RANK": "3", "WORLD_SIZE": "4"}) == (3, 3, 4)
    assert tq.dist_env({}) == (0, 0, 1)


def test_rank_seeds_are_distinct_and_deterministic():
    seeds = [tq.rank_seed(42, r) for r in range(4)]
    assert len(set(seeds)) == 4 and seeds == [tq.rank_seed(42, r) for r in range(4)]


def test_nccl_hints_disable_p2p_and_ib_only_when_peer_access_is_missing():
    full = [[True] * 4 for _ in range(4)]
    assert tq.nccl_env_hints(full) == {}
    broken = [row[:] for row in full]
    broken[0][3] = False
    assert tq.nccl_env_hints(broken) == {"NCCL_P2P_DISABLE": "1", "NCCL_IB_DISABLE": "1"}


class FakeModel:
    def __init__(self):
        self.saved: list[str] = []

    def save_pretrained(self, path):
        self.saved.append(path)
        Path(path, "adapter_model.safetensors").write_bytes(b"w")


def test_only_rank_zero_writes_the_final_adapter(tmp_path):
    for rank in (1, 2, 3):
        m = FakeModel()
        assert tq.finalize(rank == 0, m, FakeModel(), tmp_path / f"r{rank}") is False
        assert m.saved == [] and not (tmp_path / f"r{rank}").exists()
    m, t = FakeModel(), FakeModel()
    assert tq.finalize(True, m, t, tmp_path / "r0") is True
    assert m.saved == [str(tmp_path / "r0")] and t.saved == [str(tmp_path / "r0")]


def _ckpt(path: Path, size: int = 10) -> Path:
    path.mkdir(parents=True)
    (path / "adapter_model.safetensors").write_bytes(b"x" * size)
    (path / "adapter_config.json").write_text("{}", encoding="utf-8")
    (path / "optimizer.pt").write_bytes(b"o" * 1000)  # must NOT be copied
    return path


def test_export_copies_only_adapter_files_replaces_the_previous_epoch_and_records_checksums(tmp_path):
    exp = tmp_path / "home" / "run0"
    assert tq.export_adapter(_ckpt(tmp_path / "c1"), exp, epoch=1, step=10, min_free_mb=0)
    assert sorted(p.name for p in (exp / "adapter").iterdir()) == ["adapter_config.json", "adapter_model.safetensors"]
    assert tq.export_adapter(_ckpt(tmp_path / "c2", 20), exp, epoch=2, step=20, final=True, min_free_mb=0)
    meta = json.loads((exp / "epoch.json").read_text())
    assert meta["epoch"] == 2 and meta["final"] is True
    assert meta["sha256"]["adapter_model.safetensors"] == tq.file_sha256(exp / "adapter" / "adapter_model.safetensors")
    assert (exp / "adapter" / "adapter_model.safetensors").stat().st_size == 20 and not (exp / "adapter.tmp").exists()


def test_export_refuses_when_home_is_nearly_full(tmp_path, capsys):
    exp = tmp_path / "home"
    assert tq.export_adapter(_ckpt(tmp_path / "c"), exp, epoch=1, step=1, min_free_mb=10**9) is False
    assert "REFUSED" in capsys.readouterr().out and not (exp / "adapter").exists()


def test_export_without_adapter_files_copies_nothing(tmp_path):
    (tmp_path / "empty").mkdir()
    assert tq.export_adapter(tmp_path / "empty", tmp_path / "home", 1, 1, min_free_mb=0) is False


def test_resume_plan_restores_the_epoch_counter_from_the_last_copied_adapter(tmp_path):
    assert tq.resume_plan(None, 2) == (0, None)
    assert tq.resume_plan(tmp_path / "none", 2) == (0, None)
    tq.export_adapter(_ckpt(tmp_path / "c"), tmp_path / "home", epoch=1, step=5, min_free_mb=0)
    assert tq.resume_plan(tmp_path / "home", 2) == (1, tmp_path / "home" / "adapter")


def test_dry_run_prints_the_plan_for_four_gpus_without_importing_torch(cfg_file, tmp_path):
    code = (
        "import sys; from vakeel_sahayak.finetune import train_qlora as t; "
        f"rc = t.main([{str(cfg_file)!r}, '--dry-run', '--run', '1', '--world-size', '4']); "
        "assert not {'torch', 'transformers', 'peft', 'bitsandbytes'} & set(sys.modules), 'heavy library imported'; sys.exit(rc)"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO, timeout=60)
    assert r.returncode == 0, r.stderr + r.stdout
    plan = json.loads(r.stdout)
    assert plan["world_size"] == 4 and plan["gradient_accumulation_steps"] == 4 and plan["seed"] == 43
    assert plan["rows"] == {"train": 40, "dev": 4} and plan["optimizer_steps_per_epoch"] == 3
    assert plan["output"].endswith("run1")


def test_dry_run_fails_cleanly_on_bad_world_size_missing_data_and_bad_rows(cfg_file, tmp_path, capsys):
    assert tq.main([str(cfg_file), "--dry-run", "--world-size", "3"]) == 1 and "not divisible" in capsys.readouterr().out
    cfg = yaml.safe_load(cfg_file.read_text())
    Path(cfg["data"]["dev"]).write_text('{"not": "chat"}\n', encoding="utf-8")
    assert tq.main([str(cfg_file), "--dry-run"]) == 1 and "messages" in capsys.readouterr().out
    Path(cfg["data"]["dev"]).unlink()
    assert tq.main([str(cfg_file), "--dry-run"]) == 1 and "dev data not found" in capsys.readouterr().out
