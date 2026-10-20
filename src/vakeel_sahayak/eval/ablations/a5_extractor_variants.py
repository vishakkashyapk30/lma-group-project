"""Ablation A5: Fine-tuned 4B vs base 4B vs prompted 32B on clean and noisy input (plan §15.4). Switch: extractor in {finetuned_4b, base_4b, prompted_32b}."""

from __future__ import annotations

from vakeel_sahayak.orchestration.switches import Switches

EXTRACTORS = ("finetuned_4b", "base_4b", "prompted_32b")


def make_switches() -> Switches:
    """Return the Switches for A5.

    Returns:
        Switches.
    """
    return Switches.for_variant("A5", extractor="base_4b")


def run(cases_path: str, out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run A5 on 100 T1 cases, saving each case as it finishes (resumable).

    Args:
        cases_path: see behaviour
        out_dir: see behaviour
        shard: see behaviour
        n_shards: see behaviour
    """
    from vakeel_sahayak.eval.ablations.common import run_ablation

    for extractor in EXTRACTORS:  # the fine-tuned 4B is the Full system's setting, so it is built directly
        run_ablation(f"A5-{extractor}", Switches(extractor=extractor), cases_path, f"{out_dir}/{extractor}", shard, n_shards)
