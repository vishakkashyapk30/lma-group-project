"""The opt-in BGE-M3 side vectors of the vector stores (VS_STORES=bge): off by default, a separate read-only file per store,
fp16 on disk and float32 in memory, aligned by item id, and a clear error (never a silent fallback) when something is missing."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from vakeel_sahayak.models.embeddings import HashedEmbeddingClient
from vakeel_sahayak.stores import hybrid
from vakeel_sahayak.stores.hybrid import (
    HybridIndex,
    IndexRow,
    SideVectorsError,
    read_side_vectors,
    side_meta,
    side_vectors_path,
    store_vectors_manifest,
    store_vectors_mode,
    write_side_vectors,
)


class FakeBge:
    """Stand-in for BGE-M3: a different (64-dim) hashed embedder under the name 'bge-m3'."""

    name = "bge-m3"
    dim = 64

    def __init__(self) -> None:
        self._inner = HashedEmbeddingClient(dim=64)
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        return self._inner.embed(texts)


TEXTS = [
    "the applicant has been in custody for two years and the trial has not begun",
    "parity with the co-accused who was granted bail on identical allegations",
    "the prosecution says the applicant may tamper with witnesses in the village",
    "recovery of contraband of commercial quantity under the NDPS Act",
    "the charge sheet has been filed and custodial interrogation is not required",
    "antecedents: the applicant is a first offender with no criminal history",
]


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("VS_STORES", raising=False)
    hybrid._MATRICES.clear()
    yield
    hybrid._MATRICES.clear()


def _store(path) -> HybridIndex:
    index = HybridIndex(path, HashedEmbeddingClient())
    index.add([IndexRow(key=f"k{i}", text=t, payload={"i": i, "text": t}, date=f"2023-01-0{1 + i % 9}") for i, t in enumerate(TEXTS)])
    return index


def _side(path, *, ids=None, texts=TEXTS, embedder=None) -> FakeBge:
    emb = embedder or FakeBge()
    vecs = np.asarray(emb.embed(list(texts)), dtype=np.float32)
    write_side_vectors(side_vectors_path(path), ids if ids is not None else list(range(1, len(texts) + 1)), vecs,
                       {"model_revision": "test-rev", "max_length": 512, "text_sha256": "abc"})
    return emb


def test_the_opt_in_is_off_by_default_and_read_from_the_environment_only(monkeypatch):
    assert store_vectors_mode() == "default"
    monkeypatch.setenv("VS_STORES", "bge")
    assert store_vectors_mode() == "bge"
    monkeypatch.setenv("VS_STORES", "lancedb")
    with pytest.raises(ValueError, match="VS_STORES"):
        store_vectors_mode()


def test_side_file_name_sits_next_to_the_store(tmp_path):
    assert side_vectors_path(tmp_path / "caselaw" / "reasoning.sqlite") == tmp_path / "caselaw" / "reasoning.bge.sqlite"


def test_fp16_round_trip_widens_to_float32_in_id_order(tmp_path):
    rng = np.random.default_rng(0)
    vecs = rng.standard_normal((5, 8)).astype(np.float32)
    ids = [5, 3, 1, 4, 2]
    write_side_vectors(tmp_path / "s.bge.sqlite", ids, vecs, {"model_revision": "r"})
    got_ids, got = read_side_vectors(tmp_path / "s.bge.sqlite")
    assert got.dtype == np.float32 and list(got_ids) == [1, 2, 3, 4, 5]
    order = np.argsort(ids)
    assert np.array_equal(got, vecs[order].astype(np.float16).astype(np.float32))
    conn = sqlite3.connect(tmp_path / "s.bge.sqlite")
    assert len(conn.execute("SELECT vec FROM vectors WHERE id=1").fetchone()[0]) == 8 * 2  # two bytes per value on disk
    conn.close()
    meta = side_meta(tmp_path / "s.bge.sqlite")
    assert meta["embedder"] == "bge-m3" and meta["dtype"] == "float16" and meta["rows"] == "5" and meta["dim"] == "8"


def test_duplicate_ids_are_refused(tmp_path):
    with pytest.raises(ValueError, match="unique"):
        write_side_vectors(tmp_path / "d.bge.sqlite", [1, 1], np.zeros((2, 4)), {})


def test_without_the_opt_in_a_side_file_is_never_read(tmp_path):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    plain = HybridIndex(path)
    before = [(h.key, h.score) for h in plain.search("custody trial delay", k=6)]
    plain.close()
    hybrid._MATRICES.clear()
    _side(path)
    again = HybridIndex(path)
    assert [(h.key, h.score) for h in again.search("custody trial delay", k=6)] == before
    assert again.store_embedder == "hashed-ngram"
    again.close()


def test_with_the_opt_in_the_dense_ranking_comes_from_the_side_vectors(tmp_path):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    fake = _side(path)
    index = HybridIndex(path, side_vectors="bge", side_embedder=fake)
    assert index.store_embedder == "bge-m3"
    query = "parity with the co-accused granted bail"
    dense = index._dense(query, "", [], 6)
    q = np.asarray(fake.embed([query])[0], dtype=np.float32)
    mat = np.asarray(fake.embed(TEXTS), dtype=np.float16).astype(np.float32)
    sims = mat @ q
    expected = [int(i) + 1 for i in np.argsort(-sims, kind="stable") if sims[i] > 0]
    assert dense == expected and dense[0] == 2
    hits = index.search(query, k=3)  # BM25 and payloads still come from the main file
    assert hits[0].key == "k1" and hits[0].payload["i"] == 1
    assert fake.calls >= 2
    index.close()


def test_the_main_store_file_is_not_modified(tmp_path):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    before = path.read_bytes()
    fake = _side(path)
    index = HybridIndex(path, side_vectors="bge", side_embedder=fake)
    index.search("custody", k=3)
    with pytest.raises(SideVectorsError, match="read-only"):
        index.add([IndexRow(key="new", text="x", payload={})])
    index.close()
    assert path.read_bytes() == before


def test_a_missing_side_file_fails_with_the_fix(tmp_path):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    with pytest.raises(SideVectorsError, match="bge_vectors apply"):
        HybridIndex(path, side_vectors="bge", side_embedder=FakeBge())


def test_a_side_file_with_another_row_count_fails(tmp_path):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    _side(path, ids=list(range(1, 5)), texts=TEXTS[:4])
    with pytest.raises(SideVectorsError, match="stale"):
        HybridIndex(path, side_vectors="bge", side_embedder=FakeBge())


def test_side_ids_that_do_not_line_up_with_the_store_fail_on_the_first_search(tmp_path):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    _side(path, ids=[1, 2, 3, 4, 5, 99])
    index = HybridIndex(path, side_vectors="bge", side_embedder=FakeBge())
    with pytest.raises(SideVectorsError, match="item ids"):
        index.search("custody", k=3)
    index.close()


def test_missing_bge_m3_weights_fail_with_the_fix(tmp_path, monkeypatch):
    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    _side(path)
    import vakeel_sahayak.models.embeddings as emb
    import vakeel_sahayak.models.nli as nli

    monkeypatch.setattr(emb, "bge_m3_available", lambda: True)
    monkeypatch.setattr(nli, "local_checkpoint", lambda model_id: None)
    with pytest.raises(SideVectorsError, match="make models"):
        HybridIndex(path, side_vectors="bge")
    monkeypatch.setattr(emb, "bge_m3_available", lambda: False)
    with pytest.raises(SideVectorsError, match="sentence-transformers"):
        HybridIndex(path, side_vectors="bge")


def test_the_stores_follow_the_environment(tmp_path, monkeypatch):
    from vakeel_sahayak.stores.caselaw_reasoning import ReasoningStore

    path = tmp_path / "reasoning.sqlite"
    _store(path).close()
    store = ReasoningStore()
    store.open(str(path))  # opt-in off: opens as before
    assert store._index.store_embedder == "hashed-ngram"
    store.close()
    monkeypatch.setenv("VS_STORES", "bge")
    with pytest.raises(SideVectorsError, match="no BGE-M3 side file"):
        ReasoningStore().open(str(path))
    fake = _side(path)
    monkeypatch.setattr(hybrid, "_bge_query_embedder", lambda max_length=None: fake)
    store = ReasoningStore()
    store.open(str(path))
    assert store._index.store_embedder == "bge-m3"
    store.close()


def test_the_manifest_records_the_store_embedder(monkeypatch, tmp_path):
    info = store_vectors_manifest()
    assert info["mode"] == "default" and set(info["stores"]) == set(hybrid.VECTOR_STORES)
    monkeypatch.setenv("VS_STORES", "bge")
    info = store_vectors_manifest()
    assert info["mode"] == "bge"
    assert all("model_revision" in e for e in info["stores"].values())
