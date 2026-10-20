"""Ablation A9: Completes the 2x2 with Full, A2, A8 (plan §15.4). Switch: no_sparring=True, no_check_repair=True."""

from __future__ import annotations

from vakeel_sahayak.orchestration.switches import Switches


def make_switches() -> Switches:
    """Return the Switches for A9.

    Returns:
        Switches.
    """
    return Switches.for_variant("A9")


def run(cases_path: str, out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run A9 on 100 T1 cases, saving each case as it finishes (resumable).

    Args:
        cases_path: see behaviour
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    from vakeel_sahayak.eval.ablations.common import run_ablation

    run_ablation("A9", make_switches(), cases_path, out_dir, shard, n_shards)
