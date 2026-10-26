"""Tiny synthetic T1 gold and run directories for the scoring tests (offline, no data/ dependency)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets.blind import seal_blind

ALL = ["custody_period", "charge_sheet_filed", "trial_delay", "antecedents", "flight_risk", "gravity_and_punishment"]


def gold_row(case_id: str, g1: list[str], g5: list[str] | None = None, g4: list[str] | None = None, g2: list[str] | None = None,
             answerable: list[str] | None = None) -> dict[str, Any]:
    return {"case_id": case_id, "doc_id": f"DOC-{case_id}", "court": "X High Court", "date": "2025-01-01", "before": "2025-01-01", "facts_text": "facts",
            "bns_era": True, "post_release": True, "script": "latin", "answerable": ALL if answerable is None else answerable,
            "gold": {"G1": {"labels": g1}, "G2": {"labels": g2 or [], "raw": list(g2 or []), "unresolved": []}, "G3": {"labels": []}, "G4": {"labels": g4 or []},
                     "G5": {"labels": g5 or []}, "G6": {"labels": []}, "G7": {"labels": []}}}


def write_t1(root: Path, source: str, dev: list[dict[str, Any]], test: list[dict[str, Any]], open_ids: list[str], blind_ids: list[str]) -> Path:
    """`<root>/t1` (agreed) or `<root>/t1_rule_only` (rule) with cases, dev, the id manifests and the sealed blind slice."""
    d = root / ("t1" if source == "agreed" else "t1_rule_only")
    d.mkdir(parents=True, exist_ok=True)
    (d / "cases.jsonl").write_text("\n".join(json.dumps(r) for r in test) + "\n", encoding="utf-8")
    (d / "dev.jsonl").write_text("\n".join(json.dumps(r) for r in dev) + "\n", encoding="utf-8")
    (d / "manifest_open.json").write_text(json.dumps({"slice": "open", "n": len(open_ids), "case_ids": open_ids}), encoding="utf-8")
    seal_blind(blind_ids, str(d))
    return d


def ground(factor: str, stance: str = "favourable", check: str = "SUPPORTED", argument: str = "an argument") -> dict[str, Any]:
    return {"id": f"G-{factor}", "factor": factor, "stance": stance, "argument": argument, "authorities": [], "check": check}


def record(case_id: str, factors: list[str], *, tokens: int = 100, store_calls: int = 2, objections: list[str] | None = None, retrieved: list[str] | None = None,
           gates: bool = True, error: str | None = None) -> dict[str, Any]:
    rec: dict[str, Any] = {"case_id": case_id, "brief": {"case_id": case_id, "grounds": [ground(f) for f in factors], "open_issues": []},
                           "meta": {"tokens": tokens, "store_calls": store_calls, "seconds": 1.5},
                           "sparring": {"objections": [{"id": f"O{i}", "factor": f} for i, f in enumerate(objections or [])]}}
    if gates:
        rec["gate1_approved"] = True
    if retrieved is not None:
        rec["retrieved"] = retrieved
    if error:
        rec["error"] = error
    return rec


def write_run(root: Path, system: str, run: int, records: list[dict[str, Any]], *, gold_source: str = "agreed", backend: str = "offline") -> Path:
    name = system if run == 1 else f"{system}__run{run}"
    d = root / "outputs" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "MANIFEST.json").write_text(json.dumps({"system": system, "variant": system, "gold_source": gold_source, "models": {"llm_backend": backend, "models_mode": backend}}), encoding="utf-8")
    for r in records:
        (d / f"{r['case_id']}.json").write_text(json.dumps(r), encoding="utf-8")
    return d
