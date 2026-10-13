"""Builder for advocacy.arguments: defense-submission paragraphs (plan §5.1). Excludes test and same-FIR orders (plan §2).

Input: `<interim_dir>/orders.jsonl` (format in `corpus.py`). Each order is split into parts, only the `defense_submissions` paragraphs
are kept, each with its metadata (§5.2: part, sections, section_family, factors, cites, authority).
"""

from __future__ import annotations

from vakeel_sahayak.pipelines.store_builders.common import corpus_for, out_file, write_hybrid
from vakeel_sahayak.schemas.enums import OrderPart, StoreName
from vakeel_sahayak.stores.paragraph_store import paragraph_index_rows


def build_arguments(
    interim_dir: str,
    out_dir: str,
    exclude_doc_ids: set[str] | None = None,
    *,
    embedder: str | None = None,
    concordance_path: str | None = None,
) -> int:
    """Build the store on disk (SQLite, FTS5 for BM25, dense vectors). Embeddings use BGE-M3 when installed, else the hashed fallback.

    Args:
        interim_dir: folder with `orders.jsonl`
        out_dir: folder that receives the SQLite file named in configs/stores.yaml
        exclude_doc_ids: test and same-FIR orders to leave out (`pipelines.leakage.excluded_doc_ids`)
        embedder: embedder name; None uses VS_EMBEDDER or 'auto'
        concordance_path: concordance for section families; default the one in `out_dir`, else the default store

    Returns:
        Rows written.
    """
    corpus = corpus_for(interim_dir, out_dir, exclude_doc_ids, concordance_path)
    rows = (
        row
        for p in corpus.orders
        for row in paragraph_index_rows([rec for rec in p.paragraphs if rec.part == OrderPart.DEFENSE])
    )
    return write_hybrid(out_file(StoreName.ADVOCACY_ARGUMENTS, out_dir), rows, embedder)
