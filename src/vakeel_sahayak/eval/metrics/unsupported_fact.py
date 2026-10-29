"""Metrics: Unsupported-fact rate: share of factual sentences MiniCheck finds unsupported by the input; checker validation (plan §15.9) (plan §15.8).

The evaluation checker must not be the system's own checker (evaluation-plan 2.4: Vakeel repairs its claims until the DeBERTa NLI accepts
them, so scoring M6 with that model would favour Full). The checker is chosen as follows (`VS_M6_CHECKER`, default `auto`):

- MiniCheck-RoBERTa-Large (Tang et al., EMNLP 2024, LLM-AggreFact), loaded with transformers from the local copy
  `models/hf/lytang--MiniCheck-RoBERTa-Large` (`make models`; `$VS_MODELS_DIR` moves the root), or failing that the optional `minicheck`
  package. Used in `real` and `auto` model mode, or whenever `VS_M6_CHECKER=minicheck` (which refuses to fall back when it cannot load).
- The offline lexical stand-in (`offline` model mode, the default): allowed so offline runs and tests score end to end; its name
  `offline-lexical-nli` marks every table as a stand-in (a plumbing check, not a validated judge), and no reported number comes from it.
- The system's real NLI (DeBERTa, `models.factory.get_nli`) only with the explicit opt-in `VS_M6_ALLOW_SYSTEM_CHECKER=1` (or `VS_M6_CHECKER=nli`
  with that opt-in); without it `SystemCheckerRefused` is raised instead of a silent fallback. The opt-in name carries "(system checker)".

`checker_backend()` names the checker in use; the scorer records it in the score meta (`m6_checker`) and Table 1 prints it.
"""

from __future__ import annotations

import functools
import importlib.util
import os
import re

from vakeel_sahayak.schemas.bail_brief import BailBrief

_DATE = re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})\b")
_NUMBER = re.compile(r"\d+")

MINICHECK_ID = "lytang/MiniCheck-RoBERTa-Large"
MINICHECK_NAME = "minicheck-roberta-large"
CHECKER_ENV = "VS_M6_CHECKER"  # auto (default) | minicheck | nli
ALLOW_SYSTEM_ENV = "VS_M6_ALLOW_SYSTEM_CHECKER"
CHUNK_TOKENS = 400  # MiniCheck's RoBERTa chunk size: the premise is split into chunks of about 400 tokens and the claim's score is the max over chunks
MAX_LEN = 512


class SystemCheckerRefused(RuntimeError):
    """M6 would be scored by the system's own claim checker (the DeBERTa NLI Vakeel repairs against); install MiniCheck or opt in explicitly."""


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


@functools.lru_cache(maxsize=2)
def _roberta_scorer(path: str):  # noqa: ANN202
    """(premise, claim) -> P(supported) from the MiniCheck-RoBERTa-Large checkpoint at `path`: max over premise chunks of softmax label 1."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path)
    model.eval()
    supported = 1  # config.json id2label {0: "0", 1: "1"}: label 1 is "supported" in MiniCheck

    def score(premise: str, claim: str) -> float:
        claim_ids = tok(claim, add_special_tokens=False)["input_ids"]
        doc_ids = tok(premise, add_special_tokens=False)["input_ids"] or [tok.unk_token_id]
        size = max(16, min(CHUNK_TOKENS, MAX_LEN - len(claim_ids) - 4))
        chunks = [tok.decode(doc_ids[i:i + size], clean_up_tokenization_spaces=False) for i in range(0, len(doc_ids), size)]
        best = 0.0
        with torch.no_grad():
            for i in range(0, len(chunks), 8):
                batch = chunks[i:i + 8]
                enc = tok(batch, [claim] * len(batch), truncation="only_first", max_length=MAX_LEN, padding=True, return_tensors="pt")
                probs = torch.softmax(model(**enc).logits, dim=-1)[:, supported]
                best = max(best, float(probs.max()))
        return best

    return score


@functools.lru_cache(maxsize=1)
def _package_scorer():  # noqa: ANN202
    """The `minicheck` package's RoBERTa scorer (downloads its own weights), or None when the package is missing or cannot load."""
    if importlib.util.find_spec("minicheck") is None:
        return None
    try:
        from minicheck.minicheck import MiniCheck

        scorer = MiniCheck(model_name="roberta-large", cache_dir=None)

        def score(premise: str, sentence: str) -> float:
            _, probs, _, _ = scorer.score(docs=[premise], claims=[sentence])
            return float(probs[0])

        return score
    except Exception:  # noqa: BLE001 - heavy optional dependency: any load failure means MiniCheck is unavailable
        return None


def _minicheck_scorer():  # noqa: ANN202
    """A (premise, sentence) -> support-probability callable from MiniCheck-RoBERTa-Large, or None when neither the local weights nor the package load."""
    from vakeel_sahayak.models.nli import local_checkpoint

    path = local_checkpoint(MINICHECK_ID)
    if path is not None and importlib.util.find_spec("torch") is not None and importlib.util.find_spec("transformers") is not None:
        try:
            return _roberta_scorer(path)
        except Exception:  # noqa: BLE001 - a broken local copy: try the package, then report unavailable
            pass
    return _package_scorer()


def _scorer():  # noqa: ANN202
    """(name, score(premise, hypothesis), cut) of the evaluation checker; see the module docstring for the choice and the refusal."""
    from vakeel_sahayak.models.factory import get_nli, models_mode
    from vakeel_sahayak.models.nli import nli_threshold

    choice = os.environ.get(CHECKER_ENV, "").strip().lower() or "auto"
    if choice not in {"auto", "minicheck", "nli"}:
        raise ValueError(f"{CHECKER_ENV} must be auto, minicheck or nli, got {choice!r}")
    if choice == "minicheck" or (choice == "auto" and models_mode() != "offline"):
        mini = _minicheck_scorer()
        if mini is not None:
            return MINICHECK_NAME, mini, 0.5
        if choice == "minicheck":
            raise SystemCheckerRefused(f"{CHECKER_ENV}=minicheck but MiniCheck cannot load: run `make models` ({MINICHECK_ID} under models/hf) with torch installed")
    client = get_nli()
    name = getattr(client, "name", "nli")
    if not getattr(client, "is_offline", False):
        if not _truthy(ALLOW_SYSTEM_ENV):
            raise SystemCheckerRefused(
                f"the unsupported-fact checker would be {name}, the system's own claim checker (Vakeel repairs until it agrees), so M6 would not be "
                f"independent: install MiniCheck ({MINICHECK_ID} under models/hf via `make models`, plus torch), or set {ALLOW_SYSTEM_ENV}=1 to score "
                "with the system checker on purpose (the tables then name it)")
        name = f"{name} (system checker)"
    return name, client.entails, nli_threshold("fact_support", client)


def checker_backend() -> str:
    """Name of the checker a call would use ('minicheck-roberta-large', 'offline-lexical-nli' or '<nli> (system checker)' under the opt-in); raises
    `SystemCheckerRefused` where the scoring call would."""
    return _scorer()[0]


def _factual_sentences(brief: BailBrief) -> list[str]:
    from vakeel_sahayak.eval.feature_common import sentences_of

    out: list[str] = []
    for ground in brief.grounds:
        out.extend(sentences_of(ground.argument))
    return out


def unsupported_fact_counts(brief: BailBrief, input_text: str) -> tuple[int, int]:
    """(factual sentences, unsupported sentences) of the brief. The count, not the rate, is the null-agent-safe companion of M6 (a silent brief has 0 of 0)."""
    sentences = _factual_sentences(brief)
    if not sentences:
        return 0, 0
    _, score, cut = _scorer()
    return len(sentences), sum(1 for s in sentences if score(input_text, s) < cut)


def unsupported_fact_rate(brief: BailBrief, input_text: str) -> float | None:
    """Share of the brief's factual sentences that the input does not support.

    Args:
        brief: the drafted brief; every sentence of every ground's argument is a factual sentence
        input_text: the facts the system was given (the reference point, plan §15.9)

    Returns:
        Unsupported sentences / factual sentences, or None when the brief has no factual sentence ("no claims", plan 5.7). It is never 0.0 for an empty brief:
        a system that says nothing would otherwise earn a perfect M6. Callers exclude None from the mean, count the cases that have claims, and read the
        unsupported-fact count and the answerable-factor coverage beside the rate.
    """
    n, bad = unsupported_fact_counts(brief, input_text)
    return None if n == 0 else bad / n


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
