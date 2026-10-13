"""Keyword-rule labeler tagging paragraphs with the 12 bail factors (plan §5.2). Rules only; gold labels additionally need labeler agreement (pipelines/gold).

Each factor of Appendix A has a few case-insensitive regexes. A paragraph gets a factor when any regex matches. The
rules favour precision on court text; they are deliberately transparent so the label-sensitivity report (plan §15.9)
can compare them with Llama-3.1-8B.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.text_utils import read_jsonl, write_jsonl
from vakeel_sahayak.schemas.enums import Factor

_SECTION = r"(?:section|sec\.?|s\.)\s*"

FACTOR_RULES: dict[Factor, list[str]] = {
    Factor.GRAVITY_AND_PUNISHMENT: [
        r"\bgravity\b", r"\bheinous\b", r"\bseriousness\b", r"\bsevere\b|\bseverity\b",
        r"\bserious\s+(?:nature|offence|offense|allegations?|crime)", r"\bgrave\s+(?:offence|offense|nature|crime)",
        r"\bpunishable\s+with\s+(?:death|imprisonment|life|rigorous|fine)", r"\b(?:maximum|minimum)\s+(?:punishment|sentence)\b",
        r"\bimprisonment\s+for\s+life\b", r"\bnature\s+(?:and|of)\s+(?:the\s+)?(?:gravity|accusation|offence|allegations?)",
    ],
    Factor.CUSTODY_PERIOD: [
        r"\bin\s+(?:judicial\s+|police\s+)?custody\s+(?:since|for|from)\b", r"\bperiod\s+of\s+(?:his\s+|her\s+)?(?:custody|incarceration|detention)",
        r"\bincarcerat", r"\bbehind\s+(?:the\s+)?bars\b", r"\blanguish", r"\b(?:remained|remaining|been)\s+in\s+(?:jail|custody|prison)\b",
        r"\bcustody\s+for\s+(?:about|nearly|over|more\s+than|almost|a\s+period)", r"\b\d+\s+(?:days|months|years)\s+(?:in|of)\s+(?:custody|jail|incarceration)",
        r"\bsince\s+(?:his|her)\s+arrest\b",
    ],
    Factor.CHARGE_SHEET_FILED: [
        r"\bcharge[\s-]?sheet", r"\bfinal\s+report\b", r"\bchallan\b", r"\binvestigation\s+(?:is\s+|has\s+been\s+|stands\s+)?(?:complete|completed|concluded|over)",
        r"\bcognizance\b|\bcognisance\b", r"\bcustodial\s+interrogation\s+(?:is\s+)?(?:no\s+longer|not)\s+required",
    ],
    Factor.TRIAL_DELAY: [
        r"\bdelay\s+in\s+(?:the\s+)?(?:trial|conclusion)", r"\btrial\s+delay\b|\bdelayed\s+trial\b", r"\bspeedy\s+trial\b", r"\bprolonged\s+(?:trial|incarceration|pre-trial)",
        r"\btrial\s+(?:is\s+)?(?:not\s+likely|unlikely|likely\s+to\s+take|will\s+take|has\s+not\s+(?:commenced|begun|started))",
        r"\bwitnesses?\s+(?:are\s+)?(?:yet\s+to\s+be|still\s+to\s+be|remain\s+to\s+be)\s+examined", r"\bconclusion\s+of\s+(?:the\s+)?trial\b",
        r"\barticle\s+21\b", r"\bright\s+to\s+(?:a\s+)?speedy\b",
    ],
    Factor.PARITY_WITH_CO_ACCUSED: [
        r"\bparity\b", r"\bco[\s-]?accused\b", r"\bsimilarly\s+(?:placed|situated)\b", r"\bsame\s+footing\b",
        r"\bidentical\s+(?:role|allegations?)\b", r"\bother\s+accused\b.{0,60}\b(?:bail|released)",
    ],
    Factor.ANTECEDENTS: [
        r"\bantecedents?\b", r"\bcriminal\s+(?:history|record|antecedents?)\b", r"\bprevious(?:ly)?\s+(?:case|cases|involve|convict|FIR)",
        r"\bhistory[\s-]?sheet", r"\bhabitual\b", r"\bother\s+(?:cases|FIRs?)\s+(?:are\s+)?(?:pending|registered)\b",
        r"\bno\s+(?:other\s+)?(?:criminal\s+)?(?:case|record|antecedents?)\s+(?:is\s+|are\s+)?(?:pending|registered|against)",
        r"\bclean\s+(?:record|antecedents)\b", r"\brepeat\s+offender\b",
    ],
    Factor.FLIGHT_RISK: [
        r"\bflight\s+risk\b", r"\babscond", r"\bfugitive\b", r"\bflee\b|\bfleeing\b", r"\brun\s+away\b",
        r"\broots\s+in\s+(?:the\s+)?society\b", r"\bpermanent\s+(?:address|resident)", r"\bsurrender\s+(?:his\s+|her\s+)?passport",
        r"\bavailab(?:le|ility)\s+(?:for|during|at)\s+(?:the\s+)?(?:trial|investigation)", r"\bnon[\s-]?bailable\s+warrants?\b",
        r"\bsecur(?:e|ing)\s+(?:his|her|the)\s+presence\b", r"\bsubstantial\s+ties\b",
    ],
    Factor.WITNESS_TAMPERING: [
        r"\btamper", r"\binfluence\s+(?:the\s+)?(?:prosecution\s+)?witness", r"\bthreaten(?:ed|ing|s)?\s+(?:the\s+)?(?:prosecution\s+)?witness",
        r"\bwitness(?:es)?\s+(?:may\s+be\s+|being\s+|were\s+|are\s+)?(?:influenced|intimidated|pressuri[sz]ed|won\s+over|turned\s+hostile)",
        r"\bintimidat", r"\binterfere\s+with\s+(?:the\s+)?(?:investigation|evidence|trial|witness)", r"\bhostile\s+witness",
        r"\bdestroy(?:ing)?\s+(?:the\s+)?evidence\b",
    ],
    Factor.WEAK_PRIMA_FACIE: [
        r"\bno\s+prima\s+facie\b", r"\bprima\s+facie\s+(?:no|not|case|material|evidence|satisf)", r"\bfalsely\s+implicated\b|\bfalse\s+implication\b",
        r"\bno\s+(?:material|evidence)\s+(?:to\s+connect|against|on\s+record)", r"\b(?:general|vague|omnibus)\s+allegations?\b", r"\bbaseless\b",
        r"\bmala\s?fide\b", r"\bcivil\s+(?:dispute|nature|liability)\b", r"\bno\s+specific\s+role\b",
        r"\babsence\s+of\s+(?:any\s+)?(?:evidence|material)\b", r"\bnothing\s+(?:incriminating|has\s+been\s+recovered)\b", r"\bno\s+recovery\b",
    ],
    Factor.HEALTH_AGE_FAMILY: [
        r"\b(?:ill|illness|ailments?|ailing)\b", r"\bmedical\s+(?:condition|grounds?|treatment|records?|reports?|certificates?)\b",
        r"\b(?:cancer|heart\s+(?:disease|attack|ailment)|diabet\w+|surgery|disabilit\w+|disabled|hospitali[sz]ed|dialysis)\b",
        r"\bpregnan\w+", r"\b(?:woman|women|female)\b", r"\bminor\s+(?:child|children|son|daughter)", r"\b(?:aged|elderly|senior\s+citizen|old\s+age)\b", r"\b\d{2}\s+years?\s+(?:old|of\s+age)\b",
        r"\bsole\s+bread[\s-]?winner\b", r"\bdependent\s+(?:parents|family|children|wife)", r"\b(?:infant|aged\s+parents)\b", r"\bmental(?:ly)?\s+(?:ill|health|unsound)",
        r"\bfamily\s+(?:circumstances|members|responsibilit)",
    ],
    Factor.STATUTORY_BAR: [
        r"\btwin\s+conditions?\b", r"\b43\s?D\s?\(?5\)?", rf"{_SECTION}37\b.{{0,60}}(?:NDPS|narcotic)", r"(?:NDPS|narcotic).{0,80}" + _SECTION + r"37\b",
        rf"{_SECTION}45\b.{{0,60}}(?:PMLA|money[\s-]laundering)", r"(?:PMLA|money[\s-]laundering).{0,80}" + _SECTION + r"45\b",
        r"\bcommercial\s+quantity\b", r"\breasonable\s+grounds\s+for\s+believing\b", r"\bbar\s+(?:under|contained\s+in|imposed\s+by)\b",
    ],
    Factor.UNDERTRIAL_PERIOD: [
        r"\b436[\s-]?A\b", rf"(?:{_SECTION}|BNSS\s+){{1}}479\b|\b479\s+(?:of\s+(?:the\s+)?)?(?:BNSS|B\.N\.S\.S)", r"\bundertrial\b|\bunder[\s-]trial\b",
        r"\b(?:one[\s-]?half|half|one[\s-]?third|1/2|1/3)\s+of\s+(?:the\s+)?(?:maximum\s+)?(?:period|sentence|term|punishment)",
        r"\bfirst[\s-]time\s+offender\b",
    ],
}  # fmt: skip
_COMPILED: dict[Factor, list[re.Pattern[str]]] = {
    f: [re.compile(p, re.IGNORECASE | re.DOTALL) for p in pats] for f, pats in FACTOR_RULES.items()
}


# A co-accused who absconds says nothing about the applicant's own flight risk (it is parity material).
_OTHER_ABSCONDING = re.compile(r"\b(?:co[\s-]?accused|other\s+accused)\b(?:\s+\w+){0,3}?\s+(?:abscond\w*|(?:has|have)\s+fled|fled)\b", re.IGNORECASE)


def tag_factors(text: str) -> list[Factor]:
    """Return factors a paragraph discusses.

    Args:
        text: see behaviour

    Returns:
        Factors in Appendix A order, no duplicates.
    """
    without_others_absconding = _OTHER_ABSCONDING.sub(" ", text)
    return [
        f for f in Factor
        if any(p.search(without_others_absconding if f == Factor.FLIGHT_RISK else text) for p in _COMPILED[f])
    ]  # fmt: skip


def tag_corpus(paragraphs_path: str, out_path: str) -> int:
    """Tag every paragraph.

    Input: JSONL, one object per paragraph with a `text` field (a ParagraphRecord dump works). Output: the same objects
    with `factors` set to the tagged factor values.

    Args:
        paragraphs_path: see behaviour
        out_path: see behaviour

    Returns:
        Count.
    """
    rows: list[dict[str, Any]] = []
    for row in read_jsonl(Path(paragraphs_path)):
        row["factors"] = [f.value for f in tag_factors(str(row.get("text", "")))]
        rows.append(row)
    return write_jsonl(out_path, rows)
