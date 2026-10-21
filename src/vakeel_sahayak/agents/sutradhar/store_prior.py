"""S6 / B5: a learned store prior (`Switches.store_prior`), evaluation plan 3.3 (S6, A12 and B5, S6b).

A tiny router that says, per factor and case signature (section family, era, court), how likely each store is to hold what the
factor needs, and at what cost. Three modes:

* `off` (default): contracts decide everything; this module is never touched.
* `order` (S6, A12): inside each slot Sutradhar tries the contract's allowed stores in the prior's order instead of the contract's
  order. No allowed store is removed. A store whose probability falls below `prune_below` is *deferred* to the end of the slot's
  list (still reachable when the slot stays unfilled), so a prior can save calls but never lose a source (plan section 12.5: "never removes a contract-allowed store").
* `only` (B5, S6b): no contracts. The prior alone picks the top-k queryable stores per factor and the factor's generic queries run
  against them (`run_prior_only`); no slots, no stopping rule, no re-plan.

Papers and what was taken (adapted, not reproduced):

* Zhang et al., "AgentRouter: A Knowledge-Graph-Guided LLM Router for Collaborative Multi-Agent Question Answering", ACL 2026 (Long Papers),
  pp. 788-809, https://aclanthology.org/2026.acl-long.33/ (checked on the ACL Anthology page). Taken: routing probabilities over a
  set of candidates, learned from *observed candidate performance* as soft supervision. Changed: no graph network and no LLM agents
  to route among: our action space is about ten stores and twelve factors, so a hierarchical count model over the case signature
  (the "context" of the knowledge graph reduced to factor, section family, era, court) is enough and is auditable.
* Feng et al., "GraphRouter: A Graph-based Router for LLM Selections", ICLR 2025, https://iclr.cc/virtual/2025/poster/28926 (cited
  as in the evaluation plan): router as a prediction of performance and cost per (query, candidate). Taken: the utility
  `p(useful) - lambda * cost`. Changed: counts, not a GNN.
* Ong et al., "RouteLLM: Learning to Route LLMs with Preference Data", ICLR 2025,
  https://proceedings.iclr.cc/paper_files/paper/2025/hash/5503a7c69d48a2f86fc00b3dc09de686-Abstract-Conference.html: a
  cost-quality threshold decides when the cheap option is enough. Taken: the threshold idea (`prune_below`, deferral of weak candidates).
* Chen et al., "RouterDC: Query-Based Router by Dual Contrastive Learning for Assembling LLMs", NeurIPS 2024, and Yue et al.,
  "MasRouter: Learning to Route LLMs for Multi-Agent Systems", ACL 2025, pp. 15549-15572 (https://aclanthology.org/2025.acl-long.757/, page
  checked; authors Yue, Zhang, Liu, Wan, Wang, Cheng and Qi): learned routing from outcomes, related work only; nothing is taken beyond the framing.
  RouterDC's page was not re-checked.

Training uses no manual label. The ground truth is read off the court's own text of TRAIN-split orders (before 2024): whether the order
cites resolved precedents (gold G2), has prosecution and defence parts, states sections, events and fields (G3). `outcomes_from_orders`
turns each order into one `Outcome` per (factor the order argues, store); where the order gives no evidence either way the row is
skipped (unknown is not "useless"). Dev, test and blind rows are refused, so the prior never sees an evaluation order.
The trainer (`python -m vakeel_sahayak.agents.sutradhar.store_prior train ...`) is deterministic: same rows, same artefact bytes.

Honest limits: only about 17% of citation occurrences resolve, so the corpus stores' labels rest on a biased subset; costs are static
hand-set units unless the rows carry measured costs; with no artefact the prior is neutral (every store 0.5 and cost ignored, so the order is the contract's
and `trained` is False in the signals).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vakeel_sahayak.agents.sutradhar.planning import (
    FACTOR_LABEL,
    authority_query,
    make_steps,
    objection_query,
)
from vakeel_sahayak.agents.sutradhar.relaxation import offence_group
from vakeel_sahayak.contracts.loader import ALLOWED_STORES
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus, StoreName
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, PlanStep, SlotResult

if TYPE_CHECKING:
    from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent

SHRINK = 4.0  # pseudo-count of the parent estimate in the back-off chain
COST_WEIGHT = 0.05  # lambda in utility = p - lambda * cost
TRAIN_BEFORE = "2024-01-01"  # plan section 2: train is before 2024
EVAL_SPLITS = frozenset({"dev", "test", "blind", "unused"})
ONLY_TOP_K = 3  # stores B5 queries per factor
ONLY_MIN_UTILITY = 0.0
# relative cost of one call (corpus search with a reranker or embedding is dearer than a case lookup); hand-set unless rows carry `cost`
STORE_COST: dict[str, float] = {
    "caselaw.reasoning": 1.0, "caselaw.similar": 1.2, "caselaw.citations": 0.5, "advocacy.objections": 0.8, "advocacy.arguments": 0.8,
    "law.statutes": 0.3, "law.concordance": 0.3, "case.docs": 0.6, "case.timeline": 0.2, "case.facts": 0.2,
}
# B5 has no slot names: the stores it can ask by text or by case, with the pseudo-slot each call is filed under (the contracts' slot names)
ONLY_STORES: dict[StoreName, str] = {
    StoreName.CASELAW_REASONING: "authority", StoreName.CASELAW_SIMILAR: "similar_orders", StoreName.ADVOCACY_OBJECTIONS: "likely_objection",
    StoreName.ADVOCACY_ARGUMENTS: "argument_patterns", StoreName.CASE_DOCS: "case_docs", StoreName.CASE_TIMELINE: "custody_days",
    StoreName.CASE_FACTS: "antecedents", StoreName.LAW_STATUTES: "sections_text",
}  # the citation store takes document ids and the concordance a section, so neither is asked by text (as in B4)
ARTEFACT_NAME = "store_prior.json"


class StorePriorUnavailable(RuntimeError):
    """A training input is unusable (no usable rows)."""


@dataclass(frozen=True)
class PriorContext:
    """The case signature a prediction is made for."""

    factor: str
    family: str = "other"  # offence group of the section family ('cheating', 'theft', ...), else 'other'
    era: str = "unknown"  # 'bns' | 'ipc' | 'mixed' | 'unknown'
    court: str | None = None  # None when the case does not say (a level that is then skipped)


@dataclass(frozen=True)
class Outcome:
    """One training row: in an order that argued `factor`, was `store` useful (held what the court used)?"""

    factor: str
    store: str
    useful: bool
    family: str = "other"
    era: str = "unknown"
    court: str | None = None
    cost: float | None = None


def era_of(codes: Iterable[str]) -> str:
    """'bns' when only BNS/BNSS sections are charged, 'ipc' when only IPC/CrPC, 'mixed' when both, else 'unknown'."""
    new = any(c in ("BNS", "BNSS") for c in codes)
    old = any(c in ("IPC", "CRPC") for c in (str(x).upper() for x in codes))
    return "mixed" if new and old else "bns" if new else "ipc" if old else "unknown"


def context_for(factor: Factor, sig: Any, court: str | None = None) -> PriorContext:
    """The prior's context of a factor in a case (`sig` is the planner's `CaseSignals`)."""
    return PriorContext(factor=Factor(factor).value, family=offence_group(list(sig.refs)) or "other", era=era_of(sig.codes), court=court)


def _levels(ctx: PriorContext, store: str) -> list[str]:
    """Back-off keys from the broadest to the most specific."""
    keys = [f"S|{store}", f"F|{ctx.factor}|{store}", f"FM|{ctx.factor}|{ctx.family}|{store}", f"FME|{ctx.factor}|{ctx.family}|{ctx.era}|{store}"]
    if ctx.court:
        keys.append(f"FMEC|{ctx.factor}|{ctx.family}|{ctx.era}|{ctx.court}|{store}")
    return keys


@dataclass(frozen=True)
class Ranking:
    """A prior's answer for one context: the order to try, the deferred stores (last in the order) and every score."""

    order: list[str]
    deferred: list[str]
    scores: dict[str, float]  # store -> p(useful)
    utilities: dict[str, float]


class StorePrior:
    """Hierarchical count model of p(store useful | factor, section family, era, court), shrunk towards its parent level."""

    def __init__(self, counts: dict[str, list[float]] | None = None, costs: dict[str, float] | None = None, *, shrink: float = SHRINK,
                 prune_below: float | None = None, meta: dict[str, Any] | None = None) -> None:
        self.counts = {k: [float(v[0]), float(v[1])] for k, v in sorted((counts or {}).items())}
        self.costs = {**STORE_COST, **(costs or {})}
        self.shrink = shrink
        self.prune_below = prune_below
        self.meta = dict(meta or {})

    @property
    def trained(self) -> bool:
        """False for the neutral prior (no counts)."""
        return bool(self.counts)

    def p(self, ctx: PriorContext, store: StoreName | str) -> float:
        """Probability that `store` is useful for the factor in this context (0.5 with no data)."""
        name = getattr(store, "value", store)
        estimate = 0.5
        for key in _levels(ctx, str(name)):
            pos, n = self.counts.get(key, (0.0, 0.0))
            if key.startswith("S|"):
                estimate = (pos + 1.0) / (n + 2.0) if n else 0.5  # Laplace at the root
            else:
                estimate = (pos + self.shrink * estimate) / (n + self.shrink)
        return estimate

    def utility(self, ctx: PriorContext, store: StoreName | str) -> float:
        """p(useful) minus the weighted cost of the call."""
        name = str(getattr(store, "value", store))
        if not self.trained:
            return self.p(ctx, name)  # the neutral prior orders nothing: every store ties, so the contract order stands
        return self.p(ctx, name) - COST_WEIGHT * self.costs.get(name, 1.0)

    def rank(self, ctx: PriorContext, stores: Iterable[StoreName | str]) -> Ranking:
        """Order candidate stores by utility, best first; ties keep the given (contract) order. Below `prune_below` a store is deferred to the end."""
        names = [str(getattr(s, "value", s)) for s in stores]
        util = {s: self.utility(ctx, s) for s in names}
        prob = {s: self.p(ctx, s) for s in names}
        order = sorted(names, key=lambda s: (-util[s], names.index(s)))
        deferred: list[str] = []
        if self.prune_below is not None and len(order) > 1:
            weak = [s for s in order if prob[s] < self.prune_below]
            deferred = weak if len(weak) < len(order) else weak[1:]  # never defer every candidate: the best stays first
            order = [s for s in order if s not in deferred] + deferred
        return Ranking(order=order, deferred=deferred, scores={s: round(prob[s], 6) for s in names}, utilities={s: round(util[s], 6) for s in names})

    # ---------------------------------------------------------------- training and persistence

    @classmethod
    def train(cls, rows: Iterable[Outcome], *, shrink: float = SHRINK, prune_below: float | None = None) -> StorePrior:
        """Fit the counts from outcome rows (deterministic; no randomness).

        Raises:
            StorePriorUnavailable: no rows.
        """
        counts: dict[str, list[float]] = {}
        spent: dict[str, list[float]] = {}
        n = 0
        for r in rows:
            n += 1
            ctx = PriorContext(r.factor, r.family, r.era, r.court)
            for key in _levels(ctx, r.store):
                cell = counts.setdefault(key, [0.0, 0.0])
                cell[0] += 1.0 if r.useful else 0.0
                cell[1] += 1.0
            if r.cost is not None:
                cell = spent.setdefault(r.store, [0.0, 0.0])
                cell[0] += float(r.cost)
                cell[1] += 1.0
        if not n:
            raise StorePriorUnavailable("no training rows")
        costs = {s: round(c[0] / c[1], 6) for s, c in sorted(spent.items())}
        return cls(counts, costs, shrink=shrink, prune_below=prune_below, meta={"rows": n})

    @classmethod
    def neutral(cls, prune_below: float | None = None) -> StorePrior:
        """The prior with no data: every store 0.5 and cost ignored, so the order is the contract's."""
        return cls(prune_below=prune_below)

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "shrink": self.shrink, "prune_below": self.prune_below, "costs": dict(sorted(self.costs.items())),
                "counts": dict(sorted(self.counts.items())), "meta": self.meta}

    def digest(self) -> str:
        """Short SHA-256 of the artefact content (identifies the prior in run signals)."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()[:16]

    def save(self, path: str | Path) -> str:
        """Write the artefact (sorted keys, so equal priors are byte-identical); returns its digest."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), sort_keys=True, indent=1) + "\n", encoding="utf-8")
        return self.digest()

    @classmethod
    def load(cls, path: str | Path | None = None) -> StorePrior:
        """Read an artefact; a missing file gives the neutral prior (callers can see `trained` is False)."""
        p = Path(path) if path else default_artefact_path()
        if not p.is_file():
            return cls.neutral()
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls(data.get("counts"), data.get("costs"), shrink=float(data.get("shrink", SHRINK)), prune_below=data.get("prune_below"), meta=data.get("meta"))


def default_artefact_path() -> Path:
    """`<data dir>/eval/store_prior.json` (`VS_STORE_PRIOR` overrides the whole path)."""
    if os.environ.get("VS_STORE_PRIOR"):
        return Path(os.environ["VS_STORE_PRIOR"])
    from vakeel_sahayak.eval.runners.driver import REPO

    return Path(os.environ.get("VS_DATA_DIR") or REPO / "data") / "eval" / ARTEFACT_NAME


# ------------------------------------------------------------------------------------------------ labels from the court's text


def _gold(order: dict[str, Any], key: str) -> dict[str, Any]:
    g = (order.get("gold") or {}).get(key)
    return g if isinstance(g, dict) else {}


def _store_outcome(store: StoreName, order: dict[str, Any]) -> bool | None:
    """Was the store useful in this order, read off the court's text (True / False / None when the order gives no evidence)."""
    g2, g3, parts = _gold(order, "G2"), _gold(order, "G3"), order.get("parts") or {}
    if store in (StoreName.CASELAW_REASONING, StoreName.CASELAW_CITATIONS, StoreName.CASELAW_SIMILAR):  # proxy for similar: precedent-rich neighbours
        if g2.get("labels"):
            return True
        return None if g2.get("unresolved") or g2.get("raw") else (False if g2 else None)  # unresolved citations say nothing: only 17% resolve
    if store == StoreName.ADVOCACY_OBJECTIONS:
        return bool(str(parts.get("prosecution") or "").strip()) if parts else None
    if store == StoreName.ADVOCACY_ARGUMENTS:
        return bool(str(parts.get("defense") or parts.get("defence") or "").strip()) if parts else None
    if store == StoreName.LAW_STATUTES:
        return bool((g3.get("fields") or {}).get("sections")) if g3 else None
    if store == StoreName.LAW_CONCORDANCE:
        sections = (g3.get("fields") or {}).get("sections") if g3 else None
        if sections is None:
            return None
        codes = {str(x).split(" ")[0] for x in sections}
        new, old = bool(codes & {"BNS", "BNSS"}), bool(codes & {"IPC", "CrPC"})
        return (new and old) or (new and not order.get("bns_era", True)) or (old and bool(order.get("bns_era", False)))  # a mapping between the codes was needed
    if store == StoreName.CASE_TIMELINE:
        return bool(g3.get("events")) if g3 else None
    if store == StoreName.CASE_FACTS:
        return bool(g3.get("fields")) if g3 else None
    if store == StoreName.CASE_DOCS:
        return bool(str(order.get("facts_text") or "").strip()) if "facts_text" in order else None
    return None


def _usable(order: dict[str, Any]) -> bool:
    """TRAIN rows only: an evaluation split, or a date from 2024 on, is refused (the prior never sees dev, test or blind orders)."""
    split = str(order.get("split") or "").lower()
    if split in EVAL_SPLITS:
        return False
    if split == "train":
        return True
    date = str(order.get("date") or "")
    return bool(date) and date < TRAIN_BEFORE


def outcomes_from_orders(orders: Iterable[dict[str, Any]]) -> tuple[list[Outcome], dict[str, int]]:
    """Training rows from T1-style order records (`court`, `date`, optional `split`, `bns_era`, `gold` with G1, G2, G3, optional `parts`, `facts_text`).

    Args:
        orders: records of orders; only TRAIN ones count

    Returns:
        (rows, stats) with stats `orders`, `used`, `refused` (not TRAIN), `rows`, `unknown` (store/factor pairs skipped for lack of evidence).
    """
    rows: list[Outcome] = []
    stats = {"orders": 0, "used": 0, "refused": 0, "rows": 0, "unknown": 0}
    for order in orders:
        stats["orders"] += 1
        if not _usable(order):
            stats["refused"] += 1
            continue
        stats["used"] += 1
        sections = list(((_gold(order, "G3").get("fields") or {}).get("sections")) or order.get("sections") or [])
        family = offence_group([str(s) for s in sections]) or "other"
        codes = {str(s).split(" ")[0].upper() for s in sections}
        era = era_of(codes) if codes else ("bns" if order.get("bns_era") else "ipc" if "bns_era" in order else "unknown")
        for label in _gold(order, "G1").get("labels") or []:
            try:
                factor = Factor(label).value
            except ValueError:
                continue
            for store in ONLY_STORES:
                outcome = _store_outcome(store, order)
                if outcome is None:
                    stats["unknown"] += 1
                    continue
                rows.append(Outcome(factor, store.value, outcome, family, era, order.get("court")))
                stats["rows"] += 1
    return rows, stats


def train_from_file(orders_path: str | Path, out_path: str | Path | None = None, *, prune_below: float | None = None) -> dict[str, Any]:
    """Train from a JSON-lines file of order records and save the artefact; returns the stats and the digest."""
    records = [json.loads(line) for line in Path(orders_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    rows, stats = outcomes_from_orders(records)
    prior = StorePrior.train(rows, prune_below=prune_below)
    prior.meta.update(stats)
    path = Path(out_path) if out_path else default_artefact_path()
    return {**stats, "digest": prior.save(path), "path": str(path)}


# ------------------------------------------------------------------------------------------------ signals


def order_signals(work: Any, prior: StorePrior, spent_calls: int) -> dict[str, Any]:
    """Per-factor signals of `order` mode from the factor's work record: stores queried, calls saved, slot-fill rate, regret.

    `calls saved` and `regret` are estimates against the contract order: for each filled slot, the position of the store that filled
    it in the contract order minus its position in the prior's order (saved when the prior put it earlier, regret when later).
    """
    trace = work.prior_trace
    required = [sw for sw in work.slots.values() if sw.required]
    filled = [sw for sw in required if sw.status == SlotStatus.FILLED]
    saved = regret = 0
    queried: set[str] = set()
    for name, sw in work.slots.items():
        t = trace.get(name)
        if not t or not sw.sources:
            continue
        used = [str(getattr(s, "value", s)) for s in sw.sources[: sw.src_idx + 1]]
        queried.update(u for u in used if u in t["contract"])
        if sw.status == SlotStatus.FILLED and used and used[-1] in t["contract"]:
            delta = t["contract"].index(used[-1]) - t["prior"].index(used[-1])
            saved += delta
            regret += max(0, -delta)
    return {
        "mode": "order", "trained": prior.trained, "artefact": prior.digest(), "stores_queried": sorted(queried), "store_calls": int(spent_calls),
        "calls_saved": saved, "regret": regret, "slot_fill_rate": round(len(filled) / len(required), 4) if required else 1.0,
        "slots": {n: {"contract": t["contract"], "prior": t["prior"], "deferred": t["deferred"]} for n, t in sorted(trace.items())},
    }


# ------------------------------------------------------------------------------------------------ B5: the prior alone


def run_prior_only(agent: SutradharAgent, state: CaseGraphState, prior: StorePrior, *, top_k: int = ONLY_TOP_K) -> list[EvidencePack]:
    """B5 / S6b: no contracts. For each applicable factor the prior ranks the queryable stores; the top `top_k` (utility above `ONLY_MIN_UTILITY`,
    at least one) are queried once with the factor's generic query; each result is filed as a slot named after the store's pseudo-slot.

    No sufficiency check, re-plan or open issues. Honours A10 knock-outs and the store-call budget (a call past it comes back as an error and the slot is MISSING).
    """
    shells = agent.pick_factors(state)
    pctx = agent.plan_context(state)
    packs: list[EvidencePack] = []
    for shell in shells:
        if shell.stance == FactorStance.NOT_APPLICABLE:
            continue
        factor = shell.factor
        ctx = context_for(factor, pctx.sig)
        candidates = [s for s in ONLY_STORES if agent.switches.store_allowed(s)]
        ranking = prior.rank(ctx, candidates)
        chosen = [s for s in ranking.order if ranking.utilities[s] > ONLY_MIN_UTILITY][:top_k] or ranking.order[:1]
        contract_stores = sorted(s.value for s in ALLOWED_STORES[factor])
        slots: list[SlotResult] = []
        queried: list[str] = []
        for name in chosen:
            store = StoreName(name)
            slot = ONLY_STORES[store]
            query = objection_query(factor) if store == StoreName.ADVOCACY_OBJECTIONS else authority_query(factor, pctx)
            steps: list[PlanStep] = make_steps(factor, slot, store, pctx, query=query)
            items: list[dict[str, Any]] = []
            with agent.factor_scope(factor):
                for step in steps:
                    items.extend(i for i in agent.exec_step(step, factor).items if not (i.get("court") and str(i.get("date") or "") >= pctx.before))
            queried.append(name)
            slots.append(SlotResult(slot=slot, status=SlotStatus.FILLED if items else SlotStatus.MISSING, items=items[:10],
                                    note=f"B5: store prior p={ranking.scores[name]:.2f}, one call, no check"))
        skipped = [s for s in contract_stores if s not in queried]
        signal = {
            "mode": "only", "trained": prior.trained, "artefact": prior.digest(), "stores_queried": sorted(queried),
            "store_calls": len(queried), "calls_saved": len(contract_stores) - len(queried),
            "slot_fill_rate": round(sum(1 for s in slots if s.status == SlotStatus.FILLED) / len(slots), 4) if slots else 0.0,
            "contract_stores_skipped": skipped, "expected_regret": round(sum(prior.p(ctx, s) for s in skipped if s in {x.value for x in ONLY_STORES}), 6),
            "scores": ranking.scores,
        }
        agent.retrieval_signals[factor.value] = {"factor": factor.value, "store_prior": signal}
        agent._decision("store_prior", f"{factor.value}: B5 queried {', '.join(queried)}.", factor=factor.value, **signal)
        packs.append(EvidencePack(factor=factor, stance=shell.stance, reason=shell.reason, slots=slots,
                                  open_issues=[] if any(s.status == SlotStatus.FILLED for s in slots) else [f"Nothing retrieved for {FACTOR_LABEL[factor]} (B5)."]))
    return packs


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.agents.sutradhar.store_prior train --orders FILE [--out FILE] [--prune-below P]`."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "train" or "--orders" not in args:
        print("usage: store_prior train --orders ORDERS.jsonl [--out ARTEFACT.json] [--prune-below P]")
        return 2

    def opt(name: str) -> str | None:
        return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None

    prune = opt("--prune-below")
    print(json.dumps(train_from_file(str(opt("--orders")), opt("--out"), prune_below=float(prune) if prune else None), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
