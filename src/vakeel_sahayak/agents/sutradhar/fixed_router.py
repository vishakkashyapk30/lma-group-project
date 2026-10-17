"""A6 variant and default fallback: contracts run in a fixed order with fixed queries, no planning or sufficiency check (plan §6.5, §15.4, §19).

For every applicable factor, in Appendix A order, the contract's slots run in the contract's order, each with its first
allowed source and the slot's templated query, exactly once: no model writes a query, nothing is reworded, relaxed or
followed, and no rule check judges the result. A slot is FILLED when anything came back and MISSING when nothing did (the one rule it keeps is the leakage guard: no
corpus item dated on or after the case's order date). Parity goes first when a co-accused was granted bail, then
Appendix A order.
It is also the fallback when the orchestrator loops (plan §19): the same evidence packs, with none of the planning.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from vakeel_sahayak.agents.sutradhar.contracts_runtime import contract_for, is_optional
from vakeel_sahayak.agents.sutradhar.planning import companions, make_steps, slot_sources
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, SlotResult

if TYPE_CHECKING:
    from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent

MAX_ITEMS = 10  # items kept per slot (the router does not rank or filter, it only caps)


def run_fixed_router(state: CaseGraphState, agent: SutradharAgent | None = None) -> list[EvidencePack]:
    """Execute each applicable contract with templated queries.

    Args:
        state: the graph state (dossier, rights report, order date)
        agent: the Sutradhar whose tools, budget and log are used (default: one built from the state's case and switches)

    Returns:
        Evidence packs, one per applicable factor, in Appendix A order.
    """
    if agent is None:
        from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent

        agent = SutradharAgent(case_id=state.case_id, switches=state.switches, log=state.event_log())
    shells = agent.pick_factors(state)
    pctx = agent.plan_context(state)
    packs: list[EvidencePack] = []
    # fixed order: parity first when a co-accused was granted bail (the contract that most often decides a hearing), then Appendix A
    shells = sorted(shells, key=lambda p: (p.factor != Factor.PARITY_WITH_CO_ACCUSED, list(Factor).index(p.factor)))
    for shell in shells:
        if shell.stance == FactorStance.NOT_APPLICABLE:
            continue
        factor, contract = shell.factor, contract_for(shell.factor)
        slots: list[SlotResult] = []
        issues: list[str] = []
        found: dict[str, list[dict[str, Any]]] = {}

        def refs(token: str, found: dict[str, list[dict[str, Any]]] = found) -> list[str] | None:
            m = re.fullmatch(r"\$authority\.top(\d+)", token)
            docs = list(dict.fromkeys(str(i["doc_id"]) for i in found.get("authority", []) if i.get("doc_id")))
            return docs[: int(m.group(1))] if m else None

        with agent.factor_scope(factor):
            for name, slot in contract.slots.items():
                sources = slot_sources(contract, name, pctx)
                steps = (make_steps(factor, name, sources[0], pctx) if sources else []) + [s for t in companions(contract, name) for s in make_steps(factor, name, t, pctx)]
                items: list[dict[str, Any]] = []
                for step in steps:
                    got = agent.exec_step(step, factor, refs=refs).items
                    items.extend(i for i in got if not (i.get("court") and str(i.get("date") or "") >= pctx.before))  # the leakage rule is not optional
                found[name] = items
                status = SlotStatus.FILLED if items else SlotStatus.MISSING
                slots.append(SlotResult(slot=name, status=status, items=items[:MAX_ITEMS], note="fixed router: one templated call, no check" if items else "fixed router: nothing returned"))
                if not items and not is_optional(slot.need):
                    issues.append(f"No {name.replace('_', ' ')} retrieved for {factor.value} (fixed router: no re-planning).")
        agent._decision("fixed_router", f"{factor.value}: {sum(1 for s in slots if s.status == SlotStatus.FILLED)} of {len(slots)} slots returned something.", factor=factor.value)
        packs.append(EvidencePack(factor=factor, stance=shell.stance, reason=shell.reason, slots=slots, open_issues=issues))
    return packs
