"""Scaffolding of the Munshi variant tests (S17 guard and spotlighting, S7 hierarchy re-reading, P7 image-only; `docs/literature-to-code-map.md`, Sweep 3).

Munshi runs over the constructed 14-page bundle of the integration tests (scripted pages, scripted laptop model) with one event log. `canonical_run`
reduces a run to plain JSON with the volatile event fields removed: two runs are byte-identical when their canonical forms are equal. The golden file
`golden_default_run.json` next to this module holds the digests of the DEFAULT run, captured before the Sweep-3 Munshi variants were added.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.integration import _helpers as h
from vakeel_sahayak.agents.munshi.agent import MunshiAgent
from vakeel_sahayak.orchestration.switches import Switches

VOLATILE = {"event_id", "ts", "parent_id"}
GOLDEN = Path(__file__).with_name("golden_default_run.json")


def build(switches: Switches | None = None, pages: list | None = None, boundaries: list | None = None, answers: list[str] | None = None,
          events: Any = None, cases_dir: str | None = None) -> SimpleNamespace:
    """Munshi on the scripted bundle (or `pages`), with its toolbox, model and log. `cases_dir` isolates the page index and alias map (document numbers
    continue from the saved index, so a run in a shared folder is not repeatable); default: a fresh temporary folder."""
    world = h.fresh_case_world()
    toolbox = h.ScenarioToolbox(world, pages=pages if pages is not None else h.build_bundle(),
                                boundaries=boundaries if boundaries is not None else h.BUNDLE_BOUNDARIES, answers=answers or [""] * 6)
    llm = h.make_llm(where="laptop", events=events or h.munshi_events_responder(), free="")
    munshi, ctx, _ = h.build_agent(MunshiAgent, llm=llm, toolbox=toolbox, world=world, **({"switches": switches} if switches else {}))
    munshi.cases_dir = cases_dir or tempfile.mkdtemp(prefix="munshi-variants-")
    return SimpleNamespace(munshi=munshi, toolbox=toolbox, ctx=ctx, log=ctx.log, llm=llm, world=world)


def run(env: SimpleNamespace) -> Any:
    """Run Munshi over the seeded state; returns the state."""
    return env.munshi.run(h.seed_state())


def stable(event: Any) -> dict[str, Any]:
    """An event without its volatile fields."""
    return {k: v for k, v in json.loads(event.model_dump_json()).items() if k not in VOLATILE}


def canonical_run(env: SimpleNamespace) -> dict[str, Any]:
    """Run Munshi and reduce the outcome to plain JSON: the ingestion report, the events in order, the tool calls in order."""
    state = run(env)
    return {
        "report": json.loads(state.ingestion.model_dump_json()),
        "events": [stable(e) for e in env.log.events],
        "calls": [[c.name, json.loads(json.dumps(c.kwargs, default=str, sort_keys=True))] for c in env.toolbox.calls],
        "variant_signals": json.loads(json.dumps(state.variant_signals, default=str)),
    }


def digest(value: Any) -> str:
    """Short SHA-256 of a canonical JSON value."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def digests(run_: dict[str, Any]) -> dict[str, Any]:
    """The golden form: one digest per part plus the counts (signals are checked separately)."""
    return {**{k: digest(v) for k, v in run_.items() if k != "variant_signals"}, "n_events": len(run_["events"]), "n_calls": len(run_["calls"])}
