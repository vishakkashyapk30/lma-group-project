"""S16 / S16b chunking strategies (`Switches.chunking`): propositions (Dense X Retrieval, EMNLP 2024), late chunking (Jina 2024), the B3 naive chunkers.

Synthetic stores only: no real store is built.
"""

from __future__ import annotations

import pytest

from tests.unit.stores._helpers import norm, paragraph
from vakeel_sahayak.eval.baselines.chunking_variants import compare_strategies, evaluate_strategy
from vakeel_sahayak.models.embeddings import HashedEmbeddingClient
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import OrderPart
from vakeel_sahayak.stores.chunk_strategies import STRATEGIES, LateChunkEmbedder, chunk_order_with, propositions, strategy_for
from vakeel_sahayak.stores.chunking import chunk_order

REASONING = (
    "1. The petitioner was arrested on 12.03.2024 and has remained in custody since then; the charge sheet has been filed and the trial has not begun. "
    "The offence is under Section 420 IPC, but the maximum punishment is seven years. "
    "2. Bail is the rule and jail the exception, and the Court must weigh the gravity of the offence against the period of custody undergone."
)
PARTS = {OrderPart.FACTS: paragraph(1, 60, "f"), OrderPart.REASONING: REASONING, OrderPart.OPERATIVE: "3. Bail is granted on furnishing a bond of Rs. 50,000 with two sureties."}


def test_switch_values_and_variants():
    assert Switches().chunking == "structure" and strategy_for(Switches()) == "structure"
    for s in STRATEGIES:
        assert Switches(chunking=s).chunking == s
    assert Switches.for_variant("S16").chunking == "proposition" and Switches.for_variant("S16b").chunking == "late"
    assert {"S16", "S16b"} <= Switches.implemented_variants()
    with pytest.raises(ValueError):
        Switches(chunking="sliding")


def test_structure_and_late_are_exactly_the_default_chunker():
    base = [r.model_dump() for r in chunk_order(PARTS)]
    assert [r.model_dump() for r in chunk_order_with("structure", PARTS)] == base
    assert [r.model_dump() for r in chunk_order_with("late", PARTS)] == base


def test_unknown_strategy_is_refused():
    with pytest.raises(ValueError):
        chunk_order_with("sliding", PARTS)


def test_propositions_lose_no_word_and_split_clauses():
    units = propositions(REASONING.split("2. ")[0])
    assert len(units) >= 3  # two sentences, the first with a semicolon, the second with ', but'
    assert norm(" ".join(units)).replace(";", "").replace(",", "") == norm(REASONING.split("2. ")[0]).replace(";", "").replace(",", "")
    assert propositions("Short sentence here.") == ["Short sentence here."]
    assert propositions("He ran; she ran.") == ["He ran; she ran."]  # halves under the minimum size are not split


@pytest.mark.parametrize("strategy", [s for s in STRATEGIES if s not in ("structure", "late")])
def test_every_strategy_keeps_parts_in_order_and_loses_no_text(strategy):
    records = chunk_order_with(strategy, PARTS)
    assert records
    order = [OrderPart(r.part) for r in records]
    assert order == sorted(order, key=lambda p: [OrderPart.FACTS, OrderPart.DEFENSE, OrderPart.PROSECUTION, OrderPart.REASONING, OrderPart.OPERATIVE].index(p))
    for part, text in PARTS.items():
        got = {w.strip(".,;") for r in records if r.part == part for w in r.text.split()}
        assert {w.strip(".,;") for w in text.split()} <= got
    assert [r.para for r in records] == sorted(r.para for r in records)


def test_proposition_records_remember_their_paragraph_and_are_smaller():
    props = chunk_order_with("proposition", PARTS)
    structure = chunk_order_with("structure", PARTS)
    assert len(props) > len(structure)
    assert {r.para for r in props if r.part == OrderPart.REASONING} == {1, 2}
    assert max(len(r.text.split()) for r in props) <= max(len(r.text.split()) for r in structure)


def test_a_custom_propositionizer_is_used():
    records = chunk_order_with("proposition", {OrderPart.REASONING: "1. One two three four five six."}, propositionizer=lambda p: ["A", "B"])
    assert [r.text for r in records] == ["A", "B"]


# ---- late chunking ------------------------------------------------------------------------------------------------
def test_late_embedder_approximation_is_contextual_deterministic_and_unit_length():
    base = HashedEmbeddingClient()
    doc = "Alpha beta gamma delta. Epsilon zeta eta theta. Iota kappa lambda mu."
    chunks = ["Alpha beta gamma delta.", "Iota kappa lambda mu."]
    a, b = LateChunkEmbedder(base), LateChunkEmbedder(base)
    assert a.mode == "approximation" and a.prepare(doc, chunks) == 2 == b.prepare(doc, chunks)
    va, vb, plain = a.embed(chunks), b.embed(chunks), base.embed(chunks)
    assert va == vb and va != plain
    assert all(abs(sum(x * x for x in v) - 1) < 1e-9 for v in va)
    q = "unseen query text"
    assert a.embed([q]) == base.embed([q])


def test_late_embedder_uses_token_vectors_when_the_base_offers_them():
    class Tok(HashedEmbeddingClient):
        def embed_tokens(self, text):
            spans, vecs, pos = [], [], 0
            for w in text.split():
                s = text.index(w, pos)
                spans.append((s, s + len(w)))
                vecs.append(self.embed([w])[0])
                pos = s + len(w)
            return spans, vecs

    emb = LateChunkEmbedder(Tok())
    assert emb.mode == "token_pooling"
    emb.prepare("one two three four", ["one two", "three four"])
    assert emb.embed(["one two"]) != emb.embed(["three four"])


# ---- retrieval-only hook ------------------------------------------------------------------------------------------
DOCS = [
    {"doc_id": "D1", "court": "X", "date": "2020-01-01", "parts": {OrderPart.REASONING: "1. Prolonged custody of an undertrial violates Article 21 and bail must follow. 2. The trial has been delayed for years without fault of the accused."}},
    {"doc_id": "D2", "court": "X", "date": "2020-02-01", "parts": {OrderPart.REASONING: "1. Parity with the co-accused who was granted bail on a similar role requires the same relief. 2. The role of the petitioner is not distinguishable."}},
    {"doc_id": "D3", "court": "X", "date": "2020-03-01", "parts": {OrderPart.REASONING: "1. Antecedents alone cannot defeat bail. 2. Flight risk is absent as the accused has family roots and a fixed address."}},
]
QUERIES = [{"query": "parity co-accused granted bail similar role", "gold": ["D2"]}, {"query": "prolonged custody undertrial Article 21", "gold": ["D1"]}]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_evaluate_strategy_reports_recall_and_index_size_deterministically(strategy):
    a = evaluate_strategy(strategy, DOCS, QUERIES, ks=(1, 5))
    b = evaluate_strategy(strategy, DOCS, QUERIES, ks=(1, 5))
    assert a == b and a["strategy"] == strategy and a["queries"] == 2
    assert a["index"]["chunks"] >= 3 and a["index"]["tokens"] > 0
    assert 0.0 <= a["recall"]["1"] <= a["recall"]["5"] <= 1.0
    assert a["recall"]["5"] == 1.0  # three documents, k=5 reaches them all


def test_compare_strategies_lists_every_strategy_and_late_marks_its_mode():
    out = compare_strategies(DOCS, QUERIES, ks=(1,))
    assert [r["strategy"] for r in out] == list(STRATEGIES)
    assert next(r for r in out if r["strategy"] == "late")["late_mode"] == "approximation"
    assert next(r for r in out if r["strategy"] == "proposition")["index"]["chunks"] > next(r for r in out if r["strategy"] == "structure")["index"]["chunks"]


def test_evaluation_does_not_touch_real_stores(tmp_path, monkeypatch):
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    evaluate_strategy("structure", DOCS, QUERIES, ks=(1,))
    assert not list(tmp_path.iterdir())
