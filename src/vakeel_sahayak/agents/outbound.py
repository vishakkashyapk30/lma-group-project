"""Clean public text before it enters an outbound prompt (corpus rows, citations), without touching the privacy boundary.

Public corpus rows (objection-bank paragraphs, orders, statutes) can hold an email, phone or ID number (a bank account number is
twelve digits); the boundary refuses such text, so the agents mask it first: same tokens as `privacy.pseudonymise` ([EMAIL],
[PHONE], [ID-NUMBER]). Identifier fields (doc ids, chunk ids) are left alone so the model can still point to them. A citation
that carries party names ('State of X v. Y, (2022) 10 SCC 51') is cut to its reporter or case-number form before it is placed
among the case data, where the name guard would refuse it; the link to the source (doc id and paragraph) is kept.
"""

from __future__ import annotations

import re
from typing import Any

from vakeel_sahayak.privacy.pseudonymise import _PII

_ID_FIELDS = re.compile(r"^(?:doc_ids?|chunk_ids?|para_ids?|ground_ids?|objection_ids?|id|ids|store|source|url|link|href|uri)$")
_PARTIES = re.compile(r"\s(?:v\.?|vs\.?|versus)\s", re.IGNORECASE)
_REPORTER = re.compile(
    r"(?:\(\d{4}\)\s*\d+\s*[A-Z][A-Za-z.]*\s*\d+|\b\d{4}\s*(?:SCC\s*OnLine\s*[A-Za-z]+\s*\d+|SCC\s*\d+|\(\d+\)\s*SCC\s*\d+)|\bAIR\s*\d{4}\s*[A-Za-z]+\s*\d+"
    r"|\b(?:Crl\.?\s*(?:M\.?C|A|Rev|M\.?P|Appl)\.?|SLP\s*\(Crl\.?\)|B\.?A\.?|Bail\s*Appl\.?|WP\s*\(Crl\.?\))\s*(?:No\.?)?\s*\d+(?:\s*/\s*\d{2,4})?)"
)


def mask_text(text: str) -> str:
    """The text with emails, phone numbers and ID or account numbers replaced by tokens."""
    for pattern, token in _PII:
        text = pattern.sub(token, text)
    return text


def mask_public(value: Any, key: str = "") -> Any:
    """`value` (nested dicts, lists, strings) with every string masked, except under identifier keys."""
    if isinstance(value, str):
        return value if _ID_FIELDS.match(key) else mask_text(value)
    if isinstance(value, dict):
        return {k: mask_public(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_public(v, key) for v in value]
    return value


def normalise_citation(citation: Any, doc_id: Any = None, para: Any = None) -> Any:
    """A citation without party names: the reporter or case-number part when there is one, else the document id; unchanged when it names no parties."""
    if not isinstance(citation, str) or not _PARTIES.search(citation):
        return citation
    m = _REPORTER.search(citation)
    tail = f", para {para}" if isinstance(para, int) and not re.search(r"para\s*\d+\s*$", citation[m.start():] if m else "") else ""
    if m:
        rest = citation[m.start():]
        return rest if re.search(r"para\s*\d+\s*$", rest) else rest + tail
    return f"Judgment {doc_id}{tail}" if doc_id else "Judgment (parties omitted)"
