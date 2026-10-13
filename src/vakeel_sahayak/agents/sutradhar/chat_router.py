"""Chat routing table (plan §6.4)."""

from __future__ import annotations

CHAT_ROUTES: dict[str, list[str]] = {
    "custody_days": ["get_timeline", "date_calc"],
    "section_equivalent": ["map_section"],
    "eligibility": ["rights_check"],
    "precedent_search": ["search_reasoning", "citations"],
    "what_did_court_say": ["search_case_docs"],
    "how_state_opposes": ["search_objections", "get_statute"],
}


def route_question(question: str) -> list[str]:
    """Choose tools for a counsel question; refuse prediction and lay-advice requests.

    Args:
        question: see behaviour

    Returns:
        Tool names (empty means refuse).
    """
    raise NotImplementedError
