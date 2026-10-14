"""T4 rights scenarios: 500 scenarios from specs written from the bare acts by a team member who does not write the Radar code; dates either side of each threshold (day 59/60/61, one-third vs one-half, 7 vs 10 years, first-time vs repeat), rendered as bundles (plan §15.2)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.testsets.common import TestSetManifest


def load_scenario_specs(spec_path: str) -> list[dict[str, Any]]:
    """Load testsets/specs/rights_scenarios.yaml.

    Args:
        spec_path: see behaviour

    Returns:
        Specs.
    """
    raise NotImplementedError


def build_t4(spec_path: str, out_dir: str) -> TestSetManifest:
    """Render scenarios with designed answers.

    Args:
        spec_path: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    raise NotImplementedError
