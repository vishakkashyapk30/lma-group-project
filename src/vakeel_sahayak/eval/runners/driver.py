"""Thin evaluation driver (plan §7.3, docs/evaluation-plan.md): runs the agents in sequence for a case. It does NOT use LangGraph.

Sequence for one case: Munshi (only when a bundle is given) -> Peshkar -> Gate 1 -> Sutradhar -> Vakeel -> Abhiyojak (Sutradhar's
`delegate` runs Vakeel's drafting, check-and-repair and Abhiyojak's sparring, honouring the switches) -> Gate 2 -> an export attempt.

* **Scripted counsel** (`ScriptedCounsel`): approves a gate only when the scenario says so, and only through `GateGuard.approve`, the
  one path that writes counsel's approval. Nothing here writes a GATE_APPROVED event itself, and the export attempt goes through the
  tool layer (`call_tool("export")`), so an unapproved export stays blocked by `GateGuard`; the result records `export.blocked`.
* **Resumable shards**: `run_cases` saves one file per case (`<out_dir>/<case_id>.json`) the moment the case finishes; a re-run skips
  saved cases; shard `i` of `n` takes the cases whose index is `i` modulo `n`.
* **Seeds and budgets**: the seed is set for `random` before each case and recorded; the token and store-call budgets default to
  configs/budgets.yaml and can be overridden per run.
* **Run manifest** (`write_run_manifest`): code version, config hash, model name/version/date stamp (`describe_run_models()`), seed, switches,
  budgets, the hash of the case file. Per-case event logs are dumped to `<out_dir>/_events/<case_id>.jsonl`.
* **Output layout** (README C6): `data/eval/runs/<run_id>/manifest.json` and `.../outputs/<system>/<case_id>.json`; see `run_dir_for`.
* **Blind slice**: `testsets.blind.assert_may_score_blind` refuses to score blind ids without the freeze tag; the driver only RUNS cases.

* **Hosted models** (`VS_LLM_BACKEND=openai|sarvam`, `VS_MODELS=auto`): run with `VS_EXTERNAL=pseudonymised`, not `public`. `_case_scope` declares each case
  with `policy.public_source_scope`: the T1 and constructed cases come from published court orders, not from a client, so no counsel consent is asked for
  and none is ever written. Every agent role still declares client text, and the role's own declaration wins, so the wire step (`privacy.quasi`: aliases
  for FIR numbers, police stations, places and the other quasi-identifiers, the case's date shift, the reply turned back) and the wire-strength boundary
  run exactly as in production. A text-only case is pseudonymised as the production intake does (`file_facts`: Munshi's `Filer`, the same alias map saved
  on the laptop so `assert_pseudonymised` knows the real names, plus the court-order caption rule `learn_caption_names`; an evaluation case's date shift is
  computed from its id, so reruns send the same text); only the pseudonymised text is filed on the case shelf and passed on as `state.facts_text`. A case
  marked `data_class: client` gets no declaration and so needs counsel's consent like any client case. The manifest's `privacy` block records this.
* **NLI** in `auto` mode is the real DeBERTa checker when `torch` and `transformers` are installed (`pip install .[nli]`), else the offline lexical checker
  with the reason recorded (`models.nli.nli_status()`): in the run manifest, in every case's `meta.nli`, and as an `nli_backend` event in the case log.

Smoke: `python -m vakeel_sahayak.eval.runners.driver smoke` (`make smoke`) runs the case-0007 fixture end to end on the offline
stand-ins; `... eval-smoke` (`make eval-smoke`) runs three T1 dev cases offline.
"""

from __future__ import annotations

import argparse
import functools
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.agents.base import AgentContext
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.enums import AgentName, ExportFormat, GateId
from vakeel_sahayak.schemas.events import COUNSEL, Event

REPO = Path(__file__).resolve().parents[4]
EVAL_ROOT = "data/eval"
MANIFEST_NAMES = {"MANIFEST", "manifest"}
SMOKE_FACTS = ("The accused was arrested on 20.08.2024 for cheating under Section 318(4) BNS. Charge sheet filed 02.11.2024. "
               "Co-accused-1 granted bail 05.12.2024.")


# ---------------------------------------------------------------------------------------------------------------- counsel
@dataclass
class ScriptedCounsel:
    """Counsel as a script: a gate is approved only when the scenario says so (plan §7.3, T7)."""

    approve_gate1: bool = True
    approve_gate2: bool = False
    resolve_items: bool = True  # when approving Gate 2, resolve NEEDS_REVIEW and UNANSWERED items first
    decisions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_scenario(cls, scenario: dict[str, Any] | None) -> ScriptedCounsel:
        """Build from a case's `scenario` dict (keys `approve_gate1`, `approve_gate2`, `resolve_items`); no scenario: Gate 1 yes, Gate 2 no."""
        s = scenario or {}
        return cls(bool(s.get("approve_gate1", True)), bool(s.get("approve_gate2", False)), bool(s.get("resolve_items", True)))

    def decide(self, guard: Any, log: Any, case_id: str, gate: GateId) -> bool:
        """Open the gate and approve it when the script says so; returns whether it was approved."""
        guard.open(case_id, gate)
        wanted = self.approve_gate1 if gate == GateId.GATE_1_DOSSIER else self.approve_gate2
        status = guard.status(case_id, gate)
        record = {"gate": gate.value, "approved": False, "scripted": wanted, "unresolved": {
            "unsupported": list(status.unresolved_unsupported), "needs_review": list(status.unresolved_needs_review),
            "unanswered": list(status.unresolved_unanswered)}}
        if wanted:
            if self.resolve_items and status.unresolved_needs_review:
                _counsel_reviews(log, case_id, set(status.unresolved_needs_review))
            try:
                guard.approve(case_id, gate, acknowledged=list(status.unresolved_unsupported))
                record["approved"] = True
            except Exception as exc:  # noqa: BLE001 - a checklist that cannot be cleared leaves the gate closed
                record["error"] = f"{type(exc).__name__}: {exc}"
        self.decisions.append(record)
        return bool(record["approved"])


def _counsel_reviews(log: Any, case_id: str, ground_ids: set[str]) -> None:
    """Counsel reviews the grounds still marked NEEDS_REVIEW and marks them SUPPORTED (a counsel-authored write of the brief view).

    # SKELETON-GAP: no route resolves a Gate 2 checklist item yet (tests/README.md); an UNANSWERED objection cannot be resolved this way, so a
    scenario with one leaves Gate 2 closed and the export blocked.
    """
    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.schemas.enums import ClaimCheck, EventKind

    brief = CaseState(case_id, log).brief()
    grounds = [g.model_copy(update={"check": ClaimCheck.SUPPORTED}) if g.id in ground_ids else g for g in brief.grounds]
    reviewed = brief.model_copy(update={"grounds": grounds})
    log.append(Event(event_id="", ts="", case_id=case_id, kind=EventKind.STORE_WRITE, actor=COUNSEL,
                     inputs={"store": "case.views", "view": "brief"}, outputs={"value": reviewed.model_dump(mode="json")}))


# ---------------------------------------------------------------------------------------------------------------- context
def case_facts(case: dict[str, Any]) -> str:
    """The facts text of a case row (`facts`, or `facts_text` of a T1 row)."""
    return str(case.get("facts") or case.get("facts_text") or "")


def build_context(case: dict[str, Any], switches: Any = None, *, tools: dict[str, Any] | None = None, llm: Any = None,
                  budgets: dict[str, int] | None = None, cases_dir: str | None = None, log: Any = None, cache: Any = None) -> AgentContext:
    """An `AgentContext` for one case: in-memory event log (dumped afterwards), budgets from configs/budgets.yaml or the override.

    Args:
        case: row with `case_id` and `before` (the order date: shared-store searches see only earlier documents)
        switches: `Switches` (default: the full system)
        tools: a toolbox replacing the registry (fixtures); None uses the real tools and stores
        llm: one client for every agent (tests); None lets each agent resolve its own role
        budgets: `{"tokens_per_case", "store_calls_per_factor", "tokens_per_factor"}` overrides
        cases_dir: cases folder for logs; default in-memory
        log: an existing event log
        cache: a shared retrieval cache (`batch.cache.RetrievalCache`) for the batch variants S14 and S14d; None (default) means no cache
    """
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.orchestration.budgets import BudgetTracker
    from vakeel_sahayak.orchestration.switches import Switches
    from vakeel_sahayak.record.event_log import EventLog

    config = load_config()
    log = log or EventLog(":memory:")
    tracker = BudgetTracker.from_config(config, log=log, case_id=case["case_id"])
    for key, value in (budgets or {}).items():
        setattr(tracker, key, int(value))
    return AgentContext(case_id=case["case_id"], config=config, log=log, budgets=tracker, llm=llm,
                        switches=switches or Switches(), tools=dict(tools or {}), before=case.get("before"), cases_dir=cases_dir,
                        cache=cache)


# ---------------------------------------------------------------------------------------------------------------- pipeline
def run_agents(case: dict[str, Any], ctx: AgentContext, counsel: ScriptedCounsel | None = None, *, bundle: str | list[str] | None = None,
               stop_after: str | None = None, sutradhar: Any = None) -> dict[str, Any]:
    """Run the agents in sequence for one case and return a result record (dossier summary, brief, sparring, gates, export, spend).

    Args:
        case: `case_id`, `facts`, `before`, optional `bundle` (files for Munshi) and `scenario` (counsel's script)
        ctx: the case's context (shared event log and budget)
        counsel: scripted counsel (default: from `case["scenario"]`)
        bundle: files for Munshi; None skips Munshi (text-only cases)
        stop_after: 'retrieval' stops after Sutradhar's evidence packs (A10)
        sutradhar: factory `ctx -> agent` replacing Sutradhar (B4's every-store retrieval); drafting, checks and sparring are unchanged
    """
    from vakeel_sahayak.agents.registry import create_agent
    from vakeel_sahayak.orchestration.gates import GateGuard
    from vakeel_sahayak.orchestration.state import CaseGraphState
    from vakeel_sahayak.record.gates import GateNotApproved

    counsel = counsel or ScriptedCounsel.from_scenario(case.get("scenario"))
    files = [bundle] if isinstance(bundle, str) else list(bundle or case.get("bundle") or [])
    case_id = case["case_id"]
    state = CaseGraphState(case_id=case_id, before=case.get("before"), as_of=case.get("as_of") or case.get("before"),
                           files=[str(f) for f in files], facts_text=case_facts(case) or None, switches=ctx.switches,
                           )
    guard = GateGuard(ctx.log)
    errors: list[str] = []
    agents: dict[str, Any] = {}

    def agent(name: AgentName) -> Any:
        if name.value not in agents:
            agents[name.value] = sutradhar(ctx) if name == AgentName.SUTRADHAR and sutradhar else create_agent(name, ctx)
            if name == AgentName.SUTRADHAR:
                wire_variants(agents[name.value], ctx, case)
        return agents[name.value]

    def step(name: str, fn: Any) -> None:
        nonlocal state
        try:
            out = fn(state)
            state = out if out is not None else state
        except Exception as exc:  # noqa: BLE001 - one failed stage is recorded, the case still yields a (possibly empty) brief
            errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:300]}")

    if files:
        step("munshi", lambda s: agent(AgentName.MUNSHI).run(s))
    elif case_facts(case):  # a text-only case: pseudonymise like Munshi's Filer, then (on the real tools) shelve the facts for Peshkar
        try:
            state = state.model_copy(update={"facts_text": file_facts(ctx, case, shelve=not ctx.tools)})
        except Exception as exc:  # noqa: BLE001 - never fall back to the raw text: the boundary would refuse it, and the raw names must not travel
            errors.append(f"file_facts: {type(exc).__name__}: {str(exc)[:200]}")
            state = state.model_copy(update={"facts_text": None})
    step("peshkar", lambda s: agent(AgentName.PESHKAR).run(s))
    gate1 = counsel.decide(guard, ctx.log, case_id, GateId.GATE_1_DOSSIER)
    result: dict[str, Any] = {"case_id": case_id, "gate1_approved": gate1, "gate2_approved": False, "export": {"attempted": False}}
    if gate1:
        sutradhar = agent(AgentName.SUTRADHAR)
        step("sutradhar", lambda s: sutradhar.run(s))
        if stop_after != "retrieval":
            step("delegate", lambda s: sutradhar.delegate(s, list(s.evidence_packs)))
            result["gate2_approved"] = counsel.decide(guard, ctx.log, case_id, GateId.GATE_2_EXPORT)
            result["export"] = _try_export(agent(AgentName.VAKEEL), case_id, GateNotApproved)
    else:
        errors.append("gate1 not approved by the scripted counsel: the run stops before retrieval")
    for a in agents.values():
        a.close()
    brief = state.brief or BailBrief(case_id=case_id)
    signals = collect_variant_signals(agents.get(AgentName.SUTRADHAR.value))
    signals.update(collect_sweep3_signals(ctx, agents))
    if signals:
        result["variant_signals"] = signals  # only when a Sweep-2 or Sweep-3 variant ran: default records are unchanged
    result.update(brief=brief.model_dump(mode="json"), sparring=state.sparring.model_dump(mode="json") if state.sparring else None,
                  packs=len(state.evidence_packs), errors=errors, counsel=counsel.decisions)
    result["_brief_obj"] = brief
    return result


def wire_variants(sutradhar: Any, ctx: AgentContext, case: dict[str, Any]) -> None:
    """Dispatch on the switches that replace an agent of the delegate step: `critic_mode='sampling'` (S9 / A8b) and `'three_role'` (S11 / A8d) put the sampling or
    three-role critic in Sutradhar's peer table (`eval.ablations.a8b_sampling_critic.install`, `a8d_three_role.install`); `case['sparring_tokens']` is the sampling critic's equal-token budget. Default switches change nothing."""
    mode = getattr(ctx.switches, "critic_mode", "abhiyojak")
    if mode == "sampling":
        from vakeel_sahayak.eval.ablations import a8b_sampling_critic

        budget = case.get("sparring_tokens")
        a8b_sampling_critic.install(sutradhar, ctx, token_budget=int(budget) if budget else None)
    elif mode == "three_role":
        from vakeel_sahayak.eval.ablations import a8d_three_role

        a8d_three_role.install(sutradhar, ctx)


def collect_variant_signals(sutradhar: Any) -> dict[str, Any]:
    """Signals of the Sweep-2 variants from the agents Sutradhar used ('repair' from Vakeel, 'critic' from Abhiyojak); empty in a default run."""
    out: dict[str, Any] = {}
    peers = getattr(sutradhar, "_peers", None) or {}
    for key, name, method in (("repair", AgentName.VAKEEL, "repair_signals"), ("critic", AgentName.ABHIYOJAK, "critic_signals")):
        peer = peers.get(name)
        signals = getattr(peer, method, lambda: {})() if peer is not None else {}
        if signals:
            out[key] = signals
    return out


def collect_sweep3_signals(ctx: AgentContext, agents: dict[str, Any]) -> dict[str, Any]:
    """Signals of the Sweep-3 variants, only when one is on: 'injection' (S17 arms: each agent's defence counters), 'munshi' (S7 gap policy, P7 image-only),
    'prefix' (S14d shared prefix tokens) and 'plan_cache' (S14 hits and tokens saved); empty in a default run."""
    out: dict[str, Any] = {}
    sw = ctx.switches
    if any(getattr(sw, f) for f in ("no_typed_handoff", "no_spotlighting", "no_guard")):
        out["injection"] = {name: a.injection_signals() for name, a in agents.items() if hasattr(a, "injection_signals")}
    munshi = agents.get(AgentName.MUNSHI.value)
    if munshi is not None and (sw.munshi_gap_policy == "hierarchy" or sw.munshi_image_only):
        out["munshi"] = {**({"gaps": munshi.gap_signals()} if sw.munshi_gap_policy == "hierarchy" else {}),
                         **({"image_only": munshi.image_only_signals()} if sw.munshi_image_only else {})}
    if sw.prefix_layout and agents:
        out["prefix"] = next(iter(agents.values())).prefix_signals()
    if sw.plan_cache and ctx.cache is not None:
        from vakeel_sahayak.batch.cache import plans_of

        out["plan_cache"] = plans_of(ctx.cache).stats()
    return out


_CAPTION_ROLE = r"(?P<role>Petitioner|Appellant|Applicant|Accused|Respondent|Opposite\s+Party|Complainant|Informant)"
_CAPTION_PATTERNS = (  # (pattern on one line, role): party names of a court-order caption, which the intake's name rules do not catch
    (re.compile(rf"^\s*(?:\d+\s*\.\s*)?(?P<n>[^\n.\u2026:]{{3,70}}?)\s*(?:\.{{2,}}|\u2026|\s{{3,}}).*?\b{_CAPTION_ROLE}", re.IGNORECASE | re.MULTILINE), None),
    (re.compile(r"In\s+the\s+matter\s+of\s*:\s*(?P<n>[^\n.\u2026]{3,70})", re.IGNORECASE), "accused"),
    (re.compile(r"^\s*(?:\d+\s*\.\s*)?(?P<n>[A-Z][A-Za-z ]{3,60}?)\s+(?:S/O|D/O|W/O)\b", re.MULTILINE), "person"),
    # the father's, husband's or guardian's name after the relation word, often in capitals: 'S/O LATE RAMESHWAR SINGH R/O ...'
    (re.compile(r"\b(?:S/O|D/O|W/O|son\s+of|daughter\s+of|wife\s+of)\s+(?:late\s+|smt\.?\s+|shri\s+|sri\s+)?(?P<n>[A-Za-z][A-Za-z.' ]{2,50}?)\s*(?=R/O|,|\n|\.\.|\bP\.?\s?S\b|\bDISTT?\b|\bvillage\b|\bresident\b|\bage\b|$)", re.IGNORECASE | re.MULTILINE), "person"),
    # counsel and judges: 'Mr.Rama Kant Singh, Adv.', 'For the State : Mr. S.K. Srivastava, APP', 'JUSTICE RATNAKER BHENGRA'
    (re.compile(r"\b(?:Mr|Ms|Mrs|Shri|Smt|Dr)\.?\s*(?P<n>[A-Za-z][A-Za-z. ]{2,40}?)\s*,\s*(?:Adv|Advocate|APP|Spl|Sr|Senior|Addl|AAG|A\.G|P\.P|PP|Counsel)", re.IGNORECASE), "person"),
    (re.compile(r"\bJUSTICE\s+(?P<n>[A-Z][A-Z.' ]{2,40}?)(?=\s*(?:\n|,|\.|$|ORAL|CAV|JUDGMENT))", re.MULTILINE), "person"),
)
_NOT_A_PARTY = re.compile(r"\b(state|union|court|versus|vs|india|police|station|government|directorate|bureau|cbi|ncb|petition|appeal|matter)\b", re.IGNORECASE)


def learn_caption_names(text: str, mapping: Any) -> list[str]:
    """Register the party names of a court-order caption (`X ... Petitioner`, `In the matter of: X`, `X S/O Y`) in the alias map.

    The production intake reads a client's documents, where names follow role words; a court order lists parties before the role word, so the
    intake's rules miss them. Evaluation cases are such orders, and the boundary only knows names the map holds, so they are learned here
    (the T1 orders are public, but real names still must not reach a hosted model). Returns the names registered ('A @ B' gives both)."""
    found: list[str] = []
    for pattern, fixed in _CAPTION_PATTERNS:
        for m in pattern.finditer(text):
            role = fixed or ("complainant" if re.match(r"respondent|opposite|complainant|informant", m.group("role"), re.IGNORECASE) else "accused")
            for part in re.split(r"\s*@\s*|\s+alias\s+|\s+and\s+(?:(?:Mr|Ms|Mrs|Shri|Smt|Dr)\.?\s*)?", re.sub(r"^(?:Mr|Ms|Mrs|Shri|Smt|Dr)\.?\s*", "", m.group("n").strip(" ,;-"))):
                part = " ".join(part.split())
                if len(part) >= 4 and not _NOT_A_PARTY.search(part) and re.fullmatch(r"[A-Za-z][A-Za-z .']+", part) and not re.search(r"\b(?:r/o|adv|advocate)\b", part, re.IGNORECASE) and part not in found:
                    mapping.alias_for(part, role)
                    found.append(part)
    return found


_EVAL_CASE_ID = re.compile(r"^t\d+[a-z]*-")  # t1dev-000, t2-..., the ids of the evaluation test sets (production ids look like case-0007)


def _fresh_shelf(ctx: AgentContext, case_id: str) -> None:
    """Delete an evaluation case's folder on the laptop (shelf stores, alias map) left by an earlier run.

    The shelf has no delete and chunk ids repeat, so a rerun would otherwise read the earlier run's text (the first hosted pilot left raw names there that
    a later, pseudonymised run then found). Only ids of the evaluation test sets are touched, never a production case."""
    import shutil

    from vakeel_sahayak.privacy.pseudonymise import _map_path

    if _EVAL_CASE_ID.match(case_id):
        shutil.rmtree(_map_path(case_id, ctx.cases_dir).parent, ignore_errors=True)


def file_facts(ctx: AgentContext, case: dict[str, Any], *, shelve: bool = True) -> str:
    """Pseudonymise a text-only case's facts as Munshi's Filer does, and return the pseudonymised text.

    The names are learned (the intake's rules plus the caption rule above), the case's alias map is saved on the laptop so the privacy
    boundary (`assert_pseudonymised`) knows the real names, and, when `shelve` is true (the real tools), the pseudonymised facts are filed
    as one `case.docs` document (page 1) where Peshkar reads them. Only the returned text may travel onward (`state.facts_text`)."""
    from vakeel_sahayak.ingestion.filing import Filer
    from vakeel_sahayak.schemas.enums import DocumentType

    if shelve:
        _fresh_shelf(ctx, case["case_id"])
    filer = Filer(case["case_id"], ctx.log, cases_dir=ctx.cases_dir, actor=AgentName.MUNSHI)
    try:
        raw = case_facts(case)
        if _EVAL_CASE_ID.match(case["case_id"]):  # public-source evaluation case: a reproducible shift (same text on a rerun, so the cache answers); production cases draw a random one
            filer.mapping.ensure_date_shift(case["case_id"])
        learn_caption_names(raw, filer.mapping)
        clean = filer.pseudonymise_batch([raw])[0]
        filer.save_map()
        if shelve:
            filer.file_chunks("d1", DocumentType.OTHER, [{"page": 1, "text": clean, "lang": "en", "route": "text_layer", "confidence": 1.0}])
        return clean
    finally:
        filer.close()


def _try_export(vakeel: Any, case_id: str, blocked_type: type[Exception]) -> dict[str, Any]:
    """Ask Vakeel's `export` tool for a DOCX; the tool layer (GateGuard) blocks it unless counsel approved Gate 2."""
    try:
        res = vakeel.call_tool("export", case_id=case_id, format=ExportFormat.DOCX)
    except blocked_type as exc:
        return {"attempted": True, "blocked": True, "reason": str(exc)[:200]}
    except Exception as exc:  # noqa: BLE001
        return {"attempted": True, "blocked": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    kind = getattr(res, "kind", None)
    if kind:  # a ToolError (for example the export module is not built yet)
        return {"attempted": True, "blocked": False, "error": f"{kind}: {getattr(res, 'message', '')[:200]}"}
    return {"attempted": True, "blocked": False, "paths": [str(p) for p in (res if isinstance(res, list) else [res])]}


# ---------------------------------------------------------------------------------------------------------------- spend and metadata
@functools.lru_cache(maxsize=1)
def models_stamp() -> dict[str, Any]:
    """`describe_run_models()` once per process (it reads configs and env; the stamp does not change within a run)."""
    from vakeel_sahayak.models.factory import describe_run_models

    return describe_run_models()


def run_metadata(ctx: AgentContext, seed: int, system: str, elapsed_s: float | None = None) -> dict[str, Any]:
    """Run metadata stamped on every case output: model names/versions/date, tokens, store calls, seed, switches."""
    tokens, store_calls = 0, 0
    try:
        tokens, store_calls = ctx.budgets.spent(None)
    except Exception:  # noqa: BLE001 - minimal budgets of tests
        pass
    from vakeel_sahayak.models.nli import nli_status

    meta = {"system": system, "seed": seed, "tokens": int(tokens), "store_calls": int(store_calls),
            "switches": ctx.switches.model_dump(), "variant": ctx.switches.variant(), "models": models_stamp(), "nli": nli_status()}
    if elapsed_s is not None:
        meta["seconds"] = round(elapsed_s, 3)
    return meta


def dump_events(ctx: AgentContext, path: Path) -> int:
    """Write the case's event log as JSON lines (per-case event log of the run); returns the number of events."""
    events = ctx.log.read(ctx.case_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(ev.model_dump_json() + "\n")
    return len(events)


# ---------------------------------------------------------------------------------------------------------------- shards
def load_progress(out_dir: str) -> set[str]:
    """Case ids already saved in `out_dir` (valid JSON files; a half-written file is not counted; manifests are not cases)."""
    root = Path(out_dir)
    if not root.is_dir():
        return set()
    done: set[str] = set()
    for p in root.glob("*.json"):
        if p.stem in MANIFEST_NAMES:
            continue
        try:
            json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        done.add(p.stem)
    return done


def read_cases(cases_path: str) -> list[dict[str, Any]]:
    """Case rows of a JSON-lines file (`case_id`, `facts` or `facts_text`, `before` or `date`)."""
    rows = []
    for line in Path(cases_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            row.setdefault("before", row.get("date"))
            rows.append(row)
    return rows


def save_json(path: Path, obj: Any) -> None:
    """Write atomically (temp file, then rename) so a killed session never leaves a half file counted as done."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    tmp.replace(path)


def _case_scope(case: dict[str, Any], system: str, ctx: AgentContext | None = None) -> Any:
    """The privacy scope for one evaluation case: the T1 and constructed sets are public or synthetic data, declared as such with
    `public_source_scope` (no counsel consent is needed or faked; agent calls keep the client-text wire step and boundary), so hosted model
    backends may be used when `VS_EXTERNAL` allows it. A case marked `data_class: client` gets no declaration: its calls need counsel's consent."""
    import contextlib

    if case_data_class(case) == "client":
        return contextlib.nullcontext()
    from vakeel_sahayak.models.sarvam.policy import public_source_scope

    mapping = None
    if ctx is not None:
        from vakeel_sahayak.privacy.pseudonymise import load_map

        def mapping() -> Any:  # the case's alias map as `file_facts` saved it (read when a hosted call needs it)
            return load_map(case["case_id"], getattr(ctx, "cases_dir", None))

    return public_source_scope(f"eval-{system}", mapping=mapping)


def case_data_class(case: dict[str, Any]) -> str:
    """'client' for a case marked `data_class: client`, else 'public' (published court orders or constructed data)."""
    return "client" if str(case.get("data_class", "public")).lower() == "client" else "public"


def privacy_manifest(cases_path: str | None) -> dict[str, Any]:
    """The manifest's record of the data class used: how many cases ran under the public-source declaration and how many as client cases."""
    counts = {"public": 0, "client": 0}
    if cases_path and Path(cases_path).is_file():
        try:
            for row in read_cases(cases_path):
                counts[case_data_class(row)] += 1
        except (OSError, ValueError):
            pass
    return {"case_scope": "public_source (policy.public_source_scope)", "agent_data_class": "client_text", "consent": "not required for public-source cases; client cases need counsel's event",
            "cases_by_data_class": counts}


def _log_nli_fallback(ctx: AgentContext) -> None:
    """When `auto` mode fell back to the offline NLI, say so in the case's event log (never silently)."""
    from vakeel_sahayak.models.nli import nli_status
    from vakeel_sahayak.schemas.enums import EventKind

    st = nli_status()
    if not st["fallback_reason"]:
        return
    try:
        ctx.log.append(Event(event_id="", ts="", case_id=ctx.case_id, kind=EventKind.AGENT_MESSAGE, actor="driver",
                             outputs={"type": "nli_backend", "text": f"nli: offline stand-in ({st['fallback_reason']})", **st}))
    except Exception:  # noqa: BLE001 - a fake context's log may not take it
        pass


def run_cases(cases_path: str, out_dir: str, system: str, runner: Any, switches: Any = None, *, shard: int = 0, n_shards: int = 1,
              seed: int = 0, tools: dict[str, Any] | None = None, llm: Any = None, budgets: dict[str, int] | None = None,
              deadline: float | None = None, limit: int | None = None, scenario: dict[str, Any] | None = None) -> int:
    """Run `runner(case, ctx)` over this shard's cases, saving each case as it finishes; returns the number completed now.

    Args:
        cases_path: JSON-lines case file
        out_dir: where `<case_id>.json` files go (also `_events/` and `MANIFEST.json`)
        system: label recorded in outputs and the manifest ('full', 'b1', 'A2', ...)
        runner: `(case, ctx) -> BailBrief | dict` (a baseline's `run_case`, or the Full system)
        switches: `Switches` for the run
        shard: this shard's index; n_shards: the shard count
        seed: base seed; case k runs with seed `seed + k`
        tools, llm, budgets: see `build_context`
        deadline: `time.monotonic()` value after which no new case starts
        limit: stop after this many cases of the shard (smoke runs)
        scenario: counsel's script for every case without its own
    """
    from vakeel_sahayak.orchestration.switches import Switches

    if not 0 <= shard < n_shards:
        raise ValueError(f"shard {shard} is outside 0..{n_shards - 1}")
    switches = switches or Switches()
    cases = read_cases(cases_path)
    mine = [(i, c) for i, c in enumerate(cases) if i % n_shards == shard]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    write_run_manifest(out, system=system, switches=switches, seed=seed, budgets=budgets, cases_path=cases_path, shard=shard, n_shards=n_shards, extra=_system_manifest_extra(system))
    cache = shared_cache_for(switches)  # one retrieval cache for the whole run when a batch variant (S14, S14d) is on; None otherwise
    done = load_progress(out_dir)
    completed = 0
    for i, case in mine:
        if case["case_id"] in done:
            continue
        if deadline is not None and time.monotonic() >= deadline:
            break
        if limit is not None and completed >= limit:
            break
        if scenario and "scenario" not in case:
            case = {**case, "scenario": scenario}
        random.seed(seed + i)
        ctx = build_context(case, switches, tools=tools, llm=llm, budgets=budgets, cache=cache)
        t0 = time.monotonic()
        error = None
        try:
            with _case_scope(case, system, ctx):
                produced = runner(case, ctx)
        except Exception as exc:  # noqa: BLE001 - a crashed case is saved as an error record so the shard goes on
            produced, error = BailBrief(case_id=case["case_id"]), f"{type(exc).__name__}: {str(exc)[:300]}"
        record = produced if isinstance(produced, dict) else {"brief": produced.model_dump(mode="json")}
        record = {k: v for k, v in record.items() if not k.startswith("_")}
        record.update(getattr(ctx, "eval_record", None) or {})  # gates, sparring record, export attempt of the Full pipeline
        record.update(case_id=case["case_id"], system=system, meta=run_metadata(ctx, seed + i, system, time.monotonic() - t0))
        if error:
            record["error"] = error
        _log_nli_fallback(ctx)
        try:
            dump_events(ctx, out / "_events" / f"{case['case_id']}.jsonl")
        except Exception:  # noqa: BLE001 - the log of a fake context may not be readable
            pass
        save_json(out / f"{case['case_id']}.json", record)
        completed += 1
    return completed


# ---------------------------------------------------------------------------------------------------------------- manifest and paths
def run_dir_for(run_id: str, root: str | None = None) -> Path:
    """`data/eval/runs/<run_id>` (README C6); `VS_DATA_DIR` rebases `data/`."""
    import os

    base = Path(root) if root else Path(os.environ.get("VS_DATA_DIR") or REPO / "data") / "eval"
    return base / "runs" / run_id


def outputs_dir(run_id: str, system: str, run_index: int = 1, root: str | None = None) -> Path:
    """`<run_dir>/outputs/<system>` for the first run, `<system>__run<k>` for repeat k > 1 (README C6 plus repeats)."""
    system = system.replace(":", "-")  # 'A10:caselaw.reasoning' -> 'A10-caselaw.reasoning' (a colon is not safe in a path)
    name = system if run_index <= 1 else f"{system}__run{run_index}"
    return run_dir_for(run_id, root) / "outputs" / name


@functools.lru_cache(maxsize=1)
def code_version() -> str:
    """Git short SHA (plus '-dirty' for uncommitted changes), or 'unknown'."""
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "src", "configs"], cwd=REPO, capture_output=True, text=True, timeout=10).stdout.strip()
        return (sha or "unknown") + ("-dirty" if dirty and sha else "")
    except Exception:  # noqa: BLE001
        return "unknown"


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, timeout=30).stdout
    except Exception:  # noqa: BLE001
        return ""


@functools.lru_cache(maxsize=1)
def git_sha() -> str:
    """Full SHA of HEAD of the code that runs, 'unknown' outside a git checkout."""
    return _git("rev-parse", "HEAD").strip() or "unknown"


@functools.lru_cache(maxsize=1)
def git_dirty() -> bool:
    """True when `src/` or `configs/` has uncommitted changes (`git status --porcelain`)."""
    return bool(_git("status", "--porcelain", "--", "src", "configs").strip())


@functools.lru_cache(maxsize=1)
def code_tree_hash() -> str:
    """SHA-256 (hex) over the path and content hash of every tracked `src/**/*.py` and `configs/**` file as it is on disk now (an edit changes it even without a commit)."""
    h = hashlib.sha256()
    for rel in sorted(_git("ls-files", "-z", "--", "src", "configs").split("\0")):
        p = REPO / rel
        if rel and p.is_file() and (rel.startswith("configs/") or rel.endswith(".py")):
            h.update(rel.encode())
            h.update(hashlib.sha256(p.read_bytes()).digest())
    return h.hexdigest()


@functools.lru_cache(maxsize=1)
def config_hash() -> str:
    """SHA-256 (first 16 hex) over every configs/**/*.yaml, in sorted order."""
    h = hashlib.sha256()
    for p in sorted((REPO / "configs").rglob("*.yaml")):
        h.update(p.relative_to(REPO).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def file_hash(path: str | Path) -> str | None:
    """SHA-256 (first 16 hex) of a file, None when it does not exist."""
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.is_file() else None


def _nli_manifest() -> dict[str, Any]:
    """The NLI backend of the run for the manifest: the real model, or 'offline stand-in (reason)'. Resolving it here makes `auto` choose (and a failure to load show) before the first case."""
    from vakeel_sahayak.models.factory import get_nli
    from vakeel_sahayak.models.nli import nli_status

    try:
        client = get_nli()
        if getattr(client, "fallback_reason", None) is None and not getattr(client, "is_offline", False):
            client.entails("warm up", "warm up")  # loads the weights now, so a missing checkpoint is a recorded fallback and not a mid-case surprise
    except Exception as exc:  # noqa: BLE001
        return {"backend": None, "fallback_reason": f"{type(exc).__name__}: {str(exc)[:200]}"}
    st = nli_status()
    return {**st, "label": f"nli: offline stand-in ({st['fallback_reason']})" if st["fallback_reason"] else f"nli: {st['backend']}"}


PROMPT_FILES = ("src/vakeel_sahayak/models/prompting.py",)  # plus every agents/**/prompts.py


@functools.lru_cache(maxsize=1)
def prompt_hash() -> str:
    """SHA-256 (first 16 hex) over the prompt templates of the code under test: `models/prompting.py` and every `agents/**/prompts.py`, in sorted order.

    It changes when a template changes, so two manifests with the same hash ran the same prompt text (the switch set is recorded beside it)."""
    h = hashlib.sha256()
    files = [REPO / f for f in PROMPT_FILES] + sorted((REPO / "src" / "vakeel_sahayak" / "agents").rglob("prompts.py"))
    for p in files:
        if p.is_file():
            h.update(p.relative_to(REPO).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def system_scope(system: str) -> str:
    """What the system changes in a per-case run (`runners.systems.SCOPES`); 'pipeline' for a label that is not a system id (tests, ad hoc runs)."""
    from vakeel_sahayak.eval.runners.systems import SCOPES, scope_of

    try:
        return SCOPES[scope_of(system)]
    except ValueError:
        return SCOPES["pipeline"]


def shared_cache_for(switches: Any) -> Any:
    """A fresh in-memory retrieval cache for the batch variants (plan cache S14, shared prefix S14d), else None (the default run is unchanged)."""
    if getattr(switches, "plan_cache", False) or getattr(switches, "prefix_layout", False):
        from vakeel_sahayak.batch.cache import RetrievalCache

        return RetrievalCache()
    return None


def _gold_manifest(cases_path: str | None) -> dict[str, Any]:
    """`gold_source` (agreed | rule) and `gold_sha256` of the T1 gold the cases carry (None for the other test sets); see testsets/gold_source.py."""
    if cases_path and Path(cases_path).parent.name[:2] in {f"t{k}" for k in range(2, 10)}:
        return {"gold_source": None, "gold_sha256": None}
    from vakeel_sahayak.testsets.gold_source import gold_info_for_cases

    return gold_info_for_cases(cases_path)


def _system_manifest_extra(system: str) -> dict[str, Any] | None:
    """Manifest keys only some systems add: `b0l_model` (the hosted model id B0L runs on; nothing for the offline and local paths or any other system)."""
    if system.lower() == "b0l":
        from vakeel_sahayak.eval.baselines.b0_single_pass import b0l_model_id

        try:
            model = b0l_model_id()
        except NotImplementedError:
            model = None
        return {"b0l_model": model} if model else None
    return None


def _store_vectors_manifest() -> dict[str, Any]:
    """`store_embedder` (hashed-ngram by default, bge-m3 with the opt-in VS_STORES=bge) and `store_vectors` (mode and per-store side-file stamps), see `stores.hybrid.store_vectors_manifest`;
    B2/B3 and the retrieval metrics are reported per store embedder."""
    from vakeel_sahayak.stores.hybrid import store_vectors_manifest

    info = store_vectors_manifest()
    return {"store_embedder": info["store_embedder"], "store_vectors": info}


def write_run_manifest(out_dir: Path, *, system: str, switches: Any, seed: int, budgets: dict[str, int] | None = None,
                       cases_path: str | None = None, shard: int = 0, n_shards: int = 1, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write `MANIFEST.json`: code version, config hash, model/version/date stamp, seed, switches, budgets, the case-file hash."""
    from vakeel_sahayak.config import load_config
    b = load_config().budgets
    manifest = {
        "system": system, "variant": switches.variant(), "describe": switches.describe(), "scope": system_scope(system),
        "prompt_hash": prompt_hash(), "switches": switches.model_dump(), "seed": seed,
        "budgets": {"tokens_per_case": b.tokens_per_case, "store_calls_per_factor": b.store_calls_per_factor,
                    "tokens_per_factor": b.tokens_per_factor, "drafting_tokens_per_factor": b.drafting_tokens_per_factor, **(budgets or {})},
        "code_version": code_version(), "git_sha": git_sha(), "git_dirty": git_dirty(), "code_tree_hash": code_tree_hash(), "config_hash": config_hash(), "models": models_stamp(), "nli": _nli_manifest(),
        "cases_file": cases_path, "cases_hash": file_hash(cases_path) if cases_path else None, **_gold_manifest(cases_path),
        "shard": shard, "n_shards": n_shards, "privacy": privacy_manifest(cases_path), **_store_vectors_manifest(), **(extra or {}),
    }
    save_json(out_dir / "MANIFEST.json", manifest)
    return manifest


# ---------------------------------------------------------------------------------------------------------------- smoke CLI
def fixture_toolbox() -> tuple[dict[str, Any], dict[str, Any]]:
    """The case-0007 fixture world on the offline stand-ins (tests/fixtures through tests.fakes): tools and the case row."""
    root = str(REPO)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tests.fakes.data import build_world
    from tests.fakes.toolbox import FakeToolbox

    world = build_world()
    toolbox = FakeToolbox(world)
    case = {"case_id": "case-0007", "before": world.case_date, "facts": SMOKE_FACTS}
    return toolbox.tools, case


def smoke(argv: list[str] | None = None) -> int:
    """Run the case-0007 fixture end to end offline and print the grounds, their statuses and the sparring verdicts; 0 on success."""
    import os
    import tempfile

    os.environ.setdefault("VS_MODELS", "offline")
    os.environ.setdefault("VS_LLM_BACKEND", "offline")
    os.environ.setdefault("VS_DATA_DIR", tempfile.mkdtemp(prefix="vs-smoke-"))
    tools, case = fixture_toolbox()
    from vakeel_sahayak.eval.baselines import full_system

    ctx = build_context(case, tools=tools)
    result = full_system.run_pipeline(case, ctx, ScriptedCounsel(approve_gate1=True, approve_gate2=False))
    print(f"case {case['case_id']}: gate1 approved={result['gate1_approved']}, gate2 approved={result['gate2_approved']}, "
          f"export blocked={result['export'].get('blocked')}")
    print("BailBrief grounds:")
    for g in result["brief"]["grounds"]:
        print(f"  {g['id']}  {g['factor']:<28} stance={g['stance']:<12} check={g['check']}  state={g['state']}")
    print("SparringRecord verdicts:")
    spar = result["sparring"]
    for o in (spar or {}).get("objections", []):
        print(f"  {o['id']}  {o['factor']:<28} verdict={o['verdict']}")
    if not (spar or {}).get("objections"):
        print("  (no objections raised by the offline stand-in)")
    meta = run_metadata(ctx, 0, "full")
    print(f"tokens={meta['tokens']} store_calls={meta['store_calls']} errors={result['errors']}")
    ok = bool(result["brief"]["grounds"]) and result["export"].get("blocked") is True
    print("SMOKE OK" if ok else "SMOKE FAILED")
    return 0 if ok else 1


def eval_smoke(argv: list[str] | None = None) -> int:
    """Run 3 T1 dev cases offline (data/testsets/t1/dev.jsonl; build it with the T1 builder) through the Full system; 0 on success."""
    import os
    import tempfile

    os.environ.setdefault("VS_MODELS", "offline")
    os.environ.setdefault("VS_LLM_BACKEND", "offline")
    ap = argparse.ArgumentParser(prog="eval-smoke")
    ap.add_argument("--cases", default=str(REPO / "data" / "testsets" / "t1" / "dev.jsonl"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--n", type=int, default=3)
    args = ap.parse_args(argv)
    if not Path(args.cases).is_file():
        print(f"no dev cases at {args.cases}: build T1 first (python -m vakeel_sahayak.testsets.t1_court_grounded)")
        return 2
    os.environ.setdefault("VS_DATA_DIR", tempfile.mkdtemp(prefix="vs-eval-smoke-"))
    from vakeel_sahayak.eval.baselines import full_system

    out = args.out or tempfile.mkdtemp(prefix="vs-eval-smoke-out-")
    n = run_cases(args.cases, out, "full", full_system.run_case, limit=args.n)
    done = load_progress(out)
    print(f"completed {n} dev case(s) offline into {out}: {sorted(done)}")
    return 0 if n >= 1 or done else 1


# ---------------------------------------------------------------------------------------------------------------- run, plan, smoke-all
def run_system(argv: list[str] | None = None) -> int:
    """`driver run --system <id> [--cases F] [--out DIR] [--n N] [--shard i --n-shards k] [--seed S] [--run-index K]`: one system on a case file, through
    `systems.system_runner` (the single entry for Full, the baselines, the ablations and every implemented variant). Writes the per-case outputs, `_events/` and
    `MANIFEST.json` (switch set, `Switches.describe()`, prompt hash, code and config hashes, models, seed). A declared but unbuilt id exits 2 with the reason.

    Default cases are the 200 T1 test cases in the fixed run order (`data/testsets/t1/cases.jsonl`); default output is `data/eval/runs/adhoc/outputs/<system>`.
    Hosted models are chosen by the environment as for `eval-smoke` (see the module docstring); with nothing set the offline stand-ins run."""
    from vakeel_sahayak.eval.runners.systems import canonical_system, system_runner

    ap = argparse.ArgumentParser(prog="driver run")
    ap.add_argument("--system", required=True)
    ap.add_argument("--cases", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--run-id", default="adhoc")
    ap.add_argument("--run-index", type=int, default=1, help="repeat number: output goes to <system>__run<k> for k > 1 and the seed is k")
    ap.add_argument("--n", type=int, default=None, help="stop after this many cases of the shard")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--gold-source", choices=["agreed", "rule"], default=None, help="T1 gold for the default case file: agreed (primary, default) or rule (secondary); env VS_GOLD_SOURCE")
    args = ap.parse_args(argv)
    try:
        system = canonical_system(args.system)
        runner, switches = system_runner(system)
    except NotImplementedError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.cases:
        cases = args.cases
    else:
        from vakeel_sahayak.eval.runners.jobs import t1_cases_path

        cases = str(t1_cases_path(args.gold_source))
    if not Path(cases).is_file():
        print(f"ERROR: no case file at {cases}: build T1 first (python -m vakeel_sahayak.testsets.t1_court_grounded)", file=sys.stderr)
        return 2
    out = args.out or str(outputs_dir(args.run_id, system, args.run_index))
    seed = args.seed if args.seed is not None else args.run_index
    n = run_cases(cases, out, system, runner, switches, shard=args.shard, n_shards=args.n_shards, seed=seed, limit=args.n)
    print(f"{system} ({switches.describe()}): {n} case(s) completed now, {len(load_progress(out))} saved in {out}")
    return 0


def plan_command(argv: list[str] | None = None) -> int:
    """`driver plan --job <name>[,<name>...] | --all | --sarvam-full`: print the cases, systems, runs, estimated tokens and cost of a job of configs/eval/runs.yaml. Runs nothing and calls no model."""
    from vakeel_sahayak.eval.runners import plan

    ap = argparse.ArgumentParser(prog="driver plan")
    ap.add_argument("--job", default=None)
    ap.add_argument("--all", action="store_true", help="one line per job in priority order, with the running OpenAI spend")
    ap.add_argument("--sarvam-full", action="store_true", help="price every generative job on Sarvam-105B: the credits needed to run everything there (cap: VS_SARVAM_CAP_INR or budgets.sarvam_cap_inr)")
    ap.add_argument("--sweep", action="store_true", help="the pre-freeze dev-set sweep of configs/eval/sweep_dev.yaml: every arm with backend, cases, runs and the spend still to pay")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.sweep:
            rows = plan.sweep_rows()
            print(json.dumps(rows, indent=1) if args.json else plan.format_sweep(rows))
        elif args.sarvam_full:
            print(plan.sarvam_full_view())
        elif args.all or not args.job:
            rows = plan.plan_all()
            print(json.dumps(rows, indent=1) if args.json else plan.format_table(rows))
        else:
            rows = plan.jobs_plan([j.strip() for j in args.job.split(",") if j.strip()])
            if args.json:
                print(json.dumps(rows, indent=1))
            else:
                print("\n".join(plan.format_plan(p) for p in rows))
                spend, warnings = plan.spend_summary(rows)
                print(f"planned on openai: {spend['openai_usd']:.2f} USD; planned on sarvam: INR {spend['sarvam_inr']:.2f}")
                print("\n".join(warnings))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def _smoke_data_dir(stores: str) -> str:
    """A scratch data directory for a smoke run. `real` links the built stores into it (read only use), so retrieval is the system that is measured; nothing is written to `data/`."""
    import os
    import tempfile

    root = tempfile.mkdtemp(prefix="vs-smoke-all-")
    real = REPO / "data" / "stores"
    if stores == "real" and real.is_dir():
        os.symlink(real, Path(root) / "stores")
    return root


def smoke_all(argv: list[str] | None = None) -> int:
    """`driver smoke-all [--ids a,b] [--n 1] [--stores real|empty] [--out DIR]`: run every dispatchable id (Full, the baselines, every implemented variant; A5, A10 and S13
    once per default arm) offline on the first T1 dev case(s) and print a pass/fail table; a variant that is declared but unbuilt (none today) must be refused loudly to pass. 0 when all pass.

    Offline only: `VS_MODELS`, `VS_LLM_BACKEND` and `VS_EXTERNAL` are forced to the offline stand-ins and `VS_DATA_DIR` is a scratch directory (stores linked read-only with
    `--stores real`, the default when `data/stores` exists). A row passes when the case completed with no crashed-case error and no stage error, and the manifest
    names the switch set, its `describe()` line and the prompt hash."""
    import os
    import tempfile

    ap = argparse.ArgumentParser(prog="driver smoke-all")
    ap.add_argument("--cases", default=str(REPO / "data" / "testsets" / "t1" / "dev.jsonl"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--ids", default=None, help="comma-separated subset of ids (default: all)")
    ap.add_argument("--stores", choices=["real", "empty"], default="real" if (REPO / "data" / "stores").is_dir() else "empty")
    ap.add_argument("--json", default=None, help="also write the table as JSON here")
    args = ap.parse_args(argv)
    if not Path(args.cases).is_file():
        print(f"no dev cases at {args.cases}: build T1 first (python -m vakeel_sahayak.testsets.t1_court_grounded)")
        return 2
    os.environ.update(VS_MODELS="offline", VS_LLM_BACKEND="offline", VS_EXTERNAL="off", VS_NLI="offline", VS_HEAVY_CLIENTS="offline")
    os.environ["VS_DATA_DIR"] = _smoke_data_dir(args.stores)
    from vakeel_sahayak.eval.runners.systems import canonical_system, dispatchable_ids, system_runner
    from vakeel_sahayak.orchestration.switches import IMPLEMENTED_VARIANTS, _variant_table

    unbuilt = sorted(k for k in _variant_table() if k not in IMPLEMENTED_VARIANTS)  # declared but unbuilt: must be refused loudly (empty since S15b was built)
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else dispatchable_ids() + unbuilt
    out_root = Path(args.out or tempfile.mkdtemp(prefix="vs-smoke-all-out-"))
    rows: list[dict[str, Any]] = []
    for ident in ids:
        row: dict[str, Any] = {"id": ident, "status": "FAIL", "seconds": 0.0, "tokens": 0, "variant": "", "detail": ""}
        t0 = time.monotonic()
        try:
            system = canonical_system(ident)
            runner, switches = system_runner(system)
            row["variant"] = switches.variant()
            out = outputs_dir("smoke-all", system, 1, root=str(out_root))
            run_cases(args.cases, str(out), system, runner, switches, limit=args.n)
            saved = sorted(out.glob("t1*.json"))
            manifest = json.loads((out / "MANIFEST.json").read_text(encoding="utf-8"))
            rec = json.loads(saved[0].read_text(encoding="utf-8")) if saved else {}
            problems = []
            if len(saved) < args.n:
                problems.append(f"{len(saved)} of {args.n} case(s) saved")
            if rec.get("error"):
                problems.append(f"case error: {rec['error']}")
            if rec.get("errors"):
                problems.append("stage errors: " + "; ".join(rec["errors"])[:300])
            for key in ("describe", "prompt_hash", "switches", "variant"):
                if not manifest.get(key):
                    problems.append(f"manifest lacks {key}")
            row["tokens"] = int((rec.get("meta") or {}).get("tokens", 0))
            row["status"], row["detail"] = ("FAIL", " | ".join(problems)) if problems else ("PASS", manifest["describe"][:90])
        except NotImplementedError as exc:
            expected = ident.upper() in {u.upper() for u in unbuilt}
            row["status"], row["detail"] = ("PASS", f"refused loudly as declared-but-unbuilt: {str(exc)[:70]}") if expected else ("FAIL", f"NotImplementedError: {str(exc)[:200]}")
        except Exception as exc:  # noqa: BLE001 - one id's crash is a row of the table, the others still run
            row["detail"] = f"{type(exc).__name__}: {str(exc)[:240]}"
        row["seconds"] = round(time.monotonic() - t0, 1)
        rows.append(row)
        print(f"{row['status']:<5}{ident:<28}{row['seconds']:>7.1f}s {row['tokens']:>8} tok  {row['detail'][:140]}", flush=True)
    failed = [r["id"] for r in rows if r["status"] != "PASS"]
    print(f"\nsmoke-all: {len(rows) - len(failed)} of {len(rows)} passed offline on {args.n} T1 dev case(s); outputs in {out_root}" + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    if args.json:
        Path(args.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 1 if failed else 0


def paid_backend_locked() -> str | None:
    """The lock message when `VS_LLM_BACKEND` (or the labeler/teacher variables) name a paid provider that is locked (`models.paid_lock`), else None.

    The driver refuses to start then, instead of letting every agent call fall back to the local client and producing a run that is not the
    backend it claims to be."""
    import os

    from vakeel_sahayak.models.paid_lock import lock_message, paid_unlocked

    for var in ("VS_LLM_BACKEND", "VS_LABELER", "VS_TEACHER"):
        name = (os.environ.get(var) or "").strip().lower()
        if name and not paid_unlocked(name):
            return f"{var}={name}: " + lock_message(name)
    return None


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.eval.runners.driver smoke|eval-smoke|smoke-all|run|plan`."""
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args.pop(0) if args else "smoke"
    if cmd != "plan":
        locked = paid_backend_locked()
        if locked:
            print(locked, file=sys.stderr)
            return 3
    commands = {"smoke": smoke, "eval-smoke": eval_smoke, "smoke-all": smoke_all, "run": run_system, "plan": plan_command}
    if cmd in commands:
        return commands[cmd](args)
    print("usage: driver smoke | eval-smoke | smoke-all | run --system <id> | plan --job <name>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
