"""Router 'library' (plan §5.3, §5.4, §13.5 `/library`): the precedent explorer.

Search reasoning paragraphs (every query carries a `before` date, the leakage rule), the citation graph with good-law
badges, and the IPC <-> BNS / CrPC <-> BNSS bridge with a text diff. The stores are resolved through the registry.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException

from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.stores import registry

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("/search", response_model=list[ParagraphRecord])
async def search_precedents(q: str) -> list[ParagraphRecord]:
    """Precedent explorer search over caselaw.reasoning; every query carries a before date (plan §2, §13.5)."""
    store = registry.open_store(StoreName.CASELAW_REASONING)
    return list(store.search(q, before=date.today().isoformat(), k=20))


@router.get("/citations/{doc_id}", response_model=dict[str, Any])
async def get_citation_graph(doc_id: str) -> dict[str, Any]:
    """Citation graph with good-law badges and the SC root (plan §5.3)."""
    store = registry.open_store(StoreName.CASELAW_CITATIONS)
    edges = list(store.cited_by(doc_id)) + list(store.cites(doc_id))
    if not edges:
        raise HTTPException(status_code=404, detail=f"unknown order {doc_id}")
    node_ids = {doc_id} | {e.citing_doc_id for e in edges} | {e.cited_doc_id for e in edges}
    nodes = []
    for nid in sorted(node_ids):
        gl = store.good_law(nid)
        nodes.append({"id": nid, "authority": store.authority_score(nid), "good_law": gl.status.value,
                      "overruled_by": gl.overruled_by})
    graph_edges = [{"source": e.citing_doc_id, "target": e.cited_doc_id, "treatment": e.treatment.value} for e in edges]
    return {"root": store.sc_root(doc_id), "nodes": nodes, "edges": graph_edges}


@router.get("/bridge/{code}/{section}", response_model=dict[str, Any])
async def get_bridge(code: str, section: str) -> dict[str, Any]:
    """IPC <-> BNS / CrPC <-> BNSS bridge with a text diff; a split provision lists candidates and does not guess (plan §5.4)."""
    store = registry.open_store(StoreName.LAW_CONCORDANCE)
    ref = f"{code} {section}"
    touching = list(store.edges_for(ref))
    if not touching:
        raise HTTPException(status_code=404, detail=f"unknown section {ref}")

    forward = [e for e in touching if e.old_ref == ref]
    if forward:
        old_ref, chosen = ref, forward
        new_refs = [e.new_ref for e in forward]
    else:
        backward = [e for e in touching if e.new_ref == ref]
        old_ref, chosen = backward[0].old_ref, backward
        new_refs = [ref]

    ambiguous = len(new_refs) > 1
    new_ref = None if ambiguous else new_refs[0]
    transfer = store.transfer_flag(old_ref, new_ref).flag.value if new_ref else None
    return {
        "old_ref": old_ref,
        "new_ref": new_ref,
        "edge_type": chosen[0].type.value,
        "text_diff": chosen[0].text_diff,
        "transfer": transfer,
        "ambiguous": ambiguous,
        "candidates": new_refs if ambiguous else [],
    }
