"""Assemble the SFT dataset in chat format (plan §2, §12): train/dev JSON lines, with TEST orders and SAME-FIR orders excluded from the
fine-tuning data (plan §2 leakage rule).

# SKELETON-GAP: `build_sft_dataset(pairs_path, out_dir)` has no argument for the exclusion list; the tests make it come from
# `pipelines.leakage.excluded_doc_ids` (patched) and assume the output files are `train.jsonl` and `dev.jsonl` (configs/finetune/qlora.yaml
# `data.train` / `data.dev`). The chat shape is ASSUMPTION: {"messages": [system?, user = facts, assistant = target dossier JSON]}.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from tests.unit.finetune._helpers import pair_row, patch_everywhere, read_rows, write_jsonl
from vakeel_sahayak.finetune.build_dataset import build_sft_dataset

EXCLUDED = {"TESTORD-2024-0001", "SAMEFIR-2024-0002"}


def run_build(tmp_path, monkeypatch, rows, excluded=EXCLUDED):
    patch_everywhere(monkeypatch, "vakeel_sahayak.pipelines.leakage", "excluded_doc_ids", lambda *a, **k: set(excluded))
    src = write_jsonl(tmp_path / "pairs.jsonl", rows)
    out = tmp_path / "sft"
    n = build_sft_dataset(str(src), str(out))
    return n, read_rows(out / "train.jsonl"), read_rows(out / "dev.jsonl")


def rows_with_leaks(n: int = 100):
    return [pair_row(f"DLHC-2022-{i:04d}") for i in range(n)] + [pair_row("TESTORD-2024-0001"), pair_row("SAMEFIR-2024-0002")]


def test_signature():
    assert list(inspect.signature(build_sft_dataset).parameters) == ["pairs_path", "out_dir"]


def test_the_data_paths_of_qlora_yaml_are_the_two_files_written(load_yaml):
    data = load_yaml("finetune/qlora.yaml")["data"]
    assert Path(data["train"]).name == "train.jsonl" and Path(data["dev"]).name == "dev.jsonl"


def test_test_orders_and_same_fir_orders_are_excluded(tmp_path, monkeypatch):
    """Plan §2: test orders AND orders with the same FIR as a test order never reach fine-tuning data."""
    n, train, dev = run_build(tmp_path, monkeypatch, rows_with_leaks())
    blobs = [json.dumps(r) for r in train + dev]
    assert not any(x in blob for x in EXCLUDED for blob in blobs)
    assert n == 100 == len(train) + len(dev)


def test_train_and_dev_are_disjoint_and_cover_every_kept_pair(tmp_path, monkeypatch):
    n, train, dev = run_build(tmp_path, monkeypatch, rows_with_leaks())
    t = {json.dumps(r, sort_keys=True) for r in train}
    d = {json.dumps(r, sort_keys=True) for r in dev}
    assert not t & d and len(t) + len(d) == n


def test_dev_is_a_small_nonempty_share(tmp_path, monkeypatch):
    """# ASSUMPTION: dev is a minority split (used for the threshold tuning of plan §14.2) but never empty on 100 pairs."""
    _, train, dev = run_build(tmp_path, monkeypatch, rows_with_leaks())
    assert 0 < len(dev) < len(train)


def test_rows_are_chat_format_with_facts_in_and_dossier_out(tmp_path, monkeypatch):
    """Each row is a conversation: the user turn is the facts text, the assistant turn is the dossier JSON the extractor must output."""
    source = rows_with_leaks(10)
    _, train, dev = run_build(tmp_path, monkeypatch, source)
    by_facts = {r["facts"]: r["dossier"] for r in source}
    for row in train + dev:
        roles = [m["role"] for m in row["messages"]]
        assert roles[-2:] == ["user", "assistant"]
        user, assistant = row["messages"][-2]["content"], row["messages"][-1]["content"]
        assert user in by_facts
        assert json.loads(assistant) == by_facts[user]


def test_noisy_inputs_keep_their_clean_target(tmp_path, monkeypatch):
    """A pair whose facts were replaced by OCR noise (step 4) still has the original dossier as the assistant turn."""
    row = pair_row("o1", facts="Fcts of 0rder 1: arrested on 2O.O8.2O24 under Sect1on 318(4) BNS.")
    _, train, dev = run_build(tmp_path, monkeypatch, [row] + [pair_row(f"o{i}") for i in range(2, 30)])
    found = [r for r in train + dev if "Sect1on" in r["messages"][-2]["content"]]
    assert len(found) == 1 and json.loads(found[0]["messages"][-1]["content"]) == row["dossier"]


def test_output_is_deterministic(tmp_path, monkeypatch):
    rows = rows_with_leaks(50)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, t1, d1 = run_build(tmp_path / "a", monkeypatch, rows)
    _, t2, d2 = run_build(tmp_path / "b", monkeypatch, rows)
    assert (t1, d1) == (t2, d2)


@pytest.mark.parametrize("excluded", [set(), {"nope"}])
def test_nothing_excluded_keeps_everything(tmp_path, monkeypatch, excluded):
    """With an empty exclusion set every pair is kept (the filter removes only what the leakage module names)."""
    rows = [pair_row(f"o{i}") for i in range(20)]
    n, train, dev = run_build(tmp_path, monkeypatch, rows, excluded)
    assert n == 20 == len(train) + len(dev)
