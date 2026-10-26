"""Command line of the scoring package.

    python -m vakeel_sahayak.eval.scoring score --runs <dir> [--gold-source agreed|rule|both] [--slice dev|open|blind] [--reference full] [--open-blind] --out <dir>
    python -m vakeel_sahayak.eval.scoring report --scores <dir> [--out <dir>] [--gold-source agreed|rule]

`--gold-source both` is the gold-source sweep (job `gold_source_sweep`): the same outputs scored against both golds, plus `sweep.json`. The blind slice needs
`--open-blind`, the git tag `eval-freeze-v1` and no lock file `data/eval/blind.lock` (plan 5.8); it is refused otherwise and nothing is written.
"""

from __future__ import annotations

import argparse
import sys

from vakeel_sahayak.eval.scoring import case_metrics as cm


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m vakeel_sahayak.eval.scoring")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="score a driver run directory against the T1 gold")
    s.add_argument("--runs", required=True, help="a driver output directory (any depth: every directory with a MANIFEST.json is a run)")
    s.add_argument("--out", required=True)
    s.add_argument("--gold-source", choices=["agreed", "rule", "both"], default="agreed")
    s.add_argument("--slice", dest="slice_name", choices=["dev", "open", "blind"], default="dev")
    s.add_argument("--reference", default="full", help="system the others are compared with (default full)")
    s.add_argument("--testsets", default=None, help="test-set root (default: the configured data/testsets)")
    s.add_argument("--open-blind", action="store_true", help="explicit flag to open the blind slice once (also needs the freeze tag and no lock)")
    s.add_argument("--pass-bar", type=float, default=0.5, help="factor recall a case needs to pass (pass^k; provisional)")
    s.add_argument("--stances", default="favourable,adverse", help="ground stances that count as arguing a factor")
    s.add_argument("--allow-mixed-code", action="store_true", help="compare runs whose manifests record different git commits (refused by default)")
    s.add_argument("--strict", action="store_true", help="raise NotImplementedError naming a stub scorer instead of marking its column pending")
    r = sub.add_parser("report", help="write Markdown, LaTeX and CSV tables and figures from the scores")
    r.add_argument("--scores", required=True, help="the directory `score` wrote")
    r.add_argument("--out", default=None, help="default: the same directory")
    r.add_argument("--gold-source", choices=["agreed", "rule"], default=None)
    a = ap.parse_args(argv)
    if a.cmd == "report":
        from vakeel_sahayak.eval.scoring.render import write_report

        try:
            written = write_report(a.scores, a.out, a.gold_source)
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {len(written['tables'])} table files and {len(written['figures'])} figure files under {a.out or a.scores}")
        if not written["figures"]:
            print("figures: matplotlib is not installed, only the figure CSVs were written")
        return 0
    from vakeel_sahayak.eval.scoring.pipeline import score_command
    from vakeel_sahayak.testsets.blind import BlindSliceError

    cfg = cm.ScoreConfig(stances=tuple(x.strip() for x in a.stances.split(",") if x.strip()), pass_bar=a.pass_bar, strict=a.strict, cost_per_token_usd=_openai_price())
    try:
        res = score_command(a.runs, a.out, gold_source=a.gold_source, slice_name=a.slice_name, reference=a.reference, testsets_dir=a.testsets, open_blind=a.open_blind, cfg=cfg, allow_mixed_code=a.allow_mixed_code)
    except BlindSliceError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for src in ("agreed", "rule"):
        if src in res:
            meta = res[src]["meta"]
            print(f"scored {len(res[src]['systems'])} system(s) on {meta['n_gold_cases']} {meta['slice']} order(s), gold {src}; pending: {sorted(meta['pending']) or 'none'}")
    print(f"wrote scores to {a.out}")
    return 0


def _openai_price() -> float | None:
    """Blended USD per token from the measured pilot in configs/eval/runs.yaml (`estimate`); None when the file or the numbers are missing."""
    try:
        from vakeel_sahayak.eval.runners.plan import runs_config

        est = runs_config().get("estimate") or {}
        total = float(est["tokens_in_per_case"]) + float(est["tokens_out_per_case"])
        return float(est["usd_per_case"]) / total if total else None
    except Exception:  # noqa: BLE001 - a missing registry only removes the USD column
        return None
