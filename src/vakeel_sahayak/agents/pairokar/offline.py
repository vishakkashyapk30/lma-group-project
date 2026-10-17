"""Offline handler for Pairokar's decision task: the scheduler's own rule, no language model (plan §3.3, §11)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.agents.pairokar.prompts import TASK_DECIDE
from vakeel_sahayak.batch.scheduler import Scheduler
from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler
from vakeel_sahayak.schemas.triage import TriageCard


def decide_offline(req: OfflineRequest) -> dict[str, Any]:
    """The decision the rule gives for the card in the request (`case.card`), with the reason."""
    card = TriageCard.model_validate(req.case.get("card") or {"case_id": "case", "urgency_rank": 0})
    decision = Scheduler().decide(card)
    why = {
        "flag_counsel": "A default-bail window is open or opening soon, or a rights flag stands: counsel must see it now.",
        "request_documents": "A document is missing and nothing is time-critical.",
        "full_brief": "Nothing is missing and nothing needs counsel before the brief.",
    }[decision]
    return {"decision": decision, "why": why}


def register() -> None:
    """Register the handler with the offline client (the agent module does this at import)."""
    register_offline_handler(TASK_DECIDE, decide_offline)


register()
