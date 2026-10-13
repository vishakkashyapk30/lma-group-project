"""Ten-row bail-related CrPC<->BNSS table coded from the bare acts as tool configuration (436/436A/437/438/439 -> 478/479/480/482/483) (plan §2)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.pipelines.concordance.refs import make_ref
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge


def edges_from_rows(rows: list[dict[str, Any]]) -> list[ConcordanceEdge]:
    """Turn bail_sections rows ({crpc, bnss, topic, optional type, optional text_diff}) into edges.

    Rows without a `type` are read as SAME: the plan lists the pairs but not how the text changed (week-0 check).
    """
    edges: list[ConcordanceEdge] = []
    for row in rows:
        edges.append(
            ConcordanceEdge(
                old_ref=make_ref("CrPC", str(row["crpc"])),
                new_ref=make_ref("BNSS", str(row["bnss"])),
                type=ConcordanceEdgeType(str(row.get("type", "SAME")).upper()),
                text_diff=row.get("text_diff"),
            )
        )
    return edges


def load_bail_sections_table() -> list[ConcordanceEdge]:
    """Return the coded table (configs/bail_sections.yaml).

    Returns:
        Edges.
    """
    from vakeel_sahayak.config import load_config

    return edges_from_rows(load_config().bail_sections)
