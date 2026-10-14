"""Build an `AgentContext` wired to fakes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.fakes.data import CaseWorld, build_world
from tests.fakes.log import InMemoryEventLog
from tests.fakes.models import ScriptedLLM
from tests.fakes.toolbox import FakeToolbox
from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.config import AppConfig
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches


def make_context(
    llm: ScriptedLLM | None = None,
    toolbox: FakeToolbox | None = None,
    world: CaseWorld | None = None,
    case_id: str = "case-0007",
    switches: Switches | None = None,
    log: Any = None,
    budgets: BudgetTracker | None = None,
    sqlite_dir: Path | None = None,
) -> AgentContext:
    """A context whose model is `llm`, whose tools are `toolbox.tools` and whose log is in memory unless `sqlite_dir`
    is given (then the real SQLite `EventLog` is used)."""
    world = world or (toolbox.world if toolbox else build_world())
    toolbox = toolbox or FakeToolbox(world)
    if log is None:
        if sqlite_dir is not None:
            from vakeel_sahayak.record.event_log import EventLog

            log = EventLog(str(sqlite_dir / f"{case_id}-events.sqlite"))
        else:
            log = InMemoryEventLog()
    return AgentContext(
        case_id=case_id,
        config=AppConfig(),
        log=log,
        budgets=budgets or BudgetTracker(),
        llm=llm or ScriptedLLM(strict=False, default=""),
        switches=switches or Switches(),
        tools=toolbox.tools,
    )
