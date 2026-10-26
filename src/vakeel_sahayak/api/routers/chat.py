"""Router 'chat' (plan §6.4, §13.5): counsel's question goes to Sutradhar, which routes it to a store or tool and answers
shortly with citations; outcome predictions and lay advice are refused. The centre of the workspace.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import get_event_log
from vakeel_sahayak.api.models import ChatRequest
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.chat import ChatMessage
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event

router = APIRouter(prefix="/api/cases/{case_id}/chat", tags=["chat"])


def _persist(log: EventLog, case_id: str, message: ChatMessage, kind: EventKind, actor: object) -> None:
    log.append(Event(event_id="", case_id=case_id, ts="", kind=kind, actor=actor,
                     inputs={"action": "chat"} if kind == EventKind.USER_ACTION else {},
                     outputs={"chat": message.model_dump(mode="json"), "text": message.text}))


@router.post("", response_model=ChatMessage)
async def post_chat(case_id: str, body: ChatRequest, log: Annotated[EventLog, Depends(get_event_log)]) -> ChatMessage:
    """Chat (core): Sutradhar routes to a store or tool; short cited answers; predictions and lay advice refused (plan §6.4)."""
    service.require_case(log, case_id)

    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.orchestration.state import CaseGraphState

    cs = service.case_state(log, case_id)
    state = CaseGraphState(case_id=case_id, log_path=log.db_path, dossier=cs.dossier(), rights=cs.rights_report())
    # Counsel may type a name: the log and the agents see the case's alias instead (plan §16); the alias map stays on the laptop.
    from vakeel_sahayak.privacy.pseudonymise import load_map, pseudonymise_text, save_map

    mapping = load_map(case_id)
    text, _ = pseudonymise_text(body.text, case_id, mapping)
    save_map(case_id, mapping)
    question = ChatMessage(message_id=uuid.uuid4().hex, case_id=case_id, role="counsel", text=text)
    _persist(log, case_id, question, EventKind.USER_ACTION, COUNSEL)

    def answer_in_thread() -> ChatMessage:
        sutradhar = create_agent(AgentName.SUTRADHAR, service.agent_context(log, case_id))
        try:
            return sutradhar.answer_chat(state, text)
        finally:
            sutradhar.close()

    answer = await run_in_threadpool(answer_in_thread)  # never block the event loop with agent work
    answer = answer.model_copy(update={"case_id": case_id})
    _persist(log, case_id, answer, EventKind.AGENT_MESSAGE, AgentName.SUTRADHAR)
    return answer


@router.get("", response_model=list[ChatMessage])
async def get_history(case_id: str, log: Annotated[EventLog, Depends(get_event_log)]) -> list[ChatMessage]:
    """Chat history, in order."""
    service.require_case(log, case_id)
    history: list[ChatMessage] = []
    for ev in log.read(case_id):
        raw = ev.outputs.get("chat")
        if raw:
            history.append(ChatMessage.model_validate(raw))
    return history
