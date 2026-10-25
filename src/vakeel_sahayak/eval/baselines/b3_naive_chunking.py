"""Baseline B3. Naive chunking: B1 with fixed 512, 512 with 20% overlap, recursive splitter, semantic chunking or page chunks; best on dev goes into generation. (plan §15.3)

Isolates: chunking. The call pattern is B1's (one top-10 retrieval, one drafting call); the retrieved paragraphs are re-cut with the chosen chunker
(`chunking_variants`) and the first ten chunks go to the model. `select_best_variant` picks the variant with the best dev recall (retrieval-only analysis).
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.eval.baselines import chunking_variants as cv
from vakeel_sahayak.eval.baselines.common import call_tool, draft, evidence_rows, facts_of
from vakeel_sahayak.schemas.bail_brief import BailBrief

TASK = "baseline.b3_naive_chunking"
K = 10
VARIANTS = {"fixed_512": cv.fixed_512, "fixed_512_overlap": cv.fixed_512_overlap, "recursive": cv.recursive_split, "semantic": cv.semantic_chunks}
# S16: proposition units (Dense X Retrieval, EMNLP 2024) can be tried on the retrieved paragraphs too; the other S16 strategies need whole documents (`cv.evaluate_strategy`)
VARIANTS["proposition"] = lambda text: __import__("vakeel_sahayak.stores.chunk_strategies", fromlist=["propositions"]).propositions(text)
DEFAULT_VARIANT = "recursive"  # replaced by the dev choice (`select_best_variant`) once the retrieval-only analysis has run


def select_best_variant(dev_recall: dict[str, float]) -> str:
    """The chunking variant with the highest dev recall (ties: the first in name order).

    Args:
        dev_recall: variant name to recall on the dev set

    Returns:
        The best variant name.
    """
    if not dev_recall:
        raise ValueError("no dev recall to choose from")
    return sorted(dev_recall.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


def run_case(case: dict[str, Any], ctx: AgentContext) -> BailBrief:
    """Produce a brief for one T1 case under B3 (variant: `case["chunk_variant"]`, else the default).

    Args:
        case: `case_id`, `facts`, `before`, optional `chunk_variant`
        ctx: context

    Returns:
        BailBrief.
    """
    variant = str(case.get("chunk_variant") or DEFAULT_VARIANT)
    cut = VARIANTS.get(variant, cv.recursive_split)
    rows = evidence_rows(call_tool(ctx, "search_reasoning", query=facts_of(case), before=case.get("before"), k=K), K)
    chunks: list[dict[str, Any]] = []
    for row in rows:
        for part in cut(str(row.get("text") or "")):
            chunks.append({**row, "text": part})
    return draft(case, ctx, task=TASK, evidence=chunks[:K], extra={"chunking": variant})
