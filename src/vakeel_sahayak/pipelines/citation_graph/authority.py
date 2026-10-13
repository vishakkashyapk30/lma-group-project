"""Authority score: court level, bench size, citations from other bail cases, recency (plan §5.3)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph


def configured_weights() -> dict[str, float] | None:
    """Authority weights from configs/thresholds.yaml (`retrieval.authority_weights`); None while they are still TODO (null)."""
    from vakeel_sahayak.config import load_config

    raw = (load_config().thresholds.get("retrieval") or {}).get("authority_weights") or {}
    weights = {k: float(v) for k, v in raw.items() if v is not None}
    return weights or None


def compute_authority(graph_path: str, out_path: str) -> None:
    """Compute and store scores.

    Reads the SQLite graph written by `CitationGraph.write_sqlite` and writes a SQLite file with one `authority` row
    (`doc_id`, `score`) per judgment, using the weights in configs/thresholds.yaml when set (else the defaults).

    Args:
        graph_path: see behaviour
        out_path: see behaviour
    """
    graph = CitationGraph.from_sqlite(graph_path)
    scores = graph.all_authority(configured_weights())
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(out_path)
    try:
        with conn:
            conn.execute("DROP TABLE IF EXISTS authority")
            conn.execute("CREATE TABLE authority (doc_id TEXT PRIMARY KEY, score REAL NOT NULL)")
            conn.executemany("INSERT INTO authority VALUES (?, ?)", sorted(scores.items()))
    finally:
        conn.close()


def find_overruled(graph_path: str) -> dict[str, str]:
    """Precedents treated as overruled by a later SC judgment or larger bench.

    Args:
        graph_path: SQLite graph file

    Returns:
        Doc id to overruling doc id.
    """
    return CitationGraph.from_sqlite(graph_path).find_overruled()
