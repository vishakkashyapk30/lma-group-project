"""Builder for caselaw.citations: citation graph (plan §5.1). Excludes test and same-FIR orders (plan §2).

Input: `<interim_dir>/orders.jsonl` (format in `corpus.py`). Citations in reasoning paragraphs are extracted, resolved
against the corpus's own metadata and labelled with a treatment (cue words; agreed with a labeler when one is given).
Edges to or from excluded orders do not exist because excluded orders never enter the corpus.
"""

from __future__ import annotations

from vakeel_sahayak.pipelines.citation_graph.treatment import TreatmentLabeler
from vakeel_sahayak.pipelines.store_builders.common import concordance_for, out_file
from vakeel_sahayak.pipelines.store_builders.corpus import process_corpus
from vakeel_sahayak.schemas.enums import StoreName


def build_citations(
    interim_dir: str,
    out_dir: str,
    exclude_doc_ids: set[str] | None = None,
    *,
    concordance_path: str | None = None,
    labeler: TreatmentLabeler | None = None,
) -> int:
    """Build the citation graph file (tables `nodes` and `edges`).

    Args:
        interim_dir: folder with `orders.jsonl`
        out_dir: folder that receives the SQLite file named in configs/stores.yaml
        exclude_doc_ids: test and same-FIR orders to leave out
        concordance_path: unused by the graph itself; keeps the corpus cache shared with the paragraph builders
        labeler: evaluation labeler for treatment agreement; None keeps cue-word labels

    Returns:
        Edges written.
    """
    corpus = process_corpus(
        interim_dir, exclude_doc_ids, concordance_path=concordance_for(out_dir, concordance_path), labeler=labeler
    )
    return corpus.graph.write_sqlite(out_file(StoreName.CASELAW_CITATIONS, out_dir))
