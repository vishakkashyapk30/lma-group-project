"""Chat routing table (plan §6.4).

Counsel's questions go to the store or tool that holds the answer (the table below). Two kinds of question are
refused instead of routed: outcome predictions (the system never predicts, plan §1.3) and lay advice from a member of
the public (the system serves counsel; the public is pointed to NALSA, 15100).
"""

from __future__ import annotations

import re

CHAT_ROUTES: dict[str, list[str]] = {
    "custody_days": ["get_timeline", "date_calc"],
    "section_equivalent": ["map_section"],
    "eligibility": ["rights_check"],
    "precedent_search": ["search_reasoning", "citations"],
    "what_did_court_say": ["search_case_docs"],
    "how_state_opposes": ["search_objections", "get_statute"],
}
NALSA_HELPLINE = "15100"
REFUSE_PREDICTION, REFUSE_ADVICE = "refuse_prediction", "refuse_lay_advice"
EXPORT_PRESSURE = "export_pressure"  # a request to export, to skip counsel's approval or to approve for counsel: answered with where approval happens, no tool

_I = re.IGNORECASE
_PREDICT = [
    re.compile(p, _I)
    for p in (
        r"\b(?:will|would|shall)\b[^?.]{0,40}\b(?:get|be\s+granted|be\s+given|be\s+released|be\s+rejected|be\s+refused|win|succeed|lose)\b[^?.]{0,25}\bbail\b",
        r"\bbail\b[^?.]{0,30}\b(?:be\s+granted|be\s+rejected|be\s+refused|be\s+allowed|succeed|go\s+through|come\s+through)\b",
        r"\b(?:chances?|odds|probability|likelihood|prospects?|percentage|how\s+likely|how\s+probable)\b",
        r"\b(?:grant|success|rejection|acceptance)\s+rates?\b|\bpredict\b|\bforecast\b",
        r"\bwill\s+(?:the\s+)?(?:court|judge|bench|hc|high\s+court|sessions)\b[^?.]{0,40}\b(?:grant|allow|reject|refuse|dismiss)\b",
        r"\bwill\s+(?:i|he|she|they|we|my\s+\w+)\s+(?:win|succeed|get\s+out|be\s+released)\b",
        r"\bis\s+(?:bail|release)\s+(?:certain|guaranteed|assured|sure|definite)\b|\bbail\b[^?.]{0,25}\b(?:certain|guaranteed|assured)\b",
        r"\b(?:most\s+|more\s+|very\s+)?likely\s+to\s+(?:allow|grant|reject|refuse|dismiss|succeed|win|get)\b",
        r"\bgrant(?:ed)?\s+(?:in|for)\s+(?:what|how)\s+(?:share|many|much)\b",
        r"जमानत[^?।]{0,40}(?:मिलेगी|मिल\s*जाएगी|मिल\s*पाएगी|मिलने\s+की|मंजूर\s+होगी|खारिज\s+होगी|होगी)|संभावना|कितनी\s+उम्मीद|कितने\s+प्रतिशत|भविष्यवाणी",
    )
]
_ADVICE = [
    re.compile(p, _I)
    for p in (
        r"\b(?:my|our)\s+(?:husband|wife|son|daughter|brother|sister|father|mother|friend|uncle|relative)\b[^?.]{0,50}\b(?:arrested|in\s+jail|in\s+custody|detained|booked)\b",
        r"\bi\s+(?:am|was|have\s+been)\s+(?:arrested|accused|booked|detained|charged)\b",
        r"\b(?:run|running|flee|fleeing|escape|escaping|hide|hiding|abscond)\b[^?.]{0,25}\b(?:police|arrest|custody|jail|court)\b",
        r"\b(?:what|how)\s+should\s+(?:i|we)\b",
        r"\bshould\s+(?:i|we)\s+(?:surrender|apply|plead|confess|pay|run|hide|sign|settle|appear|go)\b",
        r"\bcan\s+i\s+(?:get|apply|file|be\s+given)\b[^?.]{0,25}\bbail\b",
        r"\b(?:i|we)\s+(?:want|need)\s+(?:a\s+)?(?:bail|lawyer|advice)\b",
        r"\bwhat\s+do\s+i\s+do\b|\bwhat\s+can\s+i\s+do\b|\bhelp\s+me\b.{0,40}\b(?:bail|police|arrest|jail)\b",
        r"\bi\s+am\s+(?:the\s+|a\s+)?(?:complainant|victim|informant|accused|applicant|petitioner|witness)\b",
        r"\bshould\s+(?:i|we)\s+(?:withdraw|compromise|cooperate|testify|say|tell|answer|give|take|accept|refuse|meet|call|talk|speak|leave|stay)\b",
        r"(?:मेरे|हमारे)\s+(?:भाई|बेटे|बेटी|पति|पत्नी|पिता|पिताजी|माँ|माता|मां|बहन|दोस्त|रिश्तेदार)[^?।]{0,60}(?:गिरफ्तार|पकड़|हिरासत|जेल)",
        r"(?:मैं|हम)\s+क्या\s+कर(?:ूँ|ूं|ें|ना)|मुझे\s+क्या\s+करना",
    )
]
_PRESSURE = re.compile(
    r"\bexport\b[^?.]{0,40}\b(?:application|docx|pdf|files?|brief|it|now|bas)\b|\b(?:skip|without|bypass)\b[^?.]{0,25}\bapproval\b"
    r"|\bapprov\w*\b[^?.]{0,25}\b(?:gate|for\s+me)\b|\bgate\s*[12]\b[^?.]{0,30}\bapproved\b|\bexport\s+kar\b|एक्सपोर्ट|निर्यात|\bapproval\s+baad\b",
    _I,
)
_INTENTS: list[tuple[str, re.Pattern[str]]] = [
    ("custody_days", re.compile(r"\bhow\s+many\s+days\b|\bdays?\s+(?:in|of|spent\s+in)\s+(?:custody|jail|lock-?up|detention)\b|\bcustody\s+(?:period|days|so\s+far|duration)\b|\bhow\s+long\b[^?.]{0,30}\b(?:custody|jail|detention|inside)\b", _I)),
    ("section_equivalent", re.compile(r"\b(?:bns|bnss|ipc|crpc|cr\.?p\.?c)\b[^?.]{0,30}\b(?:equivalent|counterpart|corresponds?|replac\w+|now|new\s+(?:section|code|law))\b|\b(?:equivalent|counterpart|corresponding)\b[^?.]{0,40}\b(?:bns|bnss|ipc|crpc|section)\b|\bwhat\s+is\s+\d+\w*\s+(?:ipc|crpc)\b", _I)),
    ("eligibility", re.compile(r"\beligible\b|\beligibility\b|\bdefault\s+bail\b|\bs(?:ection|\.)?\s*(?:479|436\s?a)\b|\bundertrial\s+(?:limit|period)\b|\brights?\s+radar\b|\bentitled\s+to\b|\bantil\s+categor", _I)),
    ("how_state_opposes", re.compile(r"\bhow\s+(?:does|do|would|will)\s+the\s+(?:state|prosecution)\b|\b(?:state|prosecution)\s+(?:usually|typically|normally|generally|often)\s+(?:oppose|argue|object|resist)\w*\b|\bobjections?\s+(?:the\s+)?(?:state|prosecution)\b|\busual\s+objections?\b", _I)),
    ("what_did_court_say", re.compile(r"\bwhat\s+did\s+the\b[^?.]{0,40}\b(?:court|judge|magistrate|bench)\b|\b(?:order|orders)\s+(?:say|says|said|state|states|record|records)\b|\bremand\s+order\b|\b(?:court|judge|magistrate)\s+(?:said|held|observed|noted|recorded|ordered)\b|\bin\s+the\s+(?:order|fir|charge\s+sheet|remand)\b", _I)),
    ("precedent_search", re.compile(r"\b(?:any|which|find|show|cite|give\s+me)\b[^?.]{0,30}\b(?:sc|supreme\s+court|high\s+court|hc)?\s*(?:case|cases|judgments?|precedents?|rulings?|authorit(?:y|ies)|decisions?)\b|\bcase\s*law\b|\bprecedents?\b|\bauthorit(?:y|ies)\s+(?:on|for)\b", _I)),
]


def is_lay_advice(question: str) -> bool:
    """True when the question reads as coming from the accused or their family (the answer points to NALSA)."""
    return any(p.search(question or "") for p in _ADVICE)


def classify_question(question: str) -> str | None:
    """What a question is: a CHAT_ROUTES key, 'refuse_prediction', 'refuse_lay_advice', or None when it matches no route.

    Args:
        question: counsel's question

    Returns:
        The route key (refusals take precedence over every route).
    """
    from vakeel_sahayak.agents.base import prediction_language

    text = question or ""
    if any(p.search(text) for p in _PREDICT) or prediction_language(text):
        return REFUSE_PREDICTION
    if any(p.search(text) for p in _ADVICE):
        return REFUSE_ADVICE
    if _PRESSURE.search(text):
        return EXPORT_PRESSURE
    for key, pattern in _INTENTS:
        if pattern.search(text):
            return key
    return None


def route_question(question: str) -> list[str]:
    """Choose tools for a counsel question; refuse prediction and lay-advice requests.

    A question that matches no route is treated as a question about the case file and goes to the case documents.

    Args:
        question: counsel's question

    Returns:
        Tool names (empty means refuse).
    """
    key = classify_question(question)
    if key in (REFUSE_PREDICTION, REFUSE_ADVICE, EXPORT_PRESSURE):
        return []
    return list(CHAT_ROUTES[key]) if key else ["search_case_docs"]
