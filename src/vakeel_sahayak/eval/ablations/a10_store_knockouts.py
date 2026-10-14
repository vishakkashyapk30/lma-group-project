"""Ablation A10: Remove one store at a time; retrieval and slot-fill only, no drafting (plan §15.4). Switch: knockout_store=<store>."""

from __future__ import annotations

from vakeel_sahayak.orchestration.switches import Switches


def make_switches() -> Switches:
    """Return the Switches for A10.

    Returns:
        Switches.
    """
    raise NotImplementedError


def run(cases_path: str, out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run A10 on 100 T1 cases, saving each case as it finishes (resumable).

    Args:
        cases_path: see behaviour
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    raise NotImplementedError
