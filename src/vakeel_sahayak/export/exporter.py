"""Gated export entry point used by the export tool and API (plan §8.1, §16)."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import ExportFormat


def export_case(case_id: str, format: ExportFormat) -> list[str]:
    """Run GateGuard.assert_export_allowed, then write application, List of Dates, objections sheet and hearing card.

    Args:
        case_id: see behaviour
        format: see behaviour

    Returns:
        Paths of exported files.
    """
    raise NotImplementedError
