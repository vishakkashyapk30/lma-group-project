"""Tools in interaction (plan §4.3). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.tools.base import ToolError, ToolSpec


def interrupt(payload: dict) -> list[str]:
    """Hand a payload of questions to counsel and wait for the answers.

    The installed handler (`ingestion.questions.set_ask_handler`) comes first; otherwise LangGraph's interrupt is used
    when a graph is running. With neither, the questions stay open and no answers come back. Tests replace this name.
    """
    from vakeel_sahayak.ingestion.questions import put_to_counsel

    questions = list(payload["questions"])
    case_id = str(payload.get("case_id", ""))
    answers = put_to_counsel(questions, case_id)
    if answers:
        return answers
    try:
        from langgraph.types import interrupt as graph_interrupt

        result = graph_interrupt(payload)
    except (ImportError, RuntimeError):  # no langgraph, or called outside a running graph
        return []
    return [str(a) for a in result] if isinstance(result, (list, tuple)) else ([str(result)] if result else [])


def ask_user(questions: list[str], case_id: str) -> list[str] | ToolError:
    """Ask counsel. Munshi and Peshkar share a limit of 3 questions per round; unreadable pages are grouped into one question. (plan §4.3)

    Per-page "unreadable" questions are merged into one, then at most the room left in the round is asked; the rest
    are deferred (not asked, not lost: the caller asks again next round). The questions are logged, so the count is
    shared across agents and survives a restart; counsel's answers end the round.

    Args:
        questions: the questions; group related ones (for example all unreadable pages) into one
        case_id: see behaviour

    Returns:
        Counsel's answers, one per question asked (an empty list while the questions are only logged, or when there
        was nothing to ask).
    """
    from vakeel_sahayak.ingestion.questions import (
        group_unreadable,
        question_limit,
        questions_used_this_round,
        record_answers,
        record_questions,
    )
    from vakeel_sahayak.tools.runtime import get_runtime
    from vakeel_sahayak.tools.store_call import invalid

    tool = "ask_user"
    try:
        check_case_id(case_id)
    except (ValueError, TypeError) as exc:
        return invalid(tool, str(exc))
    if not isinstance(questions, list) or not all(isinstance(q, str) and q.strip() for q in questions):
        return invalid(tool, "questions must be a list of non-empty strings")
    if not questions:
        return []
    grouped = group_unreadable([q.strip() for q in questions])
    log = get_runtime().event_log(case_id)
    room = max(0, question_limit() - questions_used_this_round(log, case_id))
    if room == 0:
        return ToolError(
            tool=tool,
            kind="question_limit",
            message="the round's questions are used up (Munshi and Peshkar share the limit); wait for counsel's answers",
            retryable=False,
        )
    asked = grouped[:room]
    record_questions(log, case_id, asked)
    answers = [str(a) for a in interrupt({"questions": asked, "case_id": case_id})]
    if answers:
        record_answers(log, case_id, asked)
    return answers


ASK_USER_SPEC = ToolSpec(
    name="ask_user",
    description="Ask counsel. Munshi and Peshkar share a limit of 3 questions per round; unreadable pages are grouped into one question.",
    agents=[AgentName.MUNSHI, AgentName.PESHKAR],
    stores=[],
    plan_ref="§4.3",
)
