"""Helpers shared by the store builders (plan §5, §5.5)."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from vakeel_sahayak.models.embeddings import get_embedder
from vakeel_sahayak.pipelines.store_builders.corpus import Corpus, process_corpus
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.stores.hybrid import HybridIndex, IndexRow
from vakeel_sahayak.stores.paths import sqlite_name


def out_file(name: StoreName, out_dir: str) -> Path:
    """The SQLite file a builder writes: `<out_dir>/<name from configs/stores.yaml, .sqlite>`."""
    return Path(out_dir) / sqlite_name(name)


def concordance_for(out_dir: str, concordance_path: str | None) -> str | None:
    """Concordance used for section families: the argument, else the one built into `out_dir`, else the default store."""
    if concordance_path:
        return concordance_path
    built = out_file(StoreName.LAW_CONCORDANCE, out_dir)
    return str(built) if built.is_file() else None


def corpus_for(interim_dir: str, out_dir: str, exclude: set[str] | None, concordance_path: str | None) -> Corpus:
    """The processed corpus for a builder (cached across builders in one process)."""
    return process_corpus(interim_dir, exclude, concordance_path=concordance_for(out_dir, concordance_path))


def write_hybrid(target: Path, rows: Iterable[IndexRow], embedder: str | None) -> int:
    """Write a fresh hybrid index file (an existing file is replaced) and return the number of rows.

    Args:
        target: SQLite file
        rows: documents to index
        embedder: 'hashed-ngram', 'bge-m3', 'auto', or None for `models.factory.get_embedder` (VS_EMBEDDER, default 'auto')
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    index = HybridIndex(target, get_embedder(embedder) if embedder else None)  # None: models.factory.get_embedder
    try:
        return index.add(rows)
    finally:
        index.close()
