"""Per-case metrics of the headline table (evaluation plan 4.1, 4.3, 4.5, 4.6, 4.8), from one saved case record and one T1 gold row.

A metric that is undefined for a case is None (never 0): recall on an order with no agreed answerable factor, recall@10 on an order with no resolved
court-cited precedent, objection recall on an order with no agreed objection. The table prints n beside each.

Metrics whose scoring function is a stub in `eval/metrics` stay None and are named in the `pending` map of the result: unsupported-fact rate
(`eval.metrics.unsupported_fact.unsupported_fact_rate`, MiniCheck) and, with it, the risk side of the coverage-risk curve. With `strict=True` the call raises
`NotImplementedError` naming the function instead.

Definitions fixed here (written into the pre-registration at the freeze; the plan leaves them dev-fixed):
* argued factors P: grounds that are not the "no supported argument could be drafted" placeholder and whose stance is in `ScoreConfig.stances`
  (default: favourable or adverse, that is, every ground except not_applicable);
* answerable factors: the case row's `answerable` list if present, else `pipelines.gold.common.answerable_factors(facts_text)` (rule method);
* pass (for pass^k): factor recall at least `pass_bar` (default 0.5), no crashed case and no stage error;
* coverage: share of grounds emitted without NEEDS_REVIEW (a system that cannot decline emits all of its grounds: coverage 1.0, one point on the curve).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from vakeel_sahayak.eval.metrics.agentic import pass_hat_k  # noqa: F401  (re-exported for the aggregation step)
from vakeel_sahayak.eval.metrics.factor_scores import factor_recall_precision
from vakeel_sahayak.eval.metrics.retrieval import recall_at_k
from vakeel_sahayak.eval.scoring.citation_scores import citation_values
from vakeel_sahayak.schemas.enums import Factor

NO_GROUND_PREFIX = "No supported argument could be drafted"
UNSUPPORTED_FN = "vakeel_sahayak.eval.metrics.unsupported_fact.unsupported_fact_rate"
FACTORS = [f.value for f in Factor]


@dataclass
class ScoreConfig:
    """Scoring choices recorded in the output."""

    stances: tuple[str, ...] = ("favourable", "adverse")
    pass_bar: float = 0.5
    k: int = 10
    strict: bool = False
    cost_per_token_usd: float | None = None
    env: Any = None  # a `ScoreEnv` (paragraph stores, citation graph, rest of the order, checker); None builds the configured one on first use

    def as_dict(self) -> dict[str, Any]:
        return {"stances": list(self.stances), "pass_bar": self.pass_bar, "k": self.k, "strict": self.strict}


def _factors(labels: Any) -> list[Factor]:
    out = []
    for x in labels or []:
        try:
            out.append(Factor(x))
        except ValueError:
            continue
    return out


def argued_factors(brief: dict[str, Any], stances: tuple[str, ...]) -> list[Factor]:
    """Factors the brief argues (see the module docstring)."""
    seen: list[Factor] = []
    for g in (brief or {}).get("grounds") or []:
        if str(g.get("argument") or "").startswith(NO_GROUND_PREFIX) or str(g.get("stance")) not in stances:
            continue
        try:
            f = Factor(g.get("factor"))
        except ValueError:
            continue
        if f not in seen:
            seen.append(f)
    return seen


def answerable_of(case: dict[str, Any]) -> list[Factor]:
    """Answerable factors of a T1 row: its `answerable` list, else the rule method on the facts text."""
    if case.get("answerable") is not None:
        return _factors(case["answerable"])
    from vakeel_sahayak.pipelines.gold.common import answerable_factors

    return answerable_factors(str(case.get("facts_text") or case.get("facts") or ""))


def _prf(pred: list[Factor], gold: list[Factor], answerable: list[Factor]) -> tuple[float | None, float | None, list[tuple[str, int]]]:
    """(recall, precision, per-gold-factor hits) with None where the denominator is empty (the library function would return 1.0 there)."""
    ans = set(answerable)
    gold_a, pred_a = set(gold) & ans, set(pred) & ans
    items = [(f.value, int(f in pred_a)) for f in sorted(gold_a, key=lambda f: FACTORS.index(f.value))]
    if not gold_a and not pred_a:
        return None, None, items
    recall, precision = factor_recall_precision(pred, gold, answerable)
    return (recall if gold_a else None), (precision if pred_a else None), items


def retrieved_docs(record: dict[str, Any], events: list[dict[str, Any]]) -> tuple[list[str], str]:
    """The ranked document ids a case retrieved, and where they came from.

    Order of preference: the record's own `retrieved` list; the results of Sutradhar's search tools in the event log (`doc_id` of each item, first
    occurrence first); the authorities of the brief's grounds (documents cited, an under-estimate of what was retrieved). Duplicates keep their first rank.
    """
    def dedupe(ids: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for i in ids:
            seen.setdefault(str(i).split("#", 1)[0], None)
        return list(seen)

    if record.get("retrieved"):
        return dedupe([str(x) for x in record["retrieved"]]), "record"
    ids = []
    for ev in events:
        if ev.get("kind") == "TOOL_RESULT" and ev.get("actor") == "SUTRADHAR":
            res = (ev.get("outputs") or {}).get("result")
            for item in res if isinstance(res, list) else []:
                if isinstance(item, dict) and item.get("doc_id"):
                    ids.append(str(item["doc_id"]))
    if ids:
        return dedupe(ids), "events"
    cited = [a.get("doc_id") for g in (record.get("brief") or {}).get("grounds") or [] for a in g.get("authorities") or [] if a.get("doc_id")]
    return dedupe([str(c) for c in cited]), "brief_authorities"


def objection_factors(record: dict[str, Any]) -> list[Factor]:
    """Factors of the prosecution objections the system raised (`sparring.objections`); [] when it did not spar."""
    out: list[Factor] = []
    for o in ((record.get("sparring") or {}).get("objections")) or []:
        try:
            f = Factor(o.get("factor"))
        except ValueError:
            continue
        if f not in out:
            out.append(f)
    return out


def coverage_of(record: dict[str, Any]) -> float:
    """Share of grounds emitted without NEEDS_REVIEW; a record with no gate fields (a baseline) cannot decline, so every ground counts as emitted."""
    grounds = (record.get("brief") or {}).get("grounds") or []
    if not grounds:
        return 0.0
    if "gate1_approved" not in record:
        return 1.0
    emitted = [g for g in grounds if str(g.get("check")) != "NEEDS_REVIEW" and not str(g.get("argument") or "").startswith(NO_GROUND_PREFIX)]
    return len(emitted) / len(grounds)


def case_cost(tokens: float, manifest: dict[str, Any], cfg: ScoreConfig) -> float | None:
    """USD of a case: 0.0 on the offline stand-ins, tokens times the measured blended price on OpenAI, None where there is no price (Ada models, Sarvam in INR)."""
    backend = str((manifest.get("models") or {}).get("llm_backend") or "")
    if backend == "offline":
        return 0.0
    if backend == "openai" and cfg.cost_per_token_usd is not None:
        return tokens * cfg.cost_per_token_usd
    return None


def score_case(case: dict[str, Any], record: dict[str, Any], manifest: dict[str, Any], events: list[dict[str, Any]], cfg: ScoreConfig,
               pending: dict[str, str]) -> dict[str, Any]:
    """All per-case metrics of one saved record against one T1 gold row.

    Args:
        case: T1 row (`gold`, `facts_text`)
        record: the driver's saved case record (`brief`, `sparring`, `meta`, ...)
        manifest: the run's MANIFEST.json
        events: the case's event log lines (may be empty)
        cfg: scoring choices
        pending: mutated; metric name -> the stub function it waits for
    """
    gold = case.get("gold") or {}
    brief = record.get("brief") or {}
    ans = answerable_of(case)
    pred = argued_factors(brief, cfg.stances)
    g1, g4, g5 = (_factors((gold.get(k) or {}).get("labels")) for k in ("G1", "G4", "G5"))
    recall, precision_strict, items = _prf(pred, g1, ans)
    _, precision_lenient, _ = _prf(pred, list(dict.fromkeys(g1 + g5)), ans)
    g5_recall, _, _ = _prf(pred, g5, ans)
    if recall is None:
        f1 = None
    elif precision_lenient is None or recall + precision_lenient == 0:
        f1 = 0.0  # a brief that argues nothing answerable earns no credit; recall is defined, so the case counts
    else:
        f1 = 2 * recall * precision_lenient / (recall + precision_lenient)
    obj = objection_factors(record)
    obj_recall = (len(set(obj) & set(g4)) / len(set(g4))) if g4 else None
    obj_precision = (len(set(obj) & set(g4)) / len(set(obj))) if g4 and obj else None
    g2 = (gold.get("G2") or {})
    g2_labels = [str(x) for x in g2.get("labels") or []]
    retrieved, rsource = retrieved_docs(record, events)
    meta = record.get("meta") or {}
    tokens = float(meta.get("tokens") or 0)
    errors = list(record.get("errors") or []) + ([record["error"]] if record.get("error") else [])
    unsupported: float | None = None
    try:
        from vakeel_sahayak.eval.metrics.unsupported_fact import unsupported_fact_rate
        from vakeel_sahayak.schemas.bail_brief import BailBrief

        unsupported = float(unsupported_fact_rate(BailBrief.model_validate(brief), str(case.get("facts_text") or case.get("facts") or "")))
    except NotImplementedError as exc:
        if cfg.strict:
            raise NotImplementedError(f"{UNSUPPORTED_FN} is not implemented (unsupported-fact rate, MiniCheck)") from exc
        pending["unsupported_fact_rate"] = UNSUPPORTED_FN
    return {
        "case_id": case["case_id"], "factor_recall": recall, "factor_precision_strict": precision_strict, "factor_precision_lenient": precision_lenient,
        "factor_f1": f1, "court_discussed_recall": g5_recall, "factor_items": items, "unsupported_fact_rate": unsupported,
        "recall_at_10": recall_at_k(retrieved, g2_labels, cfg.k) if g2_labels else None, "retrieved_source": rsource,
        "g2_gold_n": len(g2_labels), "g2_raw_n": len(g2.get("raw") or []), "g2_unresolved_n": len(g2.get("unresolved") or []),
        "objection_recall": obj_recall, "objection_precision": obj_precision, "n_objections": len(obj), "g4_n": len(set(g4)),
        "coverage": coverage_of(record), "tokens": tokens, "store_calls": float(meta.get("store_calls") or 0),
        "seconds": float(meta["seconds"]) if meta.get("seconds") is not None else None, "cost_usd": case_cost(tokens, manifest, cfg),
        "passed": (recall >= cfg.pass_bar and not errors) if recall is not None else None, "n_errors": len(errors),
        "g7_n": len((gold.get("G7") or {}).get("labels") or []),
        **citation_values(case, record, events, cfg.env, pending, strict=cfg.strict),
    }


def is_nan(x: Any) -> bool:
    return isinstance(x, float) and math.isnan(x)
