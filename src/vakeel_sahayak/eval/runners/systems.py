"""The systems of the run plan by name: Full, the baselines B0..B6 and the ablations (docs/evaluation-plan.md §3.1, §3.4).

`system_runner(name)` returns `(runner, switches)`: `runner(case, ctx) -> BailBrief` and the `Switches` the run uses. Ablation names are
the variant ids of `Switches.for_variant` ('A2', 'A8', 'A9', ...); every ablation runs the Full system with its switches flipped.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from typing import Any

from vakeel_sahayak.orchestration.switches import Switches, assert_variant_implemented

BASELINE_MODULES = {
    "b0": "b0_single_pass", "b1": "b1_single_rag", "b2": "b2_whole_doc", "b3": "b3_naive_chunking",
    "b4": "b4_all_stores", "b6": "b6_expert_rule",
}
B0_MODELS = {"b0": None, "b0l": "teacher", "b0s": "munshi_4b"}  # B0 on the shared 14B, B0L on the teacher role, B0S on the base 4B


def system_runner(name: str) -> tuple[Callable[[dict[str, Any], Any], Any], Switches]:
    """The runner and switches of a system name ('full', 'b0', 'b0l', 'b0s', 'b1'..'b4', 'b6', or 'A1'..'A10').

    Raises:
        ValueError: unknown system.
    """
    key = name.strip().lower()
    base = "vakeel_sahayak.eval.baselines."
    if key == "full":
        return importlib.import_module(base + "full_system").run_case, Switches()
    if key in B0_MODELS:
        mod = importlib.import_module(base + "b0_single_pass")
        role = B0_MODELS[key]
        return (lambda case, ctx, _m=mod, _r=role: _m.run_case_with_model(case, ctx, _r)), Switches()
    if key in BASELINE_MODULES:
        return importlib.import_module(base + BASELINE_MODULES[key]).run_case, Switches()
    if re.fullmatch(r"[as]\d+[a-d]?|b5", key):
        assert_variant_implemented(key)  # NotImplementedError naming the variant when no agent reads its switches yet
        return importlib.import_module(base + "full_system").run_case, Switches.for_variant(key.upper())
    raise ValueError(f"unknown system {name!r}")
