"""Feature evaluations F1-F8 (plan §15.6)."""

from __future__ import annotations

from vakeel_sahayak.eval.runners import shard_runner

JOBS = ['f2_change_sets', 'f1_f5_f6', 'f3_baselines', 'f4_nocache']


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
