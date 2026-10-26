"""Per-case citation, authority, abstention and stopping metrics for the scoring step (M9, M13, M15, M16, M17, M18, M33, M35; definitions in `eval/metrics/citations.py`).

The resources (paragraph stores, citation graph, the rest of the order, the support checker) come from a `ScoreEnv`. A metric whose resource is absent (for example the stores on a
machine without `data/stores`) is left None and named in `pending` with the reason, but only when the case has something to measure, so a run with no citations never reports a
missing store. The checker is MiniCheck, DeBERTa NLI or the deterministic lexical stand-in; the name is recorded (`checker`) and tables mark the stand-in.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.eval.metrics import citations as ci

_DEFAULT: dict[str, ci.ScoreEnv] = {}

NEW_KEYS = ("fabricated_citation_rate", "n_citations", "authority_reasoning_share", "authority_sc_share", "authority_before_share", "good_law_violation_rate",
            "known_treatment_share", "citation_precision", "citation_recall", "citation_removal_change", "over_search_rate", "unfinished_factor_share",
            "confident_wrong_rate")


def default_env() -> ci.ScoreEnv:
    """The environment built from the configured stores directory, once per stores directory (so a test with its own data directory gets its own)."""
    from vakeel_sahayak.config import load_config

    key = str(load_config().paths.stores_dir)
    if key not in _DEFAULT:
        _DEFAULT[key] = ci.ScoreEnv.from_config()
    return _DEFAULT[key]


def empty_values() -> dict[str, Any]:
    """Every key None (plus an empty claim list), the shape of a case with nothing to measure."""
    return {**dict.fromkeys(NEW_KEYS), "claims": [], "can_decline": False, "confident_cells": None}


def citation_values(case: dict[str, Any], record: dict[str, Any], events: list[dict[str, Any]], env: ci.ScoreEnv | None, pending: dict[str, str], *, strict: bool = False) -> dict[str, Any]:
    """All the new per-case values of one saved record (see the module docstring); `pending` is mutated with the metrics a missing resource blocks."""
    env = env or default_env()
    brief = record.get("brief") or {}
    out = empty_values()
    out["can_decline"] = "gate1_approved" in record
    cites = ci.extract_citations(brief)
    before = case.get("before")

    def block(metric: str, resource: str) -> None:
        pending[metric] = env.reasons.get(resource, f"the {resource} resource")
        if strict:
            raise NotImplementedError(f"{metric} needs {pending[metric]}")

    if cites:
        out["n_citations"] = len(cites)
        if env.paragraphs is None:
            for m in ("fabricated_citation_rate", "authority_reasoning_share", "citation_precision"):
                block(m, "paragraphs")
        else:
            out["fabricated_citation_rate"] = ci.fabricated_citations(cites, env.paragraphs)["rate"]
            q = ci.authority_quality(cites, env.paragraphs, before)
            out.update(authority_reasoning_share=q["reasoning_share"], authority_sc_share=q["sc_share"], authority_before_share=q["before_share"])
            pr = ci.citation_precision_recall(brief, env.paragraphs, env.get_checker())
            out.update(citation_precision=pr["precision"], citation_recall=pr["recall"])
        if env.treatment is None:
            block("good_law_violation_rate", "treatment")
        else:
            g = ci.good_law(brief, env.treatment, before)
            out.update(good_law_violation_rate=g["violation_rate"], known_treatment_share=g["known_share"])
    if record.get("removal"):
        out["citation_removal_change"] = ci.removal_change(record["removal"])["rate"]
    if events:
        sq = ci.stopping_quality(events)
        out.update(over_search_rate=sq["over_search_rate"], unfinished_factor_share=sq["unfinished_share"])
    if (brief.get("grounds") or []):
        try:
            from vakeel_sahayak.eval.metrics.unsupported_fact import sentence_support
            from vakeel_sahayak.schemas.bail_brief import BailBrief

            sents = sentence_support(BailBrief.model_validate(brief), str(case.get("facts_text") or case.get("facts") or ""))
        except NotImplementedError:
            sents = []
        if not out["can_decline"]:  # a baseline has no gate: every sentence it wrote is emitted (the same rule as `coverage_of`)
            sents = [{**x, "check": "EMITTED"} for x in sents]
        out["claims"] = [[int(c["emitted"]), c["score"], c["cut"]] for c in ci.claim_records(sents, True)]
        rest = env.rest_of_order(str(case.get("doc_id"))) if env.rest_of_order is not None else None
        if env.rest_of_order is None:
            block("confident_wrong_rate", "rest_of_order")
        elif rest:
            cw = ci.confident_wrong(sents, rest, env.get_checker(), True)
            out["confident_wrong_rate"], out["confident_cells"] = cw["rate"], cw["cells"]
    return out
