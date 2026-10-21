"""S3 (A11b): a prompted sufficiency rater for Sutradhar's stopping rule, and the per-factor stopping signals.

Switch: `Switches.stopping` = 'rules' (default, the current behaviour), 'rules_llm' (S3) or 'llm' (S3b).

Papers and what we took
-----------------------
* Hailey Joren, Jianyi Zhang, Chun-Sung Ferng, Da-Cheng Juan, Ankur Taly, Cyrus Rashtchian. "Sufficient Context: A New Lens
  on Retrieval Augmented Generation Systems". ICLR 2025.
  https://proceedings.iclr.cc/paper_files/paper/2025/hash/33dffa2e3d2ab74a783d1a8c292f66d9-Abstract-Conference.html
  Taken: the idea of an autorater that reads the question and the retrieved context and classifies the context as sufficient
  or not, and of using that signal to decide whether to go on or to abstain.
* Jingbo Sun et al. "AutoSearch: Adaptive Search Depth for Efficient Agentic RAG via Reinforcement Learning". Findings of ACL
  2026. https://aclanthology.org/2026.findings-acl.1399/ Taken: every question has a minimal sufficient search depth, so a
  search can stop too early or search too long; we measure both (`FactorSignals.stopped_too_early`, `over_search_calls`).
* Jaewan Park et al. "Stop-RAG: Value-Based Retrieval Control for Iterative RAG". NeurIPS 2025 Workshop (MTI-LLM).
  https://arxiv.org/abs/2510.14337 Taken: stopping as a separate decision after each retrieval round of a black-box pipeline.

What we changed, and why
------------------------
AutoSearch and Stop-RAG train a stopper with reinforcement learning; we train nothing (no compute and no labels for it). The
stopper is the prompted rater (`sutradhar.rate_sufficiency`) and, in 'rules_llm', the rule checks of `slot_rules.py` stay the
first check: the rater is asked only when the rules say every required slot is FILLED, and may veto the stop. In 'llm' the
rater alone decides each round (rule statuses are then only a fallback and a measurement). The rater reads the evidence it is
shown, in the format of the shared prompt layout; the paper's autorater was a prompted large model, ours is the agents model
(offline: a deterministic text-overlap rule, `offline.rate_offline`, which is not a language model). Unlike the paper we ask
about a bail factor and its contract slots, not a question with a gold answer, so no 'abstain' answer is produced here; the
verdict and the missing slots are logged and, when the factor stops short, the slots stay open issues as before.

Assumptions: the rater never raises a budget (it is asked only while the factor has store calls and tokens left, and a failed
or refused call falls back to the rules); stopped-too-early is measured online as 'the rater said sufficient while a required
slot was not FILLED by the rules and budget was left' (the plan's replay-to-budget measure, M18, runs offline from the log).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vakeel_sahayak.agents.sutradhar.contracts_runtime import required_count
from vakeel_sahayak.agents.sutradhar.prompts import TASK_RATE, USER_PROMPT_TEMPLATES, SufficiencyJudgment
from vakeel_sahayak.agents.sutradhar.slot_rules import FACTOR_TERMS, SLOT_KEYWORDS
from vakeel_sahayak.agents.sutradhar.work import FactorWork
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError

EVIDENCE_ITEMS = 6  # items per slot shown to the rater
TEXT_CHARS = 300
_TEXT_KEYS = ("text", "label", "value", "detail")


def _text(item: dict[str, Any]) -> str:
    return " ".join(str(item[k]) for k in _TEXT_KEYS if item.get(k) is not None)[:TEXT_CHARS]


def _item_id(item: dict[str, Any]) -> str:
    return f"{item['doc_id']}#{item['para']}" if item.get("para") is not None else str(item.get("chunk_id") or item.get("event_id") or item.get("doc_id") or "item")


def rater_inputs(work: FactorWork) -> tuple[dict[str, Any], dict[str, Any]]:
    """The case-private and the public part of the rater's input: required slots with their need, status and the evidence so far.

    Court paragraphs (public corpus text) go under `corpus`; case-store items (pseudonymised, private) under `case`.
    """
    slots, evidence = [], {}
    for name, sw in work.slots.items():
        if not sw.required:
            continue
        items = list(sw.result.items if sw.result else sw.items)[:EVIDENCE_ITEMS]
        public = [{"id": _item_id(i), "text": _text(i)} for i in items if i.get("para") is not None]
        private = [{"id": _item_id(i), "text": _text(i)} for i in items if i.get("para") is None]
        slots.append({"slot": name, "need": required_count(sw.need), "status": sw.status.value, "n_items": len(items), "case_evidence": private})
        if public:
            evidence[name] = public
    return {"factor": work.factor.value, "slots": slots}, {"evidence": evidence}


def supported_count(factor: str, slot: dict[str, Any], public: list[dict[str, Any]]) -> int:
    """How many of a slot's items the offline rater accepts: text that mentions the factor (court paragraphs) or the slot's subject
    (case records); a slot read from rules, statutes or the citation graph carries no text, so any item counts. Distinct sources only."""
    items = [*public, *slot.get("case_evidence", [])]
    terms = FACTOR_TERMS.get(factor, ()) if public else SLOT_KEYWORDS.get(slot["slot"], ())
    kept = {i["id"] for i in items if not terms or not i["text"] or any(t in i["text"].lower() for t in terms)}
    return len(kept) if items else int(slot.get("n_items", 0) > 0)


def rate_data(case: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    """The offline rater: sufficient when every required slot has as many supported items as it needs (deterministic, rule-based)."""
    evidence = corpus.get("evidence", {})
    missing = [s["slot"] for s in case.get("slots", []) if supported_count(case.get("factor", ""), s, evidence.get(s["slot"], [])) < s["need"]]
    reason = "every required slot has enough relevant evidence" if not missing else "not enough relevant evidence for " + ", ".join(missing)
    return {"sufficient": not missing, "missing": missing, "reason": reason}


def rate(agent: Any, work: FactorWork) -> SufficiencyJudgment | None:
    """Ask the rater about the factor's evidence so far; None when the model cannot answer (budget spent, refusal, bad output)."""
    case, corpus = rater_inputs(work)
    try:
        out = agent.ask(
            TASK_RATE, USER_PROMPT_TEMPLATES[TASK_RATE].format(factor=work.factor.value), case=case, corpus=corpus,
            schema=SufficiencyJudgment, factor=work.factor, max_tokens=300,
        )  # fmt: skip
        return out if isinstance(out, SufficiencyJudgment) else SufficiencyJudgment.model_validate(out)
    except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError, ValueError):
        return None


@dataclass
class StoppingTrace:
    """What the stopping rule did for one factor (kept on `FactorWork`; the evaluation reads `FactorSignals`)."""

    rule_pass_calls: int | None = None  # store calls spent when the rules first found every required slot FILLED
    judgments: list[dict[str, Any]] = field(default_factory=list)
    rater_failures: int = 0
    rater_stop: bool = False  # stopped because the rater said sufficient while the rules did not
    rules_short_at_stop: bool = False


def signals_of(work: FactorWork, mode: str, store_calls: int, tokens: int) -> dict[str, Any]:
    """Per-factor stopping signals (plan 4.3, M18): the evaluation runners read these from the `retrieval_signals` event and state field.

    `over_search_calls`: store calls made after the rules first passed every required slot. `stopped_too_early`: the rater stopped
    the factor while the rules still had a required slot unfilled and the budget was not spent.
    """
    trace = work.stopping
    passed = trace.rule_pass_calls
    return {
        "factor": work.factor.value, "stopping": mode, "stopped": work.stopped, "rounds": work.round, "store_calls": store_calls, "tokens": tokens,
        "rater_calls": len(trace.judgments), "rater_failures": trace.rater_failures, "judgments": trace.judgments,
        "rule_pass_calls": passed, "over_search_calls": max(0, store_calls - passed) if passed is not None else 0,
        "stopped_too_early": trace.rater_stop and trace.rules_short_at_stop and not work.budget_hit,
    }  # fmt: skip
