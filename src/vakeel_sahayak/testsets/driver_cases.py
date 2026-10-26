"""Driver case rows for T2 and T5 (`<testsets>/t2|t5/driver_cases.jsonl`), the files `eval/runners/jobs.testset_cases_path` looks for.

T7 writes its own rows (`t7_safety.build_t7`). The builders of T2 and T5 are not changed: this adapter reads their finished outputs.

T2: one row per bundle (`case_id` = bundle id, `bundle` = the absolute PDF path, `before` = the as-of date of the truth fields, `kind`, `source_case_id`),
in a seeded shuffle so that the first N rows of a job span all six bundle kinds and many cases. T5: one row per desk case in the file order of `cases.jsonl`
(the FIFO order); T1 background cases carry their court-text `facts` (the T1 `facts_text`), planted T4 cases carry the text of their bundle documents as `facts`
and the file paths as `bundle`; `before` is the shared as-of date, and `rank`, `deadline` stay on the row.
CLI: `python -m vakeel_sahayak.testsets.driver_cases [--testsets DIR]`.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets.common import load_t1_cases, rows_from_file, rows_to_file

SEED = 20260508


def t2_driver_rows(t2_dir: str | Path) -> list[dict[str, Any]]:
    """One row per T2 bundle, shuffled by seed (K1 to K6 mixed)."""
    base = Path(t2_dir)
    rows = []
    for t in rows_from_file(base / "truth.jsonl"):
        rows.append({"case_id": t["bundle_id"], "source_case_id": t["case_id"], "kind": t["kind"], "bundle": [str((base / t["pdf"]).resolve())],
                     "before": (t.get("fields") or {}).get("as_of"), "lang": t.get("lang"), "text_layer": t.get("text_layer")})
    random.Random(f"{SEED}|t2").shuffle(rows)
    return rows


def t5_driver_rows(t5_dir: str | Path, t1_dir: str | Path) -> list[dict[str, Any]]:
    """One row per T5 desk case, in the FIFO order of `cases.jsonl`."""
    base = Path(t5_dir)
    facts = {c["case_id"]: str(c.get("facts_text") or "") for c in load_t1_cases(t1_dir, open_only=False)}
    rows = []
    for c in rows_from_file(base / "cases.jsonl"):
        row: dict[str, Any] = {"case_id": c["case_id"], "before": c["as_of"], "source": c["source"], "rank": c["rank"], "deadline": c["deadline"],
                               "deadline_kind": c["deadline_kind"], "scenario": {"approve_gate1": True, "approve_gate2": False}}
        if c.get("bundle"):
            files = sorted(p for p in (base / c["bundle"]).glob("*.txt"))
            row["bundle"] = [str(p.resolve()) for p in files]
            row["facts"] = "\n\n".join(p.read_text(encoding="utf-8") for p in files)
        else:
            row["facts"] = facts.get(c["case_id"], "")
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    """Write `t2/driver_cases.jsonl` and `t5/driver_cases.jsonl` under the test-set directory."""
    from vakeel_sahayak.config import load_config

    ap = argparse.ArgumentParser(description="Write driver case rows for T2 and T5")
    ap.add_argument("--testsets", default=str(load_config().paths.testsets_dir))
    args = ap.parse_args(argv)
    base = Path(args.testsets)
    n2 = len(t2 := t2_driver_rows(base / "t2"))
    rows_to_file(base / "t2" / "driver_cases.jsonl", t2)
    n5 = len(t5 := t5_driver_rows(base / "t5", base / "t1"))
    rows_to_file(base / "t5" / "driver_cases.jsonl", t5)
    print(f"t2: {n2} rows, t5: {n5} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
