"""Shared body of the ablation wrappers: an ablation is the Full system with switches flipped (`Switches.for_variant`), never a code fork.

`run_ablation` is the resumable shard loop of the driver: one output file per case (saved as it finishes), shard i of n, seeds and
budgets from the run, and a manifest; outputs go to `out_dir` (the runner passes the contract path
`<results>/runs/<job>/outputs/<ablation>`; see `eval.runners.driver.outputs_dir`).
"""

from __future__ import annotations

from vakeel_sahayak.orchestration.switches import Switches


def run_ablation(variant: str, switches: Switches, cases_path: str, out_dir: str, shard: int = 0, n_shards: int = 1, *, runner: object = None,
                 **kw: object) -> int:
    """Run the Full system under `switches` on this shard's cases of `cases_path`, saving each case as it finishes; returns cases completed now."""
    from vakeel_sahayak.eval.baselines import full_system
    from vakeel_sahayak.eval.runners import driver

    return driver.run_cases(cases_path, out_dir, variant, runner or (lambda case, ctx: full_system.run_case(case, ctx)), switches,
                            shard=shard, n_shards=n_shards, **kw)  # type: ignore[arg-type]
