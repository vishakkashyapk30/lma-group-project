"""Offline studies of the evaluation: experiments that are not per-case runs of the driver (nothing here calls a model).

A study is a module with `run(out_dir, n=None, seed=0, **kw) -> dict`; it writes `<out_dir>/<id>.json` (numbers, assumptions, n) and `<id>.md` (a table with a caption that says what the
numbers are). The registry below names them; `scripts/sweep_dev.py` runs the arms of `configs/eval/sweep_dev.yaml` whose `kind` is `study` through

    python -m vakeel_sahayak.eval.studies <name> --out <dir> [--n N] [--seed S]

| name | arms it covers | module | needs |
|---|---|---|---|
| `s14` | S14b, S14c (scheduling) | `eval.studies.s14` | `data/testsets/t5/cases.jsonl` |
| `s16` | S16, S16b (chunking) | `eval.studies.s16` | `data/interim/t1_work/parts.jsonl` |
| `s4s5` | S4 (skew AUROC), S5 (graph expansion recall) | `eval.studies.s4s5` | `data/stores/caselaw/{reasoning,citations}.sqlite` |
| `m17` | M17 (citation removal redraft) | `eval.runners.m17_removal` | the Full pipeline offline, T1 dev cases |

Studies write no `MANIFEST.json`, so the scoring step does not mistake their output for a driver run (`m17` is the exception: it is a driver-style run).
"""

from __future__ import annotations

import argparse
import importlib
import sys
from typing import Any

STUDIES: dict[str, str] = {"s14": "vakeel_sahayak.eval.studies.s14", "s16": "vakeel_sahayak.eval.studies.s16", "s4s5": "vakeel_sahayak.eval.studies.s4s5"}
OTHER: dict[str, str] = {"m17": "vakeel_sahayak.eval.runners.m17_removal"}  # driver-style runs, started through their own CLI
ARMS: dict[str, str] = {"S14b": "s14", "S14c": "s14", "S16": "s16", "S16b": "s16", "S4": "s4s5", "S5": "s4s5"}  # variant id -> the study that measures it


def known() -> list[str]:
    """Every study name (including the driver-style `m17`)."""
    return sorted({*STUDIES, *OTHER})


def run_study(name: str, out_dir: str, n: int | None = None, seed: int = 0, **kw: Any) -> dict[str, Any]:
    """Run one study by name and return its result dict.

    Raises:
        ValueError: unknown study, or `m17` (started through `python -m vakeel_sahayak.eval.runners.m17_removal`).
    """
    if name not in STUDIES:
        raise ValueError(f"unknown study {name!r}: use one of {', '.join(sorted(STUDIES))} (m17: python -m vakeel_sahayak.eval.runners.m17_removal)")
    module = importlib.import_module(STUDIES[name])
    return module.run(out_dir, n=n, seed=seed, **kw)


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.eval.studies <name> --out DIR [--n N] [--seed S]`; `m17` is forwarded to its own CLI."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "m17":
        from vakeel_sahayak.eval.runners.m17_removal import main as m17_main

        return m17_main(argv[1:])
    ap = argparse.ArgumentParser(prog="python -m vakeel_sahayak.eval.studies")
    ap.add_argument("name", choices=sorted(STUDIES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--late-embedder", choices=["hashed", "bge-m3"], default="hashed", help="s16 only: 'bge-m3' runs S16b with true late chunking over BGE-M3 token vectors (opt-in; needs torch and models/hf/BAAI--bge-m3)")
    a = ap.parse_args(argv)
    if a.late_embedder != "hashed" and a.name != "s16":
        ap.error("--late-embedder applies to the s16 study only")
    try:
        result = run_study(a.name, a.out, a.n, a.seed, **({"late_embedder": a.late_embedder} if a.late_embedder != "hashed" else {}))
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"study {a.name}: wrote {a.out}/{result['study']}.json")
    return 0
