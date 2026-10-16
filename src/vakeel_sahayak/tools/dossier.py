"""Tools in dossier (plan §7.1, §7.3, §7.4). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import AgentName, StoreName
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import SpanCheckResult


def extract_dossier(case_id: str, fields: list[str] | None = None) -> CaseDossier:
    """Fine-tuned Qwen3-4B extraction from the case shelf, with a quote per field. (plan §7.1)

    Reads the fields again with Peshkar's extraction (quote located, NLI span check, one re-extraction), writes what
    changed to the case record, and returns the dossier as it stands.

    Args:
        case_id: see behaviour
        fields: restrict to fields that failed the check

    Returns:
        CaseDossier.
    """
    from vakeel_sahayak.agents.base import AgentContext
    from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent, active_agent
    from vakeel_sahayak.tools.runtime import get_runtime

    agent = active_agent(case_id)
    if agent is not None:  # called from a running Peshkar: read with its own model, NLI client and budget
        return agent.extract_fields(None, fields)
    agent = PeshkarAgent(AgentContext(case_id=case_id, log=get_runtime().event_log(case_id)))
    try:
        return agent.extract_fields(None, fields)
    finally:
        agent.close()


def span_check(value: Any, quote: str) -> SpanCheckResult:
    """NLI test that the quote supports the value. (plan §7.1)

    The value is tested as a claim against the quote with the configured NLI client, at the dev-tuned `span_check`
    threshold (configs/thresholds.yaml `nli.span_check_min`). An empty quote supports nothing.

    Args:
        value: see behaviour
        quote: see behaviour

    Returns:
        SpanCheckResult.
    """
    from vakeel_sahayak.models.factory import get_nli
    from vakeel_sahayak.models.nli import nli_threshold

    if not isinstance(quote, str) or not quote.strip():
        return SpanCheckResult(supported=False, score=0.0, quote=quote if isinstance(quote, str) else "")
    nli = get_nli()
    verdict = nli.judge(quote, _claim(value), nli_threshold("span_check", nli))
    return SpanCheckResult(supported=verdict.supported, score=verdict.score, quote=quote)


def _claim(value: Any) -> str:
    """A value as a sentence for the NLI: strings as they are; objects and lists as their non-empty parts."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return ", ".join(f"{k} {_claim(v)}" for k, v in value.items() if v not in (None, ""))
    if isinstance(value, (list, tuple)):
        return "; ".join(_claim(v) for v in value)
    return str(value)


def rights_check(case_id: str, as_of: str | None = None) -> RightsReport:
    """Run the Rights Radar rules engine. (plan §7.3)

    Args:
        case_id: see behaviour
        as_of: see behaviour

    Returns:
        RightsReport.
    """
    from datetime import date

    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.rights.engine import RightsEngine
    from vakeel_sahayak.tools.runtime import get_runtime

    state = CaseState(case_id, get_runtime().event_log(case_id))
    return RightsEngine().run(state.dossier(), state.timeline(), as_of or date.today().isoformat())


def diff_case_state(case_id: str, since_hash: str | None = None) -> ChangeSet:
    """Diff current case state against the last approved state. (plan §7.4)

    The baseline is the case as it stood at counsel's last Gate 1 approval (or at Peshkar's last snapshot before any
    approval). The ChangeSet names the fields that need reading again: those whose value or status differs now, and
    those a newly filed document or timeline event speaks to (their `new_hash` may still equal `old_hash`; Peshkar
    drops those after re-extraction). Custody days follow the arrest date. The Rights Radar is not re-run here.

    Args:
        case_id: see behaviour
        since_hash: the approved dossier hash the caller holds; a mismatch with the baseline on record is an error

    Returns:
        ChangeSet (trigger 'new_document'); empty when there is no baseline yet, since nothing was built or approved.
    """
    from vakeel_sahayak.agents.peshkar import changes
    from vakeel_sahayak.agents.peshkar.fields import ALL_FIELDS
    from vakeel_sahayak.record import views
    from vakeel_sahayak.tools.case.docs import search_case_docs
    from vakeel_sahayak.tools.runtime import get_runtime

    events = get_runtime().event_log(case_id).read(case_id)
    base = changes.baseline(events, case_id)
    if base is None:
        return ChangeSet(case_id=case_id, trigger="new_document")
    if since_hash is not None and base.dossier_hash != since_hash:
        raise ValueError(f"no approved state with hash {since_hash!r} for case {case_id!r}")
    current = changes.field_hashes(views.fold_dossier_for(case_id, events))
    old = base.hashes
    names = {n for n in ALL_FIELDS if old.get(n) != current.get(n)}
    new_rows = [r for r in views.fold_timeline(events) if r.event_id not in base.event_ids]
    names |= changes.touched_by_events(new_rows)
    names |= changes.facts_written(events, base.index)
    new_chunks = changes.chunk_ids(events) - base.chunk_ids
    if new_chunks:
        names |= changes.touched_fields_by_search(case_id, new_chunks, lambda query, k: search_case_docs(case_id, query, None, k))
    if "arrest_date" in names:
        names |= changes.derived(names)
    else:  # the days only drift with the clock: that is the Rights Radar's job, not a change of the dossier
        names.discard("custody_days")
    fields = [FieldChange(field=n, old_hash=old.get(n), new_hash=current.get(n)) for n in ALL_FIELDS if n in names]
    return ChangeSet(case_id=case_id, trigger="new_document", fields=fields, new_event_ids=[r.event_id for r in new_rows])


EXTRACT_DOSSIER_SPEC = ToolSpec(
    name="extract_dossier",
    description="Fine-tuned Qwen3-4B extraction from the case shelf, with a quote per field.",
    agents=[AgentName.PESHKAR],
    stores=[StoreName.CASE_DOCS],
    plan_ref="§7.1",
)

SPAN_CHECK_SPEC = ToolSpec(
    name="span_check",
    description="NLI test that the quote supports the value.",
    agents=[AgentName.PESHKAR],
    stores=[],
    plan_ref="§7.1",
)

RIGHTS_CHECK_SPEC = ToolSpec(
    name="rights_check",
    description="Run the Rights Radar rules engine.",
    agents=[AgentName.PESHKAR, AgentName.VAKEEL, AgentName.SUTRADHAR],
    stores=[StoreName.CASE_TIMELINE, StoreName.CASE_FACTS],
    plan_ref="§7.3",
)

DIFF_CASE_STATE_SPEC = ToolSpec(
    name="diff_case_state",
    description="Diff current case state against the last approved state.",
    agents=[AgentName.PESHKAR],
    stores=[StoreName.CASE_FACTS, StoreName.CASE_TIMELINE],
    plan_ref="§7.4",
)
