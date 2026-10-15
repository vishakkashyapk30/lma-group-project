"""Tools in drafting.claims (plan §8.1). Each function has a matching <NAME>_SPEC.

`check_claim` checks one drafted claim (a ground's argument, or a reply to an objection):

- **references**: `[F:field]` dossier facts and `[A:doc#para]` authorities, written inline after the sentence they
  support and/or passed in `refs`. Every sentence must carry a reference (plan §8.1 step 1); a sentence without one
  uses `refs` when given, else it is uncited and the claim fails;
- **fact support**: NLI of the sentence against the cited fields' source quotes (the English translation for Hindi
  quotes, plan §4.5) and values. A field that is UNSUPPORTED supports nothing;
- **authority support**: NLI against the cited paragraph, fetched with `get_paragraph` (court reasoning only);
- **transfer flag**: the cited paragraph's sections against the case's sections through `transfer_check`
  (SAME_TEXT / CHANGED / NEW, plan §5.4); CHANGED does not fail a claim, it needs a qualification;
- **good-law flag**: `good_law_check`; OVERRULED fails the claim, DISTINGUISHED is reported but does not;
- **no citation that was not retrieved**: an authority must appear in a retrieval result in the case's event log
  (`search_reasoning`, `get_paragraph`, and doc-level `similar_orders` / `citations`), or in `retrieved`. With no case
  and no `retrieved` list the check falls back to "is a citable reasoning paragraph of caselaw.reasoning".

The case comes from `case_id`, else the tool runtime's current case. Thresholds are configs/thresholds.yaml
`nli.fact_support_min` and `nli.authority_support_min` (null until tuned on dev: the NLI client's default).
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.schemas.enums import AgentName, EventKind, FieldStatus, GoodLawStatus, StoreName, TransferFlag
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.types import ClaimCheckResult

_INLINE = re.compile(r"\[\s*(F|A)\s*:\s*([^\]]+?)\s*\]")
_REF = re.compile(r"^\[?\s*(F|A)\s*:\s*([^\]]+?)\s*\]?$")
_AUTH = re.compile(r"^(.+?)#(\d+)$")
_MOVE_BACK = re.compile(r"([.!?])\s*((?:\[\s*(?:F|A)\s*:[^\]]+\]\s*)+)")
RETRIEVAL_TOOLS = ("search_reasoning", "get_paragraph", "similar_orders", "citations")
_TRANSFER_RANK = {TransferFlag.SAME_TEXT: 0, TransferFlag.CHANGED: 1, TransferFlag.NEW: 2}
_GOOD_LAW_RANK = {GoodLawStatus.OK: 0, GoodLawStatus.UNKNOWN: 1, GoodLawStatus.DISTINGUISHED: 2, GoodLawStatus.OVERRULED: 3}


def _invalid(message: str, tool: str = "check_claim") -> ToolError:
    return ToolError(tool=tool, kind="invalid_input", message=message, retryable=True)


def parse_ref(ref: str) -> tuple[str, str, int | None]:
    """('F', field, None) or ('A', doc_id, para) from '[F:field]', 'F:field', '[A:doc#14]' or 'A:doc#14'.

    Raises:
        ValueError: for anything else.
    """
    m = _REF.match(ref.strip())
    if not m:
        raise ValueError(f"bad reference {ref!r}: use [F:field] or [A:doc_id#para]")
    kind, body = m.group(1), m.group(2).strip()
    if kind == "F":
        if not re.fullmatch(r"[a-z_]+", body):
            raise ValueError(f"bad fact reference {ref!r}: the field is a dossier field name such as arrest_date")
        return "F", body, None
    a = _AUTH.match(body)
    if not a:
        raise ValueError(f"bad authority reference {ref!r}: use [A:doc_id#para]")
    return "A", a.group(1).strip(), int(a.group(2))


def _units(claim: str, refs: list[str]) -> list[tuple[str, list[tuple[str, str, int | None]]]]:
    """(sentence without markers, its references) for each sentence of the claim."""
    from vakeel_sahayak.pipelines.text_utils import split_sentences

    text = _MOVE_BACK.sub(lambda m: " " + m.group(2).strip() + m.group(1), claim.strip())
    given = [parse_ref(r) for r in refs]
    if not _INLINE.search(text):
        clean = re.sub(r"\s+", " ", text).strip()
        return [(clean, given)] if clean else []
    out = []
    for sentence in split_sentences(text) or [text]:
        found = [parse_ref(f"[{k}:{b}]") for k, b in _INLINE.findall(sentence)]
        clean = re.sub(r"\s+", " ", _INLINE.sub("", sentence)).strip(" ,;")
        if not re.search(r"\w", clean):
            if out and found:  # a marker on its own: it belongs to the previous sentence
                out[-1][1].extend(found)
            continue
        out.append((clean, found or list(given)))
    return out


def _words(name: str) -> str:
    return name.replace("_", " ")


def _render_value(value: Any) -> str:
    """A dossier value as plain words for the NLI premise (booleans as the key or 'not' + key)."""
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            if v is None:
                continue
            if v is True:
                parts.append(_words(k))
            elif v is False:
                parts.append("not " + _words(k))
            else:
                parts.append(f"{_words(k)} {_render_value(v)}")
        return " ".join(parts)
    if isinstance(value, list):
        return "; ".join(_render_value(v) for v in value)
    return str(value)


def fact_premise(field: str, tracked: Any) -> str | None:
    """The text a dossier field supports a claim with: its quote (English for Hindi) and its value; None when UNSUPPORTED."""
    if tracked is None or tracked.status == FieldStatus.UNSUPPORTED or tracked.value is None:
        return None
    value = tracked.value
    dumped = value.model_dump(mode="json") if hasattr(value, "model_dump") else [
        v.model_dump(mode="json") if hasattr(v, "model_dump") else v for v in value
    ] if isinstance(value, list) else value  # fmt: skip
    parts = [f"{_words(field)}: {_render_value(dumped)}"]
    src = tracked.source
    if src is not None and (src.quote_en or src.quote):
        parts.append(src.quote_en or src.quote or "")
    return "\n".join(parts)


def retrieved_authorities(log: Any, case_id: str) -> tuple[set[tuple[str, int]], set[str]]:
    """(doc, para) pairs and doc ids that retrieval tools returned in this case's event log."""
    pairs: set[tuple[str, int]] = set()
    docs: set[str] = set()

    def walk(v: Any, tool: str) -> None:
        if isinstance(v, dict):
            d, p = v.get("doc_id"), v.get("para")
            if isinstance(d, str) and isinstance(p, int):
                pairs.add((d, p))
            elif isinstance(d, str) and tool in ("similar_orders", "citations"):
                docs.add(d)
            for k, x in v.items():
                if k == "sc_root" and isinstance(x, str):
                    docs.add(x)
                walk(x, tool)
        elif isinstance(v, list):
            for x in v:
                walk(x, tool)

    for ev in log.read(case_id, kind=EventKind.TOOL_RESULT):
        if ev.tool in RETRIEVAL_TOOLS and "result" in ev.outputs:
            result = ev.outputs["result"]
            walk(result, ev.tool or "")
            if ev.tool == "citations" and isinstance(result, dict):
                docs.update(k for k in result if isinstance(k, str))
    return pairs, docs


def _case_sections(dossier: Any) -> list[tuple[str, str | None]]:
    """(new-code ref, old-code equivalent) of the case's charged sections."""
    tracked = dossier.fields.sections
    out = []
    for sv in tracked.value or []:
        out.append((f"{sv.code} {sv.section}", sv.equivalent))
    return out


def _transfer_for(paragraph: Any, case_refs: list[tuple[str, str | None]]) -> TransferFlag | None:
    """The transfer flag of a precedent for this case (None when it shares no section with the case)."""
    from vakeel_sahayak.tools.law.concordance import transfer_check

    sections = set(paragraph.sections or [])
    flags: list[TransferFlag] = []
    for new_ref, old_ref in case_refs:
        if new_ref in sections:
            flags.append(TransferFlag.SAME_TEXT)
        elif old_ref and old_ref in sections:
            res = transfer_check(old_ref, new_ref)
            if not isinstance(res, ToolError):
                flags.append(res.flag)
    return max(flags, key=_TRANSFER_RANK.__getitem__) if flags else None


def check_claim(
    claim: str,
    refs: list[str] | None = None,
    case_id: str | None = None,
    retrieved: list[str] | None = None,
) -> ClaimCheckResult | ToolError:
    """Fact support (NLI vs dossier quote), authority support (NLI vs cited paragraph), transfer flag, good-law flag, and no citation that was not retrieved. (plan §8.1)

    Args:
        claim: the claim text, with inline [F:field] / [A:doc#para] markers after the sentences they support
        refs: [F:field] and [A:doc#para] references for sentences without inline markers
        case_id: the case whose dossier and event log are read (default: the runtime's current case)
        retrieved: extra 'doc#para' (or doc) ids that count as retrieved (for runs outside an event-logged case)

    Returns:
        ClaimCheckResult (`supported` only when every sentence is supported, no authority is OVERRULED and every
        authority was retrieved), or a ToolError for a malformed claim or reference.
    """
    tool = "check_claim"
    if not isinstance(claim, str) or not claim.strip():
        return _invalid("claim must not be empty")
    try:
        units = _units(claim, list(refs or []))
    except ValueError as exc:
        return _invalid(str(exc))
    if not units:
        return _invalid("claim has no text")
    from vakeel_sahayak.models.factory import get_nli
    from vakeel_sahayak.models.nli import nli_threshold
    from vakeel_sahayak.schemas.dossier import DossierFields
    from vakeel_sahayak.tools.runtime import get_runtime

    runtime = get_runtime()
    cid = case_id or runtime.current_case_id
    need_facts = any(k == "F" for _, rs in units for k, _, _ in rs)
    fields_known = set(DossierFields.model_fields)
    bad = sorted({n for _, rs in units for k, n, _ in rs if k == "F" and n not in fields_known})
    if bad:
        return _invalid(f"unknown dossier field(s) {bad}: use one of {sorted(fields_known)}")
    if need_facts and not cid:
        return _invalid("check_claim needs the case (case_id) to read the dossier for [F:...] references")
    dossier = None
    log = None
    if cid:
        from vakeel_sahayak.record.case_state import CaseState
        from vakeel_sahayak.schemas.ids import check_case_id

        try:
            check_case_id(cid)
        except ValueError as exc:
            return _invalid(str(exc))
        log = runtime.event_log(cid)
        dossier = CaseState(cid, log).dossier()

    from vakeel_sahayak.tools.caselaw.citations import good_law_check
    from vakeel_sahayak.tools.caselaw.reasoning import get_paragraph

    nli = get_nli()
    fact_thr = nli_threshold("fact_support", nli, runtime.config)
    auth_thr = nli_threshold("authority_support", nli, runtime.config)
    paragraphs: dict[tuple[str, int], Any] = {}
    unretrieved: list[str] = []
    for _, rs in units:
        for k, doc, para in rs:
            if k == "A" and (doc, para) not in paragraphs:
                row = get_paragraph(doc, int(para or 0))
                paragraphs[(doc, int(para or 0))] = None if isinstance(row, ToolError) else row
    explicit = {r.strip() for r in retrieved or []}
    pairs, docs = retrieved_authorities(log, cid) if (log is not None and cid) else (set(), set())
    use_store_fallback = log is None and not explicit
    for (doc, para), row in paragraphs.items():
        ref = f"{doc}#{para}"
        ok = ref in explicit or doc in explicit or (doc, para) in pairs or (doc in docs and row is not None)
        if use_store_fallback:
            ok = row is not None
        if not ok or row is None:
            unretrieved.append(ref)

    fact_scores: list[float] = []
    auth_scores: list[float] = []
    supported = True
    for sentence, rs in units:
        if not rs:
            supported = False  # an uncited sentence (plan §8.1: every sentence cites)
            continue
        premises: list[str] = []
        missing_fact = False
        for k, name, para in rs:
            if k == "F":
                text = fact_premise(name, getattr(dossier.fields, name) if dossier is not None else None)
                if text is None:
                    missing_fact = True
                else:
                    premises.append(text)
            else:
                row = paragraphs.get((name, int(para or 0)))
                if row is not None:
                    premises.append(row.text)
        score = float(nli.entails("\n".join(premises), sentence)) if premises else 0.0
        if any(k == "F" for k, _, _ in rs):
            fact_scores.append(0.0 if missing_fact else score)
            supported &= (not missing_fact) and score >= fact_thr
        if any(k == "A" for k, _, _ in rs):
            auth_scores.append(score)
            supported &= score >= auth_thr

    transfer: TransferFlag | None = None
    good_law: GoodLawStatus | None = None
    case_refs = _case_sections(dossier) if dossier is not None else []
    for (doc, _para), row in paragraphs.items():
        if row is None:
            continue
        flag = _transfer_for(row, case_refs) if case_refs else None
        if flag is not None and (transfer is None or _TRANSFER_RANK[flag] > _TRANSFER_RANK[transfer]):
            transfer = flag
        gl = good_law_check(doc, dossier.as_of if dossier is not None else None)
        status = GoodLawStatus.UNKNOWN if isinstance(gl, ToolError) else gl.status
        if good_law is None or _GOOD_LAW_RANK[status] > _GOOD_LAW_RANK[good_law]:
            good_law = status
    if good_law == GoodLawStatus.OVERRULED or unretrieved:
        supported = False
    del tool
    return ClaimCheckResult(
        supported=bool(supported),
        fact_support=round(min(fact_scores), 4) if fact_scores else None,
        authority_support=round(min(auth_scores), 4) if auth_scores else None,
        transfer=transfer,
        good_law=good_law,
        unretrieved_citations=sorted(set(unretrieved)),
    )


def _fmt_date(iso: str | None) -> str | None:
    if not iso or len(iso) < 10:
        return iso
    y, m, d = iso[:10].split("-")
    return f"{d}.{m}.{y}"


def render_citation(doc_id: str, para: int | None = None) -> str | ToolError:
    """Render citation text from corpus metadata; the model writes only IDs. (plan §8.1)

    Args:
        doc_id: the judgment's id (as retrieved)
        para: the cited paragraph; it must be a reasoning paragraph of caselaw.reasoning

    Returns:
        'Title, (2022) 10 SCC 51, para 14', or 'Order of the Delhi High Court dated 03.06.2022 (DLHC-2022-1187), para 14'
        when the corpus has no title; a ToolError (not_found) for an unknown doc id or paragraph, never invented text.
    """
    tool = "render_citation"
    if not isinstance(doc_id, str) or not doc_id.strip():
        return _invalid("doc_id must not be empty", tool)
    if para is not None and (not isinstance(para, int) or isinstance(para, bool) or para < 1):
        return _invalid("para must be an integer of at least 1", tool)
    from vakeel_sahayak.tools.caselaw.reasoning import get_paragraph
    from vakeel_sahayak.tools.drafting.citation_meta import lookup

    doc_id = doc_id.strip()
    if para is not None:
        row = get_paragraph(doc_id, para)
        if isinstance(row, ToolError):
            return ToolError(tool=tool, kind=row.kind if row.kind != "invalid_input" else "not_found",
                             message=f"cannot cite {doc_id}#{para}: {row.message}", retryable=False)  # fmt: skip
    meta = lookup(doc_id, para)
    if meta is None:
        return ToolError(
            tool=tool, kind="not_found", retryable=False,
            message=f"unknown doc_id {doc_id!r}: citations are rendered from corpus metadata only, never invented",
        )  # fmt: skip
    date = _fmt_date(meta.date)
    if meta.title:
        text = f"{meta.title}, {meta.citation}" if meta.citation else f"{meta.title} ({', '.join(x for x in (meta.court, date) if x)})" if (meta.court or date) else meta.title
    elif meta.citation:
        text = f"{meta.citation} ({doc_id})"
    else:
        court = f"the {meta.court}" if meta.court and not meta.court.lower().startswith("the ") else meta.court
        text = f"Order of {court} dated {date} ({doc_id})" if court and date else (
            f"Order of {court} ({doc_id})" if court else f"Order dated {date} ({doc_id})" if date else f"Judgment {doc_id}"
        )  # fmt: skip
    return f"{text}, para {para}" if para is not None else text


CHECK_CLAIM_SPEC = ToolSpec(
    name="check_claim",
    description="Fact support (NLI vs dossier quote), authority support (NLI vs cited paragraph), transfer flag, good-law flag, and no citation that was not retrieved.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.1",
)

RENDER_CITATION_SPEC = ToolSpec(
    name="render_citation",
    description="Render citation text from corpus metadata; the model writes only IDs.",
    agents=[AgentName.VAKEEL],
    stores=[],
    plan_ref="§8.1",
)

_ = StoreName  # the claim tools read stores through other tools; they are not store calls themselves
