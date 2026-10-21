"""Working state of one factor's retrieval, and the words of its open issues (plan §6.2).

`SlotWork` remembers, per slot, what was asked, what came back and which moves (reword, relax, follow the citation
graph, another store) are already used, so a re-plan never repeats itself and the open issue can say exactly what was
widened. `FactorWork` holds the slots of one factor, the SC roots found and the authorities found to be overruled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from vakeel_sahayak.agents.sutradhar.contracts_runtime import is_optional, required_count
from vakeel_sahayak.agents.sutradhar.factor_pick import CaseSignals
from vakeel_sahayak.agents.sutradhar.planning import FACTOR_LABEL, ISSUE_TEXT, PlanContext
from vakeel_sahayak.agents.sutradhar.relaxation import RELAXATION_ORDER
from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import PlanStep, RetrievalPlan, SlotResult

if TYPE_CHECKING:
    from vakeel_sahayak.agents.sutradhar.sufficiency import StoppingTrace

SHORT_FACTOR: dict[Factor, str] = {
    Factor.GRAVITY_AND_PUNISHMENT: "gravity",
    Factor.CUSTODY_PERIOD: "custody-period",
    Factor.CHARGE_SHEET_FILED: "charge-sheet",
    Factor.TRIAL_DELAY: "trial-delay",
    Factor.PARITY_WITH_CO_ACCUSED: "parity",
    Factor.ANTECEDENTS: "antecedents",
    Factor.FLIGHT_RISK: "flight-risk",
    Factor.WITNESS_TAMPERING: "witness-tampering",
    Factor.WEAK_PRIMA_FACIE: "weak-prima-facie",
    Factor.HEALTH_AGE_FAMILY: "health, age and family",
    Factor.STATUTORY_BAR: "statutory-bar",
    Factor.UNDERTRIAL_PERIOD: "undertrial-period",
}
SLOT_NOUN: dict[str, str] = {
    "authority": "authority",
    "conditions": "authority on conditions",
    "good_law": "good-law check",
    "sc_root": "Supreme Court authority behind the High Court paragraph",
    "likely_objection": "recorded State objection",
    "argument_patterns": "defence argument pattern",
    "co_accused_order": "co-accused's bail order",
    "role_comparison": "comparison of the roles",
    "charge_sheet_date": "charge-sheet date",
    "trial_stage": "trial stage",
    "witness_examination": "record of which witnesses were examined",
    "fir_allegations": "FIR allegations",
    "custody_days": "custody-days record",
    "statutory_position": "statutory position",
    "antil_category": "Antil category",
    "bar_provision": "bar provision",
    "statute_text": "statute text",
    "sections_text": "text of the sections charged",
    "s480_proviso": "BNSS s.480 proviso",
    "rights_report": "Rights Radar entry",
    "personal_papers": "medical or personal papers",
    "community_roots": "roots in the community",
}


@dataclass
class SlotWork:
    """What Sutradhar has done for one slot."""

    name: str
    need: str | int
    sources: list[Any]  # StoreName or tool names, in the order they are tried
    src_idx: int = 0
    orig: list[PlanStep] | None = None  # the slot's calls as first planned, before any relaxation (None: not planned yet)
    level: int = -1  # how far the filters are relaxed: -1 none, 0 factor, 1 + section family, 2 + court (cumulative)
    tried_queries: list[str] = field(default_factory=list)
    widened: list[str] = field(default_factory=list)  # words for the open issue ('widened to all cheating offences')
    done: set[str] = field(default_factory=set)  # moves used: 'reword', 'relax:0', 'sc_follow', 'more_docs'
    mode: str = "normal"  # normal | sc_follow
    docs_level: int = 3  # how many authorities a citation slot checks
    items: list[dict[str, Any]] = field(default_factory=list)  # everything retrieved for the slot (de-duplicated by the rules)
    result: SlotResult | None = None
    pending: bool = True  # to be run in the next plan
    exhausted: bool = False
    errors: list[str] = field(default_factory=list)
    calls: int = 0
    # S1 (self_critique): the critic's cached verdicts per paragraph, discarded paragraphs, the pending corrective action and actions taken
    verdicts: dict[str, dict[str, Any]] = field(default_factory=dict)
    discarded: set[str] = field(default_factory=set)
    critic_action: str | None = None
    critic_used: list[str] = field(default_factory=list)
    skew_last: dict[str, Any] | None = None  # S4: skew statistics of the slot's latest scored search ({n, gini, top_gap, weak})
    skipped: bool = False  # S2: a corpus slot of a factor whose adaptive depth is 'none' (not retrieved, not an open issue)

    @property
    def required(self) -> bool:
        return not is_optional(self.need)

    @property
    def relaxed_names(self) -> tuple[str, ...]:
        return tuple(RELAXATION_ORDER[: self.level + 1])

    @property
    def status(self) -> SlotStatus:
        return self.result.status if self.result else SlotStatus.MISSING

    @property
    def source(self) -> Any:
        return self.sources[self.src_idx] if self.src_idx < len(self.sources) else None


def _new_critique() -> Any:
    from vakeel_sahayak.agents.sutradhar.critique import CritiqueTrace

    return CritiqueTrace()


def _new_trace() -> StoppingTrace:
    from vakeel_sahayak.agents.sutradhar.sufficiency import StoppingTrace

    return StoppingTrace()


@dataclass
class FactorWork:
    """Working state of one factor's retrieval."""

    factor: Factor
    stance: FactorStance
    reason: str | None
    contract: EvidenceContract
    pctx: PlanContext
    slots: dict[str, SlotWork] = field(default_factory=dict)
    round: int = 1
    unavailable: set[str] = field(default_factory=set)  # stores that failed or are knocked out
    budget_hit: bool = False
    stopped: str | None = None  # filled | budget | exhausted | max_rounds | depth_cap | rater_sufficient
    roots: set[str] = field(default_factory=set)  # Supreme Court roots found in the citation graph
    overruled: dict[str, str] = field(default_factory=dict)  # authority doc -> the judgment that overruled it
    avoid: set[str] = field(default_factory=set)  # authorities a failed claim must not be built on again
    plans: list[RetrievalPlan] = field(default_factory=list)
    only: set[str] | None = None  # re-run only these slots (a failed claim's re-retrieval)
    fresh: list[dict[str, Any]] = field(default_factory=list)  # reasoning paragraphs found since the last share
    stopping: StoppingTrace = field(default_factory=lambda: _new_trace())  # S3: what the stopping rule did
    critique: Any = field(default_factory=lambda: _new_critique())  # S1: what the retrieval critic did (CritiqueTrace)
    depth: Any = None  # S2: the `depth.Depth` chosen for the factor (None when retrieval_policy is not 'adaptive')
    graph: dict[str, Any] = field(default_factory=lambda: {"calls": 0, "hits": 0, "sc_hits": 0, "docs": set()})  # S5: expansion counters
    skew: dict[str, Any] = field(default_factory=lambda: {"scored_calls": 0, "weak_flags": 0, "downgrades": 0, "calls": []})  # S4 trace
    round_cap: int | None = None  # S2: plan rounds this factor may use (None: the agent's limit)
    prior_trace: dict[str, dict[str, Any]] = field(default_factory=dict)  # S6: per slot {contract, prior, deferred} store orders (empty unless store_prior='order')

    @property
    def sig(self) -> CaseSignals:
        return self.pctx.sig

    def unfilled_required(self) -> list[SlotWork]:
        """Required slots that are not FILLED."""
        return [sw for sw in self.slots.values() if sw.required and sw.status != SlotStatus.FILLED and (self.only is None or sw.name in self.only)]

    def all_required_filled(self) -> bool:
        return not self.unfilled_required()


def open_issue(work: FactorWork, sw: SlotWork) -> str | None:
    """The open issue a required slot that is not FILLED becomes (plan §6.2 step 2.5), in the plan's wording.

    Example: 'No parity authority in the same section family; widened to all cheating offences.'
    """
    result = sw.result
    if not sw.required or result is None or result.status == SlotStatus.FILLED:
        return None
    if sw.name in ISSUE_TEXT:
        return ISSUE_TEXT[sw.name]
    noun = SLOT_NOUN.get(sw.name, sw.name.replace("_", " "))
    short = SHORT_FACTOR[work.factor]
    if sw.name in ("authority", "conditions", "likely_objection", "argument_patterns"):
        noun = f"{short} {noun}" if sw.name == "authority" else f"{noun} for {short}"
    else:
        noun = f"{noun} for {short}"
    weak = result.status == SlotStatus.WEAK
    head = f"Only {result.note.split(';')[0]} {noun} found" if weak and result.note else (f"Weak evidence for {noun}" if weak else f"No {noun}")
    if not weak and sw.name in ("authority", "conditions", "good_law", "sc_root", "likely_objection") and work.pctx.family:
        head += " in the same section family"
    tail: list[str] = []
    if sw.widened:
        tail.append("; ".join(sw.widened))
    unavailable = [str(getattr(s, "value", s)) for s in sw.sources if str(getattr(s, "value", s)) in work.unavailable]
    if unavailable and not tail:
        tail.append(f"store {', '.join(unavailable)} unavailable in this run")
    if work.budget_hit and not tail:
        tail.append("the factor's store-call budget was spent")
    if not sw.sources:
        tail.append("no allowed store is available in this run")
    if not tail and sw.errors:
        tail.append(sw.errors[-1])
    return head + ("; " + "; ".join(tail) if tail else "") + "."


def plan_assessment(work: FactorWork) -> dict[str, str]:
    """The `assessment` field of a RetrievalPlan: slot -> 'FILLED' | 'WEAK (1 of 2)' | 'MISSING'."""
    out: dict[str, str] = {}
    for name, sw in work.slots.items():
        r = sw.result
        if r is None:
            continue
        if r.status == SlotStatus.WEAK and r.note:
            out[name] = f"WEAK ({r.note.split(';')[0]})"
        else:
            out[name] = r.status.value
    return out


def label_of(factor: Factor) -> str:
    return FACTOR_LABEL[Factor(factor)]


def needed(sw: SlotWork) -> int:
    return required_count(sw.need)
