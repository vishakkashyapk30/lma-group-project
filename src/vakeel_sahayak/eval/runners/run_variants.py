"""The VI-03 jobs: the hosted blocks and one job per implemented variant (docs/evaluation-plan.md 7.2 rows 15-33; `docs/handoff/eval-jobs.md`).

Each job runs its `systems` through `systems.system_runner`. The hosted blocks (`openai_sparring_block`, `rq1_secondary_sarvam`) need the hosted environment and, for Sarvam, a spend ledger
that does not exist yet: do not launch them without it. Print what a job would cost first with `driver plan --job <name>`.
"""

from __future__ import annotations

from vakeel_sahayak.eval.runners import shard_runner

JOBS = ['openai_sparring_block', 'rq1_secondary_sarvam', 's8_self_critique', 's9_sampling_critic', 's10_no_isolation', 's1_critique_retrieval', 's3_stopping', 's7_gap_reread', 's15_output_format', 's17_defences', 's2_adaptive_depth', 's6_b5_router', 's12_topology', 's14_batch', 's14_scheduling', 's16_chunking', 's4_s5_retrieval', 's11_review_debate', 's13_workflow_search', 's18_authority_stance', 'p_munshi_variants', 'gold_source_sweep']


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
