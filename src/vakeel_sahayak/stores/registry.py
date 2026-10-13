"""Store registry by name (plan §5.1)."""

from __future__ import annotations

import importlib

from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.stores.base import CaseStore, Store

STORE_CLASSES: dict[str, str] = {
    "law.statutes": "vakeel_sahayak.stores.law_statutes.StatuteStore",
    "law.concordance": "vakeel_sahayak.stores.law_concordance.ConcordanceStore",
    "caselaw.reasoning": "vakeel_sahayak.stores.caselaw_reasoning.ReasoningStore",
    "caselaw.citations": "vakeel_sahayak.stores.caselaw_citations.CitationStore",
    "caselaw.similar": "vakeel_sahayak.stores.caselaw_similar.SimilarStore",
    "advocacy.arguments": "vakeel_sahayak.stores.advocacy_arguments.ArgumentStore",
    "advocacy.objections": "vakeel_sahayak.stores.advocacy_objections.ObjectionStore",
    "case.docs": "vakeel_sahayak.stores.case_docs.CaseDocsStore",
    "case.timeline": "vakeel_sahayak.stores.case_timeline.TimelineStore",
    "case.facts": "vakeel_sahayak.stores.case_facts.FactsStore",
}


def open_store(name: StoreName, path: str | None = None, case_id: str | None = None) -> Store:
    """Instantiate and open a store by name.

    Args:
        name: see behaviour
        path: see behaviour
        case_id: required for case.* stores

    Returns:
        Open store.

    Raises:
        ValueError: for a case.* store requested without a case_id.
    """
    module, _, cls_name = STORE_CLASSES[StoreName(name).value].rpartition(".")
    store = getattr(importlib.import_module(module), cls_name)()
    if isinstance(store, CaseStore):
        if not case_id:
            raise ValueError(f"{StoreName(name).value} is a per-case store: pass case_id")
        store.bind_case(case_id)
    store.open(path)
    return store


def open_all(config: AppConfig, case_id: str | None = None) -> dict[StoreName, Store]:
    """Open all ten stores (shared ones read-only).

    Args:
        config: see behaviour
        case_id: see behaviour

    Returns:
        Mapping.
    """
    return {name: open_store(name, None, case_id) for name in StoreName}
