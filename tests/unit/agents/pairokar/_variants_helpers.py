"""Scaffolding of the serving-variant tests (S14 scheduling policies, plan cache, prefix layout; `docs/literature-to-code-map.md`, Sweep 3).

Pairokar over an in-memory queue with stub stage-1 and full-run functions (no agent runs): six constructed files arrive in a fixed order with cards
that differ in urgency, so the scheduling order, the next steps, the stage-2 order under a GPU budget and the events are deterministic. `canonical_run`
reduces a run to plain JSON (ids and timestamps removed). The golden file `golden_default_run.json` holds the digests of the DEFAULT run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.unit.agents._helpers import build_agent
from tests.unit.batch._helpers import DEFAULT_OPEN, DEFAULT_SOON, S479_CROSSED_48, card
from vakeel_sahayak.agents.pairokar.agent import PairokarAgent
from vakeel_sahayak.batch.queue import TriageQueue
from vakeel_sahayak.orchestration.switches import Switches

VOLATILE = {"event_id", "ts", "parent_id"}
GOLDEN = Path(__file__).with_name("golden_default_run.json")
FILES = [f"/batch/file-{i}.pdf" for i in range(1, 7)]
SPECS = {  # arrival order: a no-deadline case first, the most urgent ones later
    "case-0001": dict(custody=100),
    "case-0002": dict(custody=120, missing=["custody certificate"]),
    "case-0003": dict(default_bail=DEFAULT_SOON, custody=70),
    "case-0004": dict(custody=300),
    "case-0005": dict(default_bail=DEFAULT_OPEN, custody=64),
    "case-0006": dict(undertrial=S479_CROSSED_48, custody=900),
}


def build(switches: Switches | None = None, *, hours_per_case: float = 0.25, sizes: dict[str, float] | None = None) -> SimpleNamespace:
    """Pairokar on stub runners: stage 1 returns the constructed card, a full run returns a small summary and is logged in `ran`."""
    cards = {cid: card(cid, **spec) for cid, spec in SPECS.items()}
    ran: list[str] = []

    def stage1(case_id: str, path: str):
        return cards[case_id]

    def full(case_id: str, path: str) -> dict[str, Any]:
        ran.append(case_id)
        return {"case_id": case_id, "grounds": 1, "statutory_bar": False}

    agent, ctx, _ = build_agent(PairokarAgent, **({"switches": switches} if switches else {}))
    # a Pairokar over a fresh queue and the stub runners, sharing the context of the fake agent
    agent = PairokarAgent(ctx, queue=TriageQueue(":memory:"), stage1_runner=stage1, full_runner=full, hours_per_case=hours_per_case)
    if sizes:
        agent.scheduler.sizes = dict(sizes)
    return SimpleNamespace(agent=agent, ctx=ctx, cards=cards, ran=ran, log=ctx.log)


def stable(event: Any) -> dict[str, Any]:
    """An event without its volatile fields."""
    return {k: v for k, v in json.loads(event.model_dump_json()).items() if k not in VOLATILE}


def canonical_run(env: SimpleNamespace, budget_hours: float = 0.75) -> dict[str, Any]:
    """Stage 1 on the six files, then stage 2 under `budget_hours`; the cards in order, the cases run in order and the events."""
    cards = env.agent.stage1(FILES)
    done = env.agent.stage2(cards, budget_hours)
    return {
        "cards": [json.loads(c.model_dump_json()) for c in cards],
        "done": done,
        "ran": list(env.ran),
        "events": [stable(e) for e in env.log.events],
    }


def digest(value: Any) -> str:
    """Short SHA-256 of a canonical JSON value."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def digests(run: dict[str, Any]) -> dict[str, Any]:
    """The golden form: one digest per part plus the counts."""
    return {**{k: digest(v) for k, v in run.items()}, "n_events": len(run["events"]), "n_done": len(run["done"])}
