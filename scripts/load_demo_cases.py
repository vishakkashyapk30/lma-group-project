"""Load the T2 test bundles into a running API as demo cases, through the same calls the web interface makes.

T2 (`data/testsets/t2`) holds 100 cases built from public court bail orders, each printed in six input kinds (K1 born-digital, K2 scanned,
K3 degraded scan, K4 phone photo, K5 Hindi born-digital, K6 legacy-font Hindi). One bundle per case is loaded, the kinds taken in turn,
so the cause list has 100 distinct cases and every input kind appears. Each case is created (POST /api/cases) and its bundle uploaded
(POST /api/cases/{id}/upload), which runs intake: Munshi reads the pages, Peshkar builds the dossier, the List of Dates and the Rights
check. Nothing is approved: the two gates stay for counsel to approve in the interface.

Public data only (no client files). Re-running skips the cases whose title is already on the cause list.

Usage: .venv/bin/python scripts/load_demo_cases.py [--api http://127.0.0.1:8000] [--limit N] [--kinds K1,K2,K3,K4,K5,K6]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
T2 = ROOT / "data" / "testsets" / "t2"
KIND_NAMES = {"K1": "born-digital PDF", "K2": "scanned", "K3": "degraded scan", "K4": "phone photo", "K5": "Hindi PDF", "K6": "legacy-font Hindi"}


def plan(kinds: list[str], limit: int | None) -> list[dict]:
    """One bundle per case, the kinds taken in turn: [{case, bundle, path, title}]."""
    rows = [json.loads(line) for line in (T2 / "truth.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    by_case: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_case.setdefault(r["case_id"], {})[r["kind"]] = r
    out = []
    for i, case in enumerate(sorted(by_case)):
        kind = next((k for k in kinds[i % len(kinds):] + kinds if k in by_case[case]), None)
        if kind is None:
            continue
        r = by_case[case][kind]
        sections = ", ".join((r.get("fields") or {}).get("sections") or []) or "sections not stated"
        out.append({"case": case, "bundle": r["bundle_id"], "path": T2 / r["pdf"],
                    "title": f"{case} · {sections} · {KIND_NAMES.get(kind, kind)}"})
    return out[:limit] if limit else out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--kinds", default=",".join(KIND_NAMES))
    args = ap.parse_args(argv)
    if not (T2 / "truth.jsonl").is_file():
        print(f"{T2} is missing: install the team data bundle first (make data)", file=sys.stderr)
        return 1
    todo = plan([k.strip() for k in args.kinds.split(",") if k.strip()], args.limit)
    with httpx.Client(base_url=args.api, timeout=600) as api:
        have = {c["title"] for c in api.get("/api/cases").raise_for_status().json()}
        done = failed = 0
        for item in todo:
            if item["title"] in have:
                continue
            start = time.time()
            try:
                case_id = api.post("/api/cases", json={"title": item["title"]}).raise_for_status().json()["case_id"]
                with open(item["path"], "rb") as fh:
                    api.post(f"/api/cases/{case_id}/upload", files=[("files", (item["path"].name, fh, "application/pdf"))]).raise_for_status()
                stage = api.get(f"/api/cases/{case_id}").raise_for_status().json()["stage"]
                done += 1
                print(f"{case_id}  {item['bundle']:12s} {stage:8s} {time.time() - start:5.1f}s  {item['title']}", flush=True)
            except httpx.HTTPError as exc:
                failed += 1
                print(f"FAILED {item['bundle']}: {exc}", flush=True)
    print(f"loaded {done}, failed {failed}, already present {len(todo) - done - failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
