"""MRR and nDCG@k on toy inputs (plan §15.8), document-level like recall@k."""

import math

import pytest

from vakeel_sahayak.eval.metrics.retrieval import mean_reciprocal_rank, ndcg_at_k, recall_at_k


def test_mrr_is_the_reciprocal_rank_of_the_first_gold_document():
    assert mean_reciprocal_rank(["X", "Y", "A"], ["A", "B"]) == pytest.approx(1 / 3)
    assert mean_reciprocal_rank(["A#3", "A#9", "B#1"], ["B"]) == 0.5  # paragraphs of one document are one rank
    assert mean_reciprocal_rank(["X"], ["A"]) == 0.0


def test_ndcg_hand_computed():
    """Gold {A, C}; ranking A, B, C: DCG = 1 + 1/log2(4); ideal = 1 + 1/log2(3)."""
    assert ndcg_at_k(["A", "B", "C"], ["A", "C"], k=10) == pytest.approx((1 + 0.5) / (1 + 1 / math.log2(3)))
    assert ndcg_at_k(["A", "C"], ["A", "C"], k=10) == pytest.approx(1.0)
    assert ndcg_at_k(["B", "C"], ["C"], k=1) == 0.0


def test_ranking_metrics_agree_with_recall_on_empty_gold():
    assert mean_reciprocal_rank(["A"], []) == ndcg_at_k(["A"], []) == recall_at_k(["A"], []) == 1.0
