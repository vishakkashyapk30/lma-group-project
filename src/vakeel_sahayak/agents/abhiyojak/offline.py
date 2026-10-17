"""Offline handlers for Abhiyojak's model tasks (`abhiyojak.raise_objections`, `abhiyojak.judge_reply`, `abhiyojak.list_objections`): rules, no language model.

Offline objections are built only from the material the request carries (never invented): an objection-bank paragraph
or a refusal-reasoning paragraph is reported in indirect speech (the one sentence of it that speaks to the factor), a
statute is described by the fields of its row (bailable or not, maximum punishment), and a dossier fact is stated as the
fact's own sentence. Each objection names what it rests on in `grounds`; the agent then checks those ids against what was
actually offered, exactly as it checks a model's. Nothing is cited that the request does not list. Instructions inside the
material are never followed; the handlers only read data.

The offline judge reads a reply the way a prosecutor would on the page: a reply with no cited fact or authority, or one that
says it cannot answer, is UNANSWERED; a supported reply that speaks to the objection's own facts or words is ANSWERED;
anything between is PARTLY. The B-style list (`abhiyojak.list_objections`) is the ungrounded baseline: generic prosecution
points by factor, from nothing but the case facts.
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.agents.peshkar.fields import unwrap
from vakeel_sahayak.agents.sutradhar.slot_rules import FACTOR_TERMS
from vakeel_sahayak.agents.vakeel.facts import FACTOR_FIELDS
from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
from vakeel_sahayak.pipelines.text_utils import split_sentences

from .prompts import TASK_JUDGE, TASK_LIST, TASK_RAISE

QUOTE_LIMIT = 300
BANK, REFUSALS, STATUTES = "advocacy.objections", "caselaw.reasoning", "law.statutes"
_WORD = re.compile(r"[a-z]{4,}")
_MARKER = re.compile(r"\[(?:F|A):[^\]]+\]")
_FACT_MARKER = re.compile(r"\[F:([^\]]+)\]")
_NO_REPLY = "no supported reply could be drafted"
# A fact that is an objection in itself: the factor it speaks to -> a test on the fact's own sentence.
_FACT_OBJECTION = {
    "gravity_and_punishment": ("sections", lambda t: "maximum punishment" in t.lower() or "not bailable" in t.lower()),
    "antecedents": ("antecedents", lambda t: t.lower().startswith("antecedents:")),
    "witness_tampering": ("trial_stage", lambda t: bool(t.strip())),
}  # fmt: skip
_GENERIC = {
    "gravity_and_punishment": "The offence alleged is serious and carries a heavy punishment, so bail should be refused.",
    "flight_risk": "The accused may abscond and will not be available to face the trial if released.",
    "witness_tampering": "The accused may influence or intimidate witnesses if released on bail.",
    "antecedents": "The accused has a criminal history and may repeat the offence if released.",
    "statutory_bar": "A statutory bar on the grant of bail applies to the offence charged.",
    "parity_with_co_accused": "The role of the accused differs from that of the co-accused who was granted bail, so parity does not apply.",
}  # fmt: skip


def _overlap(a: str, b: str) -> int:
    return len(set(_WORD.findall(a.lower())) & set(_WORD.findall(b.lower())))


def quote_for(text: str, factor: str) -> str | None:
    """The sentence of a paragraph that speaks most to the factor (None when none does), at most QUOTE_LIMIT characters."""
    terms = FACTOR_TERMS.get(factor, ())
    best, best_score = None, 0
    for s in split_sentences(re.sub(r"\s+", " ", unwrap(text))):
        if len(s.split()) < 5:
            continue
        score = sum(1 for t in terms if t in s.lower())
        if score > best_score:
            best, best_score = s, score
    if best is None:
        return None
    best = best.strip().rstrip(".;:")
    return best if len(best) <= QUOTE_LIMIT else best[:QUOTE_LIMIT].rsplit(" ", 1)[0]


def _fact_ground(factor: str, facts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """The first dossier fact the factor reads (its own sentence), as a ground."""
    for name in FACTOR_FIELDS.get(factor, ()):
        if name in facts and facts[name].get("text"):
            return {"fact": name}
    return None


def _paragraph_objection(row: dict[str, Any], factor: str, kind: str, facts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    quote = quote_for(str(row.get("text") or ""), factor)
    if not quote:
        return None
    lead = "In comparable cases the prosecution argued" if kind == BANK else "Courts that refused bail have reasoned"
    text = f"{lead}: “{quote}”. The State may press the same here"
    grounds: list[dict[str, Any]] = [{"store": kind, "doc_id": row["doc_id"], "para": row["para"]}]
    fact = _fact_ground(factor, facts)
    if fact is not None:
        record = str(facts[fact["fact"]]["text"]).rstrip(".")
        text += f", on the record that {record[:1].lower() + record[1:]}"
        grounds.append(fact)
    return {"factor": factor, "objection": text + ".", "grounds": grounds}


def _statute_objection(row: dict[str, Any], factor: str) -> dict[str, Any] | None:
    ref = f"{row.get('code')} {row.get('section')}".strip()
    bits = []
    if row.get("bailable") is False:
        bits.append("is not bailable")
    if row.get("max_punishment"):
        bits.append(f"carries a maximum punishment of {row['max_punishment']}")
    if not bits:
        return None
    return {"factor": factor, "objection": f"Section {ref} {' and '.join(bits)}, and the State will say that bail should be refused for an offence of this gravity.", "grounds": [{"store": STATUTES, "doc_id": ref}]}


def raise_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `abhiyojak.raise_objections`: objections from the facts, paragraphs and statutes given (none when they say nothing).

    For a ground: up to `limit` objections on the ground's factor. For the general call (no ground, `factors` listed): one
    objection per listed factor that the material supports.
    """
    case, corpus = req.case, req.corpus
    limit = int(case.get("limit") or 2)
    facts = {str(f["field"]): f for f in case.get("facts") or [] if isinstance(f, dict) and f.get("field")}
    paths = lambda rows: [r for r in rows or [] if isinstance(r, dict) and r.get("doc_id") and isinstance(r.get("para"), int)]  # noqa: E731
    bank, refusals = paths(corpus.get("objection_bank")), paths(corpus.get("refusals"))
    statutes = [r for r in corpus.get("statutes") or [] if isinstance(r, dict) and r.get("code")]
    ground = case.get("ground") if isinstance(case.get("ground"), dict) else None
    hint = unwrap(str((ground or {}).get("argument") or ""))
    factors = [str(f) for f in case.get("factors") or []] if ground is None else [str(case.get("factor") or "")]
    per_factor = 1 if ground is None else limit

    def rank(rows: list[dict[str, Any]], factor: str) -> list[dict[str, Any]]:
        mine = [r for r in rows if factor in (r.get("factors") or [factor])]
        return sorted(mine, key=lambda r: -_overlap(hint, unwrap(str(r.get("text") or ""))))

    out: list[dict[str, Any]] = []
    for factor in factors:
        bank_o = [o for r in rank(bank, factor) if (o := _paragraph_objection(r, factor, BANK, facts))]
        refusal_o = [o for r in rank(refusals, factor) if (o := _paragraph_objection(r, factor, REFUSALS, facts))]
        statute_o = [o for r in statutes if (o := _statute_objection(r, factor))] if factor in ("gravity_and_punishment", "statutory_bar") else []
        found: list[dict[str, Any]] = []
        if factor == "statutory_bar":
            found += statute_o[:1]
        found += bank_o[:1] + refusal_o[:1]
        found += bank_o[1:2] + refusal_o[1:2] + statute_o[:1]
        if not found and ground is None and factor in _FACT_OBJECTION:  # a general objection the dossier itself carries
            field, test = _FACT_OBJECTION[factor]
            fact = facts.get(field)
            if fact is not None and test(str(fact.get("text") or "")):
                text = str(fact["text"]).rstrip(".")
                found.append({"factor": factor, "objection": f"The State will rely on the record: {text}.", "grounds": [{"fact": field}]})
        for o in found[:per_factor]:
            out.append({"against": "general" if ground is None else str((ground or {}).get("id") or ""), **o})
    return {"objections": out[: limit if ground is not None else len(out)]}


def judge_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `abhiyojak.judge_reply`: how well the reply, as written and cited, meets the objection."""
    case = req.case
    objection = unwrap(str(case.get("objection") or ""))
    reply = case.get("reply") if isinstance(case.get("reply"), dict) else {}
    text = unwrap(str(reply.get("text") or ""))
    check = str(reply.get("check") or "")
    if not text.strip() or _NO_REPLY in text.lower() or not _MARKER.search(text):
        return {"verdict": "UNANSWERED", "reason": "The reply cites no fact or authority that meets the objection." if text.strip() and _NO_REPLY not in text.lower() else "There is no reply that meets the objection."}
    asked = {str(f) for f in case.get("objection_facts") or []}
    answered = {m.group(1) for m in _FACT_MARKER.finditer(text)}
    prose = _MARKER.sub("", text)
    overlap = _overlap(objection, prose)
    supported = check in ("SUPPORTED", "REPAIRED")
    if supported and (asked & answered or overlap >= 3):
        return {"verdict": "ANSWERED", "reason": "The reply meets the objection with checked facts or authority" + (" on the same facts." if asked & answered else ".")}
    return {"verdict": "PARTLY", "reason": "The reply is cited but" + (" not fully checked" if not supported else " meets only part of the objection") + "; counsel should strengthen it."}


def list_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `abhiyojak.list_objections`: the generic points a prosecutor makes, from the case facts alone."""
    facts = {str(f["field"]) for f in req.case.get("facts") or [] if isinstance(f, dict) and f.get("field")}
    keys = ["gravity_and_punishment", "flight_risk", "witness_tampering", "antecedents", "statutory_bar"]
    if "co_accused_bail" in facts:
        keys.append("parity_with_co_accused")
    return {"objections": [{"factor": k, "objection": _GENERIC[k]} for k in keys]}


def register() -> None:
    """Register the handlers with the offline client (the agent module does this at import)."""
    register_offline_handler(TASK_RAISE, raise_offline)
    register_offline_handler(TASK_JUDGE, judge_offline)
    register_offline_handler(TASK_LIST, list_offline)


register()
