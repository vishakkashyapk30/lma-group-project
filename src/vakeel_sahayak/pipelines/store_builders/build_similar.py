"""Builder for caselaw.similar: whole-order facts vectors and fact signatures (plan §5.1). Excludes test and same-FIR orders (plan §2).

Input: `<interim_dir>/orders.jsonl` (format in `corpus.py`). One row per order with a non-empty facts part: the facts
text is vectorised and a fact signature (sections, custody band, charge-sheet status, co-accused outcome) is read from it by rules.
"""

from __future__ import annotations

from vakeel_sahayak.pipelines.store_builders.common import corpus_for, out_file, write_hybrid
from vakeel_sahayak.schemas.enums import OrderPart, StoreName
from vakeel_sahayak.schemas.store_rows import SimilarOrderRow
from vakeel_sahayak.stores.caselaw_similar import similar_index_row


def build_similar(
    interim_dir: str,
    out_dir: str,
    exclude_doc_ids: set[str] | None = None,
    *,
    embedder: str | None = None,
    concordance_path: str | None = None,
) -> int:
    """Build the store on disk.

    Args:
        interim_dir: folder with `orders.jsonl`
        out_dir: folder that receives the SQLite file named in configs/stores.yaml
        exclude_doc_ids: test and same-FIR orders to leave out
        embedder: embedder name; None uses VS_EMBEDDER or 'auto'
        concordance_path: concordance for section families; default the one in `out_dir`, else the default store

    Returns:
        Rows written.
    """
    corpus = corpus_for(interim_dir, out_dir, exclude_doc_ids, concordance_path)
    rows = (
        similar_index_row(
            SimilarOrderRow(doc_id=p.order.doc_id, court=p.order.court, date=p.order.date, signature=p.signature),
            p.parts[OrderPart.FACTS],
            p.section_family,
        )
        for p in corpus.orders
        if p.parts.get(OrderPart.FACTS, "").strip()
    )
    return write_hybrid(out_file(StoreName.CASELAW_SIMILAR, out_dir), rows, embedder)
