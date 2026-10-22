"""Gold label G2: Precedents the court cited (plan §15.1). From: reasoning. Method: Citation regexes resolved to Open India Law; resolvable only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations
from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex, load_index
from vakeel_sahayak.pipelines.gold.common import agreed_view, run_gold
from vakeel_sahayak.schemas.enums import OrderPart

METADATA_FILE = "oil_metadata.jsonl"  # metadata format: see `citation_graph/resolve.py`


def metadata_file(parts_path: str) -> Path | None:
    """The Open India Law metadata JSONL (`oil_metadata.jsonl`): next to the parts file, else in the interim folder."""
    from vakeel_sahayak.config import load_config

    for folder in (Path(parts_path).parent, Path(load_config().paths.interim_dir)):
        if (folder / METADATA_FILE).is_file():
            return folder / METADATA_FILE
    return None


def build_gold(parts_path: str, out_path: str) -> int:
    """Build G2 for every cleanly split test order.

    Args:
        parts_path: JSONL from `order_splitter.split_all`; the metadata file is looked up beside it
        out_path: output JSONL

    Returns:
        Number of orders labelled.
    """
    metadata = metadata_file(parts_path)  # none found: every citation stays unresolved
    index = load_index(str(metadata)) if metadata else None
    return run_gold("G2", parts_path, out_path, lambda parts: label_detail(parts, index))


def label_order(parts: dict[OrderPart, str]) -> dict[str, Any]:
    """G2 labels of one order with no metadata index (every citation unresolved): see `label_detail`."""
    return agreed_view(label_detail(parts))


def label_detail(parts: dict[OrderPart, str], index: CitationIndex | None = None) -> dict[str, Any]:
    """Label one order for G2. No LLM is involved: regexes extract, the metadata index resolves, unresolvable citations are left out.

    Args:
        parts: the five order parts
        index: citation metadata index; None resolves nothing

    Returns:
        Gold record fields: `labels` (resolved doc ids, no duplicates), `raw` (all extracted citations),
        `unresolved` (extracted but not resolvable, reported not scored), `status` ('resolved').
    """
    raw = extract_citations(parts.get(OrderPart.REASONING, ""))
    resolved: list[str] = []
    unresolved: list[str] = []
    for citation in raw:
        doc_id = index.resolve(citation) if index else None
        if doc_id is None:
            unresolved.append(citation)
        elif doc_id not in resolved:
            resolved.append(doc_id)
    return {"labels": resolved, "rule_labels": resolved, "llm_labels": None, "raw": raw, "unresolved": unresolved, "status": "resolved"}
