"""The non-Qwen, span-grounded LLM labeler for gold G1 and G3 (VI-04; plan 15.1, 15.9; evaluation plan 5.9).

The rule extractors (`g1_defense_factors`, `g3_dossier_fields`) are labeler (i). This module is labeler (ii): a hosted non-Qwen
model (default OpenAI gpt-6-luna; Sarvam open-weight models as an optional second one) that reads PUBLIC court text only and
labels FACTS STATED IN THAT TEXT. It is never the system's model and never a judge: it produces labels, not scores.

Every label the model proposes must carry a verbatim span of the order. `validate_span` rejects a label whose span is empty,
too short or too long, is not found in the order text (whitespace and case ignored, because court PDFs lose spaces), or, for a
section or a date, does not actually contain that section number or that date. Rejected labels are recorded with a reason and
never reach gold. The model is offered no rule candidate: it labels independently, so agreement with the rules is a real
agreement and not acquiescence to a list it was handed.

G1: which of the 12 bail factors the defense argued, from the defense-submissions part.
G3: dossier fields and dated events from the whole order: offence sections, arrest date, charge-sheet status, earlier bail
refusals, co-accused bail outcome, trial stage and every date. `custody_days` is arithmetic on stated dates and is not
labelled by the model (the agreement reports it as rule-derived only).

No function here calls a model unless given a client; tests inject a fake client.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from vakeel_sahayak.pipelines.concordance.refs import make_ref, normalise_section
from vakeel_sahayak.pipelines.order_facts import DATE_RE
from vakeel_sahayak.pipelines.section_extract import charged_sections
from vakeel_sahayak.pipelines.text_utils import normalise_date
from vakeel_sahayak.schemas.enums import Factor

MIN_SPAN = 8
MAX_SPAN = 600
MAX_INPUT_CHARS = 40_000
ACTS = ["IPC", "BNS", "CrPC", "BNSS", "NDPS", "UAPA", "PMLA", "POCSO"]
FACTOR_IDS = [f.value for f in Factor]

FACTOR_GLOSS = {
    "gravity_and_punishment": "the seriousness of the offence or the severity of the punishment is argued (for bail: it is not so grave, or the maximum sentence is low)",
    "custody_period": "the time the accused has already spent in custody or jail",
    "charge_sheet_filed": "the charge sheet or final report is filed, or the investigation is complete, so custody is not needed for investigation",
    "trial_delay": "the trial is delayed or will take long, speedy trial, Article 21, witnesses yet to be examined",
    "parity_with_co_accused": "a co-accused or similarly placed person was granted bail, so the accused deserves the same",
    "antecedents": "the accused has no (or a clean) criminal history, or the prior record is addressed",
    "flight_risk": "the accused will not abscond or flee, has roots in society, a fixed address, will surrender the passport",
    "witness_tampering": "the accused will not influence, threaten or tamper with witnesses or evidence",
    "weak_prima_facie": "the case against the accused is weak: false implication, no material, no prima facie case, delay in FIR",
    "health_age_family": "health, illness, age, gender (a woman), minority or family circumstances",
    "statutory_bar": "a statutory bar on bail (NDPS section 37, UAPA 43D(5), PMLA 45) is said not to apply or to be satisfied",
    "undertrial_period": "the accused has served the statutory part of the maximum sentence as an undertrial (BNSS 479, CrPC 436A) or the default-bail period (167(2), 187(3))",
}

G1_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "factors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"factor": {"type": "string", "enum": FACTOR_IDS}, "span": {"type": "string"}},
                "required": ["factor", "span"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["factors"],
    "additionalProperties": False,
}

_DATE_ITEM = {
    "type": "object",
    "properties": {"date": {"type": "string"}, "span": {"type": "string"}},
    "required": ["date", "span"],
    "additionalProperties": False,
}


def _status_item(values: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"status": {"type": "string", "enum": values}, "span": {"type": "string"}},
        "required": ["status", "span"],
        "additionalProperties": False,
    }


G3_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"act": {"type": "string", "enum": ACTS}, "section": {"type": "string"}, "span": {"type": "string"}},
                "required": ["act", "section", "span"],
                "additionalProperties": False,
            },
        },
        "arrest_date": _DATE_ITEM,
        "charge_sheet": _status_item(["filed", "not_filed", "not_stated"]),
        "previous_bail": _status_item(["rejected_or_withdrawn", "not_stated"]),
        "co_accused_bail": _status_item(["granted", "rejected", "not_stated"]),
        "trial_stage": _status_item(["charges_framed_or_trial_started", "not_stated"]),
        "dates": {"type": "array", "items": _DATE_ITEM},
    },
    "required": ["sections", "arrest_date", "charge_sheet", "previous_bail", "co_accused_bail", "trial_stage", "dates"],
    "additionalProperties": False,
}

G1_SYSTEM = (
    "You label facts stated in a public Indian High Court bail order. You never judge merits and never use outside knowledge. "
    "Answer with one JSON object and nothing else. Every label must carry a span: an exact, contiguous quotation copied "
    "character for character from the text (8 to 400 characters) that shows the label. If no quotation shows it, leave the label out."
)


def g1_messages(defense_text: str) -> list[dict[str, str]]:
    """The G1 request: the 12 factors with a gloss, the defense-submissions text, the JSON shape."""
    gloss = "\n".join(f"- {k}: {v}" for k, v in FACTOR_GLOSS.items())
    user = (
        "Below is the part of a bail order that records what the accused's side (petitioner or applicant and counsel) submitted.\n"
        "List each bail factor that this side ARGUED in the text, with one verbatim span showing it. A factor the prosecution or "
        "the court raises, or that is only mentioned in passing without being argued by the accused's side, is not a label. "
        "At most one entry per factor.\n\nFactors:\n"
        f"{gloss}\n\nAnswer as {{\"factors\": [{{\"factor\": <one of the ids>, \"span\": <exact quotation>}}]}}; "
        "an empty list when none applies.\n\nTEXT:\n" + defense_text[:MAX_INPUT_CHARS]
    )
    return [{"role": "system", "content": G1_SYSTEM}, {"role": "user", "content": user}]


def g3_messages(text: str) -> list[dict[str, str]]:
    """The G3 request: dossier fields and dates stated anywhere in the order, JSON shape."""
    user = (
        "Extract the following facts from the bail order below. Use only what the text states. For every item give an exact "
        "quotation (span) from the text that shows it; use an empty span only where the status is not_stated.\n"
        "- sections: every statutory section the order refers to (act one of IPC, BNS, CrPC, BNSS, NDPS, UAPA, PMLA, POCSO; "
        "section as written, such as 420, 318(4), 439). One entry per act and section.\n"
        "- arrest_date: the date the accused was arrested, as YYYY-MM-DD, or an empty date and span when not stated.\n"
        "- charge_sheet: filed, not_filed (still pending investigation) or not_stated.\n"
        "- previous_bail: rejected_or_withdrawn when an earlier bail application of the accused was rejected, dismissed or "
        "withdrawn, else not_stated.\n"
        "- co_accused_bail: granted or rejected for a co-accused's bail outcome as stated, else not_stated.\n"
        "- trial_stage: charges_framed_or_trial_started when charges were framed or evidence or trial has begun, else not_stated.\n"
        "- dates: every calendar date written in the text (date as YYYY-MM-DD, span the words that contain it).\n\nTEXT:\n"
        + text[:MAX_INPUT_CHARS]
    )
    return [{"role": "system", "content": G1_SYSTEM}, {"role": "user", "content": user}]


# ------------------------------------------------------------------------------------------------ span validation


def squash(text: str) -> str:
    """Whitespace-free, case-folded form used to compare a span with the order (court PDFs run words together)."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", "", text).casefold()


def validate_span(text_squashed: str, span: str, *, min_len: int = MIN_SPAN, max_len: int = MAX_SPAN) -> str | None:
    """None when `span` is a usable verbatim quotation of the text, else the reason it is rejected.

    Args:
        text_squashed: `squash(order text)`
        span: the quotation the labeler gave
        min_len: shortest span (characters, after trimming)
        max_len: longest span

    Returns:
        None, or one of 'empty_span', 'span_too_short', 'span_too_long', 'span_not_in_text'.
    """
    s = (span or "").strip()
    if not s:
        return "empty_span"
    if len(s) < min_len:
        return "span_too_short"
    if len(s) > max_len:
        return "span_too_long"
    return None if squash(s) in text_squashed else "span_not_in_text"


def span_has_date(span: str, iso: str) -> bool:
    """True when the span contains a written date that normalises to `iso`."""
    return any(normalise_date(m.group(0).replace(",", ", ").strip()) == iso for m in DATE_RE.finditer(span))


def span_has_section(span: str, section: str) -> bool:
    """True when the span contains the section's number (digits, with any letter suffix)."""
    head = re.match(r"\d+[A-Za-z]{0,2}", normalise_section(section))
    return bool(head) and re.search(rf"(?<!\d){re.escape(head.group(0))}(?![\d])", span, re.IGNORECASE) is not None


@dataclass(frozen=True)
class Proposal:
    """One validated label with the verbatim span that grounds it."""

    label: str
    span: str


@dataclass
class LabelerOutput:
    """What a labeler produced for one order: accepted (span-grounded) labels, rejected ones with a reason, or an error."""

    accepted: list[Proposal] = field(default_factory=list)
    rejected: list[dict[str, str]] = field(default_factory=list)
    error: str | None = None

    @property
    def labels(self) -> list[str]:
        """Accepted labels, de-duplicated, in the order given."""
        return list(dict.fromkeys(p.label for p in self.accepted))


class ChatClient(Protocol):
    """The slice of `LLMClient` the labeler needs."""

    def chat(self, messages: list[dict[str, str]], max_tokens: int = ..., temperature: float = ..., json_schema: dict | None = ...) -> str:
        """One chat call; with a schema the answer is JSON text."""
        ...


def parse_json_object(raw: str) -> dict[str, Any] | None:
    """The first JSON object in a reply (tolerates a fence or text around it); None when there is none."""
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        v = json.loads(s)
    except ValueError:
        i, j = s.find("{"), s.rfind("}")
        if i < 0 or j <= i:
            return None
        try:
            v = json.loads(s[i : j + 1])
        except ValueError:
            return None
    return v if isinstance(v, dict) else None


def _ask(client: ChatClient, messages: list[dict[str, str]], schema: dict[str, Any], max_tokens: int) -> tuple[dict[str, Any] | None, str | None]:
    """One call, one repeat when the reply is not a JSON object. Returns (object, error)."""
    last = "no reply"
    for _ in range(2):
        try:
            raw = client.chat(messages, max_tokens=max_tokens, temperature=0.0, json_schema=schema)
        except Exception as exc:  # a refused, capped or failed call is an item without labels, never a crash of the batch
            return None, f"{type(exc).__name__}: {str(exc)[:200]}"
        obj = parse_json_object(raw)
        if obj is not None:
            return obj, None
        last = "reply is not a JSON object"
    return None, last


# ------------------------------------------------------------------------------------------------ the two tasks


def label_g1(client: ChatClient, defense_text: str, *, max_tokens: int = 1200) -> LabelerOutput:
    """G1 labels of one order's defense part: factor ids whose verbatim span is in the text. At most one per factor."""
    out = LabelerOutput()
    if not defense_text.strip():
        out.error = "no_input"
        return out
    obj, err = _ask(client, g1_messages(defense_text), G1_SCHEMA, max_tokens)
    if obj is None:
        out.error = err
        return out
    sq = squash(defense_text)
    for item in obj.get("factors") or []:
        if not isinstance(item, dict):
            continue
        factor, span = str(item.get("factor", "")), str(item.get("span", ""))
        if factor not in FACTOR_IDS:
            out.rejected.append({"label": factor, "span": span[:120], "reason": "unknown_factor"})
        elif factor in {p.label for p in out.accepted}:
            continue
        elif (why := validate_span(sq, span)) is not None:
            out.rejected.append({"label": factor, "span": span[:120], "reason": why})
        else:
            out.accepted.append(Proposal(factor, span.strip()))
    return out


_STATUS_FIELDS = {
    "charge_sheet": ("charge_sheet_filed", {"filed": "True", "not_filed": "False"}),
    "previous_bail": ("previous_bail", {"rejected_or_withdrawn": "rejected_or_withdrawn"}),
    "co_accused_bail": ("co_accused_bail", {"granted": "granted", "rejected": "rejected"}),
    "trial_stage": ("trial_stage", {"charges_framed_or_trial_started": "charges_framed_or_trial_started"}),
}


def label_g3(client: ChatClient, order_text: str, *, max_tokens: int = 3000) -> LabelerOutput:
    """G3 labels of one whole order, in the rule labeler's label strings ('sections=BNS 305(a)', 'event=2025-04-09', ...)."""
    out = LabelerOutput()
    if not order_text.strip():
        out.error = "no_input"
        return out
    obj, err = _ask(client, g3_messages(order_text), G3_SCHEMA, max_tokens)
    if obj is None:
        out.error = err
        return out
    sq = squash(order_text)

    def take(label: str, span: str, extra_ok: bool = True, extra_reason: str = "") -> None:
        why = validate_span(sq, span)
        if why is None and not extra_ok:
            why = extra_reason
        if why is None:
            out.accepted.append(Proposal(label, span.strip()))
        else:
            out.rejected.append({"label": label, "span": span[:120], "reason": why})

    secs: list[tuple[str, str, str]] = []
    for item in obj.get("sections") or []:
        if isinstance(item, dict) and item.get("act") in ACTS and str(item.get("section", "")).strip():
            secs.append((str(item["act"]), str(item["section"]), str(item.get("span", ""))))
    refs = {make_ref(a, s): (a, s, sp) for a, s, sp in secs}
    for ref in charged_sections(list(refs)):  # the same filter the rule labeler applies (procedural bail provisions dropped)
        a, s, sp = refs[ref]
        take(f"sections={ref}", sp, span_has_section(sp, s), "section_not_in_span")

    ad = obj.get("arrest_date")
    if isinstance(ad, dict) and str(ad.get("date", "")).strip():
        iso = normalise_date(str(ad["date"]))
        if iso is None:
            out.rejected.append({"label": f"arrest_date={ad.get('date')}", "span": str(ad.get("span", ""))[:120], "reason": "bad_date"})
        else:
            take(f"arrest_date={iso}", str(ad.get("span", "")), span_has_date(str(ad.get("span", "")), iso), "date_not_in_span")

    for key, (name, mapping) in _STATUS_FIELDS.items():
        item = obj.get(key)
        if isinstance(item, dict) and item.get("status") in mapping:
            take(f"{name}={mapping[item['status']]}", str(item.get("span", "")))

    for item in obj.get("dates") or []:
        if not isinstance(item, dict):
            continue
        iso = normalise_date(str(item.get("date", "")))
        span = str(item.get("span", ""))
        if iso is None:
            out.rejected.append({"label": f"event={item.get('date')}", "span": span[:120], "reason": "bad_date"})
        else:
            take(f"event={iso}", span, span_has_date(span, iso), "date_not_in_span")
    return out
