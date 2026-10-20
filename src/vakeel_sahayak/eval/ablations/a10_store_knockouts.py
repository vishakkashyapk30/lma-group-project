"""Ablation A10: Remove one store at a time; retrieval and slot-fill only, no drafting (plan §15.4). Switch: knockout_store=<store>."""

from __future__ import annotations

from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import StoreName

# The seven shared stores (the case-shelf stores are the client's own record, not part of the knock-out study).
SHARED_STORES = [s.value for s in StoreName if s.value.split(".")[0] in {"law", "caselaw", "advocacy"}]


def make_switches() -> Switches:
    """Return the Switches for A10.

    Returns:
        Switches.
    """
    return Switches.for_variant("A10", knockout_store=SHARED_STORES[0])


def run(cases_path: str, out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run A10 on 100 T1 cases, saving each case as it finishes (resumable).

    Args:
        cases_path: see behaviour
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    from vakeel_sahayak.eval.ablations.common import run_ablation
    from vakeel_sahayak.eval.runners.driver import run_agents

    for store in SHARED_STORES:  # one store at a time, never two together; retrieval and slot fill only (no drafting)
        run_ablation(f"A10-{store}", Switches.for_variant("A10", knockout_store=store), cases_path, f"{out_dir}/{store}", shard, n_shards,
                     runner=lambda case, ctx: run_agents(case, ctx, stop_after="retrieval"))
