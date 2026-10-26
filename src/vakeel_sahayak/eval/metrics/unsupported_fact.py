"""Metrics: Unsupported-fact rate: share of factual sentences MiniCheck finds unsupported by the input; checker validation (plan §15.9) (plan §15.8).

The checker is MiniCheck (Tang et al. 2024, LLM-AggreFact) when the optional `minicheck` package and its weights are
installed (`.[eval]`); otherwise the repository's NLI facade (`models.factory.get_nli`: DeBERTa when available, the
deterministic lexical stand-in offline). `checker_backend()` names the one in use, so a run records which it was.
"""

from __future__ import annotations

import importlib.util
import re

from vakeel_sahayak.schemas.bail_brief import BailBrief

_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_NUMBER = re.compile(r"\d+")


def _minicheck_scorer():  # noqa: ANN202
    """A (premise, sentence) -> support-probability callable from MiniCheck, or None when it is not installed or cannot load."""
    if importlib.util.find_spec("minicheck") is None:
        return None
    try:
        from minicheck.minicheck import MiniCheck

        scorer = MiniCheck(model_name="flan-t5-large", cache_dir=None)

        def score(premise: str, sentence: str) -> float:
            _, probs, _, _ = scorer.score(docs=[premise], claims=[sentence])
            return float(probs[0])

        return score
    except Exception:  # noqa: BLE001 - heavy optional dependency: any load failure means use the NLI facade
        return None


def _scorer():  # noqa: ANN202
    mini = _minicheck_scorer()
    if mini is not None:
        return "minicheck", mini, 0.5
    from vakeel_sahayak.models.factory import get_nli
    from vakeel_sahayak.models.nli import nli_threshold

    client = get_nli()
    return getattr(client, "name", "nli"), client.entails, nli_threshold("fact_support", client)


def checker_backend() -> str:
    """Name of the checker a call would use ('minicheck', 'deberta-v3-nli' or 'offline-lexical-nli')."""
    return _scorer()[0]


def _factual_sentences(brief: BailBrief) -> list[str]:
    from vakeel_sahayak.eval.feature_common import sentences_of

    out: list[str] = []
    for ground in brief.grounds:
        out.extend(sentences_of(ground.argument))
    return out


def unsupported_fact_rate(brief: BailBrief, input_text: str) -> float:
    """Share of the brief's factual sentences that the input does not support.

    Args:
        brief: the drafted brief; every sentence of every ground's argument is a factual sentence
        input_text: the facts the system was given (the reference point, plan §15.9)

    Returns:
        Unsupported sentences / factual sentences (0.0 when the brief has none).
    """
    sentences = _factual_sentences(brief)
    if not sentences:
        return 0.0
    _, score, cut = _scorer()
    return sum(1 for s in sentences if score(input_text, s) < cut) / len(sentences)


def sentence_support(brief: BailBrief, input_text: str) -> list[dict[str, object]]:
    """The support score of every factual sentence of the brief against the input (what `unsupported_fact_rate` thresholds), with the ground it belongs to.

    Returns:
        One dict per sentence: `ground_id`, `check` (the ground's claim check, a string), `sentence`, `score` (the checker's support probability), `cut` (the threshold in
        force) and `checker` (the backend's name). Empty when the brief has no sentences. The coverage-risk curve (M33) and the confident-wrong rate (M35) read these.
    """
    from vakeel_sahayak.eval.feature_common import sentences_of

    name, score, cut = _scorer()
    out: list[dict[str, object]] = []
    for ground in brief.grounds:
        for sentence in sentences_of(ground.argument):
            out.append({"ground_id": ground.id, "check": getattr(ground.check, "value", str(ground.check)), "sentence": sentence,
                        "score": float(score(input_text, sentence)), "cut": float(cut), "checker": name})
    return out


def _perturb(sentence: str) -> str | None:
    """A copy with one date or number changed (the constructed negative of plan §15.9); None when nothing can change."""
    m = _DATE.search(sentence)
    if m:
        day = int(m.group(1))
        return sentence[: m.start(1)] + f"{(day % 28) + 1:0{len(m.group(1))}d}" + sentence[m.end(1):]
    m = _NUMBER.search(sentence)
    if m:
        return sentence[: m.start()] + str(int(m.group()) + 7) + sentence[m.end():]
    return None


def validate_checker(sentences: list[str]) -> dict[str, float]:
    """In-domain check: input sentences supported; copies with a changed date or number unsupported.

    Args:
        sentences: sentences copied from the input (the premise is their concatenation)

    Returns:
        `supported_accuracy` (copies judged supported), `unsupported_accuracy` (perturbed copies judged unsupported),
        `accuracy` (both pooled) and `n_supported` / `n_unsupported`; an accuracy with no items is 0.0.
    """
    premise = " ".join(sentences)
    _, score, cut = _scorer()
    pos = [score(premise, s) >= cut for s in sentences]
    negatives = [p for p in (_perturb(s) for s in sentences) if p is not None]
    neg = [score(premise, s) < cut for s in negatives]
    total = len(pos) + len(neg)
    return {
        "supported_accuracy": sum(pos) / len(pos) if pos else 0.0,
        "unsupported_accuracy": sum(neg) / len(neg) if neg else 0.0,
        "accuracy": (sum(pos) + sum(neg)) / total if total else 0.0,
        "n_supported": float(len(pos)),
        "n_unsupported": float(len(neg)),
    }
