"""S2: adaptive retrieval depth per factor, in the manner of Adaptive-RAG (evaluation plan 3.3, variant S2).

Switch: `Switches.retrieval_policy` = 'contract' (default, the current behaviour) or 'adaptive' (S2).

Paper and what we took
----------------------
* Soyeong Jeong, Jinheon Baek, Sukmin Cho, Sung Ju Hwang, Jong C. Park. "Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large
  Language Models through Question Complexity". NAACL 2024 (Long Papers), pp. 7036-7050. https://aclanthology.org/2024.naacl-long.389/
  Taken: pick the retrieval strategy per query from its complexity: no retrieval, single-step retrieval or multi-step (iterative)
  retrieval, so simple queries do not pay for the iterative loop.

What we changed, and why
------------------------
Adaptive-RAG trains a small classifier on silver labels (which strategy answered correctly) to predict the complexity of a question.
We train nothing (no labels and no compute for it); the class of a factor is a deterministic rule (`classify`) over features read from
the factor's evidence contract, its stance and the dossier / Rights Radar signals:

* none: the factor needs no corpus retrieval. Either the contract has no required corpus slot, or a statutory right decides it on its
  face (the Rights Radar `undertrial_limit` check is ELIGIBLE, s.479 BNSS / s.436A CrPC) and no citation check is required. The corpus
  slots are skipped (recorded as MISSING with a note, not an open issue); the case and law lookups still run.
* single: one corpus slot is required, it needs at most one paragraph, no citation check is required, the factor is not adverse and the
  case is not BNS-era. One plan round, no corrective re-plan.
* multi: otherwise (a required citation slot such as good_law or sc_root, which depends on the first retrieval; an adverse factor to
  answer; an authority slot needing two or more paragraphs; or a BNS/BNSS case, where precedents are mostly written in IPC/CrPC terms
  and filters usually need relaxing). The full loop with the contract's budget.

Caps: none and single run one round; their store-call budget is capped (none: two calls plus one per non-corpus slot; single: four);
multi keeps the contract budget and the agent's round limit. The caps only shrink the budget, never raise it. A claim that fails its
check is re-retrieved at full depth. The plan's "slots filled by case.docs" feature is covered by the 'none' class (a case-record-only
factor); unlike Adaptive-RAG there is no per-query classifier, so a misclassified factor can stop short, which the per-factor signals
(`depth`, rounds, store calls, open issues) make measurable against the full loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.sutradhar.contracts_runtime import is_optional, required_count
from vakeel_sahayak.contracts.models import EvidenceContract
from vakeel_sahayak.schemas.enums import Factor, FactorStance, StoreName

NONE, SINGLE, MULTI = "none", "single", "multi"
LEVELS = (NONE, SINGLE, MULTI)
SINGLE_CALLS = 4
BNS_CODES = {"BNS", "BNSS"}
_CORPUS = {StoreName.CASELAW_REASONING, StoreName.CASELAW_SIMILAR, StoreName.CASELAW_CITATIONS, StoreName.ADVOCACY_OBJECTIONS, StoreName.ADVOCACY_ARGUMENTS}
# factor -> (Rights Radar check, statuses) under which a statute decides the factor on its face
DECISIVE_RIGHTS: dict[Factor, tuple[str, frozenset[str]]] = {Factor.UNDERTRIAL_PERIOD: ("undertrial_limit", frozenset({"ELIGIBLE"}))}


@dataclass(frozen=True)
class Depth:
    """The retrieval depth chosen for one factor and what it rests on."""

    level: str
    max_rounds: int | None  # None: the agent's own limit
    store_calls: int | None  # cap below the contract budget; None: the contract's budget
    reasons: tuple[str, ...] = ()
    features: dict[str, Any] = field(default_factory=dict)
    skip_corpus: bool = False

    def as_signal(self) -> dict[str, Any]:
        return {"level": self.level, "max_rounds": self.max_rounds, "store_calls_cap": self.store_calls, "reasons": list(self.reasons), "features": dict(self.features)}


def _stores(slot: Any) -> list[StoreName]:
    return [StoreName(s) for s in slot.stores]


def features_of(factor: Factor, contract: EvidenceContract, stance: FactorStance, sig: Any) -> dict[str, Any]:
    """The rule features: required corpus slots, largest paragraph need, citation slot, adverse stance, BNS-era, decisive statute."""
    corpus = {n: s for n, s in contract.slots.items() if not is_optional(s.need) and any(st in _CORPUS for st in _stores(s))}
    citation = [n for n, s in corpus.items() if _stores(s) and all(st == StoreName.CASELAW_CITATIONS for st in _stores(s))]
    decisive = DECISIVE_RIGHTS.get(Factor(factor))
    status = (getattr(sig, "rights", {}) or {}).get(decisive[0]) if decisive else None
    return {
        "required_corpus_slots": sorted(corpus), "citation_slots": citation,
        "max_need": max((required_count(s.need) for s in corpus.values()), default=0),
        "adverse": stance == FactorStance.ADVERSE,
        "bns_era": bool(getattr(sig, "codes", set()) & BNS_CODES),
        "decisive_statute": bool(decisive and status and status[0] in decisive[1]),
        "non_corpus_slots": sorted(n for n in contract.slots if n not in corpus and not any(st in _CORPUS for st in _stores(contract.slots[n]))),
    }  # fmt: skip


def classify(factor: Factor, contract: EvidenceContract, stance: FactorStance, sig: Any) -> Depth:
    """Deterministic complexity class of a factor: none / single / multi (see the module docstring for the rules)."""
    f = features_of(factor, contract, stance, sig)
    cheap = 2 + len(f["non_corpus_slots"])
    if f["decisive_statute"] and not f["citation_slots"]:
        return Depth(NONE, 1, cheap, ("a statute decides the factor on its face (Rights Radar)",), f, skip_corpus=True)
    if not f["required_corpus_slots"]:
        return Depth(NONE, 1, cheap, ("no corpus slot is required: the case records fill the contract",), f, skip_corpus=True)
    why = []
    if f["citation_slots"]:
        why.append("a citation check depends on the first retrieval")
    if f["adverse"]:
        why.append("an adverse factor the State will raise")
    if f["max_need"] >= 2:
        why.append(f"an authority slot needs {f['max_need']} paragraphs")
    if f["bns_era"]:
        why.append("BNS-era case: precedents are in IPC/CrPC terms, filters usually need relaxing")
    if why:
        return Depth(MULTI, None, None, tuple(why), f)
    return Depth(SINGLE, 1, SINGLE_CALLS, ("one corpus slot needing one paragraph, favourable, not BNS-era",), f)


def corpus_slot_names(contract: EvidenceContract) -> list[str]:
    """Slots read from the corpus stores (the ones a 'none' factor skips)."""
    return [n for n, s in contract.slots.items() if any(st in _CORPUS for st in _stores(s))]


def signals(work: Any, store_calls: int, tokens: int) -> dict[str, Any]:
    """The per-factor depth signals for `retrieval_signals[factor]['depth']`: class, caps, rounds and calls actually used."""
    d: Depth = work.depth
    out = d.as_signal()
    out.update({"rounds": work.round, "store_calls": store_calls, "tokens": tokens, "stopped": work.stopped, "skipped_slots": sorted(n for n, sw in work.slots.items() if sw.skipped)})
    return out
