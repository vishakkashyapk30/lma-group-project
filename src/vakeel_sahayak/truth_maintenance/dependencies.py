"""Dependency records and value hashing (plan §10)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.bail_brief import Authority, DependsOn
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.rights_report import RightsReport


def hash_value(value: Any) -> str:
    """Stable short hash of a value, e.g. 'h:3f2a' (plan §10).

    Args:
        value: a dossier value

    Returns:
        Hash string.
    """
    raise NotImplementedError


def collect_dependencies(
    claim_text: str, facts: CaseDossier, rights: RightsReport, authorities: list[Authority]
) -> DependsOn:
    """Build the depends_on record of a claim from its [F:field] and [A:doc#para] tags (plan §8.1, §10).

    Args:
        claim_text: see behaviour
        facts: see behaviour
        rights: see behaviour
        authorities: see behaviour

    Returns:
        DependsOn.
    """
    raise NotImplementedError
