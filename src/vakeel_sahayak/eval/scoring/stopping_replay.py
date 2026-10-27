"""M18 stopped-too-early from two directories of saved runs (offline; reads `_events/<case>.jsonl`, makes no call).

    python -m vakeel_sahayak.eval.scoring.stopping_replay --runs <dir of the system under test> --reference <dir of a deeper run of the same cases> [--budget 16] [--out stopping.json]

`--reference` is a run of the same dev cases whose Sutradhar was allowed to retrieve further (for example Full with the 16-call factor budget); its stored trajectory plays the role of
"running the same case to the budget". Definition and limits: `eval.metrics.citations.stopped_too_early`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.metrics import citations as ci


def read_events(path: Path) -> list[dict[str, Any]]:
    """One case's event log (JSON lines); a missing file or a broken line gives what could be read."""
    rows: list[dict[str, Any]] = []
    if path.is_file():
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                continue
    return rows


def replay_dirs(runs: str | Path, reference: str | Path, budget: int = 16) -> dict[str, Any]:
    """`stopped_too_early` for every case present in both `_events` folders, and the pooled rates."""
    a, b = Path(runs) / "_events", Path(reference) / "_events"
    per_case: dict[str, Any] = {}
    for f in sorted(a.glob("*.jsonl")):
        if (b / f.name).is_file():
            per_case[f.stem] = ci.stopped_too_early(read_events(f), read_events(b / f.name), budget)
    return {"budget": budget, "per_case": per_case, "pooled": ci.stopped_too_early_rate(per_case.values()), "cases_in_both": len(per_case)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="stopping_replay")
    ap.add_argument("--runs", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--budget", type=int, default=16)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    res = replay_dirs(a.runs, a.reference, a.budget)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    p = res["pooled"]
    print(f"{res['cases_in_both']} case(s) in both; stopped-too-early: case rate {p['case_rate']}, factor rate {p['factor_rate']} ({p['too_early']} of {p['factors']} factors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
