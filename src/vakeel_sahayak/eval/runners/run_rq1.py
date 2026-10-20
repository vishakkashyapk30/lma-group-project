"""RQ1 main runs: Full, B0, B1, B4 x 3 runs; B2, B3 x 1 (plan §15.3, §17)."""

from __future__ import annotations

from vakeel_sahayak.eval.runners import shard_runner

JOBS = ['rq1_full', 'rq1_b2_b3', 'rq1_b0l_b0s_b6']


def main(argv: list[str] | None = None) -> int:
    """CLI: `--shard N --n-shards M --out-dir DIR [--hours H]`; runs this runner's jobs as one shard each.

    Args:
        argv: arguments (default: sys.argv)

    Returns:
        Exit code (a bad shard index exits non-zero with a usage message and launches nothing).
    """
    return shard_runner.launch(JOBS, argv, __doc__ or "")


if __name__ == "__main__":
    raise SystemExit(main())
