"""Builder for law.concordance: concordance (plan §5.1).

Input: `<interim_dir>/concordance_edges.jsonl`, one `ConcordanceEdge` per line, written by `pipelines/concordance/ipc2bns.py`.
Without it, the offline seed (IPC 420 <-> BNS 318(4) ...) is used. The CrPC-BNSS bail table is always added; duplicate
(old_ref, new_ref) pairs are kept once.
Statutes are law, not orders, so there is nothing to exclude; `exclude_doc_ids` is accepted for a uniform signature.
"""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.pipelines.concordance.crpc_bnss_table import load_bail_sections_table
from vakeel_sahayak.pipelines.concordance.ipc2bns import write_edges_sqlite
from vakeel_sahayak.pipelines.concordance.seed import SEED_IPC_BNS_EDGES
from vakeel_sahayak.pipelines.store_builders.common import out_file
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge
from vakeel_sahayak.stores.law_concordance import ConcordanceStore


def build_concordance(interim_dir: str, out_dir: str, exclude_doc_ids: set[str] | None = None) -> int:
    """Build the concordance SQLite file.

    Args:
        interim_dir: folder with `concordance_edges.jsonl`
        out_dir: folder that receives the SQLite file named in configs/stores.yaml
        exclude_doc_ids: ignored (no orders in this store)

    Returns:
        Edges written.
    """
    path = Path(interim_dir) / "concordance_edges.jsonl"
    base = (
        [ConcordanceEdge.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if path.is_file()
        else list(SEED_IPC_BNS_EDGES)
    )
    edges: dict[tuple[str, str], ConcordanceEdge] = {}
    for edge in [*base, *load_bail_sections_table()]:  # the bail table is always part of the graph; the first edge of a pair wins
        edges.setdefault((edge.old_ref, edge.new_ref), edge)
    write_edges_sqlite(list(edges.values()), str(out_file(StoreName.LAW_CONCORDANCE, out_dir)))
    store = ConcordanceStore()
    store.open(out_dir)
    return store.count()
