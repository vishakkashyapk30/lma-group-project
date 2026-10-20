"""Ablation A2: No check-and-repair (sparring on); verifier arm of the 2x2 (plan §15.4). Switch: no_check_repair=True."""

from __future__ import annotations

from vakeel_sahayak.orchestration.switches import Switches


def make_switches() -> Switches:
    """Return the Switches for A2.

    Returns:
        Switches.
    """
    return Switches.for_variant("A2")


def run(cases_path: str, out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run A2 on 100 T1 cases, saving each case as it finishes (resumable).

    Args:
        cases_path: see behaviour
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    from vakeel_sahayak.eval.ablations.common import run_ablation

    run_ablation("A2", make_switches(), cases_path, out_dir, shard, n_shards)
