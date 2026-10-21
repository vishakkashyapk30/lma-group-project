"""Shared scaffolding of the Vakeel / Abhiyojak architecture-variant tests (S8, S9, S10, S15; `docs/literature-to-code-map.md`, Sweep 2).

Builds Vakeel and Abhiyojak over the in-memory case-0007 world with the offline model (rule-based handlers, no language model),
one shared event log and one shared budget, so a variant run is deterministic. `canonical_run` reduces a run to plain JSON with the
volatile event fields (ids, timestamps) removed: two runs are byte-identical when their canonical forms are equal.
The golden file `golden_default_run.json` next to this module holds the digests of the DEFAULT run, captured before any Sweep-2 change.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from tests.fakes.data import load_paragraphs
from tests.integration import _helpers as h
from tests.unit.agents.vakeel._scripts import pack
from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.models.offline_llm import OfflineLLM
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import Factor

VOLATILE = {"event_id", "ts", "parent_id"}
GOLDEN = Path(__file__).with_name("golden_default_run.json")


def packs() -> list[Any]:
    """Three evidence packs of case-0007 (parity, charge sheet, custody) with the fixture paragraphs they cite."""
    paras = load_paragraphs()
    return [
        pack(Factor.PARITY_WITH_CO_ACCUSED, paras, [("DLHC-2022-1187", 14)]),
        pack(Factor.CHARGE_SHEET_FILED, paras, [("SC-2014-0463", 21)]),
        pack(Factor.CUSTODY_PERIOD, paras, [("DLHC-2021-0420", 11)]),
    ]


def build(*, switches: Switches | None = None, vakeel_llm: Any = None, abhiyojak_llm: Any = None, budgets: BudgetTracker | None = None,
          world: Any = None) -> SimpleNamespace:
    """Vakeel and Abhiyojak on the offline model over case-0007 (one log, one budget, one toolbox)."""
    world = world or h.case_0007_world()
    toolbox = h.ScenarioToolbox(world)
    budgets = budgets or BudgetTracker()
    switches = switches or Switches()
    vllm = vakeel_llm or OfflineLLM(role="agents_14b", where="ada")
    allm = abhiyojak_llm or OfflineLLM(role="agents_14b", where="ada")
    vakeel, vctx, _ = h.build_agent(VakeelAgent, llm=vllm, toolbox=toolbox, world=world, budgets=budgets, switches=switches)
    abhiyojak, actx, _ = h.build_agent(AbhiyojakAgent, llm=allm, toolbox=toolbox, world=world, log=vctx.log, budgets=budgets, switches=switches)
    abhiyojak.replier = vakeel.reply_to_objections  # the replies come from this Vakeel, whatever the environment's model backend is
    state = h.make_state(world.dossier, world.rights).model_copy(update={"evidence_packs": packs()})
    return SimpleNamespace(world=world, toolbox=toolbox, budgets=budgets, vakeel=vakeel, abhiyojak=abhiyojak, vctx=vctx, actx=actx,
                           state=state, vakeel_llm=vllm, abhiyojak_llm=allm, log=vctx.log, switches=switches)


def stable(event: Any) -> dict[str, Any]:
    """An event without its volatile fields."""
    return {k: v for k, v in json.loads(event.model_dump_json()).items() if k not in VOLATILE}


def run_both(env: SimpleNamespace) -> SimpleNamespace:
    """Vakeel's full job, then Abhiyojak's two rounds, as the driver runs them (Vakeel replies through `reply_to_objections`)."""
    after = env.vakeel.run(env.state)
    record = env.abhiyojak.spar(after)
    return SimpleNamespace(state=after, record=record)


def canonical_run(env: SimpleNamespace) -> dict[str, Any]:
    """Run both agents and reduce the outcome to plain JSON: brief, sparring record, hearing card, events (in order), budget."""
    out = run_both(env)
    return {
        "brief": json.loads(out.state.brief.model_dump_json()),
        "sparring": json.loads(out.record.model_dump_json()),
        "card": json.loads(json.dumps(out.state.hearing_card, default=str)),
        "events": [stable(e) for e in env.log.events],
        "budget": json.loads(out.state.budget.model_dump_json()),
    }


def digest(value: Any) -> str:
    """Short SHA-256 of a canonical JSON value."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()[:16]


def digests(run: dict[str, Any]) -> dict[str, Any]:
    """The golden form of a canonical run: one digest per part plus the event count."""
    return {**{k: digest(v) for k, v in run.items()}, "n_events": len(run["events"])}


def events_of(env: SimpleNamespace, tool: str | None = None, actor: str | None = None) -> list[Any]:
    """Logged events of one decision tool (`outputs.type`) and/or actor."""
    out = []
    for e in env.log.events:
        o = e.outputs or {}
        if tool is not None and (o.get("type") != tool and e.tool != tool):
            continue
        if actor is not None and e.actor.value != actor:
            continue
        out.append(e)
    return out


class RecordingLLM(OfflineLLM):
    """The offline model that keeps every prompt and the temperature it was called with."""

    def __init__(self) -> None:
        super().__init__(role="agents_14b", where="ada")
        self.seen: list[tuple[str, float]] = []

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        self.seen.append((prompt, temperature))
        return super().generate(prompt, max_tokens=max_tokens, temperature=temperature, json_schema=json_schema)

    def of_task(self, task: str) -> list[tuple[str, float]]:
        return [(p, t) for p, t in self.seen if f"### TASK: {task}" in p]
