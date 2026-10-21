"""S4: a score-skew weak-evidence signal for corpus slots, in the manner of SkewRoute (evaluation plan 3.3, variant S4).

Switch: `Switches.weak_signal` = 'rules' (default, the current behaviour) or 'skew' (S4).

Paper and what we took
----------------------
* Hairu Wang, Yuan Feng, Yukun Cao, Xike Xie, S. Kevin Zhou. "SkewRoute: Training-Free LLM Routing for Knowledge Graph Retrieval-
  Augmented Generation via Score Skewness of Retrieved Context". Findings of EMNLP 2025, pp. 11324-11340.
  https://aclanthology.org/2025.findings-emnlp.606/ Taken: the idea that the shape of the retriever's score distribution (how skewed
  it is) tracks how hard the query is, so a training-free statistic of the scores can decide how much to trust a result. The page
  states the correlation between score distributions and query difficulty; it does not name its measures, so the statistics here
  (Gini coefficient and relative top gap) are those our evaluation plan names for this variant, not necessarily the paper's.

What we changed, and why
------------------------
SkewRoute routes a query to a smaller or larger LLM and was validated on knowledge-graph retrieval scores. We use the signal for a
different decision: whether the retrieved paragraphs of a corpus slot are trustworthy. Our scores are fused BM25 plus dense (reciprocal
rank fusion) scores, whose shape differs from KG scores, so the paper's result does not carry over by assumption; the evaluation
measures it (M19: AUROC of the skew for "the top-10 contains a G2 paragraph", retrieval-only). A list of at least three scores with a flat
shape (Gini below `GINI_FLAT` and relative top gap below `GAP_FLAT`: no paragraph stands out) is flagged weak. When the rules would
mark the slot FILLED the flag downgrades it to WEAK, which cues the existing filter relaxation (factor, section family, court), but only
while a relaxation is still available, so the signal can cost a few extra rounds and never loops. The thresholds are assumptions
(untuned) and can be overridden in `configs/thresholds.yaml` under `retrieval.skew_gini_flat` / `retrieval.skew_gap_flat`; the continuous
statistics are always recorded so the evaluation can pick thresholds and report the AUROC without them.
"""

from __future__ import annotations

from typing import Any

GINI_FLAT = 0.05  # ASSUMPTION (untuned): below this the scores are nearly uniform
GAP_FLAT = 0.02  # ASSUMPTION (untuned): relative gap between the best and second best score
MIN_SCORES = 3  # fewer scores say nothing about a distribution's shape


def gini(scores: list[float]) -> float | None:
    """Gini coefficient of non-negative scores: 0 when all are equal, towards 1 when one score holds all the mass; None for fewer than two or a zero sum."""
    xs = sorted(max(0.0, float(s)) for s in scores)
    n, total = len(xs), sum(xs)
    if n < 2 or total <= 0:
        return None
    weighted = sum((i + 1) * x for i, x in enumerate(xs))
    return round(max(0.0, (2 * weighted) / (n * total) - (n + 1) / n), 6)


def top_gap(scores: list[float]) -> float | None:
    """Relative gap between the best and the second best score, (s1 - s2) / s1; None for fewer than two scores or a zero best score."""
    xs = sorted((float(s) for s in scores), reverse=True)
    if len(xs) < 2 or xs[0] <= 0:
        return None
    return round((xs[0] - xs[1]) / xs[0], 6)


def thresholds() -> tuple[float, float]:
    """(Gini, top-gap) thresholds: the module defaults unless `configs/thresholds.yaml` sets `retrieval.skew_gini_flat` / `skew_gap_flat`."""
    try:
        from vakeel_sahayak.config import load_config

        cfg = load_config().thresholds.get("retrieval") or {}
        return float(cfg.get("skew_gini_flat") or GINI_FLAT), float(cfg.get("skew_gap_flat") or GAP_FLAT)
    except Exception:  # noqa: BLE001 - a config that cannot be read leaves the defaults
        return GINI_FLAT, GAP_FLAT


def skew_of(scores: list[float], *, gini_flat: float | None = None, gap_flat: float | None = None) -> dict[str, Any]:
    """The skew statistics of one result list and the flag: `{n, gini, top_gap, weak}`; `weak` needs `MIN_SCORES` scores and both statistics flat."""
    g_cut, d_cut = thresholds()
    g_cut, d_cut = (g_cut if gini_flat is None else gini_flat), (d_cut if gap_flat is None else gap_flat)
    g, d = gini(scores), top_gap(scores)
    weak = len(scores) >= MIN_SCORES and g is not None and d is not None and g < g_cut and d < d_cut
    return {"n": len(scores), "gini": g, "top_gap": d, "weak": bool(weak)}


def scores_of(items: list[dict[str, Any]]) -> list[float]:
    """The hybrid scores carried by search results (`score`, or `text_score` for graph-expanded results), in result order."""
    out = []
    for i in items:
        s = i.get("score", i.get("text_score"))
        if isinstance(s, (int, float)) and not isinstance(s, bool):
            out.append(float(s))
    return out
