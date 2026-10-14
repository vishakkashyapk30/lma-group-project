"""Helpers for the test-set construction tests (plan §15.2, T1-T9): synthetic inputs built by construction, an independent 8-gram check.

ASSUMPTIONS (one place to adjust; the plan fixes sizes and composition, not file layouts):

* `parts_path` (input of T1): JSON lines of {"doc_id", "court", "date", "offence_date", "parts": {<OrderPart value>: text}}.
* `gold_dir` (input of T1): g1.jsonl ... g7.jsonl, each row {"doc_id", "labels": ...}.
* T1 output (`out_dir/cases.jsonl`): {"case_id", "doc_id", "court", "facts_text", "bns_era", "gold": {"G1": ..., ..., "G7": ...}}.
* T3, T4, T5, T6, T7, T8, T9 write `out_dir/<name>.jsonl` plus `manifest.json` (`TestSetManifest`); row keys are named in each test file.
* Every builder is deterministic (fixed seeds): two builds into different directories give identical rows.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tests.unit.pipelines._helpers import words, write_jsonl  # noqa: F401  (re-exported)
from vakeel_sahayak.schemas.enums import OrderPart
from vakeel_sahayak.testsets.common import TestSetManifest

PARTS = [p.value for p in OrderPart]
COURTS = ["Delhi High Court", "Bombay High Court", "Allahabad High Court", "Madras High Court"]


def ngrams(text: str, n: int = 8) -> set[tuple[str, ...]]:
    toks = text.lower().split()
    return {tuple(toks[i : i + n]) for i in range(len(toks) - n + 1)}


def shares_ngram(a: str, b: str, n: int = 8) -> bool:
    """Independent of `pipelines.leakage.assert_no_overlap` (which has its own tests)."""
    return bool(ngrams(a, n) & ngrams(b, n))


def order_parts(i: int, leak: bool = False) -> dict[str, str]:
    """Five parts with disjoint vocabularies (so no accidental 8-word overlap); `leak` copies 9 facts words into the reasoning."""
    parts = {p: " ".join(words(f"{p[:3]}{i:03d}w", 40)) for p in PARTS}
    if leak:
        facts = parts["facts"].split()
        parts["reasoning"] += " " + " ".join(facts[5:14])
    return parts


def write_t1_inputs(tmp: Path, n_candidates: int = 400, n_bns: int = 62, leaky: set[int] | None = None) -> tuple[Path, Path]:
    """`n_candidates` cleanly split test orders, `n_bns` of them BNS-era (offence on or after 2024-07-01), with G1-G7 gold each."""
    leaky = leaky or set()
    rows, gold = [], {f"g{k}": [] for k in range(1, 8)}
    for i in range(n_candidates):
        bns = i < n_bns
        offence = "2024-08-15" if bns else "2023-11-02"
        doc_id = f"TEST-{i:04d}"
        rows.append({"doc_id": doc_id, "court": COURTS[i % 4], "date": "2025-01-10", "offence_date": offence,
                     "parts": order_parts(i, leak=i in leaky)})
        for k in range(1, 8):
            gold[f"g{k}"].append({"doc_id": doc_id, "labels": [f"label-{k}"]})
    # shuffle the BNS-era orders to the END so that taking the first 200 would give none of them
    rows = rows[n_bns:] + rows[:n_bns]
    parts_path = write_jsonl(tmp / "parts.jsonl", rows)
    gold_dir = tmp / "gold"
    gold_dir.mkdir()
    for name, g in gold.items():
        write_jsonl(gold_dir / f"{name}.jsonl", g)
    return parts_path, gold_dir


def write_t1_dir(tmp: Path, n: int = 200, n_bns: int = 70) -> Path:
    """A finished T1 directory (the output shape above) for the sets built on top of T1."""
    d = tmp / "t1"
    d.mkdir(exist_ok=True)
    rows = []
    for i in range(n):
        rows.append({
            "case_id": f"t1-{i:03d}", "doc_id": f"TEST-{i:04d}", "court": COURTS[i % 4],
            "facts_text": f"The accused of case {i} was arrested on 20.08.2024 under Section 318(4) BNS; charge sheet not yet filed.",
            "bns_era": i < n_bns,
            "gold": {"G3": {"arrest_date": "2024-08-20", "first_remand": "2024-08-21", "charge_sheet": {"filed": False},
                            "co_accused_bail": [], "sections": ["318(4) BNS"], "fir": {"number": f"{100 + i}/2024", "police_station": "PS-1"}}},
        })
    write_jsonl(d / "cases.jsonl", rows)
    return d


def read_rows(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def read_manifest(out_dir: str | Path) -> dict[str, Any]:
    return json.loads((Path(out_dir) / "manifest.json").read_text(encoding="utf-8"))


def assert_manifest(m: TestSetManifest, set_id: str, size: int | None = None) -> None:
    assert isinstance(m, TestSetManifest) and m.set_id == set_id
    if size is not None:
        assert m.size == size
    assert m.answers_from.strip() and m.path


def write_t4_dir(tmp: Path, n: int = 120) -> Path:
    """A finished T4 directory (out_dir/scenarios.jsonl): default-bail scenarios straddling the 60-day line."""
    d = tmp / "t4"
    d.mkdir(exist_ok=True)
    rows = []
    for i in range(n):
        day = 59 + i % 3
        rows.append({"id": f"s-{i:03d}", "rule": "default_bail", "inputs": {"first_remand": "2024-08-21", "day": day, "max_punishment": "7 years"},
                     "designed_answer": "ELIGIBLE" if day == 61 else "NOT_YET", "bundle": f"s-{i:03d}.pdf"})
    write_jsonl(d / "scenarios.jsonl", rows)
    return d


def write_t2_dir(tmp: Path, t1_dir: Path, n: int = 20) -> Path:
    """A finished T2 directory (out_dir/truth.jsonl), bundles of T1 cases."""
    d = tmp / "t2"
    d.mkdir(exist_ok=True)
    cases = read_rows(t1_dir / "cases.jsonl")[:n]
    rows = [{"bundle_id": f"b-{i:03d}", "case_id": c["case_id"], "kind": f"K{1 + i % 6}", "pages": [{"page": 1, "text": "x"}],
             "documents": [{"doc_id": "d1", "type": "FIR", "pages": [1, 1]}], "fields": c["gold"]["G3"]} for i, c in enumerate(cases)]
    write_jsonl(d / "truth.jsonl", rows)
    return d
