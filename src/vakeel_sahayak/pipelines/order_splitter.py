"""Cue-phrase splitter dividing each order into facts, defense, prosecution, reasoning and operative order; unclean splits are dropped (plan §5.2, §15.1). Also builds the test set.

Method: the order is cut into paragraph blocks (`text_utils.paragraph_blocks`). Each block is classified by cue phrases
(counsel for the petitioner submits, learned APP opposes, having heard, the application is dismissed, ...) or by a
section heading. A block with no cue continues the part before it. Stages only move forward: facts, then submissions
(defense and prosecution may interleave), then reasoning, then the operative order. A split is **clean** when all five
parts are present and long enough; the rest are dropped from the test set (plan §15.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.text_utils import count_tokens, paragraph_blocks, read_jsonl, write_jsonl
from vakeel_sahayak.schemas.enums import OrderPart

PART_ORDER = (OrderPart.FACTS, OrderPart.DEFENSE, OrderPart.PROSECUTION, OrderPart.REASONING, OrderPart.OPERATIVE)
MIN_WORDS = {
    OrderPart.FACTS: 8,
    OrderPart.DEFENSE: 8,
    OrderPart.PROSECUTION: 8,
    OrderPart.REASONING: 15,
    OrderPart.OPERATIVE: 4,
}

_I = re.IGNORECASE
_DEFENSE_SIDE = (
    r"(?:learned\s+)?(?:senior\s+)?(?:counsel|advocate|lawyer)s?\s+(?:appearing\s+)?(?:for|on\s+behalf\s+of)\s+(?:the\s+)?"
    r"(?:petitioner|applicant|accused|appellant)"
    r"|(?:on\s+behalf\s+of|behalf\s+of)\s+(?:the\s+)?(?:petitioner|applicant|accused|appellant)"
    r"|(?:the\s+)?(?:petitioner|applicant|accused)\s+(?:submits?|contends?|states?|urges?|argues?)"
)
_PROSECUTION_SIDE = (
    r"(?:learned\s+)?(?:APP|A\.P\.P\.?|PP|AAG|AGA|ASG|SG|additional\s+solicitor\s+general|solicitor\s+general|additional\s+public\s+prosecutor|public\s+prosecutor|special\s+public\s+prosecutor"
    r"|additional\s+advocate\s+general|advocate\s+general|standing\s+counsel|state\s+counsel|panel\s+lawyer|spp)\b"
    r"|(?:learned\s+)?(?:counsel|advocate|lawyer)s?\s+(?:appearing\s+)?(?:for|on\s+behalf\s+of)\s+(?:the\s+)?"
    r"(?:state|respondent|prosecution|CBI|ED|NCB|NIA|complainant|informant|victim|union)"
    r"|(?:on\s+behalf\s+of|behalf\s+of)\s+(?:the\s+)?(?:state|respondent|prosecution|CBI|ED|NCB|NIA|complainant|informant)"
    r"|(?:the\s+)?(?:prosecution|state|respondent|complainant|informant)\s+(?:submits?|contends?|opposes?|states?|urges?|argues?)"
    r"|(?:strongly\s+)?opposed?\s+the\s+(?:bail|prayer|application)"
)
_SUBMISSION_VERB = re.compile(
    r"\b(?:submit(?:s|ted)?|contend(?:s|ed)?|argue[sd]?|urge[sd]?|plead(?:s|ed)?|oppos(?:e|es|ed)|stat(?:e|es|ed)\s+that|"
    r"point(?:s|ed)?\s+out|pray(?:s|ed)?|canvass(?:ed)?|emphasi[sz]ed?|assert(?:s|ed)?)\b",
    _I,
)
_DEFENSE_RE = re.compile(_DEFENSE_SIDE, _I)
_PROSECUTION_RE = re.compile(_PROSECUTION_SIDE, _I)

_REASONING_CUES = re.compile(
    r"\b(?:having\s+(?:heard|considered|perused|gone\s+through)|(?:heard|perused)\s+(?:the\s+)?(?:learned\s+)?(?:counsel|parties|advocates?|record|material)|i\s+have\s+(?:heard|considered|perused|gone\s+through|carefully)"
    r"|(?:this\s+)?court\s+has\s+(?:heard|considered|perused|gone\s+through)|(?:considered|considering)\s+the\s+(?:rival|submissions|contentions|"
    r"facts|material|nature)|(?:on|upon)\s+(?:a\s+)?(?:careful\s+|thorough\s+)?(?:perusal|consideration|examination|appreciation)"
    r"|(?:i\s+am|this\s+court\s+is|we\s+are)\s+of\s+the\s+(?:considered\s+|firm\s+|prima\s+facie\s+)?(?:view|opinion)"
    r"|(?:it\s+is|this\s+is|the\s+law\s+is)\s+(?:a\s+)?(?:well|trite|well-)[\s-]*settled|the\s+(?:question|issue)\s+(?:that\s+)?(?:arises|falls|"
    r"for\s+consideration)|the\s+principles?\s+(?:governing|applicable|laid\s+down|for\s+(?:the\s+)?grant)|this\s+court\s+(?:finds|observes|notes)"
    r"|the\s+(?:grant|object)\s+of\s+bail|in\s+(?:the\s+)?(?:facts\s+and\s+)?circumstances\s+of\s+(?:the|this)\s+case|"
    r"(?:analysis|discussion)\s+and\s+(?:findings|conclusion))\b",
    _I,
)
_OPERATIVE_CUES = re.compile(
    r"\b(?:(?:bail\s+)?(?:application|petition|appeal|prayer|plea)\s+(?:is|stands|be|are)\s+(?:hereby\s+)?(?:accordingly\s+)?"
    r"(?:allowed|dismissed|rejected|disposed|granted|accepted|refused)"
    r"|(?:is|are|be|stands?)\s+(?:hereby\s+)?(?:allowed|dismissed|rejected|disposed\s+of)\b"
    r"|(?:directed|ordered)\s+to\s+be\s+(?:released|enlarged)|(?:be|is|shall\s+be)\s+(?:hereby\s+)?(?:released|enlarged)\s+on\s+bail"
    r"|(?:be|is)\s+(?:hereby\s+)?(?:admitted|granted)\s+(?:to\s+)?(?:regular\s+|interim\s+|anticipatory\s+)?bail|bail\s+is\s+(?:hereby\s+)?granted"
    r"|furnishing\s+(?:a\s+)?personal\s+bond|on\s+(?:his|her|their)\s+furnishing|ordered\s+accordingly|stands\s+disposed|"
    r"pending\s+application\(?s?\)?\s+(?:if\s+any\s+)?(?:also\s+)?(?:stand|stands|is|are)\s+disposed|"
    r"copy\s+of\s+this\s+order\s+(?:be|shall\s+be)\s+(?:sent|communicated|forwarded)|subject\s+to\s+the\s+following\s+conditions)",
    _I,
)
# A short line alone, usually a heading ("ANALYSIS", "Submissions of the Petitioner:").
_HEADINGS: list[tuple[OrderPart, re.Pattern[str]]] = [
    (OrderPart.OPERATIVE, re.compile(r"^(?:order|operative\s+(?:part|order)|conclusion|directions?|result|relief)\s*:?$", _I)),
    (OrderPart.REASONING, re.compile(r"^(?:analysis|discussion|reasoning|reasons?|findings?|consideration|court'?s\s+(?:analysis|view)|decision)(?:\s+and\s+\w+)?\s*:?$", _I)),
    (OrderPart.PROSECUTION, re.compile(r"^(?:submissions?|arguments?|contentions?)\s+(?:of|on\s+behalf\s+of)\s+(?:the\s+)?(?:state|respondents?|prosecution|complainant)\s*:?$", _I)),
    (OrderPart.DEFENSE, re.compile(r"^(?:submissions?|arguments?|contentions?)\s+(?:of|on\s+behalf\s+of)\s+(?:the\s+)?(?:petitioners?|applicants?|accused|appellants?)\s*:?$", _I)),
    (OrderPart.FACTS, re.compile(r"^(?:facts|brief\s+facts|background|factual\s+(?:matrix|background)|prosecution\s+case|case\s+of\s+the\s+prosecution)\s*:?$", _I)),
]  # fmt: skip
_GRANTED = re.compile(
    r"(?:released|enlarged)\s+on\s+bail|(?:admitted|granted)\s+(?:to\s+)?(?:regular\s+|interim\s+|anticipatory\s+)?bail|"
    r"\b(?:bail\s+)?(?:application|petition|appeal|prayer|plea)\s+(?:is|stands|be)\s+(?:hereby\s+)?(?:accordingly\s+)?(?:allowed|granted|accepted)|"
    r"\bbail\s+is\s+(?:hereby\s+)?granted|\bgranted\s+bail\b|\bis\s+allowed\b",
    _I,
)
_REFUSED = re.compile(
    r"\b(?:dismissed|rejected|refused|declined|denied)\b|\bno\s+(?:ground|merit)\b|\bnot\s+(?:inclined|entitled)\b", _I
)
_WITHDRAWN = re.compile(r"\b(?:withdrawn|withdraw|disposed\s+of\s+as\s+(?:infructuous|withdrawn))\b", _I)


@dataclass
class SplitResult:
    """Outcome of splitting one order (plan §5.2): the parts, the clean-split verdict and why it failed."""

    parts: dict[OrderPart, str]
    clean: bool
    missing: list[OrderPart] = field(default_factory=list)
    too_short: list[OrderPart] = field(default_factory=list)
    n_blocks: int = 0

    @property
    def reasons(self) -> list[str]:
        """Human-readable reasons for an unclean split (empty when clean)."""
        out = [f"missing:{p.value}" for p in self.missing]
        return out + [f"too_short:{p.value}" for p in self.too_short]


def classify_block(block: str, current: OrderPart | None = None) -> OrderPart | None:
    """Classify one paragraph block by cue phrases; None when it carries no cue (it continues the previous part).

    Args:
        block: a paragraph of the order
        current: the part in force, used to continue a submission after 'It is further submitted'

    Returns:
        A part, or None.
    """
    text = block.strip()
    if len(text) <= 60 and "\n" not in text:
        heading = re.sub(r"^\(?[0-9ivxA-Z]{1,4}[.)]\s+", "", text).strip(" -:–")
        for part, pat in _HEADINGS:
            if pat.match(heading):
                return part
    side = _submission_side(text)
    if side:
        return side
    if current in (OrderPart.DEFENSE, OrderPart.PROSECUTION) and re.match(
        r"^\W*(?:\d+[.)]\s*)?(?:it\s+is\s+)?(?:further|also|then|lastly|next)\b", text, _I
    ):
        return current
    operative = _OPERATIVE_CUES.search(text)
    reasoning = _REASONING_CUES.search(text)
    if operative and (not reasoning or operative.start() <= reasoning.start() or len(text) < 400):
        return OrderPart.OPERATIVE
    if reasoning:
        return OrderPart.REASONING
    return None


def _submission_side(text: str) -> OrderPart | None:
    """Defense or prosecution when a counsel cue and a submission verb occur; the earlier cue wins."""
    if not _SUBMISSION_VERB.search(text):
        return None
    d, p = _DEFENSE_RE.search(text), _PROSECUTION_RE.search(text)
    if d and p:
        return OrderPart.DEFENSE if d.start() <= p.start() else OrderPart.PROSECUTION
    if d:
        return OrderPart.DEFENSE
    return OrderPart.PROSECUTION if p else None


def _assign_blocks(blocks: list[str]) -> list[OrderPart]:
    """Give every block a part; stages never move backwards (submissions of either side count as one stage)."""
    stage = {OrderPart.FACTS: 0, OrderPart.DEFENSE: 1, OrderPart.PROSECUTION: 1, OrderPart.REASONING: 2, OrderPart.OPERATIVE: 3}
    labels: list[OrderPart] = []
    current = OrderPart.FACTS
    for block in blocks:
        cue = classify_block(block, current)
        if cue is not None and stage[cue] >= stage[current]:
            current = cue
        labels.append(current)
    return labels


def analyse_split(text: str) -> SplitResult:
    """Split an order by cue phrases and give the clean-split verdict (plan §5.2, §15.1).

    Args:
        text: the whole order

    Returns:
        SplitResult. `parts` always holds all five keys (empty string when a part was not found).
    """
    blocks = paragraph_blocks(text)
    labels = _assign_blocks(blocks) if blocks else []
    buckets: dict[OrderPart, list[str]] = {p: [] for p in PART_ORDER}
    for block, label in zip(blocks, labels, strict=True):
        buckets[label].append(block)
    parts = {p: "\n\n".join(buckets[p]) for p in PART_ORDER}
    missing = [p for p in PART_ORDER if not parts[p].strip()]
    short = [p for p in PART_ORDER if p not in missing and count_tokens(parts[p]) < MIN_WORDS[p]]
    return SplitResult(parts=parts, clean=not missing and not short, missing=missing, too_short=short, n_blocks=len(blocks))


def split_order(text: str) -> dict[OrderPart, str] | None:
    """Split by cue phrases; None if it does not split cleanly.

    Args:
        text: see behaviour

    Returns:
        Parts or None.
    """
    result = analyse_split(text)
    return result.parts if result.clean else None


def infer_outcome(operative_text: str) -> str | None:
    """Read the bail outcome from the operative order: 'granted', 'rejected', 'withdrawn' or None.

    Args:
        operative_text: the operative part (or the whole order tail)

    Returns:
        Outcome label, or None when the text states none.
    """
    if _GRANTED.search(operative_text) and not re.search(r"\b(?:not|no)\s+(?:be\s+)?(?:allowed|granted)\b", operative_text, _I):
        refused_first = _REFUSED.search(operative_text)
        granted = _GRANTED.search(operative_text)
        if not refused_first or granted.start() < refused_first.start() or "released" in operative_text.lower():
            return "granted"
    if _WITHDRAWN.search(operative_text):
        return "withdrawn"
    if _REFUSED.search(operative_text):
        return "rejected"
    return None


def split_all(orders_path: str, out_path: str) -> tuple[int, int]:
    """Split all orders, writing parts and a drop log.

    Input: JSONL, one order per line with `doc_id` and `text` (other fields such as court, date and outcome are copied
    through). Output `out_path`: one line per cleanly split order, `{..., "parts": {part: text}}`. The drop log is
    `<out_path>.dropped.jsonl` with `{"doc_id", "reasons"}` for every order that did not split cleanly (plan §15.1).

    Args:
        orders_path: see behaviour
        out_path: see behaviour

    Returns:
        (kept, dropped).
    """
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for order in read_jsonl(orders_path):
        text = order.get("text") or order.get("full_text") or ""
        result = analyse_split(str(text))
        meta = {k: v for k, v in order.items() if k not in ("text", "full_text")}
        if result.clean:
            kept.append({**meta, "parts": {p.value: t for p, t in result.parts.items()}})
        else:
            dropped.append({"doc_id": order.get("doc_id"), "reasons": result.reasons or ["empty"], "text": text})
    write_jsonl(out_path, kept)
    write_jsonl(Path(str(out_path) + ".dropped.jsonl"), dropped)
    return len(kept), len(dropped)


@dataclass
class RescueReport:
    """Outcome of a rescue pass: counts and the ids of the rescued orders."""

    attempted: int = 0
    rescued: int = 0
    still_dropped: int = 0
    rescued_ids: list[Any] = field(default_factory=list)


def _rescue_schema(n_blocks: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "parts": {"type": "array", "items": {"enum": [p.value for p in PART_ORDER]}, "minItems": n_blocks, "maxItems": n_blocks}
        },
        "required": ["parts"],
    }


def rescue_split(text: str, labeler: Any | None = None) -> SplitResult | None:
    """Re-split one unclean order with the non-Qwen labeler, keeping the spans verbatim (plan §19).

    The model only chooses a part for each paragraph block; it never writes text. Every part is the join of whole blocks of
    the order, so each rescued part cites verbatim spans (checked below), and the stage order and the length floors of
    `analyse_split` still apply. Public court text only (`public_scope`). Never Qwen (the labeler refuses it).

    Args:
        text: the whole order (public court text)
        labeler: an `EvalLabeler` (or any object with `.client()`); None builds the default one from `VS_LABELER`

    Returns:
        A clean SplitResult, or None when the labeler is unavailable (offline stand-in: the rule decision stands), answers
        badly, goes backwards in stage, or the result still fails the clean-split checks.
    """
    from vakeel_sahayak.models.base import ModelUnavailable
    from vakeel_sahayak.models.labeler import EvalLabeler
    from vakeel_sahayak.models.prompting import render_prompt
    from vakeel_sahayak.models.sarvam.policy import public_scope
    from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, constrained_generate

    blocks = paragraph_blocks(text)
    if len(blocks) < len(PART_ORDER):
        return None
    labeler = labeler if labeler is not None else EvalLabeler()
    schema = _rescue_schema(len(blocks))
    numbered = [{"i": i, "text": b[:700]} for i, b in enumerate(blocks)]
    prompt = render_prompt(
        "order_splitter.rescue",
        "For each numbered paragraph of this Indian bail order choose its part: facts, defense_submissions (for the "
        "accused), prosecution_submissions (for the State), reasoning (the court's analysis) or operative_order (the final "
        "order). Parts appear in that order (defense and prosecution may interleave). Answer only with the JSON object "
        '{"parts": [one part per paragraph, in order]}.',
        {"paragraphs": numbered},
        system="You are an annotator of Indian court orders.",
        schema=schema,
    )
    try:  # LabelerUnavailable is a ModelUnavailable and a NotImplementedError: both mean "keep the rule decision"
        with public_scope("order-split-rescue"):
            out = constrained_generate(labeler.client(), prompt, schema, max_tokens=max(256, 8 * len(blocks)))
    except (ModelUnavailable, NotImplementedError, StructuredOutputError):
        return None
    raw = out.get("parts") if isinstance(out, dict) else None
    if not isinstance(raw, list) or len(raw) != len(blocks):
        return None
    try:
        labels = [OrderPart(str(x)) for x in raw]
    except ValueError:
        return None
    stage = {OrderPart.FACTS: 0, OrderPart.DEFENSE: 1, OrderPart.PROSECUTION: 1, OrderPart.REASONING: 2, OrderPart.OPERATIVE: 3}
    if any(stage[b] < stage[a] for a, b in zip(labels, labels[1:], strict=False)):
        return None
    flat = re.sub(r"\s+", " ", text)
    if not all(b in flat for b in blocks):  # span grounding: every block is verbatim in the order
        return None
    buckets: dict[OrderPart, list[str]] = {p: [] for p in PART_ORDER}
    for block, label in zip(blocks, labels, strict=True):
        buckets[label].append(block)
    parts = {p: "\n\n".join(buckets[p]) for p in PART_ORDER}
    missing = [p for p in PART_ORDER if not parts[p].strip()]
    short = [p for p in PART_ORDER if p not in missing and count_tokens(parts[p]) < MIN_WORDS[p]]
    if missing or short:
        return None
    return SplitResult(parts=parts, clean=True, n_blocks=len(blocks))


def rescue_dropped(dropped_path: str, out_path: str | None = None, labeler: Any | None = None) -> RescueReport:
    """Re-split every dropped order and write the rescued ones (see `rescue_with_non_qwen`); returns the full report."""
    report = RescueReport()
    rescued: list[dict[str, Any]] = []
    for rec in read_jsonl(dropped_path):
        text = str(rec.get("text") or "")
        report.attempted += 1
        result = rescue_split(text, labeler) if text else None
        if result is None:
            report.still_dropped += 1
            continue
        rescued.append(
            {
                "doc_id": rec.get("doc_id"),
                "parts": {p.value: t for p, t in result.parts.items()},
                "spans": {p.value: t.split("\n\n") for p, t in result.parts.items()},  # verbatim blocks, each found in the order
                "rescued_by": "non-qwen-labeler",
            }
        )
        report.rescued += 1
        report.rescued_ids.append(rec.get("doc_id"))
    write_jsonl(out_path or str(dropped_path) + ".rescued.jsonl", rescued)
    return report


def rescue_with_non_qwen(dropped_path: str, out_path: str | None = None, labeler: Any | None = None) -> int:
    """Fallback (plan §19): re-split the orders that failed the cue splitter with a non-Qwen labeler; return how many were rescued.

    Opt-in: nothing calls it by default and `split_all` is unchanged. The labeler is the evaluation labeler facade
    (`models/labeler.py`: OpenAI on public court text under `public_scope`, never Qwen). Offline (`VS_MODELS=offline`) it
    is unavailable and the stand-in keeps the rule decision: every record stays dropped and the count is 0. Rescued
    records go to `out_path` (default `<dropped_path>.rescued.jsonl`) as `{doc_id, parts, spans, rescued_by}`; `spans`
    lists the verbatim blocks of each part.

    Args:
        dropped_path: the `.dropped.jsonl` written by `split_all`
        out_path: where to write rescued records
        labeler: injected labeler (tests); None builds the default

    Returns:
        Rescued count.
    """
    return rescue_dropped(dropped_path, out_path, labeler).rescued
