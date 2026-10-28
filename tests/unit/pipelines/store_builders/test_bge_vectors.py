"""The BGE-M3 side-vector tooling (bge_vectors.py): the exported texts reproduce the stored hashed vectors, and `apply` builds side
files aligned with the store ids from shards (here produced by a small fake embedder instead of the GPU step)."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from tests.unit.pipelines.store_builders._helpers import FACTS_MARK
from vakeel_sahayak.models.embeddings import HashedEmbeddingClient
from vakeel_sahayak.pipelines.store_builders import bge_vectors as bv
from vakeel_sahayak.pipelines.store_builders.build_reasoning import build_reasoning
from vakeel_sahayak.pipelines.store_builders.build_similar import build_similar
from vakeel_sahayak.stores import hybrid
from vakeel_sahayak.stores.hybrid import HybridIndex, read_side_vectors, side_meta


@pytest.fixture()
def stores(interim, excluded, tmp_path):
    out = tmp_path / "stores"
    build_reasoning(str(interim), str(out / "caselaw"), excluded, embedder="hashed-ngram")
    build_similar(str(interim), str(out / "caselaw"), excluded, embedder="hashed-ngram")
    return out


def _export(stores, interim, tmp_path):
    return bv.export(str(stores), str(interim), str(tmp_path / "texts"), ["caselaw.reasoning", "caselaw.similar"], verify_n=10_000)


def test_export_reproduces_every_stored_hashed_vector(stores, interim, tmp_path):
    manifest = _export(stores, interim, tmp_path)
    for store in ("caselaw.reasoning", "caselaw.similar"):
        entry = manifest["stores"][store]
        check = entry["hashed_check"]
        assert check["sampled"] == entry["rows"] > 0 and check["matched"] == check["sampled"]
        rows = list(bv.read_texts(bv.texts_file(tmp_path / "texts", store)))
        assert [i for i, _ in rows] == sorted(i for i, _ in rows)
        h = hashlib.sha256("".join(json.dumps({"id": i, "text": t}, ensure_ascii=False) + "\n" for i, t in rows).encode()).hexdigest()
        assert h == entry["text_sha256"]
    similar = [t for _, t in bv.read_texts(bv.texts_file(tmp_path / "texts", "caselaw.similar"))]
    assert all(FACTS_MARK in t for t in similar)  # the similar store embedded the facts part of each order


def test_export_stops_when_the_text_does_not_reproduce_the_vectors(stores, interim, tmp_path, monkeypatch):
    monkeypatch.setattr(bv, "paragraph_texts", lambda conn: [(i, t + " changed", v) for i, t, v in _orig_paragraph_texts(conn)])
    with pytest.raises(SystemExit, match="does not reproduce"):
        bv.export(str(stores), str(interim), str(tmp_path / "texts"), ["caselaw.reasoning"], verify_n=50)


_orig_paragraph_texts = bv.paragraph_texts


def _fake_shards(texts_dir: Path, shards_dir: Path, store: str, shard_rows: int) -> HashedEmbeddingClient:
    """Shards in the layout of the GPU step, from a 64-dim hashed embedder (stands in for BGE-M3)."""
    emb = HashedEmbeddingClient(dim=64)
    rows = list(bv.read_texts(bv.texts_file(texts_dir, store)))
    shards_dir.mkdir(parents=True, exist_ok=True)
    for k, start in enumerate(range(0, len(rows), shard_rows)):
        chunk = rows[start : start + shard_rows]
        stem = bv.shard_stem(store, k)
        np.save(shards_dir / f"{stem}.npy", np.asarray(emb.embed([t for _, t in chunk]), dtype=np.float16))
        np.save(shards_dir / f"{stem}.ids.npy", np.asarray([i for i, _ in chunk], dtype=np.int64))
        info = {"store": store, "shard": k, "rows": len(chunk), "model_id": "BAAI/bge-m3", "model_revision": "rev-test", "max_length": 512,
                "pooling": "cls", "job_id": "123", "seconds": 1.0,
                "npy_sha256": bv._sha256(shards_dir / f"{stem}.npy"), "ids_sha256": bv._sha256(shards_dir / f"{stem}.ids.npy")}
        (shards_dir / f"{stem}.json").write_text(json.dumps(info))
    return emb


def _apply_args(tmp_path, stores, **kw) -> argparse.Namespace:
    base = dict(shards_dir=str(tmp_path / "shards"), texts_dir=str(tmp_path / "texts"), stores_dir=str(stores), only=["caselaw.reasoning"],
                sanity_n=0, max_length=512, delete_shards=False)
    return argparse.Namespace(**{**base, **kw})


def test_apply_builds_an_aligned_side_file_and_a_manifest(stores, interim, tmp_path):
    _export(stores, interim, tmp_path)
    emb = _fake_shards(tmp_path / "texts", tmp_path / "shards", "caselaw.reasoning", shard_rows=3)
    main = stores / "caselaw" / "reasoning.sqlite"
    before = main.read_bytes()
    manifest = bv.apply(_apply_args(tmp_path, stores))
    assert main.read_bytes() == before
    side = stores / "caselaw" / "reasoning.bge.sqlite"
    ids, mat = read_side_vectors(side)
    index = HybridIndex(main)
    own = [r[0] for r in index._conn.execute("SELECT id FROM items ORDER BY id")]
    index.close()
    assert list(ids) == own
    texts = dict(bv.read_texts(bv.texts_file(tmp_path / "texts", "caselaw.reasoning")))
    expected = np.asarray(emb.embed([texts[i] for i in own]), dtype=np.float16).astype(np.float32)
    assert np.array_equal(mat, expected)
    meta = side_meta(side)
    assert meta["model_revision"] == "rev-test" and meta["store_embedder"] == "hashed-ngram" and meta["rows"] == str(len(own))
    entry = json.loads((stores / "BGE_MANIFEST.json").read_text())["stores"]["caselaw.reasoning"]
    assert entry == manifest["stores"]["caselaw.reasoning"] and entry["rows"] == len(own) and entry["shards"] > 1
    assert entry["wiring_check"]["top_id"] is not None
    hybrid._MATRICES.clear()


def test_apply_refuses_shards_with_a_bad_hash(stores, interim, tmp_path):
    _export(stores, interim, tmp_path)
    _fake_shards(tmp_path / "texts", tmp_path / "shards", "caselaw.reasoning", shard_rows=3)
    np.save(tmp_path / "shards" / "caselaw.reasoning.000.npy", np.zeros((3, 64), dtype=np.float16))
    with pytest.raises(SystemExit, match="sha256"):
        bv.apply(_apply_args(tmp_path, stores))


def test_apply_refuses_shards_that_miss_store_rows(stores, interim, tmp_path):
    _export(stores, interim, tmp_path)
    _fake_shards(tmp_path / "texts", tmp_path / "shards", "caselaw.reasoning", shard_rows=3)
    last = sorted((tmp_path / "shards").glob("caselaw.reasoning.*.json"))[-1]
    last.unlink()
    with pytest.raises(SystemExit, match="ids"):
        bv.apply(_apply_args(tmp_path, stores))


def test_self_rank_check_counts_duplicates_apart():
    emb = HashedEmbeddingClient(dim=64)
    texts = {1: "bail granted on parity", 2: "custody of two years", 3: "bail granted on parity", 4: "witness tampering feared"}
    ids = np.asarray([1, 2, 3, 4])
    mat = np.asarray(emb.embed([texts[i] for i in ids]), dtype=np.float32)
    check = bv.self_rank_check(ids, mat, texts, emb, n=4)
    assert check["failed"] == 0 and check["self_first"] + check["duplicate_first"] == 4 and check["duplicate_first"] >= 1


def test_the_gpu_step_imports_only_outside_libraries_at_module_level():
    """The node runs `python bge_vectors.py embed` without installing the package: top-level imports are standard library only."""
    tree = ast.parse(Path(bv.__file__).read_text())
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top if isinstance(n, ast.Import) for a in n.names}
    names |= {n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert "vakeel_sahayak" not in names and "numpy" not in names and "torch" not in names
