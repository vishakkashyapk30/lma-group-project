"""NLI used by span_check and check_claim; threshold tuned on dev (plan §12). MiniCheck is evaluation-only (eval/).

Two clients share the `NliClient` interface:

- `DebertaNliClient`: DeBERTa-v3 NLI through transformers, loaded lazily on the first call;
- `OfflineNliClient`: a deterministic lexical checker for runs without the model. It is strict on exactly the things
  the in-domain checker validation perturbs (plan §15.9: "copies with a changed date, number or name count as
  unsupported"): every date, number, section reference and alias or proper name in the hypothesis must appear in the
  premise; a negation or an antonym ('granted' / 'rejected') that flips the premise's polarity is a contradiction; the
  rest is the weighted share of the hypothesis's content words found in the premise.

Thresholds: `nli_threshold(kind)` reads `nli.<kind>_min` from configs/thresholds.yaml (null until tuned on dev) and falls
back to the client's `default_threshold`; `tune_threshold` picks the dev-set cut-off.
"""

from __future__ import annotations

import importlib.util
import re
import threading
from collections.abc import Sequence
from datetime import date

from vakeel_sahayak.models.base import ModelUnavailable, NliClient, NliVerdict

_STATUS: dict[str, str | None] = {"backend": None, "fallback_reason": None}


def local_checkpoint(model_id: str) -> str | None:
    """The downloaded copy of a Hub checkpoint (`models/hf/<org>--<name>`, see scripts/download_models.sh), or None."""
    import os
    from pathlib import Path

    root = Path(os.environ.get("VS_MODELS_DIR") or Path(__file__).resolve().parents[3] / "models" / "hf")
    path = root / model_id.replace("/", "--")
    return str(path) if (path / "config.json").is_file() else None


def nli_status() -> dict[str, str | None]:
    """Which NLI backend the process ended up with: `backend` ('deberta-v3-nli', 'offline-lexical-nli' or None before the first client) and
    `fallback_reason` (set only when `auto` mode fell back to the offline stand-in, never silently: the driver records it in the manifest and the event log)."""
    return dict(_STATUS)


DEFAULT_DEBERTA = "MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli"
THRESHOLD_KINDS = ("fact_support", "authority_support", "span_check")


# --------------------------------------------------------------------------------------------- thresholds


def nli_threshold(kind: str = "fact_support", client: NliClient | None = None, config=None) -> float:  # noqa: ANN001
    """The decision threshold for one use of NLI.

    Args:
        kind: 'fact_support', 'authority_support' or 'span_check' (configs/thresholds.yaml `nli.<kind>_min`)
        client: the client whose `default_threshold` applies while the config value is null
        config: AppConfig (default: load_config())

    Returns:
        Threshold in [0, 1].
    """
    if kind not in THRESHOLD_KINDS:
        raise ValueError(f"unknown NLI threshold kind {kind!r}: use one of {THRESHOLD_KINDS}")
    if config is None:
        from vakeel_sahayak.config import load_config

        config = load_config()
    value = ((config.thresholds or {}).get("nli") or {}).get(f"{kind}_min")
    if value is not None:
        return float(value)
    return float(client.default_threshold) if client is not None else 0.5


def tune_threshold(scores: Sequence[float], labels: Sequence[bool], metric: str = "balanced_accuracy") -> float:
    """Pick the threshold that best separates supported (True) from unsupported (False) dev pairs.

    Candidates are the midpoints between consecutive distinct scores; ties go to the higher threshold (fewer false
    'supported' verdicts, the costly error). Deterministic.

    Args:
        scores: NLI scores of dev pairs
        labels: True for supported pairs
        metric: 'balanced_accuracy', 'accuracy' or 'f1'

    Returns:
        The threshold.
    """
    if len(scores) != len(labels) or not scores:
        raise ValueError("need as many labels as scores, and at least one pair")
    distinct = sorted(set(float(s) for s in scores))
    candidates = [distinct[0] - 1e-6] + [(a + b) / 2 for a, b in zip(distinct, distinct[1:], strict=False)] + [distinct[-1] + 1e-6]
    best, best_val = 0.5, -1.0
    for thr in candidates:
        tp = sum(1 for s, y in zip(scores, labels, strict=True) if s >= thr and y)
        fp = sum(1 for s, y in zip(scores, labels, strict=True) if s >= thr and not y)
        fn = sum(1 for s, y in zip(scores, labels, strict=True) if s < thr and y)
        tn = sum(1 for s, y in zip(scores, labels, strict=True) if s < thr and not y)
        if metric == "accuracy":
            val = (tp + tn) / len(scores)
        elif metric == "f1":
            val = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
        elif metric == "balanced_accuracy":
            pos, neg = tp + fn, tn + fp
            val = ((tp / pos if pos else 1.0) + (tn / neg if neg else 1.0)) / 2
        else:
            raise ValueError(f"unknown metric {metric!r}")
        if val > best_val + 1e-12 or (abs(val - best_val) <= 1e-12 and thr > best):
            best, best_val = thr, val
    return round(min(1.0, max(0.0, best)), 6)


# --------------------------------------------------------------------------------------------- DeBERTa


class DebertaNliClient(NliClient):
    """DeBERTa-v3 NLI used by span_check and check_claim; threshold tuned on dev (plan §12). MiniCheck is evaluation-only (eval/)."""

    name = "deberta-v3-nli"
    default_threshold = 0.5
    _LOCK = threading.Lock()
    _LOADED: dict[tuple[str, str | None], tuple] = {}

    def __init__(self, model: str | None = None, device: str | None = None, max_length: int = 512) -> None:
        """Choose the checkpoint (default: configs/models.yaml `nli.system`, first word); nothing loads yet.

        Args:
            model: Hugging Face id of an MNLI-style DeBERTa-v3 checkpoint
            device: 'cpu', 'cuda:0' or None for automatic
            max_length: tokens per (premise, hypothesis) pair; long premises are truncated first
        """
        self.model_id = model
        self.device = device
        self.max_length = max_length

    @staticmethod
    def available() -> bool:
        """True when transformers and torch are installed."""
        return all(importlib.util.find_spec(m) is not None for m in ("transformers", "torch"))

    def _model_name(self) -> str:
        if self.model_id:
            return self.model_id
        import os

        if os.environ.get("VS_NLI_MODEL"):
            return os.environ["VS_NLI_MODEL"]
        from vakeel_sahayak.config import load_config

        raw = str((load_config().models.get("nli") or {}).get("system") or "").strip()
        first = raw.split()[0] if raw else ""
        return first if "/" in first and "TODO" not in first and first != "microsoft/deberta-v3-large-mnli" else DEFAULT_DEBERTA

    def _source(self) -> str:
        """Where to load the checkpoint from: the downloaded copy under `$VS_MODELS_DIR` (default models/hf) when it exists, else the Hub id."""
        name = self._model_name()
        return local_checkpoint(name) or name

    def _load(self) -> tuple:
        key = (self._model_name(), self.device)
        with self._LOCK:
            if key not in self._LOADED:
                if not self.available():
                    raise ModelUnavailable("transformers and torch are not installed, so the DeBERTa NLI model cannot run", "models")
                import torch
                from transformers import AutoModelForSequenceClassification, AutoTokenizer

                try:
                    source = self._source()
                    tok = AutoTokenizer.from_pretrained(source)
                    model = AutoModelForSequenceClassification.from_pretrained(source)
                except OSError as exc:
                    raise ModelUnavailable(f"the NLI checkpoint {key[0]!r} could not be loaded: {exc}", "models") from exc
                device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
                model.to(device).eval()
                labels = {int(i): str(lbl).lower() for i, lbl in model.config.id2label.items()}
                entail = next((i for i, lbl in labels.items() if "entail" in lbl and "not" not in lbl), None)
                if entail is None:
                    raise ModelUnavailable(f"{key[0]!r} has no entailment label ({labels})", "models")
                self._LOADED[key] = (tok, model, device, entail)
            return self._LOADED[key]

    def entails(self, premise: str, hypothesis: str) -> float:
        """Entailment probability.

        Args:
            premise: source text (dossier quote or cited paragraph)
            hypothesis: claim or value

        Returns:
            P(entailment) in [0, 1].

        Raises:
            ModelUnavailable: transformers/torch or the checkpoint is missing.
        """
        return self.entails_batch([(premise, hypothesis)])[0]

    def entails_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Batched entailment probabilities."""
        if not pairs:
            return []
        import torch

        tok, model, device, entail = self._load()
        enc = tok([p for p, _ in pairs], [h for _, h in pairs], truncation="only_first", max_length=self.max_length,
                  padding=True, return_tensors="pt").to(device)  # fmt: skip
        with torch.no_grad():
            probs = torch.softmax(model(**enc).logits, dim=-1)[:, entail]
        return [float(x) for x in probs.tolist()]


# --------------------------------------------------------------------------------------------- offline lexical NLI

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6,
    "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}  # fmt: skip
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_PATTERNS = [
    re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"),  # ISO
    re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"),  # dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MONTH_RE})\.?,?\s+(\d{{4}})\b", re.I),  # 20 August 2024
    re.compile(rf"\b({_MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I),  # August 20, 2024
]
_STOP = frozenset(
    "a an the of in on at to for from by with and or as is are was were be been being has have had do does did that this "
    "these those it its which who whom whose there here than then so such into onto upon under over about after before "
    "since until while during also any all each every per via within shall should would could may might "
    "will can must he she they them his her their him we our you your i me my mr ms mrs shri smt sh learned "
    "said same further thereafter herein thereof".split()
)
# Capitalised words that are legal vocabulary, not names (a changed *name* is a contradiction; these are not names).
_NOT_NAMES = frozenset(
    "court supreme high sessions district state section sections article act code bail police station magistrate judge "
    "justice hon honourable government india indian union republic penal criminal procedure sanhita nagarik suraksha "
    "nyaya bharatiya sakshya adhiniyam fir charge sheet order orders application applicant accused complainant witness "
    "prosecution defence defense counsel public prosecutor investigating officer jail custody remand chief metropolitan "
    "judicial additional delhi bombay madras calcutta allahabad punjab haryana rajasthan karnataka kerala gujarat "
    "january february march april may june july august september october november december the this that "
    "petitioner respondent appellant special narcotic narcotics drugs psychotropic substances unlawful activities "
    "prevention money laundering".split()
)
_NEGATIONS = frozenset({"not", "no", "never", "neither", "nor", "none", "nothing", "without", "cannot", "nahi", "nahin", "नहीं", "न"})
_ANTONYMS = [
    ({"granted", "grant", "allowed", "allow", "enlarged"}, {"rejected", "reject", "refused", "refuse", "dismissed", "dismiss", "denied", "deny", "declined"}),
    ({"bailable"}, {"non_bailable"}),
    ({"cognisable", "cognizable"}, {"non_cognisable", "non_cognizable"}),
    ({"filed", "submitted"}, {"pending"}),
    ({"arrested"}, {"absconding", "absconded"}),
    ({"convicted"}, {"acquitted"}),
    ({"first", "first_time"}, {"repeat", "habitual"}),
]
_ALIAS = re.compile(r"\b(?:Co-accused|Accused|Complainant|IO|Witness|Person)-\d+\b")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z_'-]*|\d+(?:[./]\d+)*|[ऀ-ॿ]+")


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def extract_dates(text: str) -> tuple[str, list[tuple[int, int]]]:
    """ISO dates found in text (any of the formats Indian orders use) and their spans."""
    found: list[tuple[str, tuple[int, int]]] = []
    taken: list[tuple[int, int]] = []
    for i, pat in enumerate(_DATE_PATTERNS):
        for m in pat.finditer(text):
            if any(not (m.end() <= a or m.start() >= b) for a, b in taken):
                continue
            g = m.groups()
            if i == 0:
                iso = _iso(int(g[0]), int(g[1]), int(g[2]))
            elif i == 1:
                iso = _iso(int(g[2]), int(g[1]), int(g[0]))
            elif i == 2:
                iso = _iso(int(g[2]), _MONTHS[g[1].lower().rstrip(".")], int(g[0]))
            else:
                iso = _iso(int(g[2]), _MONTHS[g[0].lower().rstrip(".")], int(g[1]))
            if iso:
                found.append((iso, m.span()))
                taken.append(m.span())
    return " ".join(sorted({f for f, _ in found})), taken


def _stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ied", "edly", "ed", "es", "ly", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)] + ("y" if suffix in ("ies", "ied") else "")
    return w


class _Facts:
    """What the lexical checker reads off one text."""

    def __init__(self, text: str) -> None:
        self.text = text
        text = re.sub(r"\b(?:No|Nos|no|NO)\s*\.?\s*(?=\d)", " number ", text)  # 'FIR No. 112/2024' is not a negation
        text = text.replace("_", " ")  # field names such as custody_days read as words
        iso, spans = extract_dates(text)
        self.dates = set(iso.split()) if iso else set()
        masked = list(text)
        for a, b in spans:
            for k in range(a, b):
                masked[k] = " "
        rest = "".join(masked)
        from vakeel_sahayak.pipelines.section_extract import extract_sections  # lazy: models stays a leaf package

        self.sections = set(extract_sections(rest))
        self.aliases = {a.lower() for a in _ALIAS.findall(rest)}
        rest_no_alias = _ALIAS.sub(" ", rest)
        rest_no_alias = re.sub(r"\bnon[- ]", "non_", rest_no_alias, flags=re.I)
        tokens = _TOKEN.findall(rest_no_alias)
        self.numbers = {t for t in tokens if t[0].isdigit()}
        words = [t for t in tokens if not t[0].isdigit()]
        self.lower = [w.lower().strip("'-") for w in words]
        self.negated = any(w in _NEGATIONS or w.endswith("n't") for w in self.lower)
        self.content = {_stem(w) for w in self.lower if w not in _STOP and w not in _NEGATIONS and len(w) > 1}
        self.raw_words = set(self.lower)
        sentence_starts = {m.end() for m in re.finditer(r"(?:^|[.!?।]\s+)", rest_no_alias)}
        self.names = {
            m.group(0).lower()
            for m in re.finditer(r"\b[A-Z][a-z]{2,}\b", rest_no_alias)
            if m.start() not in sentence_starts and m.group(0).lower() not in _STOP and m.group(0).lower() not in _NOT_NAMES
        }
        self.number_parts = self.numbers | {c for n in self.numbers for c in re.split(r"[./]", n) if c}

    def has_number(self, n: str) -> bool:
        """True when a number (or every part of 'a/b', 'a.b') occurs in this text."""
        return n in self.number_parts or all(c in self.number_parts for c in re.split(r"[./]", n) if c)


class OfflineNliClient(NliClient):
    """Deterministic lexical NLI (see the module docstring). Clearly offline: `is_offline` is True."""

    name = "offline-lexical-nli"
    is_offline = True
    default_threshold = 0.5

    def judge(self, premise: str, hypothesis: str, threshold: float | None = None) -> NliVerdict:
        """Score with reasons.

        Args:
            premise: source text
            hypothesis: claim or value (a bare value such as '2024-08-20' or '112/2024' works too)
            threshold: decision threshold (default 0.5)

        Returns:
            NliVerdict whose reasons name each mismatch.
        """
        thr = self.default_threshold if threshold is None else float(threshold)
        p, h = _Facts(premise or ""), _Facts(hypothesis or "")
        reasons: list[str] = []
        contradiction = False
        for d in sorted(h.dates - p.dates):
            reasons.append(f"date {d} is not in the source")
            contradiction = True
        missing_numbers = {n for n in h.numbers if not p.has_number(n)}
        for n in sorted(missing_numbers):
            reasons.append(f"number {n} is not in the source")
            contradiction = True
        for s in sorted(h.sections - p.sections):
            reasons.append(f"section {s} is not in the source")
            contradiction = True
        for a in sorted(h.aliases - p.aliases):
            reasons.append(f"party {a} is not in the source")
            contradiction = True
        missing_names = {n for n in h.names - p.names if _stem(n) not in p.content}
        for n in sorted(missing_names):
            reasons.append(f"name {n!r} is not in the source")
            contradiction = True
        for pos, neg in _ANTONYMS:
            h_pos, h_neg = bool(h.raw_words & pos), bool(h.raw_words & neg)
            p_pos, p_neg = bool(p.raw_words & pos), bool(p.raw_words & neg)
            if (h_pos and p_neg and not p_pos) or (h_neg and p_pos and not p_neg):
                said = "/".join(sorted(h.raw_words & (pos | neg)))
                source = "/".join(sorted(p.raw_words & (pos | neg)))
                reasons.append(f"the claim says {said!r} where the source says {source!r}")
                contradiction = True
        if h.negated != p.negated and (h.content & p.content):
            reasons.append("negation differs from the source")
            contradiction = True
        weights = {w: 1.0 for w in h.content}
        covered = sum(1.0 for w in h.content if w in p.content)
        entity_total = len(h.dates) + len(h.numbers) + len(h.sections) + len(h.aliases)
        entity_hit = entity_total - (len(h.dates - p.dates) + len(missing_numbers) + len(h.sections - p.sections) + len(h.aliases - p.aliases))
        total = sum(weights.values()) + 2.0 * entity_total
        coverage = (covered + 2.0 * entity_hit) / total if total else 0.0
        if not h.content and not entity_total:
            reasons.append("the claim has no checkable content")
        if contradiction:
            score = round(0.02 + 0.08 * coverage, 4)
            label = "contradiction"
        else:
            score = round(coverage if entity_total else 0.9 * coverage, 4)
            label = "entailment" if score >= thr else "neutral"
            if score < thr:
                uncovered = sorted(w for w in h.content if w not in p.content)[:6]
                if uncovered:
                    reasons.append("not in the source: " + ", ".join(uncovered))
        return NliVerdict(score=score, threshold=thr, supported=score >= thr and not contradiction, label=label, reasons=tuple(reasons))

    def entails(self, premise: str, hypothesis: str) -> float:
        """Entailment score in [0, 1]."""
        return self.judge(premise, hypothesis).score


# --------------------------------------------------------------------------------------------- auto mode: real model, soft fallback


class AutoNliClient(NliClient):
    """`VS_MODELS=auto`: the DeBERTa checker when it can run, else the offline lexical checker, and never silently.

    Only NLI falls back (a missing `torch`/`transformers`, a missing or unreadable checkpoint); the reason is kept in `fallback_reason`,
    in `nli_status()` and logged as a warning, and the driver writes it into the run manifest and the case's event log. After a fallback
    the offline client answers for the rest of the process (`is_offline` and `default_threshold` follow the active client)."""

    def __init__(self, real: NliClient | None = None, offline: NliClient | None = None) -> None:
        """Pick the real client when its dependencies are installed (the model itself loads on the first call)."""
        self._offline = offline or OfflineNliClient()
        self._real: NliClient | None = real if real is not None else (DebertaNliClient() if DebertaNliClient.available() else None)
        self.fallback_reason: str | None = None if self._real is not None else "transformers or torch is not installed"
        self._publish()

    def _publish(self) -> None:
        import logging

        _STATUS["backend"], _STATUS["fallback_reason"] = self._active().name, self.fallback_reason
        if self.fallback_reason:
            logging.getLogger(__name__).warning("nli: offline stand-in (%s)", self.fallback_reason)

    def _active(self) -> NliClient:
        return self._real if self._real is not None else self._offline

    @property
    def name(self) -> str:  # type: ignore[override]
        """The active client's name."""
        return self._active().name

    @property
    def is_offline(self) -> bool:  # type: ignore[override]
        """True once the offline stand-in answers."""
        return self._active().is_offline

    @property
    def default_threshold(self) -> float:  # type: ignore[override]
        """The active client's untuned threshold."""
        return self._active().default_threshold

    def _call(self, method: str, *args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        if self._real is not None:
            try:
                return getattr(self._real, method)(*args, **kwargs)
            except (ModelUnavailable, ImportError, OSError) as exc:
                self._real, self.fallback_reason = None, f"{type(exc).__name__}: {str(exc)[:200]}"
                self._publish()
        return getattr(self._offline, method)(*args, **kwargs)

    def entails(self, premise: str, hypothesis: str) -> float:
        """Entailment probability from the active client."""
        return self._call("entails", premise, hypothesis)

    def entails_batch(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Batched entailment probabilities from the active client."""
        return self._call("entails_batch", pairs)

    def judge(self, premise: str, hypothesis: str, threshold: float | None = None) -> NliVerdict:
        """The active client's verdict."""
        return self._call("judge", premise, hypothesis, threshold)
