"""Feature evaluation F6: Hearing-prep card vs one-call 'what will the bench ask?'. Test set: T1, G5, G6. Metrics: recall/precision of court-discussed factors (G5); recall of imposed condition types (G6) (plan §15.6).

NOT RUN in VI-07 (the task covers F1 to F4, F7 and F8): the hearing card is part of the export modules, which are stubs, so `run` raises NotImplementedError. `score` is implemented: one JSON file per case with
`predicted_factors` and `gold_g5` (factors the court discussed), `predicted_conditions` and `gold_g6` (condition types the court imposed).
"""

from __future__ import annotations

import sys

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("hearing_card", "one_call")


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F6 (system and comparison arms), resumable.

    Args:
        out_dir: results directory
        shard: this shard's index
        n_shards: the number of shards

    Raises:
        NotImplementedError: the export modules (the hearing-prep card) are not built; F6 is outside VI-07's first scope.
    """
    raise NotImplementedError("F6 needs the export modules (the hearing-prep card); they are stubs, so no arm can run yet")


def score(run_dir: str) -> dict[str, float]:
    """Compute F6 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (see the module docstring for the keys)

    Returns:
        `factor_recall` and `factor_precision` (card factors against G5, macro over cases), `condition_recall` (imposed condition types against G6, macro over cases with a gold condition).

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    factors = [fc.set_prf(r.get("predicted_factors", []), r.get("gold_g5", [])) for r in rows]
    conditions = [fc.set_prf(r.get("predicted_conditions", []), r.get("gold_g6", []))[0] for r in rows]
    out = {
        "factor_recall": fc.mean(p[0] for p in factors if p[0] is not None),
        "factor_precision": fc.mean(p[1] for p in factors if p[1] is not None),
        "condition_recall": fc.mean(c for c in conditions if c is not None),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
