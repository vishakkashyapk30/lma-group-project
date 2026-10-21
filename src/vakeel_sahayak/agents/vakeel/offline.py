"""Offline handlers for Vakeel's model tasks (`vakeel.draft_ground`, `vakeel.reply_objection`, `vakeel.reword_claim`, ...): rules, no language model.

Offline drafting is built only from the evidence the request carries (never invented): a ground is the dossier facts
as sentences (each ending `[F:field]`), the opening reason Sutradhar gave for the factor, and, for each retrieved
paragraph, the one sentence of the paragraph that speaks to the factor, reported in indirect speech (each ending
`[A:doc#para]`). Nothing is cited that the request does not list, and no case name or citation is ever written.

The first draft is deliberately the same *kind* of text a model writes (reasons and glosses, not pure copies), so the
checker can reject it and the repair step (`reword_claim`) rewrites the failing sentence to exactly what its source says:
the fact's own sentence, or the paragraph's own words. Instructions inside the evidence are never followed; the
handlers only read data.
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.agents.peshkar.fields import unwrap
from vakeel_sahayak.agents.sutradhar.slot_rules import FACTOR_TERMS
from vakeel_sahayak.agents.vakeel.prompts import (
    TASK_DEBATE,
    TASK_DRAFT,
    TASK_REPLY,
    TASK_REWORD,
    TASK_RIGHTS,
    TASK_SELF_CRITIQUE,
    TASK_SELF_REVISE,
    TASK_TRANSFER,
)
from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
from vakeel_sahayak.pipelines.text_utils import split_sentences

MAX_FACT_SENTENCES = 3
MAX_AUTHORITY_SENTENCES = 2
QUOTE_LIMIT = 320
_DOSSIER_REF = re.compile(r"\((?:dossier|RightsReport)[^)]*\)", re.IGNORECASE)
_DOSSIER_FIELDS = re.compile(r"\(dossier:\s*([a-z_,\s]+)\)", re.IGNORECASE)
_WORD = re.compile(r"[a-z]{4,}")
_PREDICT = re.compile(r"\b(?:likely|unlikely|certain(?:ly)?|bound)\s+to\s+(?:be\s+)?(?:granted|get\s+bail|succeed)\b", re.IGNORECASE)


def _quote_of(text: str, factor: str) -> str | None:
    """The sentence of a paragraph that speaks to the factor (most factor words), at most QUOTE_LIMIT characters."""
    terms = FACTOR_TERMS.get(factor, ())
    best, best_score = None, -1
    for s in split_sentences(re.sub(r"\s+", " ", unwrap(text))):
        if len(s.split()) < 5:
            continue
        score = sum(1 for t in terms if t in s.lower())
        if score > best_score:
            best, best_score = s, score
    if best is None or (terms and best_score <= 0):  # a paragraph that never speaks to the factor is not cited for it
        return None
    best = best.strip().rstrip(".;:")
    return best if len(best) <= QUOTE_LIMIT else best[:QUOTE_LIMIT].rsplit(" ", 1)[0]


def authority_sentence(auth: dict[str, Any], factor: str, lead: str = "The court held") -> str | None:
    """'The court held: “...” [A:doc#para].' from the paragraph's own words (None when the paragraph has no usable sentence)."""
    quote = _quote_of(str(auth.get("text") or ""), factor)
    if not quote:
        return None
    return f"{lead}: “{quote}” [A:{auth['doc_id']}#{auth['para']}]."


def fact_sentence(fact: dict[str, Any]) -> str:
    """The fact's own sentence with its marker."""
    return f"{str(fact['text']).rstrip('.')} [F:{fact['field']}]."


def fact_sentences(fact: dict[str, Any], factor: str = "", hint: str = "", limit: int = MAX_FACT_SENTENCES) -> list[str]:
    """A fact's sentences with markers: one for a dossier field; for the raw facts text (A1) the sentences that speak to the factor
    (or share words with `hint`), each cited on its own."""
    if fact.get("field") != "facts_text":
        return [fact_sentence(fact)]
    terms = FACTOR_TERMS.get(factor, ())
    parts = split_sentences(re.sub(r"\s+", " ", str(fact.get("text") or "")))
    ranked = sorted(parts, key=lambda p: -(sum(1 for t in terms if t in p.lower()) + _overlap(hint, p)))
    chosen = [p for p in ranked if (any(t in p.lower() for t in terms) or _overlap(hint, p) > 0)][:limit] or parts[:2]
    return [f"{p.rstrip('.')} [F:facts_text]." for p in chosen]


def _reason_sentence(reason: str, facts: dict[str, dict[str, Any]]) -> tuple[str | None, set[str]]:
    """Sutradhar's reason for the factor as an opening sentence, marked with the dossier fields it names."""
    m = _DOSSIER_FIELDS.search(reason or "")
    fields = [f.strip() for f in m.group(1).split(",")] if m else []
    fields = [f for f in fields if f in facts]
    body = _DOSSIER_REF.sub("", reason or "").strip(" .:;")
    if not fields or not body:
        return None, set()
    body = body[0].upper() + body[1:]
    return f"{body} " + " ".join(f"[F:{f}]" for f in fields) + ".", set(fields)


def _ground(case: dict[str, Any], text: str) -> dict[str, Any]:
    """The Ground-shaped answer the model returns: ids and the argument, with the authorities its markers name."""
    seen: list[dict[str, Any]] = []
    for doc, para in re.findall(r"\[A:([^\]#]+)#(\d+)\]", text):
        row = {"doc_id": doc.strip(), "para": int(para)}
        if row not in seen:
            seen.append(row)
    return {"id": str(case.get("id") or "G1"), "factor": case.get("factor"), "stance": case.get("stance") or "favourable", "argument": text, "authorities": seen}


def _with_reasoning(req: OfflineRequest, answer: dict[str, Any], key: str) -> dict[str, Any]:
    """S15: when the requested schema has a `reasoning` field, add a deterministic template note built from what the answer cites (never read back as evidence)."""
    props = (req.schema or {}).get("properties") or {}
    if "reasoning" not in props:
        return answer
    text = str(answer.get(key) or "")
    fields = sorted(set(re.findall(r"\[F:([^\]]+)\]", text)))
    auths = sorted(set(re.findall(r"\[A:([^\]]+)\]", text)))
    note = f"Template reasoning (offline, no language model): the point rests on {len(fields)} dossier fact(s) ({', '.join(fields) or 'none'}) and {len(auths)} paragraph(s) ({', '.join(auths) or 'none'})."
    return {"reasoning": note, **answer}


def draft_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.draft_ground`: the argument as marked sentences, from the facts and paragraphs given."""
    case, corpus = req.case, req.corpus
    factor, stance = str(case.get("factor") or ""), str(case.get("stance") or "favourable")
    label = str(case.get("label") or factor.replace("_", " "))
    facts = {str(f["field"]): f for f in case.get("facts") or [] if isinstance(f, dict) and f.get("field")}
    auths = [a for a in corpus.get("authorities") or [] if isinstance(a, dict) and a.get("doc_id") and isinstance(a.get("para"), int)]
    sentences: list[str] = []
    opening, used = _reason_sentence(str(case.get("reason") or ""), facts)
    if opening:
        sentences.append(opening)
    for name, fact in list(facts.items()):
        if len([s for s in sentences if "[F:" in s]) >= MAX_FACT_SENTENCES:
            break
        if name not in used:
            sentences += fact_sentences(fact, factor)
    lead = "The court held" if stance != "adverse" else f"On {label}, the court held"
    for auth in auths[:MAX_AUTHORITY_SENTENCES]:
        if s := authority_sentence(auth, factor, lead):
            sentences.append(s)
    text = " ".join(_PREDICT.sub("", s) for s in sentences)
    return _with_reasoning(req, _ground(case, text), "argument")


def debate_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.debate_revise` (S11b): keeps its own draft. A rule has nothing to learn from a peer's text and never follows it."""
    case = req.case
    return _with_reasoning(req, _ground(case, unwrap(str(case.get("own") or ""))), "argument")


def _overlap(a: str, b: str) -> int:
    return len(set(_WORD.findall(a.lower())) & set(_WORD.findall(b.lower())))


def reply_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.reply_objection`: the facts and the paragraph's words that bear on the objection, else no reply."""
    case, corpus = req.case, req.corpus
    objection, factor = unwrap(str(case.get("objection") or "")), str(case.get("factor") or "")
    facts = [f for f in case.get("facts") or [] if isinstance(f, dict) and f.get("field")]
    auths = [a for a in corpus.get("authorities") or [] if isinstance(a, dict) and a.get("doc_id") and isinstance(a.get("para"), int)]
    ranked = sorted(facts, key=lambda f: -_overlap(objection, str(f["text"])))
    sentences = [x for f in ranked[:2] for x in fact_sentences(f, factor, objection, 2)][:3]
    for auth in sorted(auths, key=lambda a: -_overlap(objection, unwrap(str(a.get("text") or ""))))[:1]:
        if s := authority_sentence(auth, factor):
            sentences.append(s)
    text = " ".join(sentences)
    return _with_reasoning(req, {"text": text, "authorities": _ground(case, text)["authorities"]}, "text")


def reword_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.reword_claim`: each reference of the failing sentence rewritten to what its source says."""
    case, corpus = req.case, req.corpus
    factor = str(case.get("factor") or "")
    facts = {str(f["field"]): f for f in case.get("facts") or [] if isinstance(f, dict) and f.get("field")}
    auths = {(str(a["doc_id"]), int(a["para"])): a for a in corpus.get("authorities") or [] if isinstance(a, dict) and a.get("doc_id") and isinstance(a.get("para"), int)}
    sentence = str(case.get("sentence") or "")
    out: list[str] = []
    used_auth: set[tuple[str, int]] = set()
    spare = list(auths)
    refs = [str(r) for r in case.get("refs") or []]
    if not refs:  # an uncited sentence: the source that shares the most words with it
        pool = [("F", k, fact["text"]) for k, fact in facts.items()] + [("A", k, unwrap(str(a.get("text") or ""))) for k, a in auths.items()]
        pool = [p for p in pool if _overlap(sentence, str(p[2])) > 0]
        pool.sort(key=lambda p: -_overlap(sentence, str(p[2])))
        if pool:
            kind, key, _ = pool[0]
            refs = [f"[F:{key}]"] if kind == "F" else [f"[A:{key[0]}#{key[1]}]"]
    for ref in refs:
        m = re.match(r"\[(F|A):([^\]]+)\]", ref)
        if not m:
            continue
        if m.group(1) == "F":
            if m.group(2) in facts:
                out += fact_sentences(facts[m.group(2)], factor, sentence, 1)
            continue
        doc, _, para = m.group(2).partition("#")
        key = (doc, int(para) if para.isdigit() else 0)
        if key not in auths:  # unlisted or overruled: a listed authority instead
            alt = next((k for k in spare if k not in used_auth and k != key), None)
            if alt is None:
                continue
            key = alt
        if key in used_auth:
            continue
        used_auth.add(key)
        if s := authority_sentence(auths[key], factor):
            out.append(s)
    return _with_reasoning(req, _ground(case, " ".join(out) if out else sentence), "argument")


_ANY_MARKER = re.compile(r"\[\s*(?:F|A)\s*:")


def self_critique_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.self_critique` (S8): a stand-in for a model that re-reads its own draft with no verifier.

    A rule cannot reproduce a model's judgement. What it reproduces is the defining limit of intrinsic self-correction (Huang et al.,
    ICLR 2024): the reader sees only its own text, so it accepts what it wrote. It flags only what is visible on the page without
    any source: a sentence that ends with no [F:...] / [A:...] marker and a sentence that repeats an earlier one. It never compares a
    sentence with the fact or paragraph it cites (that comparison is the verifier this arm leaves out).
    """
    seen: set[str] = set()
    reviews: list[dict[str, Any]] = []
    for row in req.case.get("claim") or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "")
        key = " ".join(re.sub(r"\[[^\]]*\]", "", text).lower().split())
        if not _ANY_MARKER.search(text):
            reviews.append({"sentence": row.get("sentence"), "ok": False, "reason": "the sentence cites no fact or paragraph"})
        elif key in seen:
            reviews.append({"sentence": row.get("sentence"), "ok": False, "reason": "the sentence repeats an earlier one"})
        else:
            reviews.append({"sentence": row.get("sentence"), "ok": True, "reason": ""})
        seen.add(key)
    return {"reviews": reviews}


def transfer_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.judge_transfer` (A3): what a model with no concordance tool can tell from the section numbers alone."""
    case = req.case
    case_refs = [str(r) for r in case.get("case_sections") or []]
    para = [str(r) for r in case.get("paragraph_sections") or []]
    num = lambda r: re.sub(r"^[A-Za-z. ]+", "", r).strip()  # noqa: E731
    if set(case_refs) & set(para):
        return {"flag": "SAME_TEXT", "note": "the same section is cited"}
    if {num(r) for r in case_refs} & {num(r) for r in para}:
        return {"flag": "SAME_TEXT", "note": "the section numbers match"}
    return {"flag": None, "note": "no common section"}


def rights_offline(req: OfflineRequest) -> dict[str, Any]:
    """Offline handler of `vakeel.rights_summary` (A3): the dates and counts as given; no entitlement is computed."""
    case = req.case
    days, arrest = case.get("custody_days"), case.get("arrest_date")
    parts = []
    if arrest:
        parts.append(f"arrested on {arrest}")
    if days is not None:
        parts.append(f"{days} days in custody")
    seen = ", ".join(parts) or "no custody dates stated"
    return {"rights": f"Per the dossier: {seen}; entitlements under BNSS s.187(3) and s.479 were not computed (rule tools off): counsel to check."}


def register() -> None:
    """Register the handlers with the offline client (the agent module does this at import)."""
    register_offline_handler(TASK_DRAFT, draft_offline)
    register_offline_handler(TASK_REPLY, reply_offline)
    register_offline_handler(TASK_REWORD, reword_offline)
    register_offline_handler(TASK_DEBATE, debate_offline)
    register_offline_handler(TASK_SELF_CRITIQUE, self_critique_offline)
    register_offline_handler(TASK_SELF_REVISE, reword_offline)  # the rewrite itself is the same rule: it reads only the sources it was handed
    register_offline_handler(TASK_TRANSFER, transfer_offline)
    register_offline_handler(TASK_RIGHTS, rights_offline)


register()
