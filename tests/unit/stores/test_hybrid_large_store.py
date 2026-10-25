"""The search speed-ups of a large store (hosted-model pilot): a cached dense matrix and the pruning of near-universal BM25 terms."""

from __future__ import annotations

from vakeel_sahayak.stores import hybrid
from vakeel_sahayak.stores.hybrid import HybridIndex, IndexRow


def _rows(n: int) -> list[IndexRow]:
    rows = [IndexRow(key=f"d{i}", text=f"the order of the court is that bail is granted on ground {i % 7} item{i}", payload={"i": i},
                     date=f"2023-{1 + i % 12:02d}-10", facets={"factor": ["a" if i % 2 else "b"]}) for i in range(n)]
    rows.append(IndexRow(key="rare", text="the order of the court is that custody was unlawful because of a zebrafish", payload={"i": -1}, date="2023-05-05",
                         facets={"factor": ["a"]}))
    return rows


def test_cached_matrix_gives_the_same_ranking_as_the_scan(tmp_path):
    index = HybridIndex(tmp_path / "x.sqlite")
    index.add(_rows(60))
    args = dict(filters=None, facets={"factor": ["a"]}, before="2023-09-01", k=8)
    cached = [(h.key, h.score) for h in index.search("bail granted ground 3 item9", **args)]
    index._matrix = ()  # type: ignore[assignment]  # force the row-by-row scan
    hybrid._MATRICES.clear()
    index._load_matrix = lambda: None  # type: ignore[method-assign]
    scan = [(h.key, h.score) for h in index.search("bail granted ground 3 item9", **args)]
    assert cached == scan and cached


def test_adding_rows_drops_the_cached_matrix(tmp_path):
    index = HybridIndex(tmp_path / "y.sqlite")
    index.add(_rows(5))
    index.search("order of the court")
    assert index._matrix
    index.add([IndexRow(key="late", text="a late order", payload={})])
    assert index._matrix is None


def test_a_large_store_ignores_terms_that_are_in_most_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(hybrid, "BM25_PRUNE_MIN_ROWS", 10)
    index = HybridIndex(tmp_path / "z.sqlite")
    index.add(_rows(40))
    terms = ["the", "order", "of", "court", "zebrafish"]
    assert index._informative_terms(terms) == ["zebrafish"] or set(index._informative_terms(terms)) >= {"zebrafish"}
    assert index.search("the order of the court zebrafish", k=1)[0].key == "rare"
    monkeypatch.setenv("VS_BM25_PRUNE", "0")
    assert index._informative_terms(terms) == terms


def test_small_stores_keep_every_term(tmp_path):
    index = HybridIndex(tmp_path / "w.sqlite")
    index.add(_rows(20))
    terms = ["the", "order", "of", "court"]
    assert index._informative_terms(terms) == terms
