"""Shared scaffolding of the Sutradhar architecture-variant tests (S1-S5, `docs/literature-to-code-map.md`, Sweep 1).

Builds a Sutradhar over the in-memory case-0007 world with the offline model (rule-based handlers, no language model)
and runs retrieval only, so a variant run is deterministic and cheap. `canonical_run` reduces a run to JSON with the
volatile event fields (ids, timestamps) removed: two runs are byte-identical when their canonical forms are equal.
"""

from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any

from tests.integration import _helpers as h
from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent
from vakeel_sahayak.models.offline_llm import OfflineLLM
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches

VOLATILE = {"event_id", "ts", "parent_id"}


def _stable(event: Any) -> dict[str, Any]:
    """An event without its volatile fields; a BUDGET_HIT also loses its whole-case snapshot, which depends on thread timing."""
    data = {k: v for k, v in json.loads(event.model_dump_json()).items() if k not in VOLATILE}
    if data.get("kind") == "BUDGET_HIT":
        data["outputs"] = {k: v for k, v in data.get("outputs", {}).items() if k != "budget"}
    return data


def build(*, switches: Switches | None = None, world: Any = None, budgets: BudgetTracker | None = None, toolbox_cls: type = h.ScenarioToolbox, **agent_kw: Any) -> SimpleNamespace:
    """A Sutradhar with the offline model over a case-0007 world (default: the shared fixtures)."""
    world = world or h.case_0007_world()
    toolbox = toolbox_cls(world)
    budgets = budgets or BudgetTracker()
    llm = OfflineLLM(role="agents_14b", where="ada")
    agent, ctx, _ = h.build_agent(SutradharAgent, llm=llm, toolbox=toolbox, world=world, budgets=budgets, switches=switches or Switches(), **agent_kw)
    state = h.make_state(world.dossier, world.rights)
    return SimpleNamespace(world=world, toolbox=toolbox, budgets=budgets, agent=agent, ctx=ctx, state=state, llm=llm)


def canonical_run(env: SimpleNamespace) -> dict[str, Any]:
    """Run retrieval and reduce the outcome to plain JSON: packs, plans and the events (a multiset) without ids and times."""
    out = env.agent.run(env.state)
    events = sorted(  # factors run in worker threads, so the order of events between factors is not fixed: compare them as a multiset
        (_stable(e) for e in env.ctx.log.events),
        key=lambda e: json.dumps(e, sort_keys=True, default=str),
    )
    return {
        "packs": json.loads(json.dumps([p.model_dump(mode="json") for p in out.evidence_packs], default=str)),
        "plans": json.loads(json.dumps([p.model_dump(mode="json") for p in out.plans], default=str)),
        "events": events,
        "budget": json.loads(out.budget.model_dump_json()),
    }


def digest(value: Any) -> str:
    """Short SHA-256 of a canonical JSON value."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]
