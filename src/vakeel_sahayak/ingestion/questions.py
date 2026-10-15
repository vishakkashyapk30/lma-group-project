"""Questions to counsel: at most 3 per round, shared by Munshi and Peshkar, unreadable pages grouped in one (plan §4.3).

A round runs from one action by counsel to the next. Every question asked is logged as an AGENT_MESSAGE event with
`inputs.action == "ask_user"`, so the count is shared with Peshkar (which asks through the same tool) and survives a
restart. `QuestionBook` picks which questions fit in the room left; the rest are deferred, never dropped silently.
"""

from __future__ import annotations

import re
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import AgentName, EventKind
from vakeel_sahayak.schemas.events import Event

DEFAULT_LIMIT = 3
AskHandler = Callable[[list[str], str], list[str]]
_handler: AskHandler | None = None
_asker = threading.local()


def set_ask_handler(handler: AskHandler | None) -> None:
    """Install the function that puts questions to counsel and returns the answers (the graph's interrupt in Phase 4).

    Without one, questions are logged and left open: `ask_user` returns no answers.
    """
    global _handler
    _handler = handler


def set_asker(agent: AgentName | None) -> None:
    """Name the agent on whose behalf `ask_user` is called (the graph sets it per node; default Munshi)."""
    _asker.agent = agent


def current_asker() -> AgentName:
    """The agent currently asking (Munshi unless the graph says otherwise)."""
    return getattr(_asker, "agent", None) or AgentName.MUNSHI


def question_limit() -> int:
    """Questions allowed per round (configs/budgets.yaml `questions_per_round`)."""
    try:
        from vakeel_sahayak.config import load_config

        return int(load_config().budgets.questions_per_round)
    except Exception:  # a broken config must not stop intake from asking at all
        return DEFAULT_LIMIT


def questions_used_this_round(log: EventLog, case_id: str) -> int:
    """Questions already asked since counsel last acted (by Munshi and Peshkar together)."""
    used = 0
    for event in log.read(case_id):
        if event.kind == EventKind.USER_ACTION:
            used = 0
        elif event.kind == EventKind.AGENT_MESSAGE and event.inputs.get("action") == "ask_user":
            used += len(event.outputs.get("questions", []))
    return used


def record_questions(log: EventLog, case_id: str, questions: list[str], actor: AgentName | str | None = None) -> Event:
    """Log questions put to counsel (the log holds pseudonymised text only; questions never carry names)."""
    return log.append(
        Event(
            event_id="",
            case_id=case_id,
            ts="",
            kind=EventKind.AGENT_MESSAGE,
            actor=actor or current_asker(),
            tool="ask_user",
            inputs={"action": "ask_user"},
            outputs={"questions": list(questions)},
        )
    )


def record_answers(log: EventLog, case_id: str, questions: list[str]) -> None:
    """Log that counsel answered these questions (a USER_ACTION `answer_question` each), which ends the round."""
    for question in questions:
        log.append(
            Event(
                event_id="",
                case_id=case_id,
                ts="",
                kind=EventKind.USER_ACTION,
                actor="counsel",
                inputs={"action": "answer_question", "question": question},
            )
        )


_UNREADABLE_Q = re.compile(r"^\s*Page\s+(\d+)(?:\s+of\s+the\s+(.+?))?\s+(?:is|are)\s+unreadable\b", re.IGNORECASE)


def group_unreadable(questions: list[str]) -> list[str]:
    """Merge per-page 'Page N ... is unreadable' questions into one question (plan §4.3).

    The merged question takes the place of the first of them; a single such question is left as it is.

    Args:
        questions: the candidate questions

    Returns:
        Questions with the unreadable-page ones replaced by one naming all the pages.
    """
    hits = [(i, m) for i, q in enumerate(questions) if (m := _UNREADABLE_Q.match(q))]
    if len(hits) < 2:
        return list(questions)
    by_label: dict[str | None, list[int]] = defaultdict(list)
    for _, m in hits:
        by_label[m.group(2)].append(int(m.group(1)))
    bits = [f"{page_ranges(pages)}" + (f" of the {label}" if label else "") for label, pages in by_label.items()]
    merged = f"Pages {' and '.join(bits)} are unreadable. Can you upload clearer copies?"
    first, drop = hits[0][0], {i for i, _ in hits}
    return [merged if i == first else q for i, q in enumerate(questions) if i == first or i not in drop]


def put_to_counsel(questions: list[str], case_id: str) -> list[str]:
    """Hand questions to the installed handler and return its answers ([] when none is installed)."""
    return list(_handler(questions, case_id)) if _handler else []


def page_ranges(pages: list[int]) -> str:
    """Compact page list for messages: [3, 4, 5, 9] gives '3-5, 9'."""
    runs: list[list[int]] = []
    for p in sorted(set(pages)):
        if runs and p == runs[-1][1] + 1:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


def unreadable_question(unreadable: list[tuple[str, int, str | None]]) -> str:
    """One question for all unreadable pages (plan §4.3: unreadable pages are grouped into one question).

    Args:
        unreadable: (file name, page, document label or None) for each unreadable page

    Returns:
        For example 'Page 3 of the FIR in bundle_1.pdf is unreadable. Can you upload a clearer copy?' or, for several,
        'Pages 3-4 of the FIR and 8 of the Remand Order in bundle_1.pdf are unreadable. Can you upload clearer copies?'
    """
    by_file: dict[str, dict[str | None, list[int]]] = defaultdict(lambda: defaultdict(list))
    for name, page, label in unreadable:
        by_file[name][label].append(page)
    parts = []
    for name, labels in by_file.items():
        bits = [f"{page_ranges(pages)}" + (f" of the {label}" if label else "") for label, pages in labels.items()]
        parts.append(" and ".join(bits) + f" in {name}")
    if len(unreadable) == 1:
        return f"Page {parts[0]} is unreadable. Can you upload a clearer copy?"
    return f"Pages {'; '.join(parts)} are unreadable. Can you upload clearer copies?"


@dataclass
class QuestionBook:
    """Collects candidate questions and picks the ones that fit the round (lowest priority number first)."""

    limit: int = DEFAULT_LIMIT
    used: int = 0
    _items: list[tuple[int, int, str, str]] = field(default_factory=list)

    def add(self, text: str, key: str, priority: int) -> None:
        """Add a question; a second one with the same key is ignored."""
        if all(k != key for _, _, k, _ in self._items):
            self._items.append((priority, len(self._items), key, text))

    @property
    def room(self) -> int:
        """Questions that can still be asked this round."""
        return max(0, self.limit - self.used)

    def asked(self) -> list[str]:
        """The questions that fit, in priority order."""
        return [t for _, _, _, t in sorted(self._items)][: self.room]

    def deferred_keys(self) -> list[str]:
        """Keys of the questions left for the next round."""
        return [k for _, _, k, _ in sorted(self._items)][self.room :]

    def is_asked(self, key: str) -> bool:
        """Whether the question with this key made the cut."""
        return key in [k for _, _, k, _ in sorted(self._items)][: self.room]
