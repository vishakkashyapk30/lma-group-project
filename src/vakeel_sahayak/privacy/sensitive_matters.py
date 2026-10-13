"""Decline sexual-offence, POCSO and juvenile matters at intake (plan §16)."""

from __future__ import annotations

import re

from vakeel_sahayak.pipelines.concordance.refs import parse_ref

# BNS ss.63-79: rape and related offences, identity disclosure (s.72), outraging modesty, sexual harassment, voyeurism,
# stalking. Wider than strictly sexual on purpose: declining is the safe error for victim identity (BNS s.72).
_BNS_SEXUAL = {str(n) for n in range(63, 80)}
# IPC equivalents: 354 series, 375-376E, 377, 509, 228A.
_IPC_SEXUAL = {
    "354", "354A", "354B", "354C", "354D", "375", "376", "376A", "376AB", "376B", "376C", "376D", "376DA", "376DB",
    "376E", "377", "509", "228A",
}  # fmt: skip
_JUVENILE_DOC = re.compile(
    r"(?i)juvenile|\bjjb\b|child welfare|\bcwc\b|social investigation|\bpocso\b|special court \(pocso\)"
)
_JJ_ACT = re.compile(r"(?i)\bjj act\b|juvenile justice")
_POCSO = re.compile(r"(?i)\bpocso\b|protection of children from sexual offences")


def is_declined_matter(sections: list[str], doc_types: list[str]) -> tuple[bool, str | None]:
    """Check sections and document types (BNS s.72, POCSO s.23, JJ Act s.74).

    Args:
        sections: charged sections as written, for example 'BNS 64(1)', '376 IPC', 'POCSO s.4'
        doc_types: document type labels, for example 'JJB_ORDER'

    Returns:
        (declined, reason). The reason names the category, never any person.
    """
    for raw in sections:
        if _POCSO.search(raw):
            return True, "POCSO matter: declined at intake to protect the child's identity (POCSO s.23)."
        if _JJ_ACT.search(raw):
            return True, "Juvenile matter: declined at intake to protect the child's identity (JJ Act s.74)."
        code, section = parse_ref(raw)
        main = (section or "").split("(")[0]
        if (code == "BNS" and main in _BNS_SEXUAL) or (code in ("IPC", None) and main in _IPC_SEXUAL):
            return (
                True,
                f"Sexual-offence matter ({code or 'IPC'} s.{main}): declined at intake to protect the victim's identity (BNS s.72).",
            )
    for doc in doc_types:
        if _POCSO.search(doc):
            return True, "POCSO document in the file: declined at intake (POCSO s.23)."
        if _JUVENILE_DOC.search(doc.replace("_", " ")):
            return True, "Juvenile-matter document in the file: declined at intake (JJ Act s.74)."
    return False, None
