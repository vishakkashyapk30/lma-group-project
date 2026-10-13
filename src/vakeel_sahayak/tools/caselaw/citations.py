"""Tools in caselaw.citations (plan §5.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.ids import check_iso_date
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.store_call import call_store, invalid
from vakeel_sahayak.tools.types import GoodLawResult

_WANTS = ("authority", "overruled_by", "sc_root", "cited_by", "cites", "good_law")
MAX_DOC_IDS = 50


def citations(doc_ids: list[str], want: list[str] | None = None) -> dict[str, Any] | ToolError:
    """Citation-graph lookups with treatment and authority score. (plan §5.3)

    Args:
        doc_ids: see behaviour
        want: any of authority, overruled_by, sc_root, cited_by, cites, good_law (default: all of them, the full record)

    Returns:
        Per-doc results: {doc_id: {<wanted key>: value}}. `cited_by` and `cites` are lists of `CitationEdge` (treatment, court level) and
        `good_law` is a `GoodLawResult`; a judgment that is not in the graph has `{"found": false}` instead of the wanted keys.
    """
    tool = "citations"
    if not isinstance(doc_ids, list) or not 1 <= len(doc_ids) <= MAX_DOC_IDS or not all(isinstance(d, str) and d.strip() for d in doc_ids):
        return invalid(tool, f"doc_ids must be a list of 1 to {MAX_DOC_IDS} non-empty ids")
    wanted = list(want) if want else list(_WANTS)
    if bad := [w for w in wanted if w not in _WANTS]:
        return invalid(tool, f"unknown lookup(s) {bad}: use any of {list(_WANTS)}")
    return call_store(tool, StoreName.CASELAW_CITATIONS, lambda s: {d: _lookup(s, d, wanted) for d in doc_ids})


def _lookup(store: Any, doc_id: str, wanted: list[str]) -> dict[str, Any]:
    """The requested facts about one judgment."""
    known = getattr(store, "known", None)
    if known is not None and not known(doc_id):
        return {"found": False}
    out: dict[str, Any] = {}
    for key in wanted:
        if key == "authority":
            out[key] = store.authority_score(doc_id)
        elif key == "overruled_by":
            out[key] = store.good_law(doc_id).overruled_by
        elif key == "sc_root":
            out[key] = store.sc_root(doc_id)
        elif key == "cited_by":
            out[key] = store.cited_by(doc_id)
        elif key == "cites":
            out[key] = store.cites(doc_id)
        else:
            out[key] = store.good_law(doc_id)
    return out


def good_law_check(doc_id: str, as_of: str | None = None) -> GoodLawResult | ToolError:
    """Flag precedents overruled by a later SC judgment or larger bench; DISTINGUISHED is shown but does not block. (plan §5.3)

    Args:
        doc_id: see behaviour
        as_of: only judgments dated on or before this date (YYYY-MM-DD) can overrule or distinguish; default all

    Returns:
        GoodLawResult (status UNKNOWN for a judgment that is not in the citation graph).
    """
    tool = "good_law_check"
    if not isinstance(doc_id, str) or not doc_id.strip():
        return invalid(tool, "doc_id must not be empty")
    if as_of:
        try:
            check_iso_date(as_of)
        except ValueError as exc:
            return invalid(tool, str(exc))
    return call_store(tool, StoreName.CASELAW_CITATIONS, lambda s: s.good_law(doc_id, as_of))


CITATIONS_SPEC = ToolSpec(
    name="citations",
    description="Citation-graph lookups with treatment and authority score.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.CASELAW_CITATIONS],
    plan_ref="§5.3",
)

GOOD_LAW_CHECK_SPEC = ToolSpec(
    name="good_law_check",
    description="Flag precedents overruled by a later SC judgment or larger bench; DISTINGUISHED is shown but does not block.",
    agents=[AgentName.SUTRADHAR, AgentName.VAKEEL],
    stores=[StoreName.CASELAW_CITATIONS],
    plan_ref="§5.3",
)
