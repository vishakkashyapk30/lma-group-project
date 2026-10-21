"""Vakeel agent (plan §3.2). Drafting, checking and repair, the hearing card (plan §8). Qwen3-14B on Ada.

Vakeel is the advocate. From Sutradhar's evidence packs, the approved dossier and the RightsReport it:

1. **drafts** one ground per chosen factor. The model writes sentences that end with ID markers, `[F:field]` for a
   dossier fact and `[A:doc#para]` for a retrieved paragraph; citation text is rendered from corpus metadata with
   `render_citation` (an unknown doc id is an error, a case name is never invented). Vakeel itself adds the label
   "per counsel, not on record" to a USER_STATED fact and a qualification to a CHANGED precedent;
2. **replies** to Abhiyojak's objections under the same rules (`reply_to_objections`);
3. **checks** every claim, sentence by sentence: fact support (`check_claim` against the dossier quote), authority
   support (against the cited paragraph), the transfer and good-law flags, and no citation that was not retrieved;
4. **repairs or flags**, at most two rounds: a failed authority is re-retrieved through Sutradhar or swapped, a
   failed sentence is reworded to what its source supports; a claim that still fails is NEEDS_REVIEW and says why in
   the open issues. Nothing is dropped silently: every decision is an event with actor VAKEEL;
5. **assembles** the `BailBrief` (statutory position, grounds with their `depends_on`, open issues, the fixed label)
   and the hearing-prep card data (`build_hearing_card`).

Variant S8 / A2b (`Switches.repair_mode='self_critique'`, default 'grounded'): steps 3 and 4 use the drafting model's own re-reading instead of
the NLI and tool checks, see `_self_review`. Papers: Gou et al., "CRITIC: Large Language Models Can Self-Correct with Tool-Interactive
Critiquing", ICLR 2024, https://mlanthology.org/iclr/2024/gou2024iclr-critic/ (the critique step is where outside tools help);
Huang et al., "Large Language Models Cannot Self-Correct Reasoning Yet", ICLR 2024, https://iclr.cc/virtual/2024/poster/18956 (without
outside feedback self-correction does not help and can hurt); Zhang et al., "Small Language Models Need Strong Verifiers to Self-Correct
Reasoning", Findings of ACL 2024, https://aclanthology.org/2024.findings-acl.924 (small models need a strong verifier). This is the
no-verifier control arm of those papers' contrast, not a reproduction of any of them: their tasks are QA, maths and code, ours is
claim repair against a source.

Variant S15 / A13 (`Switches.output_format='reasoning_first'`, default 'answer_only'): the drafting, reply and reword schemas get a free-text
`reasoning` field BEFORE the answer fields (`prompts.DraftedGroundReasoned`, `ReasonedReply`). Papers: Tam et al., "Let Me Speak Freely? A Study On
The Impact Of Format Restrictions On Large Language Model Performance", EMNLP 2024 Industry, https://aclanthology.org/2024.emnlp-industry.91
(strict format restrictions hurt reasoning, more so the stricter they are); Banerjee et al., "CRANE: Reasoning with Constrained LLM Generation",
ICML 2025, https://proceedings.mlr.press/v267/banerjee25a.html (answer-only grammars cut reasoning; let the model reason freely, then constrain the
answer). What we took: reasoning-before-answer inside one constrained schema, so decoding stays valid. What we changed: both papers test
reasoning benchmarks; ours is claim drafting with ID markers, so the reasoning is stored in a log event (`reasoning_first`) and the agent's
`reasoning_of`, and is never parsed for markers, cited, checked or shown: only the `argument` / `text` field is read as the claim. The token limit
of a call grows by `REASONING_ROOM`. CRANE's switching between free and constrained decoding is not implemented (the field order does the job
on a schema-constrained backend). Not implemented: `free_then_parse` (S15b).

`redraft(claims, ...)` rewrites only the stale grounds and leaves the others word for word (plan §10). Switches: A1 (no
dossier: the facts text), A2 and A9 (no check-and-repair), A3 (no rule tools: the model judges the transfer and the rights
itself), A8 and A9 (no sparring: no replies). Vakeel is callable on its own:

    agent = VakeelAgent(case_id="case-0007", log=log)
    state = agent.run(CaseGraphState(case_id="case-0007", evidence_packs=packs, dossier=dossier, rights=rights))
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from vakeel_sahayak.agents.base import AgentContext, BaseAgent, prediction_language
from vakeel_sahayak.agents.vakeel import offline  # noqa: F401  (importing `offline` registers the offline handlers)
from vakeel_sahayak.agents.vakeel.brief import (
    case_refs_of,
    changed_provision_issue,
    depends_on,
    statutory_position,
)
from vakeel_sahayak.agents.vakeel.claims import (
    MARKER,
    Sentence,
    add_label,
    join_claim,
    note,
    split_claim,
)
from vakeel_sahayak.agents.vakeel.facts import (
    FACTOR_FIELDS,
    FACTOR_RIGHTS,
    FACTS_TEXT_FIELD,
    Fact,
    facts_of,
    rights_lines,
    text_fact,
)
from vakeel_sahayak.agents.vakeel.hearing import build_card
from vakeel_sahayak.agents.vakeel.prompts import (
    REASONING_NOTE,
    SYSTEM_PROMPT,
    TASK_DEBATE,
    TASK_DRAFT,
    TASK_REPLY,
    TASK_REWORD,
    TASK_RIGHTS,
    TASK_SELF_CRITIQUE,
    TASK_SELF_REVISE,
    TASK_TRANSFER,
    DraftedGround,
    DraftedGroundReasoned,
    ReasonedReply,
    RightsSummary,
    SelfReview,
    TransferJudgement,
    instructions,
)
from vakeel_sahayak.agents.vakeel.work import AUTHORITY_PROBLEMS, Evidence, SentenceCheck, Work
from vakeel_sahayak.models.base import ModelUnavailable
from vakeel_sahayak.orchestration.budgets import BudgetExhausted
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.structured_output import StructuredOutputError
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, DependsOn, Ground, OpenIssue
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import (
    AgentName,
    ClaimCheck,
    ClaimState,
    EventKind,
    Factor,
    FactorStance,
    GoodLawStatus,
    OpenIssueType,
    TransferFlag,
)
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
from vakeel_sahayak.schemas.sparring import Objection, Reply, SparringRecord
from vakeel_sahayak.schemas.store_rows import TimelineEvent
from vakeel_sahayak.tools.base import ToolError
from vakeel_sahayak.tools.types import ClaimCheckResult

MAX_REPAIR_ROUNDS = 2  # plan §8.1 step 4 (configs/budgets.yaml repair_rounds)
# A case name or a reporter citation written into the text: the model writes IDs only, citations are rendered from the corpus.
CASE_NAME = re.compile(r"\b[A-Z][\w.'&-]*(?:\s+(?:[A-Z][\w.'&-]*|of|and|the|&))*\s+vs?\.?\s+[A-Z][\w.'&-]*")
REPORTER = re.compile(r"\(\d{4}\)\s*\d+\s*(?:SCC|SCR|AIR|Cri)|\bAIR\s+\d{4}|\bSCC\s+OnLine|\b\d{4}\s+SCC\b|\bCri\.?\s?L\.?J\b")
DRAFT_SAMPLES = 3  # S11c: independent drafts of one ground that are voted on
DRAFT_TEMPERATURE = 0.7  # S11b / S11c: independent drafts need a non-zero temperature on a hosted model
CONVERGED = 0.8  # S11b: similarity of the two final drafts from which the debate counts as converged
_SIM_WORD = re.compile(r"[a-z]{4,}")
REASONING_ROOM = 1.8  # S15: factor on the token limit of a drafting call, to leave room for the reasoning field
REASONING_LOG_CHARS = 1500  # S15: characters of reasoning kept in the log event
MAX_AUTHORITIES = 4  # paragraphs offered to the drafter per factor
PARAGRAPH_LIMIT = 2000  # characters of a paragraph shown to the model
UNCHECKED = ClaimCheck.NEEDS_REVIEW  # A2/A9 run no check, so no claim may claim to be SUPPORTED
NO_REPLY = "No supported reply could be drafted from the retrieved material: counsel to answer this objection."
NO_GROUND = "No supported argument could be drafted from the evidence for this factor: counsel to draft it."
_TRANSFER_RANK = {TransferFlag.SAME_TEXT: 0, TransferFlag.CHANGED: 1, TransferFlag.NEW: 2}
_ID = re.compile(r"^G(\d+)$")
SELF_CRITIQUE_NOTICE = (
    "Claims in this brief were checked by the model's own re-reading only (variant S8 / A2b): no source check, no authority "
    "retrieval and no entailment test was run on them. Counsel to verify each claim against the papers."
)


class VakeelAgent(BaseAgent):
    """Drafting, checking and repair, the hearing card (plan §8). Qwen3-14B on Ada."""

    NAME = AgentName.VAKEEL
    ROLE_MODEL = "agents_14b"
    SYSTEM_PROMPT = SYSTEM_PROMPT

    def __init__(
        self,
        ctx: AgentContext | None = None,
        *,
        case_id: str | None = None,
        log: EventLog | None = None,
        switches: Switches | None = None,
        llm: Any = None,
        nli: Any = None,
        tools: dict[str, Any] | None = None,
        cases_dir: str | None = None,
        before: str | None = None,
        retriever: Callable[..., EvidencePack | None] | None = None,
        max_rounds: int | None = None,
    ) -> None:
        """Create Vakeel, from an AgentContext or from plain arguments (the graph is optional).

        Args:
            ctx: the injected context (case id, log, budget, switches, LLM, NLI client, toolbox)
            case_id: the case (needed when there is no context)
            log: the case's event log (default: the configured per-case log)
            switches: ablation switches (A1, A2, A3, A8, A9 are read here)
            llm: the `agents_14b` client
            nli: the NLI client the A1 check uses (the tools use their own)
            tools: a toolbox that replaces the registry's tools (fakes in tests)
            cases_dir: cases folder for the event log
            before: the case's order date when the graph state carries none
            retriever: `fn(state, factor, reason, bad_docs) -> EvidencePack | None`, how a failed authority is re-retrieved
                (default: Sutradhar's `resolve_failed_claim` through a peer agent)
            max_rounds: repair rounds (default: configs/budgets.yaml `repair_rounds`, 2: plan §8.1)
        """
        if ctx is None:
            if not case_id:
                raise ValueError("Vakeel needs a case_id or an AgentContext")
            ctx = AgentContext(
                case_id=case_id, log=log, switches=switches or Switches(), llm=llm, nli=nli,
                tools=dict(tools or {}), cases_dir=cases_dir, before=before,
            )  # fmt: skip
        super().__init__(ctx)
        self.retriever = retriever
        self._max_rounds = max_rounds
        self._peers: dict[AgentName, BaseAgent] = {}
        self._draft_stats: dict[str, Any] = {}  # S11b / S11c counters (empty in a default run)
        self._reasoning: list[dict[str, Any]] = []  # S15: the free reasoning of each drafting call (stored, never cited)
        self._repair_stats: dict[str, int] = {}  # S8 counters over the agent's life, i.e. the case (empty in a default run)
        self._reset()

    @property
    def max_rounds(self) -> int:
        """Repair rounds: the constructor's, else configs/budgets.yaml `repair_rounds` (read at use, so a changed config counts)."""
        if self._max_rounds is not None:
            return int(self._max_rounds)
        return int(getattr(getattr(self.config, "budgets", None), "repair_rounds", MAX_REPAIR_ROUNDS))

    def _reset(self) -> None:
        self._state: CaseGraphState | None = None
        self._dossier: Any = None
        self._rights: Any = None
        self._facts: dict[str, Fact] = {}
        self._timeline: list[TimelineEvent] = []
        self._sections: list[dict[str, Any]] = []  # A1: sections read off the facts text
        self._packs: dict[str, EvidencePack] = {}
        self._auth_items: dict[tuple[str, int], dict[str, Any]] = {}
        self._ret_pairs: set[tuple[str, int]] = set()
        self._ret_docs: set[str] = set()
        self._gl_pack: dict[str, dict[str, Any]] = {}
        self._work: dict[str, Work] = {}
        self._grounds: list[Ground] = []
        self._brief: BailBrief | None = None
        self._auth_cache: dict[tuple[str, int], Authority] = {}
        self._auth_info: dict[tuple[str, int], dict[str, Any]] = {}
        self._check_cache: dict[str, SentenceCheck] = {}
        self._thr: tuple[float, float] | None = None
        self._case_pairs: list[tuple[str, str | None]] = []

    # ------------------------------------------------------------------ small plumbing

    def _decision(self, tool: str, text: str = "", **outputs: Any) -> None:
        """One event for a decision (actor VAKEEL; tool `draft`, `check`, `repair`, `flag`, `qualify`, `reply`, ...)."""
        self.emit(EventKind.AGENT_MESSAGE, {"tool": tool, "outputs": {"type": tool, "text": text, **outputs}})

    def _tool(self, name: str, **kwargs: Any) -> Any:
        """call_tool, with a refused or failed call coming back as a ToolError rather than an exception."""
        from vakeel_sahayak.tools.registry import ToolPermissionError

        try:
            return self.call_tool(name, **kwargs)
        except ToolPermissionError as exc:
            return ToolError(tool=name, kind="permission_denied", message=str(exc), retryable=False)

    def _safe_ask(self, task: str, instructions: str, *, factor: Any = None, **kw: Any) -> Any:
        """`ask`, with a spent budget, a model that cannot answer or a refused payload coming back as None (logged, never silent)."""
        try:
            return self.ask(task, instructions, factor=factor, **kw)
        except (BudgetExhausted, StructuredOutputError, ModelUnavailable, PrivacyBoundaryError) as exc:
            self._decision("model_failed", f"{task} could not be answered: {type(exc).__name__}", task=task, error=type(exc).__name__)
            return None

    def _thresholds(self) -> tuple[float, float]:
        if self._thr is None:
            from vakeel_sahayak.models.nli import nli_threshold

            try:
                nli = self.get_nli()
                self._thr = (nli_threshold("fact_support", nli, self.config), nli_threshold("authority_support", nli, self.config))
            except Exception:  # noqa: BLE001 - an unreadable threshold falls back to the neutral cut-off
                self._thr = (0.5, 0.5)
        return self._thr

    def _peer(self, name: AgentName) -> BaseAgent:
        if name not in self._peers:
            from vakeel_sahayak.agents.registry import create_agent

            self._peers[name] = create_agent(name, self.ctx)
        return self._peers[name]

    # ------------------------------------------------------------------ inputs

    def _prime(self, state: CaseGraphState) -> None:
        """Read what drafting rests on: the approved dossier (A1: the facts text), the RightsReport (not A3), the timeline, the packs."""
        self._reset()
        self._state = state
        sw = self.switches
        cs = None

        def case_state():  # noqa: ANN202
            nonlocal cs
            if cs is None:
                cs = self.case_state()
            return cs

        dossier = None
        if sw.uses_dossier:
            dossier = state.dossier
            if dossier is None:
                try:
                    dossier = case_state().dossier()
                except Exception:  # noqa: BLE001 - a case with no log yet simply has no dossier
                    dossier = None
        rights = None
        if sw.uses_rule_tools:
            rights = state.rights
            if rights is None:
                try:
                    rights = case_state().rights_report()
                except Exception:  # noqa: BLE001
                    rights = None
        timeline = list(state.list_of_dates)
        if not timeline:
            try:
                timeline = case_state().timeline()
            except Exception:  # noqa: BLE001
                timeline = []
        self._dossier, self._rights, self._timeline = dossier, rights, timeline
        if sw.uses_dossier:
            self._facts = facts_of(dossier)
            tracked = dossier.fields.sections if dossier is not None else None
            self._case_pairs = [(f"{sv.code} {sv.section}", sv.equivalent) for sv in (tracked.value or [])] if tracked is not None else []
        else:
            from vakeel_sahayak.agents.sutradhar.factor_pick import signals_from_text

            self._facts = text_fact(state.facts_text)
            self._sections = signals_from_text(state.facts_text, state.before, None).sections
            self._case_pairs = [(str(s["ref"]), s.get("equivalent")) for s in self._sections if s.get("ref")]
        self._set_packs(state.evidence_packs)
        try:
            from vakeel_sahayak.tools.drafting.claims import retrieved_authorities

            pairs, docs = retrieved_authorities(self.log, self.case_id)
            self._ret_pairs |= pairs
            self._ret_docs |= docs
        except Exception:  # noqa: BLE001 - a log with no retrievals knows no more than the packs
            pass

    def _set_packs(self, packs: list[EvidencePack]) -> None:
        self._packs = {}
        for pack in packs:
            self._packs[pack.factor.value] = pack
            self._index_pack(pack)

    def _index_pack(self, pack: EvidencePack) -> None:
        """Note which paragraphs the pack retrieved (the only ones a claim may cite) and what it knows about good law."""
        for slot in pack.slots:
            for item in slot.items:
                if not isinstance(item, dict):
                    continue
                doc = item.get("doc_id")
                if not isinstance(doc, str):
                    continue
                if "chunk_id" in item or "event_id" in item:  # a client document, not a corpus paragraph
                    continue
                self._ret_docs.add(doc)
                para = item.get("para")
                if isinstance(para, int) and not isinstance(para, bool):
                    self._ret_pairs.add((doc, para))
                    if (doc, para) not in self._auth_items or (item.get("text") and not self._auth_items[(doc, para)].get("text")):
                        self._auth_items[(doc, para)] = item
                if slot.slot in ("good_law", "sc_root") or item.get("status") or item.get("sc_root"):
                    entry = self._gl_pack.setdefault(doc, {})
                    for k_src, k_dst in (("status", "status"), ("good_law", "status"), ("overruled_by", "overruled_by"), ("sc_root", "sc_root")):
                        if item.get(k_src):
                            entry[k_dst] = item[k_src]

    def _as_of(self) -> str | None:
        st = self._state
        return (self._dossier.as_of if self._dossier is not None else None) or (st.as_of if st is not None else None)

    def _is_overruled(self, doc: str, item: dict[str, Any] | None = None) -> bool:
        gl = self._gl_pack.get(doc, {})
        status = str(getattr(gl.get("status"), "value", gl.get("status")) or (item or {}).get("good_law") or "").upper()
        return status == "OVERRULED"

    def _candidates(self, pack: EvidencePack | None) -> tuple[list[dict[str, Any]], list[str]]:
        """Reasoning paragraphs of a pack worth offering to the drafter (in the pack's order), and the overruled ones left out."""
        if pack is None:
            return [], []
        out: list[dict[str, Any]] = []
        left_out: list[str] = []
        seen: set[tuple[str, int]] = set()
        for name in ("authority", "conditions"):
            for slot in (s for s in pack.slots if s.slot == name):
                for item in slot.items:
                    if not isinstance(item, dict) or "chunk_id" in item or not item.get("doc_id") or not isinstance(item.get("para"), int):
                        continue
                    part = str(getattr(item.get("part"), "value", item.get("part")) or "reasoning")
                    key = (str(item["doc_id"]), int(item["para"]))
                    if part != "reasoning" or key in seen:
                        continue
                    seen.add(key)
                    if self._is_overruled(key[0], item):
                        left_out.append(f"{key[0]}#{key[1]}")
                        continue
                    tr = item.get("transfer") if isinstance(item.get("transfer"), dict) else {}
                    out.append(
                        {"doc_id": key[0], "para": key[1], "text": str(item.get("text") or "")[:PARAGRAPH_LIMIT], "court": item.get("court"), "date": item.get("date"),
                         "transfer": tr.get("flag") if tr else None, "qualification": tr.get("qualification") if tr else None}
                    )  # fmt: skip
        return out[:MAX_AUTHORITIES], left_out

    def _evidence_for(self, pack: EvidencePack) -> Evidence:
        """The facts, paragraphs and Radar rows a factor's ground may rest on."""
        factor = pack.factor.value
        if self.switches.uses_dossier:
            names = FACTOR_FIELDS.get(factor, ())
            facts = {n: self._facts[n] for n in names if n in self._facts}
        else:
            facts = dict(self._facts)
        auths, left_out = self._candidates(pack)
        rights = rights_lines(self._rights, FACTOR_RIGHTS.get(factor, ())) if self._rights is not None else []
        return Evidence(
            factor=factor, stance=pack.stance.value, reason=pack.reason, facts=facts, auths=auths, rights=rights,
            open_issues=list(pack.open_issues), excluded=left_out, pack=pack,
        )  # fmt: skip

    # ------------------------------------------------------------------ prompts

    def _auth_payload(self, a: dict[str, Any]) -> dict[str, Any]:
        """A paragraph as the model sees it: its text wrapped as untrusted document data (plan §16)."""
        return {**a, "text": self.untrusted(str(a.get("text") or ""), SourceRef(doc=f"{a['doc_id']}#{a['para']}"))}

    def _prepare(self, sentences: list[Sentence]) -> list[Sentence]:
        """Deterministic touches the model is not trusted with: the per-counsel label on a USER_STATED fact."""
        user = {n for n, f in self._facts.items() if f.per_counsel}
        for s in sentences:
            if not s.is_note and add_label(s, user):
                self._decision("label", f"A sentence that cites counsel's own statement is labelled '{s.text.split('(')[-1].split(')')[0]}'.", facts=[f for f in s.facts if f in user])
        return sentences

    @staticmethod
    def _read_claim(out: Any, field: str) -> tuple[str, list[tuple[str, int]]]:
        """The text a model answer holds and the authorities it listed beside it (ids only: any citation text it wrote is ignored)."""
        if out is None:
            return "", []
        text = str(getattr(out, field, "") or "")
        listed = [(str(a.doc_id), int(a.para)) for a in getattr(out, "authorities", None) or []]
        return text, listed

    @property
    def _reasoning_first(self) -> bool:
        """S15 (A13): the drafting schemas carry a free reasoning field before the answer fields."""
        return self.switches.output_format == "reasoning_first"

    def _schema_and_limit(self, plain: Any, reasoned: Any, limit: int) -> tuple[Any, int]:
        """The reply schema of a drafting call and its token limit: the default's, or S15's reasoning-first schema with room for the reasoning."""
        return (reasoned, int(limit * REASONING_ROOM)) if self._reasoning_first else (plain, limit)

    def _ins(self, task: str, **kwargs: str) -> str:
        """The task's instructions; S15 adds the note on the reasoning field."""
        return instructions(task, **kwargs) + (REASONING_NOTE if self._reasoning_first else "")

    def _keep_reasoning(self, key: str, task: str, out: Any) -> None:
        """S15: store what the model reasoned (a log event and the agent's list). It is never read as an answer, never cited, never checked."""
        if not self._reasoning_first or out is None:
            return
        text = str(getattr(out, "reasoning", "") or "").strip()
        self._reasoning.append({"claim": key, "task": task, "chars": len(text), "words": len(text.split()), "text": text})
        self._decision(
            "reasoning_first", f"{key}: {len(text.split())} word(s) of reasoning before the answer (stored, never cited).", claim=key, task=task,
            chars=len(text), reasoning=text[:REASONING_LOG_CHARS], variant="S15", output_format="reasoning_first",
        )  # fmt: skip

    def reasoning_of(self, key: str) -> list[str]:
        """S15: the reasoning texts stored for a claim key ('G1', 'reply:O1'), in call order (empty in a default run)."""
        return [e["text"] for e in self._reasoning if e["claim"] == key]

    def output_signals(self) -> dict[str, Any]:
        """S15 signals for the evaluation (empty in a default run): calls, calls with an empty reasoning, characters and words of reasoning."""
        if not self._reasoning_first:
            return {}
        r = self._reasoning
        return {
            "variant": "S15", "output_format": "reasoning_first", "calls": len(r), "empty_reasoning": sum(1 for x in r if not x["chars"]),
            "reasoning_chars": sum(x["chars"] for x in r), "reasoning_words": sum(x["words"] for x in r),
        }  # fmt: skip

    def _emit_output_signals(self) -> dict[str, Any]:
        signals = self.output_signals()
        if signals:
            self._decision("output_signals", f"Reasoning-first output (S15): {signals['calls']} call(s), {signals['reasoning_words']} word(s) of reasoning.", **signals)
        return signals

    # ------------------------------------------------------------------ S11b / S11c: more than one draft of a ground

    @staticmethod
    def _signature(text: str) -> set[str]:
        """What a draft says, for comparing drafts: its markers and its words of four letters or more."""
        return set(MARKER.sub(lambda m: " ref_" + re.sub(r"\W", "", m.group(0)) + " ", text or "").lower().split()) | set(_SIM_WORD.findall(MARKER.sub("", text or "").lower()))

    @classmethod
    def _similarity(cls, a: str, b: str) -> float:
        """Jaccard similarity of two drafts' signatures (1.0 for two empty drafts)."""
        sa, sb = cls._signature(a), cls._signature(b)
        return len(sa & sb) / len(sa | sb) if (sa | sb) else 1.0

    def _medoid(self, texts: list[str], among: list[int] | None = None) -> tuple[int, float]:
        """The index (within `among`, default all) of the draft most like all the others, and its mean similarity to them (ties: the earliest)."""
        pool = list(range(len(texts))) if among is None else among
        best, best_score = pool[0], -1.0
        for i in pool:
            others = [self._similarity(texts[i], texts[j]) for j in range(len(texts)) if j != i]
            score = sum(others) / len(others) if others else 1.0
            if score > best_score + 1e-12:
                best, best_score = i, score
        return best, best_score

    def _draft_many(self, key: str, pack: EvidencePack, case: dict[str, Any], corpus: dict[str, Any], schema: Any, limit: int) -> Any:
        """S11c (`draft_mode='vote'`): three independent drafts, the one most like the others is kept. S11b (`'debate'`): two instances draft, each
        revises after reading the other's draft (two rounds), the final draft closer to all four texts is kept.

        Papers: Choi, Zhu and Li, "Debate or Vote", NeurIPS 2025, https://neurips.cc/virtual/2025/poster/116557 (voting explains most of debate's gain);
        Du et al., "Improving Factuality and Reasoning in Language Models through Multiagent Debate", ICML 2024, https://proceedings.mlr.press/v235/du24e.html
        (the debate protocol); Smit et al., "Should we be going MAD?", ICML 2024, https://proceedings.mlr.press/v235/smit24a.html. We took the protocols
        (three samples and a vote; two debaters, two rounds); we changed the aggregation: a free-text ground has no answer to count, so the vote is the
        medoid (the draft with the highest mean word-and-marker overlap with the others) and the two-debater result is the medoid of the final two against
        all four texts. Replies and rewording stay single-draft; the kept draft goes through the usual check and repair. Equal tokens are not enforced:
        the arms spend 3x and about 4x a single draft, and the spend is reported (`draft_signals`).
        """
        factor = pack.factor
        mode = self.switches.draft_mode
        label = "S11c" if mode == "vote" else "S11b"
        instr = self._ins(TASK_DRAFT, factor=factor.value, stance=pack.stance.value)
        start = sum(self._draft_tokens().values())

        def draw(tag: str, **extra: Any) -> Any:
            return self._safe_ask(TASK_DRAFT, instr, factor=factor, case={**case, **extra}, corpus=corpus, schema=schema, max_tokens=limit, temperature=DRAFT_TEMPERATURE)

        text = lambda o: str(getattr(o, "argument", "") or "")  # noqa: E731
        if mode == "vote":
            outs = [draw(f"s{i}", sample=i) for i in range(DRAFT_SAMPLES)]
            have = [o for o in outs if o is not None]
            if not have:
                self._decision("draft_vote", f"{key}: no draft could be obtained for the vote.", claim=key, variant=label, draft_mode=mode, drafts=0)
                return None
            texts = [text(o) for o in have]
            pick, agree = self._medoid(texts)
            chosen = have[pick]
            detail = {"drafts": len(have), "agreement": round(agree, 4), "chosen": pick}
        else:
            first = [draw(name, instance=name) for name in ("A", "B")]
            if any(o is None for o in first):
                have = [o for o in first if o is not None]
                chosen = have[0] if have else None
                self._decision("draft_debate", f"{key}: a debater could not draft; the other's draft stands.", claim=key, variant=label, draft_mode=mode, rounds=1)
                return chosen
            final = []
            for me, (own, other) in enumerate(((first[0], first[1]), (first[1], first[0]))):
                rev = self._safe_ask(
                    TASK_DEBATE, self._ins(TASK_DEBATE), factor=factor,
                    case={**case, "instance": "AB"[me], "own": text(own), "other": self.untrusted(text(other), SourceRef(doc=f"other draft {key}"))},
                    corpus=corpus, schema=schema, max_tokens=limit,
                )  # fmt: skip
                final.append(rev if rev is not None else own)
            texts = [text(o) for o in first] + [text(o) for o in final]
            pick, agree = self._medoid(texts, among=[2, 3])
            chosen = final[pick - 2]
            detail = {"rounds": 2, "agreement": round(agree, 4), "converged": self._similarity(texts[2], texts[3]) >= CONVERGED, "chosen": "AB"[pick - 2], "drafts": 4}
        spent = sum(self._draft_tokens().values()) - start
        st = self._draft_stats
        st["grounds"] = st.get("grounds", 0) + 1
        st["tokens_extra"] = st.get("tokens_extra", 0) + spent
        st["agreement_sum"] = st.get("agreement_sum", 0.0) + agree
        st["converged"] = st.get("converged", 0) + (1 if detail.get("converged") else 0)
        self._decision(
            "draft_vote" if mode == "vote" else "draft_debate", f"{key}: {mode} over {detail['drafts']} draft(s), agreement {agree:.2f}.",
            claim=key, variant=label, draft_mode=mode, tokens=spent, **detail,
        )  # fmt: skip
        return chosen

    def _draft_tokens(self) -> dict[str, int]:
        """Tokens spent so far on this case's budget by drafting-type calls of this agent (read from the shared budget's case total)."""
        snap = getattr(self.budgets, "snapshot", None)
        return {"case": int(getattr(snap(), "tokens_spent", 0))} if snap is not None else {"case": 0}

    def draft_signals(self) -> dict[str, Any]:
        """S11b / S11c signals (empty in a default run): grounds drafted by vote or debate, tokens they used, mean agreement, converged debates."""
        if self.switches.draft_mode == "single":
            return {}
        st = self._draft_stats
        n = st.get("grounds", 0)
        return {
            "variant": "S11c" if self.switches.draft_mode == "vote" else "S11b", "draft_mode": self.switches.draft_mode, "grounds": n,
            "tokens": st.get("tokens_extra", 0), "mean_agreement": round(st.get("agreement_sum", 0.0) / n, 4) if n else None,
            "converged": st.get("converged", 0) if self.switches.draft_mode == "debate" else None,
        }  # fmt: skip

    def _draft_work(self, key: str, pack: EvidencePack) -> Work:
        """Ask the model for one factor's ground and prepare it (no check yet)."""
        ev = self._evidence_for(pack)
        factor = pack.factor
        if ev.excluded:
            self._decision("authority_excluded", "Overruled authorities were not offered for drafting: " + ", ".join(ev.excluded), factor=factor.value, authorities=ev.excluded)
        case = {
            "id": key, "factor": factor.value, "label": factor.value.replace("_", " "), "stance": pack.stance.value, "reason": pack.reason,
            "facts": [f.payload() for f in ev.facts.values()], "rights": ev.rights, "open_issues": ev.open_issues,
        }  # fmt: skip
        schema, limit = self._schema_and_limit(DraftedGround, DraftedGroundReasoned, 900)
        corpus = {"authorities": [self._auth_payload(a) for a in ev.auths]}
        if self.switches.draft_mode == "single":
            out = self._safe_ask(
                TASK_DRAFT, self._ins(TASK_DRAFT, factor=factor.value, stance=pack.stance.value), factor=factor, case=case,
                corpus=corpus, schema=schema, max_tokens=limit,
            )  # fmt: skip
        else:
            out = self._draft_many(key, pack, case, corpus, schema, limit)
        self._keep_reasoning(key, TASK_DRAFT, out)
        text, listed = self._read_claim(out, "argument")
        work = Work(key=key, ev=ev, sentences=self._prepare(split_claim(text, listed)))
        work.empty = not work.sentences
        self._decision("draft", f"{key} ({factor.value}): {len(work.sentences)} sentence(s) drafted.", ground=key, factor=factor.value, stance=pack.stance.value, sentences=len(work.sentences))
        return work

    # ------------------------------------------------------------------ authorities and flags

    def _authority(self, doc: str, para: int) -> Authority:
        """The Authority record of a cited paragraph: citation rendered from corpus metadata, transfer and good-law flags."""
        key = (doc, para)
        if key in self._auth_cache:
            return self._auth_cache[key]
        item = self._auth_items.get(key)
        rendered = self._tool("render_citation", doc_id=doc, para=para)
        citation = rendered if isinstance(rendered, str) and rendered.strip() else None
        status, overruled_by, sc_root = self._good_law(doc, item)
        flag, info = self._transfer(doc, para, item)
        authority = Authority(doc_id=doc, para=para, citation=citation, transfer=flag, good_law=status, sc_root=sc_root)
        self._auth_cache[key] = authority
        self._auth_info[key] = {"transfer": info, "overruled_by": overruled_by, "citation_error": None if citation else (rendered.message if isinstance(rendered, ToolError) else "no citation")}
        self._decision("authority_flags", f"{doc}#{para}: transfer {flag.value if flag else 'n/a'}, good law {status.value}.", authority=f"{doc}#{para}", transfer=flag.value if flag else None, good_law=status.value, cited=citation is not None)
        return authority

    def _good_law(self, doc: str, item: dict[str, Any] | None) -> tuple[GoodLawStatus, str | None, str | None]:
        gl = self._gl_pack.get(doc, {})
        root = gl.get("sc_root") or (item or {}).get("sc_root")
        as_of = self._as_of()
        res = self._tool("good_law_check", doc_id=doc, **({"as_of": as_of} if as_of else {}))
        status = getattr(res, "status", None)
        if status is not None:
            return GoodLawStatus(getattr(status, "value", status)), getattr(res, "overruled_by", None), getattr(res, "sc_root", None) or root
        packed = gl.get("status")
        if packed:
            try:
                return GoodLawStatus(str(getattr(packed, "value", packed)).upper()), gl.get("overruled_by"), root
            except ValueError:
                pass
        return GoodLawStatus.UNKNOWN, None, root

    def _transfer(self, doc: str, para: int, item: dict[str, Any] | None) -> tuple[TransferFlag | None, dict[str, Any]]:
        """The precedent's transfer flag for this case (SAME_TEXT / CHANGED / NEW) and what the tool said about the change."""
        tr = (item or {}).get("transfer")
        if isinstance(tr, dict) and tr.get("flag"):
            return TransferFlag(str(getattr(tr["flag"], "value", tr["flag"]))), dict(tr)
        if not self._case_pairs:
            return None, {}
        sections = list((item or {}).get("sections") or [])
        if not sections:
            row = self._tool("get_paragraph", doc_id=doc, para=para)
            sections = list(getattr(row, "sections", None) or [])
        if not sections:
            return None, {}
        if not self.switches.uses_rule_tools:
            return self._judge_transfer(sections)
        flags: list[tuple[TransferFlag, dict[str, Any]]] = []
        for new_ref, old_ref in self._case_pairs:
            if new_ref in sections:
                flags.append((TransferFlag.SAME_TEXT, {"flag": "SAME_TEXT", "new_ref": new_ref}))
            elif old_ref and old_ref in sections:
                res = self._tool("transfer_check", old_ref=old_ref, new_ref=new_ref)
                if not isinstance(res, ToolError) and getattr(res, "flag", None) is not None:
                    flag = TransferFlag(getattr(res.flag, "value", res.flag))
                    flags.append((flag, {"flag": flag.value, "qualification": getattr(res, "qualification", None), "old_ref": old_ref, "new_ref": new_ref}))
        if not flags:
            return None, {}
        return max(flags, key=lambda f: _TRANSFER_RANK[f[0]])

    def _judge_transfer(self, sections: list[str]) -> tuple[TransferFlag | None, dict[str, Any]]:
        """A3: with the concordance tool off, the model judges the transfer itself from the section numbers."""
        refs = [r for pair in self._case_pairs for r in pair if r]
        out = self._safe_ask(TASK_TRANSFER, instructions(TASK_TRANSFER), case={"case_sections": refs, "paragraph_sections": sections}, schema=TransferJudgement, max_tokens=120)
        flag = getattr(out, "flag", None)
        try:
            return (TransferFlag(flag), {"flag": flag, "note": getattr(out, "note", "")}) if flag else (None, {})
        except ValueError:
            return None, {}

    # ------------------------------------------------------------------ step 3: check every claim

    @property
    def _knows_retrieval(self) -> bool:
        """True when this agent has seen what was retrieved (packs or the log); otherwise `check_claim` alone decides."""
        return bool(self._ret_pairs or self._ret_docs)

    def _is_retrieved(self, key: tuple[str, int]) -> bool:
        return not self._knows_retrieval or key in self._ret_pairs

    def _known(self, ref: str) -> bool:
        """True when a reference like 'A:doc#14' was retrieved (in a pack or in the case's log)."""
        body = ref.split(":", 1)[-1]
        doc, _, para = body.partition("#")
        return (doc, int(para)) in self._ret_pairs if para.isdigit() else doc in self._ret_docs

    def _claim_check(self, s: Sentence) -> ClaimCheckResult | ToolError | Any:
        """`check_claim` on one sentence: its plain text (no markers, no label) and its references as `refs`."""
        text, refs = s.plain, s.check_refs()
        if text and text[-1] not in ".!?":
            text += "."  # a claim is a sentence: the checker reads it as one
        res = self._tool("check_claim", claim=text, refs=refs)
        if isinstance(res, ClaimCheckResult) and res.unretrieved_citations and "check_claim" not in self.tools:
            if all(self._known(u) for u in res.unretrieved_citations):  # retrieved by the packs, which the log may not hold
                from vakeel_sahayak.tools.drafting.claims import check_claim_for_case

                extra = sorted({f"{d}#{p}" for d, p in self._ret_pairs} | self._ret_docs)
                again = check_claim_for_case(text, refs, case_id=self.case_id, retrieved=extra)
                if not isinstance(again, ToolError):
                    return again
        return res

    def _check_local(self, s: Sentence, sc: SentenceCheck) -> None:
        """A1: the raw facts text is the premise (there is no dossier for `check_claim` to read)."""
        premise = [self._facts[FACTS_TEXT_FIELD].text] if FACTS_TEXT_FIELD in self._facts else []
        for key in s.auths:
            text = str((self._auth_items.get(key) or {}).get("text") or "")
            if not text:
                row = self._tool("get_paragraph", doc_id=key[0], para=key[1])
                text = str(getattr(row, "text", "") or "")
            if text:
                premise.append(text)
        score = float(self.get_nli().entails("\n".join(premise), s.plain)) if premise else 0.0
        fthr, athr = self._thresholds()
        if score < max(fthr if s.facts else 0.0, athr if s.auths else 0.0):
            sc.problems.append("fact" if s.facts else "authority")
            sc.detail.append(f"support {score:.2f}")
        sc.result = ClaimCheckResult(supported=not sc.problems, fact_support=score if s.facts else None, authority_support=score if s.auths else None)

    @staticmethod
    def _guard_problems(s: Sentence, sc: SentenceCheck) -> None:
        """The rule-only guards of a sentence (malformed marker, a written case name or citation, outcome prediction): no source is read."""
        if s.bad_refs:
            sc.problems.append("bad_ref")
            sc.detail.append("malformed " + ", ".join(s.bad_refs))
        if CASE_NAME.search(s.plain) or REPORTER.search(s.plain):
            sc.problems.append("invented")
            sc.detail.append("the model must write IDs only: citation text is rendered from the corpus")
        if hits := prediction_language(s.plain):
            sc.problems.append("prediction")
            sc.detail.append("predicts: " + "; ".join(hits[:2]))

    def _check_sentence(self, s: Sentence) -> SentenceCheck:
        """One sentence against its sources: fact and authority support, flags, retrieval, no invented case name, no prediction."""
        if s.is_note:
            return SentenceCheck(s.text)
        cache_key = s.text + "|" + ",".join(s.check_refs())
        if cache_key in self._check_cache:
            return self._check_cache[cache_key]
        sc = SentenceCheck(s.text)
        self._check_cache[cache_key] = sc
        self._guard_problems(s, sc)
        if not s.cited:
            sc.problems.append("uncited")
            return self._settle(sc)
        for doc, para in s.auths:
            if not self._is_retrieved((doc, para)):
                sc.problems.append("unretrieved")
                sc.detail.append(f"{doc}#{para} was not retrieved")
                continue
            authority = self._authority(doc, para)
            if authority.citation is None:
                sc.problems.append("citation")
                sc.detail.append(f"{doc} is not in the corpus metadata")
            if authority.good_law == GoodLawStatus.OVERRULED:
                by = self._auth_info[(doc, para)].get("overruled_by")
                sc.problems.append("overruled")
                sc.detail.append(f"{doc} overruled" + (f" by {by}" if by else ""))
        if not self.switches.uses_dossier and FACTS_TEXT_FIELD in s.facts:
            self._check_local(s, sc)
            return self._settle(sc)
        res = self._claim_check(s)
        if isinstance(res, ToolError) or res is None:
            sc.problems.append("check_error")
            sc.detail.append(getattr(res, "message", "no result"))
            return self._settle(sc)
        sc.result = res
        fthr, athr = self._thresholds()
        unretrieved = [u for u in res.unretrieved_citations if not self._known(u)] if self._knows_retrieval else list(res.unretrieved_citations)
        if unretrieved and "unretrieved" not in sc.problems:
            sc.problems.append("unretrieved")
            sc.detail.append("not retrieved: " + ", ".join(unretrieved))
        if res.good_law == GoodLawStatus.OVERRULED and "overruled" not in sc.problems:
            sc.problems.append("overruled")
        fs, au = res.fact_support, res.authority_support
        fact_bad = bool(s.facts) and fs is not None and fs < fthr
        auth_bad = bool(s.auths) and au is not None and au < athr
        if fact_bad:
            sc.problems.append("fact")
            sc.detail.append(f"fact support {fs:.2f} < {fthr:.2f}")
        if auth_bad:
            sc.problems.append("authority")
            sc.detail.append(f"authority support {au:.2f} < {athr:.2f}")
        covered_by_packs = bool(res.unretrieved_citations) and not unretrieved
        if not res.supported and not (fact_bad or auth_bad or unretrieved or "overruled" in sc.problems):
            scored = fs is not None or au is not None
            if not (covered_by_packs and scored):  # an NLI score above the cut-off and a retrieval the packs cover: supported
                sc.problems.append("unsupported")
        return self._settle(sc)

    @staticmethod
    def _settle(sc: SentenceCheck) -> SentenceCheck:
        sc.problems = list(dict.fromkeys(sc.problems))
        return sc

    @property
    def _self_critique(self) -> bool:
        """S8 (A2b): claims are re-read by the drafting model itself instead of checked against their sources."""
        return self.switches.repair_mode == "self_critique"

    def _run_check(self, work: Work) -> None:
        work.checks = self._self_review(work) if self._self_critique else [self._check_sentence(s) for s in work.sentences]
        if work.initial_ok is None:
            work.initial_ok = not work.empty and not work.failing()
        bad = work.failing()
        self._decision(
            "check", f"{work.key}: {len(work.sentences) - len(bad)} of {len(work.sentences)} sentence(s) pass.", claim=work.key, sentences=len(work.sentences),
            failing=[{"sentence": i + 1, "problems": work.checks[i].problems, "detail": work.checks[i].detail} for i in bad],
        )  # fmt: skip

    def _work_of(self, g: Ground) -> Work:
        """The working state of a ground (rebuilt from its text when it did not come from this agent's drafting)."""
        w = self._work.get(g.id)
        if w is not None and (join_claim(w.sentences) == g.argument.strip() or (w.empty and g.argument == NO_GROUND)):
            return w
        pack = self._packs.get(g.factor.value)
        ev = self._evidence_for(pack) if pack is not None else Evidence(factor=g.factor.value, stance=g.stance.value, facts=dict(self._facts))
        w = Work(key=g.id, ev=ev, sentences=split_claim(g.argument))
        self._work[g.id] = w
        return w

    def check_claims(self, grounds: list[Ground]) -> list[Ground]:
        """Check every claim, sentence by sentence: fact and authority support, transfer and good-law flags, no unretrieved citation (plan §8.1 step 3).

        A ground whose sentences all pass is SUPPORTED (REPAIRED if a repair made it pass); any other is NEEDS_REVIEW until
        `repair_or_flag` has tried to mend it. Failures are remembered for the repair step.

        Args:
            grounds: grounds with their arguments

        Returns:
            Grounds with `check` set.
        """
        self._ensure_primed()
        out: list[Ground] = []
        for g in grounds:
            w = self._work_of(g)
            w.checks = []
            self._run_check(w)
            out.append(self._finish(g, w))
        self._grounds = out
        return out

    def _finish(self, g: Ground, w: Work) -> Ground:
        """The ground as its work now stands: notes added, authorities and dependencies rebuilt, check set."""
        self._annotate(w)
        if w.unchecked:
            check = UNCHECKED
        elif w.empty or w.failing() or not w.checks:
            check = ClaimCheck.NEEDS_REVIEW
        else:
            check = ClaimCheck.REPAIRED if w.repaired else ClaimCheck.SUPPORTED
        authorities = self._authorities_of(w.sentences)
        fields = [f for s in w.sentences for f in s.facts]
        deps = self._depends(g.factor.value, fields, authorities)
        text = join_claim(w.sentences) if w.sentences else NO_GROUND
        if " ".join(text.split()) == " ".join(g.argument.split()):
            text = g.argument  # untouched: word for word
        return g.model_copy(update={"argument": text, "authorities": authorities, "depends_on": deps, "check": check, "state": ClaimState.CURRENT})

    def _depends(self, factor: str, fields: list[str], authorities: list[Authority]) -> DependsOn:
        facts_text = self._state.facts_text if self._state is not None else None
        return depends_on(factor, fields, self._dossier, facts_text, self._timeline, self._rights, authorities)

    def _authorities_of(self, sentences: list[Sentence]) -> list[Authority]:
        out: list[Authority] = []
        seen: set[tuple[str, int]] = set()
        for s in sentences:
            for key in s.auths:
                if key in seen or not self._is_retrieved(key):
                    continue
                seen.add(key)
                out.append(self._authority(*key))
        return out

    # ------------------------------------------------------------------ notes: qualification and warning

    def _annotate(self, w: Work) -> None:
        """A CHANGED precedent is qualified in the text, an overruled or distinguished one carries a warning (never left bare)."""
        cited: list[tuple[str, int]] = []
        for s in w.sentences:
            if not s.is_note:
                cited += [k for k in s.auths if self._is_retrieved(k) and k not in cited]
        for key in cited:
            a = self._authority(*key)
            info = self._auth_info.get(key, {})
            name = a.citation or f"{key[0]}#{key[1]}"
            if a.good_law == GoodLawStatus.OVERRULED and not self._has_note(w, "Warning:", key):
                by = info.get("overruled_by")
                w.sentences.append(note("Warning:", f"{name} has been overruled" + (f" by {by}" if by else "") + "; it must not be relied on without counsel's check", [key]))
                self._decision("warn", f"{key[0]}#{key[1]} is overruled and is cited only with a warning.", authority=f"{key[0]}#{key[1]}", claim=w.key)
            if a.good_law == GoodLawStatus.DISTINGUISHED and not self._has_note(w, "Qualification:", key, "distinguished"):
                w.sentences.append(note("Qualification:", f"{name} has since been distinguished; its reach is limited", [key]))
                self._decision("qualify", f"{key[0]}#{key[1]} is distinguished: qualified.", authority=f"{key[0]}#{key[1]}", claim=w.key)
            if a.transfer == TransferFlag.CHANGED and not self._has_note(w, "Qualification:", key, exclude="distinguished"):
                tr = info.get("transfer") or {}
                old, new = tr.get("old_ref"), tr.get("new_ref") or (self._case_pairs[0][0] if self._case_pairs else "the charged provision")
                qual = str(tr.get("qualification") or "").strip().rstrip(".")
                how = f"{name} construed {old or 'an earlier provision'}; " + (qual or f"{new} is worded differently")
                if not any(word in how.lower() for word in ("differ", "reworded", "changed", "wording")):
                    how = f"{how} ({new} wording differs)"
                w.sentences.append(note("Qualification:", f"{how}, so it is relied on as persuasive authority only", [key]))
                self._decision("qualify", f"{key[0]}#{key[1]} construed an earlier provision (CHANGED): qualified in the text.", authority=f"{key[0]}#{key[1]}", claim=w.key)

    @staticmethod
    def _has_note(w: Work, prefix: str, key: tuple[str, int], include: str = "", exclude: str = "") -> bool:
        """True when the claim already carries a note of this kind about this authority."""
        return any(
            s.is_note and s.text.lstrip().startswith(prefix) and key in s.auths and include in s.text.lower() and not (exclude and exclude in s.text.lower())
            for s in w.sentences
        )

    # ------------------------------------------------------------------ step 4: repair or flag

    def repair_or_flag(self, grounds: list[Ground]) -> list[Ground]:
        """At most 2 rounds: re-retrieve via Sutradhar or reword; else NEEDS_REVIEW. Nothing is dropped silently (plan §8.1 step 4).

        Each round, a failed authority (overruled, not retrieved, not supported by its paragraph) is re-retrieved through
        Sutradhar once, then every failed sentence is reworded to what its source supports and checked again. A ground that
        passes is REPAIRED; one that still fails stays in the brief as NEEDS_REVIEW, with its reasons in the open issues.

        Args:
            grounds: grounds, checked by `check_claims` (checked here when they were not)

        Returns:
            Grounds.
        """
        self._ensure_primed()
        out: list[Ground] = []
        for g in grounds:
            w = self._work_of(g)
            if not w.checks:
                self._run_check(w)
            if w.failing() and not w.empty and self.switches.check_and_repair:
                self._repair(w, g.factor)
            out.append(self._finish(g, w))
            if out[-1].check == ClaimCheck.NEEDS_REVIEW and not w.unchecked:
                self._flag(w, g.id, g.factor.value)
        self._grounds = out
        return out

    def _repair(self, w: Work, factor: Factor | None) -> None:
        for rnd in range(1, self.max_rounds + 1):
            failing = w.failing()
            if not failing:
                break
            w.rounds = rnd
            problems = {p for i in failing for p in w.checks[i].problems}
            if problems & AUTHORITY_PROBLEMS and not w.retrieved and factor is not None and not self._self_critique:
                w.retrieved = True
                bad = sorted({d for i in failing for d, _ in w.sentences[i].auths})
                pack = self._reretrieve(w.key, factor, w.checks[failing[0]].describe(), bad)
                if pack is not None:
                    w.ev = self._evidence_for(pack)
            changed = False
            new: list[Sentence] = []
            for i, s in enumerate(w.sentences):
                if i not in failing:
                    new.append(s)
                    continue
                text, listed = self._reword(w, s, w.checks[i])
                if text and " ".join(text.split()) != " ".join(s.text.split()):
                    changed = True
                    new.extend(self._prepare(split_claim(text, listed)))
                else:
                    new.append(s)
            w.sentences = new
            self._run_check(w)
            label = {"variant": "S8", "repair_mode": "self_critique", "outside_evidence": False} if self._self_critique else {}
            self._decision(
                "repair", f"{w.key}: round {rnd}: {'reworded' if changed else 'nothing to change'}; {len(w.failing())} sentence(s) still fail.",
                claim=w.key, round=rnd, changed=changed, still_failing=len(w.failing()), problems=sorted(problems), **label,
            )  # fmt: skip
        w.repaired = not w.failing() and w.initial_ok is False
        if self._self_critique and w.repaired:
            self._repair_stats["claims_repaired"] = self._repair_stats.get("claims_repaired", 0) + 1

    def _reword(self, w: Work, s: Sentence, check: SentenceCheck) -> tuple[str, list[tuple[str, int]]]:
        """Ask for the failed sentence again, reworded to what its sources say (only facts and paragraphs of the evidence)."""
        facts, auths = self._offered_sources(w, [s])
        case = {
            "id": w.key, "factor": w.ev.factor or "general", "stance": w.ev.stance, "sentence": s.plain, "refs": s.refs() or [f"[{r[0]}:{r[2:]}]" for r in s.check_refs()],
            "problems": check.problems, "detail": check.detail, "facts": [f.payload() for f in facts.values()], "round": w.rounds,
        }  # fmt: skip
        task = TASK_SELF_REVISE if self._self_critique else TASK_REWORD
        if self._self_critique:
            self._repair_stats["revise_calls"] = self._repair_stats.get("revise_calls", 0) + 1
            case["reasons"] = list(check.detail)
        schema, limit = self._schema_and_limit(DraftedGround, DraftedGroundReasoned, 500)
        out = self._safe_ask(
            task, self._ins(task), factor=w.ev.factor, case=case,
            corpus={"authorities": [self._auth_payload(a) for a in auths.values()]}, schema=schema, max_tokens=limit,
        )  # fmt: skip
        self._keep_reasoning(w.key, task, out)
        return self._read_claim(out, "argument")

    def _offered_sources(self, w: Work, sentences: list[Sentence]) -> tuple[dict[str, Fact], dict[tuple[str, int], dict[str, Any]]]:
        """The facts and paragraphs a model may use on a claim: the evidence offered for drafting, plus what these sentences cite (and may be cited)."""
        facts = dict(w.ev.facts)
        auths = {(str(a["doc_id"]), int(a["para"])): a for a in w.ev.auths}
        for s in sentences:
            for f in s.facts:
                if f in self._facts:
                    facts.setdefault(f, self._facts[f])
            for key in s.auths:
                item = self._auth_items.get(key)
                if item is not None and key in self._ret_pairs and not self._is_overruled(key[0], item) and self._authority(*key).citation is not None:
                    auths.setdefault(key, {"doc_id": key[0], "para": key[1], "text": str(item.get("text") or "")[:PARAGRAPH_LIMIT]})
        return facts, auths

    # ------------------------------------------------------------------ S8: self-critique instead of a grounded check

    def _self_review(self, w: Work) -> list[SentenceCheck]:
        """S8 (A2b): the drafting model re-reads its own claim and says which sentences it would change. No NLI, no tool, no retrieval.

        Taken from the papers named in the module docstring (CRITIC, Gou et al., ICLR 2024; Huang et al., ICLR 2024; Zhang et al., Findings of
        ACL 2024): the critique step is done by the same model that wrote the draft, with no tool and no verifier. Changed: the tasks are claim
        repair, not QA or code; the model is given exactly the facts and paragraphs it had when drafting (the fair intrinsic setting: no new
        information), one call reads a whole claim (the papers critique whole answers) and rewrites go through the existing reword step with
        the model's own reasons in place of the checker's problem codes. Left unchanged on purpose: the per-counsel label, the CHANGED /
        DISTINGUISHED / OVERRULED notes and the open-issue list (they disclose, they do not repair), so S8 differs from the grounded
        default only in who finds the faults. The rule-only guards (`_guard_problems`: malformed marker, written case name, outcome prediction, no marker at all) stay on, because
        they read no source. A model that cannot answer leaves every sentence 'could not be checked' (NEEDS_REVIEW), never silently accepted.
        """
        stats = self._repair_stats
        checks: list[SentenceCheck] = []
        body = [(i, s) for i, s in enumerate(w.sentences) if not s.is_note]
        facts, auths = self._offered_sources(w, [s for _, s in body])
        case = {
            "id": w.key, "factor": w.ev.factor or "general", "stance": w.ev.stance, "claim": [{"sentence": n + 1, "text": s.text} for n, (_, s) in enumerate(body)],
            "facts": [f.payload() for f in facts.values()],
        }  # fmt: skip
        out = None
        if body:
            stats["critic_calls"] = stats.get("critic_calls", 0) + 1
            out = self._safe_ask(
                TASK_SELF_CRITIQUE, instructions(TASK_SELF_CRITIQUE), factor=w.ev.factor, case=case,
                corpus={"authorities": [self._auth_payload(a) for a in auths.values()]}, schema=SelfReview, max_tokens=400,
            )  # fmt: skip
        verdict: dict[int, tuple[bool, str]] = {}
        for r in getattr(out, "reviews", None) or []:
            if isinstance(r.sentence, int) and 1 <= r.sentence <= len(body):
                verdict[r.sentence - 1] = (bool(r.ok), str(r.reason or "").strip())
        slot = {i: n for n, (i, _) in enumerate(body)}
        flagged = 0
        for pos, s in enumerate(w.sentences):
            sc = SentenceCheck(s.text)
            if not s.is_note:
                self._guard_problems(s, sc)
                if not s.cited:
                    sc.problems.append("uncited")
                n = slot[pos]
                if out is None:
                    sc.problems.append("check_error")
                    sc.detail.append("the model's own re-reading could not be obtained")
                else:
                    ok, reason = verdict.get(n, (True, ""))
                    if not ok:
                        sc.problems.append("self_critique")
                        sc.detail.append(reason or "the model would change this sentence")
                sc.problems = list(dict.fromkeys(sc.problems))
                flagged += 0 if sc.ok else 1
            checks.append(sc)
        stats["sentences_reviewed"] = stats.get("sentences_reviewed", 0) + len(body)
        stats["sentences_flagged"] = stats.get("sentences_flagged", 0) + flagged
        if w.initial_ok is None:  # the first reading of this claim
            stats["claims_reviewed"] = stats.get("claims_reviewed", 0) + 1
            stats["claims_flagged_at_first_read"] = stats.get("claims_flagged_at_first_read", 0) + (1 if flagged else 0)
        self._decision(
            "self_critique", f"{w.key}: the model re-read its own claim: {flagged} of {len(body)} sentence(s) flagged (no outside check).",
            claim=w.key, sentences=len(body), flagged=flagged, variant="S8", repair_mode="self_critique", outside_evidence=False,
        )  # fmt: skip
        return checks

    def _emit_repair_signals(self) -> dict[str, Any]:
        """One `repair_signals` event with the cumulative S8 counts (none in a default run); the last one in the log is the final count."""
        signals = self.repair_signals()
        if signals:
            self._decision("repair_signals", "Self-critique repair (S8): " + ", ".join(f"{k}={v}" for k, v in signals.items() if isinstance(v, int)) + ".", **signals)
        return signals

    def repair_signals(self) -> dict[str, Any]:
        """S8 signals for the evaluation (empty in a default run): critic calls, sentences reviewed and flagged, revise calls, claims repaired."""
        if not self._self_critique:
            return {}
        stats = self._repair_stats
        return {
            "variant": "S8", "repair_mode": "self_critique", "outside_evidence": False,
            "critic_calls": stats.get("critic_calls", 0), "sentences_reviewed": stats.get("sentences_reviewed", 0),
            "sentences_flagged": stats.get("sentences_flagged", 0), "revise_calls": stats.get("revise_calls", 0),
            "claims_reviewed": stats.get("claims_reviewed", 0), "claims_flagged_at_first_read": stats.get("claims_flagged_at_first_read", 0),
            "claims_repaired": stats.get("claims_repaired", 0),
        }  # fmt: skip

    def _reretrieve(self, key: str, factor: Factor, reason: str, bad_docs: list[str]) -> EvidencePack | None:
        """Ask Sutradhar for new evidence for the slot behind a failed authority (never the failing documents again)."""
        state = (self._state or CaseGraphState(case_id=self.case_id)).model_copy(update={"evidence_packs": list(self._packs.values())})
        try:
            if self.retriever is not None:
                pack = self.retriever(state, factor, reason, bad_docs)
            else:
                from vakeel_sahayak.agents.sutradhar.agent import SutradharAgent

                peer = self._peer(AgentName.SUTRADHAR)
                assert isinstance(peer, SutradharAgent)
                decision = peer.resolve_failed_claim(state, factor, reason, claim_id=key, bad_docs=bad_docs)
                pack = decision.pack if getattr(decision, "decision", None) == "re-retrieve" else None
        except Exception as exc:  # noqa: BLE001 - a retrieval that fails leaves the claim to be reworded or flagged
            self.error("reretrieve_failed", f"{type(exc).__name__}: {str(exc)[:200]}", claim=key)
            pack = None
        if pack is None:
            self._decision("reretrieve", f"{key}: no new evidence from Sutradhar; the claim is reworded instead.", claim=key, factor=factor.value, found=False)
            return None
        self._packs[factor.value] = pack
        self._index_pack(pack)
        self._check_cache.clear()
        self._decision("reretrieve", f"{key}: Sutradhar re-retrieved evidence for {factor.value}.", claim=key, factor=factor.value, found=True, avoided=bad_docs)
        return pack

    def _flag(self, w: Work, key: str, factor: str) -> None:
        """A claim that still fails is NEEDS_REVIEW: say which sentences and why (they are kept in the text, never dropped)."""
        reasons = [f"sentence {i + 1} {w.checks[i].describe()}" for i in w.failing()]
        if w.empty:
            reasons = ["no argument could be drafted from the evidence"]
        w.notes = reasons
        self._decision("flag", f"{key} ({factor}) needs counsel's review: " + "; ".join(reasons), claim=key, factor=factor, reasons=reasons)

    # ------------------------------------------------------------------ step 1: draft

    def draft_grounds(self, state: CaseGraphState, packs: list[EvidencePack]) -> list[Ground]:
        """Draft one ground per chosen factor; each sentence cites [F:field] facts and [A:doc#para] authorities (plan §8.1 step 1).

        A factor Sutradhar marked not applicable gets no ground. Citation text is rendered from corpus metadata; the
        drafted text is labelled ("per counsel, not on record") where it rests on a USER_STATED fact. The grounds come
        back unchecked (`check` NEEDS_REVIEW until `check_claims` runs).

        Args:
            state: the graph state (dossier, RightsReport, timeline; A1: the facts text)
            packs: Sutradhar's evidence packs, one per chosen factor

        Returns:
            Grounds, ids G1, G2, ... in pack order.
        """
        if state is not self._state:
            self._prime(state)
        self._set_packs(packs)
        grounds: list[Ground] = []
        for pack in packs:
            if pack.stance == FactorStance.NOT_APPLICABLE:
                continue
            grounds.append(self._draft_ground(f"G{len(grounds) + 1}", pack))
        self._grounds = grounds
        return grounds

    def _draft_ground(self, gid: str, pack: EvidencePack) -> Ground:
        with self.factor_scope(pack.factor):
            w = self._draft_work(gid, pack)
        self._work[gid] = w
        base = Ground(id=gid, factor=pack.factor, stance=pack.stance, argument="", check=ClaimCheck.NEEDS_REVIEW)
        return self._finish(base, w)

    def _ensure_primed(self) -> None:
        if self._state is None:
            self._prime(CaseGraphState(case_id=self.case_id, switches=self.switches))

    # ------------------------------------------------------------------ step 2: reply to objections

    def reply_to_objections(self, state: CaseGraphState, objections: list[Objection]) -> list[Reply]:
        """Answer Abhiyojak's objections under the same citation and checking rules (plan §8.1 step 2).

        A reply cites only dossier facts and retrieved authorities (the ground's own authorities first), is checked and
        repaired like a ground, and is NEEDS_REVIEW when the material does not answer the objection. Under A8 and A9
        there is no sparring and no reply.

        Args:
            state: the graph state
            objections: Abhiyojak's objections (their `against` names a ground id or 'general')

        Returns:
            One Reply per objection, in order.
        """
        if not self.switches.sparring:
            self._decision("reply_skipped", "No sparring in this run (A8/A9): no replies.", objections=len(objections))
            return []
        if state is not self._state:
            self._prime(state)
        brief = self._brief or state.brief
        grounds = {g.id: g for g in (self._grounds or (brief.grounds if brief else []))}
        replies: list[Reply] = []
        for o in objections:
            replies.append(self._reply_one(o, grounds.get(o.against)))
        self._emit_repair_signals()
        self._emit_output_signals()
        return replies

    def _reply_evidence(self, o: Objection, ground: Ground | None) -> Evidence:
        factor = ground.factor.value if ground is not None else (str(o.factor) if str(o.factor) in FACTOR_FIELDS else None)
        names = list(FACTOR_FIELDS.get(factor, ())) if factor else []
        names += [g.fact for g in o.grounds if g.fact]
        facts = {n: self._facts[n] for n in dict.fromkeys(names) if n in self._facts}
        if not facts and not self.switches.uses_dossier:
            facts = dict(self._facts)
        pack = self._packs.get(factor) if factor else None
        auths, _ = self._candidates(pack)
        own = []
        for a in (ground.authorities if ground is not None else []):
            item = self._auth_items.get((a.doc_id, a.para))
            if item is not None and a.good_law != GoodLawStatus.OVERRULED:
                own.append({"doc_id": a.doc_id, "para": a.para, "text": str(item.get("text") or "")[:PARAGRAPH_LIMIT]})
        seen = {(a["doc_id"], a["para"]) for a in own}
        merged = own + [a for a in auths if (a["doc_id"], a["para"]) not in seen]
        return Evidence(factor=factor, stance="favourable", facts=facts, auths=merged[:MAX_AUTHORITIES], pack=pack)

    def _reply_one(self, o: Objection, ground: Ground | None) -> Reply:
        key = f"reply:{o.id}"
        ev = self._reply_evidence(o, ground)
        factor = Factor(ev.factor) if ev.factor else None
        case = {
            "id": o.id, "objection": self.untrusted(o.objection, SourceRef(doc=f"objection {o.id}")), "against": o.against, "factor": ev.factor or str(o.factor),
            "facts": [f.payload() for f in ev.facts.values()],
        }  # fmt: skip
        with self.factor_scope(factor):
            schema, limit = self._schema_and_limit(Reply, ReasonedReply, 600)
            out = self._safe_ask(
                TASK_REPLY, self._ins(TASK_REPLY), factor=factor, case=case,
                corpus={"authorities": [self._auth_payload(a) for a in ev.auths]}, schema=schema, max_tokens=limit,
            )  # fmt: skip
        self._keep_reasoning(key, TASK_REPLY, out)
        text, listed = self._read_claim(out, "text")
        w = Work(key=key, ev=ev, sentences=self._prepare(split_claim(text, listed)))
        w.empty = not w.sentences
        self._work[key] = w
        if w.empty:
            self._decision("reply", f"{o.id}: no reply could be drafted from the material.", objection=o.id, against=o.against, drafted=False)
            return Reply(text=NO_REPLY, authorities=[], check=ClaimCheck.NEEDS_REVIEW)
        if self.switches.check_and_repair:
            self._run_check(w)
            if w.failing():
                self._repair(w, factor)
        else:
            w.unchecked = True
        self._annotate(w)
        ok = self.switches.check_and_repair and not w.failing()
        check = UNCHECKED if w.unchecked else (ClaimCheck.NEEDS_REVIEW if not ok else (ClaimCheck.REPAIRED if w.repaired else ClaimCheck.SUPPORTED))
        if check == ClaimCheck.NEEDS_REVIEW and not w.unchecked:
            self._flag(w, key, ev.factor or "general")
        self._decision("reply", f"{o.id} against {o.against}: reply {check.value}.", objection=o.id, against=o.against, check=check.value, drafted=True)
        return Reply(text=join_claim(w.sentences), authorities=self._authorities_of(w.sentences), check=check)

    # ------------------------------------------------------------------ the brief

    def assemble_brief(self, state: CaseGraphState, grounds: list[Ground] | None = None) -> BailBrief:
        """Assemble BailBrief including dependencies and open issues (plan §8.1).

        Args:
            state: the graph state
            grounds: the grounds to assemble (default: the ones drafted, checked and repaired by this agent)

        Returns:
            BailBrief: statutory position, grounds, open issues, the fixed label.
        """
        if state is not self._state:
            self._prime(state)
        grounds = [self._with_dependencies(g) for g in (grounds if grounds is not None else (self._grounds or (state.brief.grounds if state.brief else [])))]
        rights_text = None
        if not self.switches.uses_rule_tools:
            sig = self._facts_signature()
            out = self._safe_ask(TASK_RIGHTS, instructions(TASK_RIGHTS), case=sig, schema=RightsSummary, max_tokens=150)
            rights_text = getattr(out, "rights", None) or None
        position = statutory_position(self._dossier, self._rights, self._sections or None, rights_text)
        brief = BailBrief(case_id=state.case_id, statutory_position=position, grounds=grounds, open_issues=self._open_issues(grounds, state))
        self._brief = brief
        self._decision("assemble", f"Brief assembled: {len(grounds)} ground(s), {len(brief.open_issues)} open issue(s).", grounds=[g.id for g in grounds], open_issues=len(brief.open_issues))
        return brief

    def _with_dependencies(self, g: Ground) -> Ground:
        """A ground that carries no `depends_on` gets it from its own markers (a ground drafted elsewhere); one that has it keeps it."""
        d = g.depends_on
        if d.facts or d.authorities or d.events or d.rights or d.claims:
            return g
        facts = [f for kind, body in MARKER.findall(g.argument) if kind == "F" for f in [body.strip()]]
        keys = [(a.doc_id, a.para) for a in g.authorities]
        for kind, body in MARKER.findall(g.argument):
            doc, _, para = body.strip().partition("#")
            if kind == "A" and para.isdigit() and (doc, int(para)) not in keys:
                keys.append((doc, int(para)))
        auths = [a for a in g.authorities] + [Authority(doc_id=d, para=p) for d, p in keys if (d, p) not in {(a.doc_id, a.para) for a in g.authorities}]
        return g.model_copy(update={"depends_on": self._depends(g.factor.value, facts, auths)})

    def _facts_signature(self) -> dict[str, Any]:
        d = self._dossier
        days = d.fields.custody_days.value if d is not None else None
        arrest = d.fields.arrest_date.value if d is not None else None
        return {"custody_days": days, "arrest_date": arrest}

    def _open_issues(self, grounds: list[Ground], state: CaseGraphState) -> list[OpenIssue]:
        """What counsel must clear: NEEDS_REVIEW claims and facts, CHANGED provisions, missing evidence."""
        issues: list[OpenIssue] = []

        def add(kind: OpenIssueType, item: str) -> None:
            if not any(i.type == kind and i.item == item for i in issues):
                issues.append(OpenIssue(type=kind, item=item))

        for g in grounds:
            label = g.factor.value.replace("_", " ")
            w = self._work.get(g.id)
            if g.check == ClaimCheck.NEEDS_REVIEW:
                if w is not None and w.unchecked:
                    add(OpenIssueType.NEEDS_REVIEW, f"{g.id} ({label}): not checked (check-and-repair is switched off in this run).")
                elif w is not None and w.notes:
                    add(OpenIssueType.NEEDS_REVIEW, f"{g.id} ({label}): " + "; ".join(w.notes) + ".")
                else:
                    old = [i.item for i in (state.brief.open_issues if state.brief else []) if i.type == OpenIssueType.NEEDS_REVIEW and i.item.startswith(g.id)]
                    add(OpenIssueType.NEEDS_REVIEW, old[0] if old else f"{g.id} ({label}): needs counsel's review.")
            for name in g.depends_on.facts:
                fact = self._facts.get(name)
                if fact is not None and fact.per_counsel:
                    add(OpenIssueType.NEEDS_REVIEW, f"{g.id} rests on {name.replace('_', ' ')}, stated by counsel and not on record: confirm it from the papers.")
            for a in g.authorities:
                if a.good_law == GoodLawStatus.OVERRULED:
                    by = self._auth_info.get((a.doc_id, a.para), {}).get("overruled_by")
                    add(OpenIssueType.NEEDS_REVIEW, f"{g.id} cites {a.doc_id}, which has been overruled" + (f" by {by}" if by else "") + ": replace it or confirm the warning.")
                if a.transfer == TransferFlag.CHANGED:
                    info = self._auth_info.get((a.doc_id, a.para), {}).get("transfer")
                    if info is None:
                        item = self._auth_items.get((a.doc_id, a.para)) or {}
                        info = item.get("transfer") if isinstance(item.get("transfer"), dict) else {}
                    if not any(i.type == OpenIssueType.CHANGED_PROVISION and i.item.startswith(a.doc_id + " ") for i in issues):
                        issues.append(changed_provision_issue(a.doc_id, info, case_refs_of(self._dossier, self._sections)))
            pack = self._packs.get(g.factor.value)
            for text in (pack.open_issues if pack else []):
                add(OpenIssueType.MISSING_EVIDENCE, str(text))
            if pack is not None and not g.authorities and not any(str(t) for t in pack.open_issues):
                add(OpenIssueType.MISSING_EVIDENCE, f"No authority could be cited for {label} ({g.id}).")
        if self._self_critique and grounds:
            add(OpenIssueType.NEEDS_REVIEW, SELF_CRITIQUE_NOTICE)
        for q in (self._dossier.open_questions if self._dossier is not None else []):
            add(OpenIssueType.NEEDS_REVIEW, str(q))
        ante = self._dossier.fields.antecedents if self._dossier is not None else None
        if ante is not None and (ante.value is None or ante.status.value == "UNSUPPORTED"):
            issues = [i for i in issues if not (i.type == OpenIssueType.MISSING_EVIDENCE and i.item.lower().startswith("antecedents unknown"))]
            if not any(i.type == OpenIssueType.NEEDS_REVIEW and "antecedent" in i.item.lower() for i in issues):
                issues.append(OpenIssue(type=OpenIssueType.NEEDS_REVIEW, item="Antecedents unknown: confirm no other pending cases."))
        for key, w in self._work.items():
            if key.startswith("reply:") and w.notes:
                add(OpenIssueType.NEEDS_REVIEW, f"Reply to objection {key.split(':', 1)[1]}: " + "; ".join(w.notes) + ".")
        return issues

    # ------------------------------------------------------------------ hearing card

    def build_hearing_card(self, state: CaseGraphState) -> dict[str, Any]:
        """Hearing-prep card (plan §8.3): likely concerns with short answers, three points to lead with, conditions courts impose, open issues.

        Plain data (rendering is Phase 5). No outcome prediction and no grant rates.

        Args:
            state: the graph state (brief, evidence packs, sparring record)

        Returns:
            Card.
        """
        if self._state is None:
            self._prime(state)
        brief = self._brief if self._brief is not None and self._brief.grounds else (state.brief or self._brief or self.assemble_brief(state))
        packs = list(self._packs.values()) or list(state.evidence_packs)
        citations = {(a.doc_id, a.para): a.citation for g in brief.grounds for a in g.authorities if a.citation}
        card = build_card(brief, packs, state.sparring, citations)
        self._decision("hearing_card", f"Hearing card: {len(card['bench_concerns'])} concern(s), {len(card['lead_with'])} lead point(s), {len(card['conditions'])} condition(s).", **{k: len(v) for k, v in card.items() if isinstance(v, list)})
        return card

    # ------------------------------------------------------------------ redraft (plan §10)

    def redraft(self, claims_to_redraft: list[str], state: CaseGraphState | None = None, packs: list[EvidencePack] | None = None) -> BailBrief:
        """Rewrite only the stale grounds (plan §10 step 3); every other ground stays word for word.

        Args:
            claims_to_redraft: ground ids ('G2') to rewrite; a factor name drafts that factor's ground (new or existing)
            state: the graph state with the new dossier, RightsReport and evidence packs (default: the last one primed)
            packs: evidence packs to use (default: the state's)

        Returns:
            The updated BailBrief. A ground whose factor no longer applies is kept, STALE, with an open issue (never dropped).
        """
        state = state or self._state or CaseGraphState(case_id=self.case_id, switches=self.switches)
        old = state.brief or self._brief or BailBrief(case_id=state.case_id)
        packs = list(packs if packs is not None else state.evidence_packs)
        self._prime(state)
        self._set_packs(packs)
        ids = {str(c) for c in claims_to_redraft}
        factors = {g.factor.value for g in old.grounds if g.id in ids} | {c for c in ids if c in FACTOR_FIELDS}
        used = [int(m.group(1)) for g in old.grounds if (m := _ID.match(g.id))]
        next_id = max(used, default=0) + 1
        grounds: list[Ground] = []
        flagged: list[str] = []
        for g in old.grounds:
            if g.id not in ids and g.factor.value not in factors:
                grounds.append(g.model_copy(deep=True))  # word for word
                continue
            pack = self._packs.get(g.factor.value)
            if pack is None or pack.stance == FactorStance.NOT_APPLICABLE:
                grounds.append(g.model_copy(update={"state": ClaimState.STALE}))
                flagged.append(f"{g.id} ({g.factor.value.replace('_', ' ')}) no longer applies after the change: review it or remove it.")
                self._decision("redraft_kept", f"{g.id} is kept STALE: its factor no longer applies.", claim=g.id, factor=g.factor.value)
                continue
            grounds.append(self._process_ground(g.id, pack))
            self._decision("redraft", f"{g.id} ({g.factor.value}) redrafted; the other grounds are untouched.", claim=g.id, factor=g.factor.value)
        have = {g.factor.value for g in grounds}
        for pack in packs:
            if pack.stance == FactorStance.NOT_APPLICABLE or pack.factor.value in have:
                continue
            gid = f"G{next_id}"
            next_id += 1
            grounds.append(self._process_ground(gid, pack))
            self._decision("redraft_new", f"{gid} ({pack.factor.value}) is a new ground: the factor has become available.", claim=gid, factor=pack.factor.value)
        self._grounds = grounds
        brief = self.assemble_brief(state, grounds)
        for text in flagged:
            if not any(i.item == text for i in brief.open_issues):
                brief.open_issues.append(OpenIssue(type=OpenIssueType.NEEDS_REVIEW, item=text))
        return brief

    def _process_ground(self, gid: str, pack: EvidencePack) -> Ground:
        """Draft, check and (if switched on) repair one ground."""
        g = self._draft_ground(gid, pack)
        w = self._work[gid]
        if not self.switches.check_and_repair:
            w.unchecked = True
            self._decision("unchecked", f"{gid}: not checked (check-and-repair is switched off: A2/A9).", claim=gid)
            return self._finish(g, w)
        with self.factor_scope(pack.factor):
            self._run_check(w)
            if w.failing() and not w.empty:
                self._repair(w, pack.factor)
        g = self._finish(g, w)
        if g.check == ClaimCheck.NEEDS_REVIEW:
            self._flag(w, gid, pack.factor.value)
        return g

    # ------------------------------------------------------------------ the run

    def _redraft_targets(self, state: CaseGraphState) -> list[str]:
        """Grounds to rewrite when a brief already exists: stale ones, ones still needing review, ones of reopened factors."""
        brief = state.brief
        if brief is None:
            return []
        reopened = {f.value for f in state.reopened_factors}
        out = []
        for g in brief.grounds:
            pack = self._packs.get(g.factor.value)
            if g.state == ClaimState.STALE or g.check == ClaimCheck.NEEDS_REVIEW or g.factor.value in reopened or pack is None:
                out.append(g.id)
        return out

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Vakeel's full job for the current graph state.

        Drafts a ground per chosen factor from `state.evidence_packs`, checks and repairs every claim, replies to any
        objection that has no reply yet, assembles the BailBrief and the hearing card, and writes both to the case log.
        When a brief already exists, only stale grounds, grounds still needing review, grounds of reopened factors and
        new factors are rewritten; the rest stay word for word. The stage is left for the graph to advance.

        Args:
            state: see behaviour

        Returns:
            Updated state: brief, hearing_card and (when replies were added) sparring.
        """
        self._prime(state)
        if not self.switches.drafting:
            self._decision("draft_skipped", "Retrieval only in this run (A10): nothing is drafted.")
            return state
        packs = list(state.evidence_packs)
        old = state.brief
        if old is not None and old.grounds:
            targets = self._redraft_targets(state)
            new_factors = [p for p in packs if p.stance != FactorStance.NOT_APPLICABLE and p.factor.value not in {g.factor.value for g in old.grounds}]
            if targets or new_factors:
                brief = self.redraft(targets, state, packs)
            else:
                self._grounds = list(old.grounds)
                brief = self.assemble_brief(state, list(old.grounds))
        else:
            grounds = self.draft_grounds(state, packs)
            if self.switches.check_and_repair:
                grounds = self.repair_or_flag(self.check_claims(grounds))
            else:
                self._decision("unchecked", "Claims are not checked or repaired in this run (A2/A9).", grounds=[g.id for g in grounds])
                grounds = [g.model_copy(update={"check": UNCHECKED}) for g in grounds]
                for g in grounds:
                    if g.id in self._work:
                        self._work[g.id].unchecked = True
            self._grounds = grounds
            brief = self.assemble_brief(state, grounds)
        update: dict[str, Any] = {"brief": brief}
        sparring = self._answer_open_objections(state)
        if sparring is not None:
            update["sparring"] = sparring
            self.write_view("sparring", sparring)
        extra = {k: v for k, v in (("repair", self._emit_repair_signals()), ("output", self._emit_output_signals()), ("draft", self.draft_signals())) if v}  # S8 / S15 / S11b,c only
        if extra:
            update["variant_signals"] = {**state.variant_signals, **extra}
        shown = state.model_copy(update=update)
        card = self.build_hearing_card(shown)
        update["hearing_card"] = card
        self.write_view("brief", brief)
        self.write_view("hearing_card", card)
        snap = getattr(self.budgets, "snapshot", None)
        if snap is not None:
            update["budget"] = snap()
        to_dict = getattr(self.budgets, "to_dict", None)
        if to_dict is not None:
            update["budget_tracker"] = to_dict()
        return state.model_copy(update=update)

    def request_export_approval(self, state: CaseGraphState) -> Any:
        """Open Gate 2 (export) with its checklist of open claims and objections; counsel alone approves it (plan §3.1, §16).

        Returns:
            The `ApprovalRequest` of the `request_approval` tool, or a ToolError.
        """
        from vakeel_sahayak.schemas.enums import GateId

        res = self._tool("request_approval", case_id=state.case_id, gate=GateId.GATE_2_EXPORT)
        self._decision("gate_2", "Gate 2 requested: export waits for counsel's approval.", gate=GateId.GATE_2_EXPORT.value)
        return res

    def _answer_open_objections(self, state: CaseGraphState) -> SparringRecord | None:
        """Reply to objections in the state's sparring record that have no reply yet (a re-run after Abhiyojak raised some)."""
        record = state.sparring
        if record is None or not self.switches.sparring:
            return None
        open_ones = [o for o in record.objections if o.reply is None]
        if not open_ones:
            return None
        replies = self.reply_to_objections(state, open_ones)
        by_id = {o.id: r for o, r in zip(open_ones, replies, strict=False)}
        return record.model_copy(update={"objections": [o.model_copy(update={"reply": by_id[o.id]}) if o.id in by_id else o for o in record.objections]})

