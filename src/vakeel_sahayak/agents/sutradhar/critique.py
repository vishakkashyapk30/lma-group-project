"""S1: retrieval critique with corrective re-retrieval, in the manner of Self-RAG and CRAG (evaluation plan 3.3, variant S1).

Switch: `Switches.retrieval_policy` = 'contract' (default, the current behaviour) or 'self_critique' (S1).

Papers and what we took
-----------------------
* Akari Asai, Zeqiu Wu, Yizhong Wang, Avirup Sil, Hannaneh Hajishirzi. "Self-RAG: Learning to Retrieve, Generate, and Critique
  through Self-Reflection". ICLR 2024. https://openreview.net/forum?id=hSyW5go0v8 (preprint https://arxiv.org/abs/2310.11511).
  Taken: judging every retrieved passage on its own for relevance and for whether it supports the need ("reflection token"
  verdicts), and letting the verdicts decide what to do next instead of a fixed pipeline.
* Shi-Qi Yan, Jia-Chen Gu, Yun Zhu, Zhen-Hua Ling. "Corrective Retrieval Augmented Generation" (CRAG). arXiv:2401.15884, 2024
  (preprint; no venue found). https://arxiv.org/abs/2401.15884. Taken: a retrieval evaluator whose overall judgment of the
  retrieved set (correct / ambiguous / incorrect) triggers a corrective action; here correct = FILLED, ambiguous = WEAK,
  incorrect = MISSING.

What we changed, and why
------------------------
Neither paper's mechanism is reproduced. Self-RAG trains the language model to emit reflection tokens and CRAG fine-tunes a T5
evaluator; we train nothing (no compute and no labels for it), so the critic is a prompted call to the agents model
(`sutradhar.critique_slot`, schema `SlotCritique`) with per-paragraph verdicts `relevant` and `support` (full / partial / none).
Offline it is a deterministic rule (`critique_data`: factor tag or factor terms for relevance, section-family overlap for full
support), which is not a language model. CRAG's actions are web search and document decomposition; we have no web search, so the
corrective actions are the ones our stores allow: requery (reword), relax (give up the next filter), switch_store, discard
(drop the irrelevant paragraphs, then requery) or keep. The critic replaces the rule checks of `assess_slot` only for corpus
(court paragraph) slots; the hard guards stay rules, not model calls: a paragraph that is not court reasoning (or the right
submission part), is dated on or after the case, or whose authority is overruled never reaches the critic. Case-document,
statute, timeline and citation slots keep their rule checks. The contract (slots, stores, budgets) is unchanged, so this is
"critic-driven assessment and next move inside the contract", not a free-running critic loop; the plan's falsification
question (is the contract-driven loop no worse than a generic critic loop) is answered by comparing S1 with Full.

Budget: a critic call is charged to the factor's token budget; it is skipped (the rules assess the slot) once the factor's budget
is spent, a failed call falls back to the rules, each paragraph is judged once (verdicts are cached for the factor), and a slot
with nothing retrieved is MISSING without a call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.sutradhar.contracts_runtime import required_count
from vakeel_sahayak.agents.sutradhar.planning import item_key
from vakeel_sahayak.agents.sutradhar.prompts import TASK_CRITIQUE, USER_PROMPT_TEMPLATES, SlotCritique
from vakeel_sahayak.agents.sutradhar.slot_rules import FACTOR_TERMS, _family_overlap, assess_slot
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.schemas.enums import SlotStatus, StoreName
from vakeel_sahayak.schemas.retrieval_plan import SlotResult

MAX_JUDGED = 12  # new paragraphs shown to the critic per call
TEXT_CHARS = 300
ACTIONS = ("keep", "requery", "relax", "switch_store", "discard")
# critic action -> the re-plan moves that carry it out, best first (the rest of the rule ladder follows)
ACTION_MOVES: dict[str, list[str]] = {
    "requery": ["reword"],
    "discard": ["reword"],
    "relax": ["relax:0", "relax:1", "relax:2"],
    "switch_store": ["other_store", "sc_follow"],
}
_CORPUS_STORES = (StoreName.CASELAW_REASONING, StoreName.ADVOCACY_OBJECTIONS, StoreName.ADVOCACY_ARGUMENTS)
_GUARD_RELAXED = ("factor", "section_family", "plain")  # skip only the tag and family checks; part, date and good-law guards stay


@dataclass
class CritiqueTrace:
    """What the critic did for one factor (kept on `FactorWork`; emitted as `retrieval_signals[factor]['critique']`)."""

    calls: int = 0
    failures: int = 0
    skipped_budget: int = 0
    judged: int = 0
    relevant: int = 0
    supported: int = 0  # relevant and fully supported
    not_relevant: int = 0
    actions: list[dict[str, Any]] = field(default_factory=list)  # one entry per assessed round and slot
    re_retrievals: int = 0  # corrective moves actually applied


def is_corpus_slot(sw: Any, items: list[dict[str, Any]]) -> bool:
    """True for a slot filled from court paragraphs (the critic's scope): it reads a corpus store or already holds paragraphs."""
    if any(i.get("para") is not None for i in items):
        return True
    try:
        return StoreName(sw.source) in _CORPUS_STORES
    except ValueError:  # a tool name such as 'search_statutes', not a store
        return False


def choose_action(correct: int, relevant: int, judged: int, need: int, used: list[str]) -> str:
    """The rule that picks the corrective action from the counts (the offline critic, the fallback for a model's 'keep' on a short slot).

    keep when enough paragraphs are relevant and fully supported. Otherwise a slot with relevant paragraphs (CRAG: ambiguous)
    relaxes a filter first, then requeries, then switches store; a slot with none relevant (incorrect) discards what it has (once),
    requeries, relaxes, then switches store. An action already taken is not chosen again until all are used (then switch_store).
    """
    if correct >= max(need, 1):
        return "keep"
    order = ["relax", "requery", "switch_store"] if relevant > 0 else ["discard", "requery", "relax", "switch_store"]
    if judged == 0:
        order = [a for a in order if a != "discard"]
    for action in order:
        if action not in used:
            return action
    return "switch_store"


def passage_verdict(passage: dict[str, Any], factor: str) -> tuple[bool, str]:
    """The offline reflection verdict on one paragraph: (relevant, support). Not a language model."""
    text = str(passage.get("text") or "").lower()
    tagged = factor in (passage.get("tags") or [])
    relevant = bool(passage.get("via")) or tagged or any(t in text for t in FACTOR_TERMS.get(factor, ()))
    if not relevant:
        return False, "none"
    return True, "full" if passage.get("in_family", True) else "partial"


def critique_data(case: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """Offline handler body of `sutradhar.critique_slot`: deterministic verdicts and action from the paragraphs shown and the cached counts."""
    factor = str(case.get("factor") or "")
    verdicts, correct, relevant = [], int(case.get("cached_correct", 0)), int(case.get("cached_relevant", 0))
    judged = int(case.get("cached_judged", 0))
    for p in corpus.get("passages", []):
        rel, support = passage_verdict(p, factor)
        verdicts.append({"id": p["id"], "relevant": rel, "support": support})
        judged += 1
        relevant += rel
        correct += rel and support == "full"
    action = choose_action(correct, relevant, judged, int(case.get("need", 1)), list(case.get("used") or []))
    return {"verdicts": verdicts, "action": action, "reason": f"{correct} fully supported, {relevant} relevant of {judged} judged"}


def _passage(item: dict[str, Any], family: list[str]) -> dict[str, Any]:
    tags = [str(getattr(f, "value", f)) for f in item.get("factors") or []]
    return {
        "id": item_key(item), "text": str(item.get("text") or "")[:TEXT_CHARS], "tags": tags, "via": bool(item.get("via")),
        "in_family": (not family) or _family_overlap(item.get("section_family") or [], family),
    }  # fmt: skip


def critique_assess(agent: Any, work: Any, sw: Any, items: list[dict[str, Any]]) -> SlotResult | None:
    """Assess one corpus slot with the critic (replaces `assess_slot` for it); None when the rules must do it (no critic answer, budget spent).

    Hard guards first (rules): part, date and good-law checks via `assess_slot` with the tag and family checks skipped. The guarded
    paragraphs not yet judged go to the critic once; verdicts are cached on the slot. Status: FILLED when at least `need` paragraphs are
    relevant and fully supported, WEAK when some are relevant, else MISSING. The corrective action is stored on the slot
    (`sw.critic_action`) for the re-plan and recorded in the factor's trace.
    """
    trace: CritiqueTrace = work.critique
    pctx = work.pctx
    family = list(pctx.family or [])
    need = required_count(sw.need)
    guard = assess_slot(sw.name, items, sw.need, pctx.before, work.factor, family, relaxed=_GUARD_RELAXED)
    candidates = [i for i in guard.items if item_key(i) not in sw.discarded]
    new = [i for i in candidates if item_key(i) not in sw.verdicts][:MAX_JUDGED]
    critique: SlotCritique | None = None
    if new:
        if agent._budget_spent(work):
            trace.skipped_budget += 1
            agent._decision("critic_skipped", f"{work.factor.value}/{sw.name}: factor budget spent; the rules assess the slot.", factor=work.factor.value, slot=sw.name)
            return None
        cached = [v for k, v in sw.verdicts.items() if any(item_key(i) == k for i in candidates)]
        case = {
            "factor": work.factor.value, "slot": sw.name, "need": need, "used": list(sw.critic_used),
            "cached_judged": len(cached), "cached_relevant": sum(v["relevant"] for v in cached),
            "cached_correct": sum(v["relevant"] and v["support"] == "full" for v in cached),
        }
        try:
            out = agent.ask(
                TASK_CRITIQUE, USER_PROMPT_TEMPLATES[TASK_CRITIQUE].format(slot=sw.name, factor=work.factor.value), case=case,
                corpus={"passages": [_passage(i, family) for i in new]}, schema=SlotCritique, factor=work.factor, max_tokens=600,
            )  # fmt: skip
            critique = out if isinstance(out, SlotCritique) else SlotCritique.model_validate(out)
        except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError, ValueError):
            trace.failures += 1
            agent._decision("critic_unavailable", f"{work.factor.value}/{sw.name}: no critic verdict; the rules assess the slot.", factor=work.factor.value, slot=sw.name)
            return None
        trace.calls += 1
        by_id = {v.id: v for v in critique.verdicts}
        for i in new:
            v = by_id.get(item_key(i))
            rel, support = (v.relevant, v.support) if v else (False, "none")
            sw.verdicts[item_key(i)] = {"relevant": rel, "support": support if rel else "none"}
            trace.judged += 1
            trace.relevant += rel
            trace.supported += rel and support == "full"
            trace.not_relevant += not rel
    judged = [(i, sw.verdicts[item_key(i)]) for i in candidates if item_key(i) in sw.verdicts]
    relevant = [(i, v) for i, v in judged if v["relevant"] and v["support"] != "none"]
    relevant.sort(key=lambda iv: 0 if iv[1]["support"] == "full" else 1)
    correct = sum(v["support"] == "full" for _, v in relevant)
    status = SlotStatus.FILLED if correct >= max(need, 1) else SlotStatus.WEAK if relevant else SlotStatus.MISSING
    action = choose_action(correct, len(relevant), len(judged), need, sw.critic_used)
    if critique is not None and critique.action != "keep" and status != SlotStatus.FILLED:
        action = critique.action  # the model's choice when the slot is short; 'keep' on a short slot is overridden by the rule
    if status == SlotStatus.FILLED:
        action = "keep"
    sw.critic_action = None if action == "keep" else action
    if action == "discard":
        sw.discarded |= {item_key(i) for i, v in judged if not v["relevant"]}
    out_items = [{**i, "critique": {"relevant": True, "support": v["support"]}} for i, v in relevant]
    if status == SlotStatus.MISSING:
        note = "no results" if not items else f"critic: none of {len(items)} result(s) relevant and supported" + (f"; {guard.note}" if guard.note and not guard.items else "")
    else:
        note = f"{correct} of {max(need, 1)}" if status == SlotStatus.WEAK else f"{correct} supported"
        note += f"; critic judged {len(judged)} paragraph(s), {len(judged) - len(relevant)} not relevant"
    trace.actions.append({"slot": sw.name, "round": work.round, "status": status.value, "action": action, "judged": len(judged), "relevant": len(relevant), "supported": correct})
    agent._decision(
        "critique", f"Round {work.round} for {work.factor.value}/{sw.name}: {status.value}, action {action}.", factor=work.factor.value, slot=sw.name,
        round=work.round, status=status.value, action=action, judged=len(judged), relevant=len(relevant), supported=correct,
        reason=critique.reason if critique else "from cached verdicts",
    )  # fmt: skip
    return SlotResult(slot=sw.name, status=status, items=out_items, note=note)


def reorder(ladder: list[str], action: str | None) -> list[str]:
    """The re-plan ladder with the moves of the critic's action first (the rest of the rule ladder follows)."""
    first = ACTION_MOVES.get(action or "", [])
    return [*[m for m in first if m in ladder], *[m for m in ladder if m not in first]]


def signals(work: Any) -> dict[str, Any]:
    """The per-factor critique signals for `retrieval_signals`: calls, verdict counts, corrective actions and re-retrievals."""
    t: CritiqueTrace = work.critique
    return {
        "critic_calls": t.calls, "critic_failures": t.failures, "critic_skipped_budget": t.skipped_budget, "judged": t.judged,
        "relevant": t.relevant, "supported": t.supported, "not_relevant": t.not_relevant, "re_retrievals": t.re_retrievals, "actions": t.actions,
    }
