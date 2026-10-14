"""Scenario helpers for the integration tests (plan §3.3, §4, §6-§11, §13, §16, §17).

Everything here builds *inputs* and *fake back-ends*: a constructed 14-page bundle (`FakePage`), case-0007 worlds
(in-memory stores), a scripted LLM that dispatches on the schema title, a `ScenarioToolbox` (the shared `FakeToolbox`
plus a few scenario hooks) and small builders for events and briefs. None of it re-implements the product; where a
fake tool wraps real domain code (`rights_check` -> `RightsEngine`, `diff_case_state` -> `compute_change_set`) that is
exactly what the real tool body is documented to do ("tools wrap domain code").

ASSUMPTIONS that every integration file shares (change them here once, not in each test):

* **LLM output shapes.** The schema classes of the plan (`RetrievalPlan`, `Ground`, `Objection`, `Reply`, ...) are the
  titles the agents request (`orchestration.structured_output.constrained_generate`). Wrapper models (a list of
  objections, a list of verdicts, extracted events, ...) are not fixed by the plan, so the scripted answers are *fat*:
  one JSON object carrying the same payload under every plausible key (`events`/`items`/..., `objections`/`items`,
  `verdicts`/`objections`). Pydantic ignores unknown keys, so any wrapper that names one of those keys validates.
  Schema titles are routed by keyword (`logical_kind`), so `ObjectionList`, `ObjectionsRound1` ... all work.
* **Unscripted calls** return `"{}"` and are recorded in `llm.dispatch.unrouted`; they never raise.
* **Event payload shapes** are those of tests/unit/record/_helpers.py (dossier fields and whole-object views are
  STORE_WRITE events; gates are GATE_OPENED / GATE_APPROVED).
* **The allow-list** that `BaseAgent.call_tool` enforces is `ctx.config.tools` (configs/tools.yaml); `build_agent`
  from tests/unit/agents/_helpers.py fills it.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from tests.fakes import stores as fs
from tests.fakes.data import PLANTED_NAMES, PLANTED_NAMES_HI, CaseWorld, build_world, load_paragraphs
from tests.fakes.models import LLMCall, ScriptedLLM, Seq
from tests.fakes.toolbox import PSEUDONYM_ALIASES, FakePage, FakeToolbox, leaked_names
from tests.unit.agents._helpers import build_agent, make_state  # noqa: F401  (re-exported for the tests)
from tests.unit.record._helpers import (  # noqa: F401  (re-exported for the tests)
    dossier_events,
    field_write,
    gate_approved,
    gate_opened,
    make_event,
    view_write,
)
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import CaseDossier, ChargeSheetValue
from vakeel_sahayak.schemas.enums import (
    DocumentType,
    Factor,
    FieldStatus,
    StoreName,
)
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, IngestionReport
from vakeel_sahayak.schemas.store_rows import CaseChunk, ParagraphRecord, TimelineEvent
from vakeel_sahayak.tools.types import SpanCheckResult

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS_DIR = REPO_ROOT / "src" / "vakeel_sahayak" / "contracts" / "factors"
CASE_ID = "case-0007"
AS_OF = "2025-02-03"
FAMILY = ["BNS 318(4)", "IPC 420"]  # section family of case-0007 (plan §6.3 example)

# Tool names that touch one store (one tool call == one "store call" for the per-factor budget, plan §6.2).
STORE_TOOLS = frozenset(
    {
        "search_case_docs", "get_timeline", "get_fact", "get_statute", "search_statutes", "map_section",
        "transfer_check", "search_reasoning", "get_paragraph", "citations", "good_law_check", "similar_orders",
        "search_arguments", "search_objections",
    }
)  # fmt: skip

# Documents that must never be retrieved for case-0007 (plan §2 leakage rules; see tests/fixtures/caselaw).
FORBIDDEN_DOC_IDS = frozenset({"TESTORD-2024-0001", "SAMEFIR-2024-0002", "DLHC-2025-0099"})

NAME_ACCUSED, NAME_COMPLAINANT, NAME_CO_ACCUSED, NAME_IO = PLANTED_NAMES
HI_ACCUSED, HI_COMPLAINANT = PLANTED_NAMES_HI
VAKEEL_NOTE = "VAKEEL_PRIVATE_NOTE"  # marker planted in Vakeel's scratch; Abhiyojak must never see it (plan §9)


# =====================================================================================================================
# LLM scripting
# =====================================================================================================================
_KIND_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("verdict", "judg"), "judge"),
    (("repl",), "reply"),
    (("objection",), "objections"),
    (("plan",), "plan"),
    (("pack", "stance", "pickfactor"), "factors"),
    (("ground", "draft", "claim"), "ground"),
    (("brief",), "brief"),
    (("chat", "answer"), "chat"),
    (("changeset",), "changes"),
    (("event", "timeline", "dated"), "events"),
    (("dossier",), "dossier"),
    (("classif", "doctype", "label"), "classify"),
    (("gap",), "gaps"),
]


def logical_kind(schema_title: str | None, prompt: str = "") -> str:
    """Route a schema title (or, for free-text calls, the prompt) to a logical call kind."""
    title = (schema_title or "").lower()
    if title:
        for words, kind in _KIND_KEYWORDS:
            if any(w in title for w in words):
                return kind
        return "other"
    low = prompt.lower()
    if "prosecut" in low and "objection" in low:
        return "objections"
    return "free"


class Dispatch:
    """The single `by_prompt` catch-all of a scenario LLM: handlers are keyed by logical kind; each is a literal,
    a `Seq` or a callable `(prompt, schema)`. Unrouted titles are recorded, never raised."""

    def __init__(self, **handlers: Any) -> None:
        self.handlers = dict(handlers)
        self.unrouted: list[str] = []

    def __call__(self, prompt: str, schema: dict | None) -> Any:
        title = (schema or {}).get("title")
        kind = logical_kind(title, prompt)
        handler = self.handlers.get(kind)
        if handler is None:
            self.unrouted.append(str(title))
            return "{}"
        if isinstance(handler, Seq):
            handler = handler.next()
        if callable(handler) and not isinstance(handler, (BaseModel, type)):
            return handler(prompt, schema)
        return handler


def make_llm(where: str = "laptop", llm_class: type[ScriptedLLM] = ScriptedLLM, **handlers: Any) -> ScriptedLLM:
    """A ScriptedLLM that routes every call through `Dispatch(**handlers)` (kinds: plan, factors, ground, reply,
    objections, judge, chat, events, dossier, classify, gaps, free, ...). `llm.dispatch` exposes the dispatcher."""
    dispatch = Dispatch(**handlers)
    llm = llm_class(by_prompt=[("", dispatch)], strict=True, where=where)
    llm.dispatch = dispatch  # type: ignore[attr-defined]
    return llm


def kind_of_call(call: LLMCall) -> str:
    return logical_kind(call.schema_title, call.prompt)


def calls_of(llm: ScriptedLLM, *kinds: str) -> list[LLMCall]:
    """Recorded calls of the given logical kinds."""
    return [c for c in llm.calls if kind_of_call(c) in kinds]


ABHIYOJAK_KINDS = ("objections", "judge")
PLANNING_KINDS = ("plan", "factors")


class BigTokensLLM(ScriptedLLM):
    """A scripted LLM whose every call reports a large token count (to hit the 150,000-token case cap, plan §6.2)."""

    PER_CALL = 60_000

    def count_tokens(self, text: str) -> int:
        return self.PER_CALL


def fat(items: list[dict], *keys: str) -> dict[str, Any]:
    """The same list under several wrapper keys (see the module docstring)."""
    return {k: items for k in keys}


def ids_in(prompt: str, ids: list[str]) -> list[str]:
    """Which of `ids` occur in the prompt, in the order of `ids`."""
    return [i for i in ids if re.search(rf"\b{re.escape(i)}\b", prompt)]


# =====================================================================================================================
# the constructed 14-page bundle (plan §4.6, §13.6 flow 1)
# =====================================================================================================================
def scanned(**kw: Any) -> PageSignals:
    """Signals of a scanned page: no text layer."""
    return PageSignals(has_text_layer=False, text_coverage=0.0, **kw)


FIR_P1 = (
    "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024 घटना दिनांक 10.08.2024 धारा 318(4) बी.एन.एस. "
    f"आरोपी {HI_ACCUSED} शिकायतकर्ता {HI_COMPLAINANT}"
)
FIR_P2 = f"हस्तलिखित प्रविष्टि: आरोपी {HI_ACCUSED} ने शिकायतकर्ता {HI_COMPLAINANT} से धनराशि ली।"
ARREST_SENTENCE = f"The accused {NAME_ACCUSED} was arrested on 20.08.2024 in FIR No. 112/2024"
REMAND_SENTENCE = "produced before the Magistrate and remanded to judicial custody on 21.08.2024"
REJECT_SENTENCE = f"The bail application of {NAME_ACCUSED} is rejected. Dated 30.09.2024"
ORDER_SHEET_SENTENCE = "Charge sheet filed on 02.11.2024. Charges not framed."


def _digital(text: str, doc_type: DocumentType, lang: str = "en") -> FakePage:
    return FakePage(text=text, doc_type=doc_type, lang=lang)  # default signals: good text layer


def build_bundle(second_arrest_date: str | None = None) -> list[FakePage]:
    """The 14-page file of plan §13.6 flow 1 (names planted in every page that has people in it).

    Pages 1-3 FIR (Hindi, scanned; p2 handwriting that needs the vision model; p3 unreadable even by vision), pages 4-5
    and 6-7 two remand orders (born-digital; the first recites the arrest and the first remand), pages 8-14 the
    Sessions Court bail rejection with the order-sheet text on page 14. `second_arrest_date='22.08.2024'` makes the
    second remand order recite a different arrest date (a conflict between two documents).
    """
    recital = f"The accused {NAME_ACCUSED} was arrested on {second_arrest_date}; " if second_arrest_date else ""
    return [
        FakePage(text=FIR_P1, signals=scanned(), ocr_text=FIR_P1, ocr_conf=0.81, lang="hi", doc_type=DocumentType.FIR),
        FakePage(text=FIR_P2, signals=scanned(handwriting_detected=True), ocr_text="॥ ~~ ॥ ~", ocr_conf=0.42,
                 vision_text=FIR_P2, lang="hi", doc_type=DocumentType.FIR),
        FakePage(text="", signals=scanned(skew_or_perspective=True), ocr_text="", ocr_conf=0.2, vision_text="",
                 lang="hi", doc_type=DocumentType.FIR),
        _digital(f"REMAND ORDER. {ARREST_SENTENCE} and {REMAND_SENTENCE}. Complainant {NAME_COMPLAINANT}; IO {NAME_IO}.",
                 DocumentType.REMAND_ORDER),
        _digital(f"Next date of hearing 04.09.2024. Co-accused {NAME_CO_ACCUSED} is absconding.", DocumentType.REMAND_ORDER),
        _digital(f"REMAND ORDER. {recital}Judicial custody of the accused {NAME_ACCUSED} extended till 18.09.2024.",
                 DocumentType.REMAND_ORDER),
        _digital("Copy supplied to the accused. Next date 18.09.2024.", DocumentType.REMAND_ORDER),
        *[_digital(f"IN THE COURT OF SESSIONS. Bail application page {p}. Submissions heard.", DocumentType.BAIL_ORDER)
          for p in range(8, 13)],
        _digital(f"ORDER. {REJECT_SENTENCE}.", DocumentType.BAIL_ORDER),
        _digital(f"ORDER SHEET. {ORDER_SHEET_SENTENCE}", DocumentType.BAIL_ORDER),
    ]


BUNDLE_BOUNDARIES: list[tuple[int, int, DocumentType, str]] = [
    (1, 3, DocumentType.FIR, "hi"),
    (4, 5, DocumentType.REMAND_ORDER, "en"),
    (6, 7, DocumentType.REMAND_ORDER, "en"),
    (8, 14, DocumentType.BAIL_ORDER, "en"),
]


def munshi_events_responder(extra: list[tuple[str, dict]] | None = None):
    """Scripted Munshi event extraction: finds the dated sentences of the bundle in the prompt (the text is already
    pseudonymised or at least name-free in these sentences) and answers with the matching events (fat JSON)."""
    table: list[tuple[str, dict]] = [
        ("arrested on 20.08.2024", {"event_id": "e3", "date": "2024-08-20", "label": "Arrest", "quote": "arrested on 20.08.2024"}),
        ("remanded to judicial custody on 21.08.2024",
         {"event_id": "e4", "date": "2024-08-21", "label": "First remand", "quote": REMAND_SENTENCE}),
        ("is rejected. Dated 30.09.2024",
         {"event_id": "e5", "date": "2024-09-30", "label": "Sessions Court rejected bail", "quote": "is rejected. Dated 30.09.2024"}),
        ("Charge sheet filed on 02.11.2024",
         {"event_id": "e6", "date": "2024-11-02", "label": "Charge sheet filed", "quote": "Charge sheet filed on 02.11.2024"}),
        ("arrested on 22.08.2024", {"event_id": "e3b", "date": "2024-08-22", "label": "Arrest", "quote": "arrested on 22.08.2024"}),
    ] + list(extra or [])

    def respond(prompt: str, schema: dict | None) -> dict:
        found = [ev for needle, ev in table if needle in prompt]
        return fat(found, "events", "dated_events", "timeline_events", "items")

    return respond


# =====================================================================================================================
# worlds
# =====================================================================================================================
def case_0007_world(second_parity: bool = False, excluded: set[str] | None = None, case_docs: bool = True) -> CaseWorld:
    """case-0007 in memory (test-split and same-FIR orders excluded). Optional extras go into a LOCAL copy, never into
    the shared fixtures: `second_parity` adds DLHC-2020-0777#4 (a second qualifying parity reasoning paragraph),
    `case_docs` fills case.docs with the co-accused bail order and a role comparison."""
    world = build_world(excluded_doc_ids=excluded)
    if second_parity:
        extra = ParagraphRecord(
            doc_id="DLHC-2020-0777", para=4, court="Delhi HC", date="2020-02-11", outcome="granted", part="reasoning",
            sections=["IPC 420"], section_family=["IPC 420", "BNS 318(4)"], factors=[Factor.PARITY_WITH_CO_ACCUSED],
            cites=[], authority=0.5,
            text="[synthetic] Parity: a co-accused of equal role was released on bail, so the applicant too must be released.",
        )
        world.stores[StoreName.CASELAW_REASONING] = fs.InMemoryReasoningStore(
            load_paragraphs() + [extra], excluded if excluded is not None else {"TESTORD-2024-0001", "SAMEFIR-2024-0002"}
        )
    if case_docs:
        world.stores[StoreName.CASE_DOCS] = fs.InMemoryCaseDocsStore(
            [
                CaseChunk(chunk_id="c1", doc_id="d5", doc_type=DocumentType.BAIL_ORDER, page=12,
                          text="Co-accused-1 is admitted to bail on 05.12.2024; alleged role identical to the applicant."),
                CaseChunk(chunk_id="c2", doc_id="d1", doc_type=DocumentType.FIR, page=1,
                          text="Role of accused and role of co-accused: both are alleged to have signed the same invoices."),
            ]
        )
    return world


def fresh_case_world() -> CaseWorld:
    """case-0007 shared stores, but an EMPTY case shelf (docs, timeline, facts) to be filled by Munshi."""
    world = build_world()
    world.stores[StoreName.CASE_TIMELINE] = fs.InMemoryTimelineStore([])
    world.stores[StoreName.CASE_FACTS] = fs.InMemoryFactsStore(CaseDossier(case_id=CASE_ID, court="Delhi High Court", as_of=AS_OF))
    world.stores[StoreName.CASE_DOCS] = fs.InMemoryCaseDocsStore()
    return world


def with_charge_sheet(dossier: CaseDossier, filed: bool, date: str | None = None, as_of: str | None = None) -> CaseDossier:
    """Deep copy with the charge-sheet value replaced (and, optionally, the as-of date)."""
    out = dossier.model_copy(deep=True)
    out.fields.charge_sheet = TrackedField[ChargeSheetValue](
        value=ChargeSheetValue(filed=filed, date=date),
        source=SourceRef(doc="d4 (order sheet)", page=9, lang="en", route="text_layer",
                         quote=ORDER_SHEET_SENTENCE if filed else "Investigation continuing; charge sheet awaited"),
        status=FieldStatus.VERIFIED,
    )
    if as_of:
        out.as_of = as_of
    return out


def timeline_without(world: CaseWorld, *event_ids: str) -> list[TimelineEvent]:
    return [e.model_copy(deep=True) for e in world.timeline if e.event_id not in event_ids]


# =====================================================================================================================
# the scenario toolbox
# =====================================================================================================================
_DATE_DOT = re.compile(r"\b(\d{2})\.(\d{2})\.(\d{4})\b")
PSEUDONYM_ALIASES_ALL = {**PSEUDONYM_ALIASES, HI_ACCUSED: "Accused-1", HI_COMPLAINANT: "Complainant-1"}


def iso_dates(text: str) -> str:
    """dd.mm.yyyy -> yyyy-mm-dd (the form the dossier stores)."""
    return _DATE_DOT.sub(lambda m: f"{m[3]}-{m[2]}-{m[1]}", text)


def mentions_date(text: str, iso: str) -> bool:
    """True if `text` writes the date as ISO or as dd.mm.yyyy."""
    y, m, d = iso.split("-")
    return iso in text or f"{d}.{m}.{y}" in text or f"{d}/{m}/{y}" in text


def _leaves(value: Any) -> list[str]:
    if isinstance(value, BaseModel):
        value = value.model_dump()
    if isinstance(value, dict):
        return [x for v in value.values() for x in _leaves(v)]
    if isinstance(value, (list, tuple)):
        return [x for v in value for x in _leaves(v)]
    if value is None or isinstance(value, bool):
        return []
    return [str(value)]


class ScenarioToolbox(FakeToolbox):
    """`FakeToolbox` plus scenario hooks.

    * `boundaries` makes `split_bundle` return explicit document ranges (the base class would merge the two remand orders);
    * `pseudonymise` knows the Hindi planted names too; `file_item` keeps status / conflicts_with and upserts by event id;
    * `extract_dossier` is the fine-tuned extractor's *fake*: it reads the truth of the world, resets every status to the
      default (an extractor does not verify itself), reads the charge-sheet state from the case shelf, and only offers
      `personal` when counsel said something in chat (`chat_facts`, source `{"chat": "turn 3"}`). With `fields=[...]`
      it re-extracts just those fields and keeps the rest of the current dossier (plan §7.4);
    * `span_check` is lenient NLI: every date or number in the value must occur in the quote (dd.mm.yyyy read as ISO);
    * `rights_check` and `diff_case_state` are the real engines (`RightsEngine`, `compute_change_set`) over the shelf.
    """

    def __init__(
        self,
        world: CaseWorld,
        pages: list[FakePage] | None = None,
        answers: list[str] | None = None,
        gate2_approved: bool = False,
        *,
        boundaries: list[tuple[int, int, DocumentType, str]] | None = None,
        as_of: str = AS_OF,
        chat_facts: list[str] | None = None,
        approved_dossier: CaseDossier | None = None,
        approved_rights: Any = None,
    ) -> None:
        self.boundaries = boundaries
        self.as_of = as_of
        self.chat_facts = chat_facts
        self.approved_dossier = approved_dossier
        self.approved_rights = approved_rights
        super().__init__(world, pages, answers, gate2_approved)

    # -- shelf access ------------------------------------------------------------------------------------------
    @property
    def timeline_store(self) -> fs.InMemoryTimelineStore:
        return self.world.stores[StoreName.CASE_TIMELINE]

    @property
    def facts_store(self) -> fs.InMemoryFactsStore:
        return self.world.stores[StoreName.CASE_FACTS]

    @property
    def docs_store(self) -> fs.InMemoryCaseDocsStore:
        return self.world.stores[StoreName.CASE_DOCS]

    # -- intake ------------------------------------------------------------------------------------------------
    def t_split_bundle(self, file_path: str) -> list[DocumentEntry]:
        if self.boundaries is None:
            return super().t_split_bundle(file_path)
        return [DocumentEntry(doc_id=f"d{i}", type=t, pages=[a, b], lang=lang) for i, (a, b, t, lang) in enumerate(self.boundaries, 1)]

    def t_pseudonymise(self, text: str, case_id: str) -> str:
        for name, alias in PSEUDONYM_ALIASES_ALL.items():
            text = text.replace(name, alias)
        return text

    def t_file_item(self, store: StoreName, item: dict[str, Any], source: SourceRef):
        from vakeel_sahayak.tools.types import FileItemResult

        store = StoreName(store)
        if store == StoreName.CASE_TIMELINE:
            keep = {k: item[k] for k in ("event_id", "date", "label", "status", "conflicts_with") if k in item}
            event = TimelineEvent(**keep, source=source)
            self.timeline_store.events = [e for e in self.timeline_store.events if e.event_id != event.event_id]
            self.timeline_store.add_event(event)
            return FileItemResult(store=store, item_id=event.event_id)
        return super().t_file_item(store, item, source)

    # -- dossier and rights ------------------------------------------------------------------------------------
    def _raw_extraction(self) -> CaseDossier:
        d = self.world.dossier.model_copy(deep=True)
        for name in type(d.fields).model_fields:
            tf = getattr(d.fields, name)
            if name == "personal":
                tf = (TrackedField[list[str]](value=list(self.chat_facts), source=SourceRef(chat="turn 3"), status=FieldStatus.USER_STATED)
                      if self.chat_facts else TrackedField[list[str]]())
            elif name in ("antecedents", "custody_days"):
                tf = type(tf)()
            else:
                tf = tf.model_copy(update={"status": FieldStatus.UNSUPPORTED})
            setattr(d.fields, name, tf)
        events = self.timeline_store.get()
        filed = [e for e in events if "charge sheet" in e.label.lower()]
        d.fields.charge_sheet = TrackedField[ChargeSheetValue](
            value=ChargeSheetValue(filed=bool(filed), date=filed[0].date if filed else None),
            source=filed[0].source if filed else None,
            status=FieldStatus.UNSUPPORTED,
        )
        d.as_of = self.as_of
        return d

    def t_extract_dossier(self, case_id: str, fields: list[str] | None = None) -> CaseDossier:
        raw = self._raw_extraction()
        current = self.facts_store.dossier()
        if fields is None:
            merged = raw
        else:
            merged = current.model_copy(deep=True)
            for name in fields:
                setattr(merged.fields, name, getattr(raw.fields, name))
        merged.case_id = case_id
        self.facts_store._dossier = merged
        return merged

    def t_span_check(self, value: Any, quote: str) -> SpanCheckResult:
        premise = iso_dates(quote or "")
        needles = [x for x in (iso_dates(leaf) for leaf in _leaves(value)) if re.fullmatch(r"[\d\-/().]+", x)]
        ok = bool(premise) and all(n in premise for n in needles)
        return SpanCheckResult(supported=ok, score=0.95 if ok else 0.05, quote=quote)

    def t_rights_check(self, case_id: str, as_of: str | None = None):
        from vakeel_sahayak.rights.engine import RightsEngine

        return RightsEngine().run(self.facts_store.dossier(), self.timeline_store.get(), as_of or self.as_of)

    def t_diff_case_state(self, case_id: str, since_hash: str | None = None):
        from vakeel_sahayak.truth_maintenance.staleness import compute_change_set

        new_rights = self.t_rights_check(case_id)
        return compute_change_set(self.approved_dossier, self.facts_store.dossier(), self.approved_rights, new_rights)


def planted_in_stores(toolbox: FakeToolbox, names: list[str] | None = None) -> list[str]:
    """Planted names found in any row of the case shelf (timeline, docs, facts)."""
    rows = [e.model_dump_json() for e in toolbox.world.stores[StoreName.CASE_TIMELINE].events]
    rows += [c.model_dump_json() for c in toolbox.world.stores[StoreName.CASE_DOCS].chunks]
    rows.append(toolbox.world.stores[StoreName.CASE_FACTS].dossier().model_dump_json())
    return leaked_names(rows, names or PLANTED_NAMES + PLANTED_NAMES_HI)


def seed_state(file: str = "bundle_1.pdf", case_id: str = CASE_ID):
    """The state Munshi starts from. ASSUMPTION: the file to ingest is named by a seeded `IngestionReport.file`
    (the graph state has no other field for it)."""
    from vakeel_sahayak.orchestration.state import CaseGraphState

    return CaseGraphState(case_id=case_id, ingestion=IngestionReport(case_id=case_id, file=file))


# =====================================================================================================================
# Sutradhar: contract-driven scripted plans
# =====================================================================================================================
def contract_spec(factor: Factor) -> dict:
    return yaml.safe_load((CONTRACTS_DIR / f"{factor.value}.yaml").read_text(encoding="utf-8"))


def contract_slots(factor: Factor) -> list[str]:
    return list(contract_spec(factor)["slots"])


def contract_stores(factor: Factor, slot: str) -> list[str]:
    return list(contract_spec(factor)["slots"][slot].get("stores", []))


def contract_steps(
    factor: Factor,
    *,
    family: list[str] = FAMILY,
    before: str = AS_OF,
    authority_court: str | None = None,
    authority_factor: bool = True,
    query: str | None = None,
) -> list[dict]:
    """What a sensible 14B planner writes for a contract: first allowed store of each slot, plan §6.3 argument style."""
    steps: list[dict] = []
    for slot, spec in contract_spec(factor)["slots"].items():
        store = (spec.get("stores") or [None])[0]
        q = query or f"{slot.replace('_', ' ')} {factor.value.replace('_', ' ')}"
        if store == "case.docs":
            args: dict = {"case_id": CASE_ID, "query": "co-accused granted bail" if slot == "co_accused_order" else q}
            if slot == "co_accused_order":
                args["doc_types"] = ["BAIL_ORDER"]
            tool = "search_case_docs"
        elif store == "case.timeline":
            tool, args = "get_timeline", {"case_id": CASE_ID}
        elif store == "case.facts":
            tool, args = "get_fact", {"case_id": CASE_ID, "field": "personal"}
        elif store == "caselaw.reasoning":
            tool = "search_reasoning"
            args = {"query": q, "section_family": list(family), "before": before, "outcome": "granted", "k": 10}
            if authority_factor:
                args["factor"] = factor.value
            if authority_court and slot == "authority":
                args["court"] = authority_court
        elif store == "caselaw.citations":
            tool, args = "citations", {"doc_ids": "$authority.top3", "want": ["overruled_by", "sc_root"]}
        elif store == "advocacy.objections":
            tool = "search_objections"
            args = {"query": q, "factor": factor.value, "section_family": list(family), "before": before}
        elif store == "advocacy.arguments":
            tool = "search_arguments"
            args = {"query": q, "factor": factor.value, "section_family": list(family), "before": before}
        elif store == "law.statutes":
            tool, args = "search_statutes", {"query": q}
        else:
            tool, args = "rights_check", {"case_id": CASE_ID}
        steps.append({"slot": slot, "tool": tool, "args": args})
    return steps


def detect_factor(prompt: str, default: Factor = Factor.PARITY_WITH_CO_ACCUSED) -> Factor:
    """The factor a planning prompt is about: the only factor stem in the prompt, else the last one mentioned."""
    hits = sorted(((prompt.rfind(f.value), f) for f in Factor if f.value in prompt), key=lambda t: t[0])
    return hits[-1][1] if hits else default


def plan_responder(
    *,
    extra_steps: list[dict] | None = None,
    replace_slot: dict[str, dict] | None = None,
    default: Factor = Factor.PARITY_WITH_CO_ACCUSED,
    **step_kw: Any,
):
    """Scripted `RetrievalPlan` answers (idempotent: the same plan every time it is asked, so any filter relaxation
    seen in later rounds comes from the agent's fixed relaxation order, not from the script). `replace_slot` swaps a
    slot's step (to script a bad planner); `extra_steps` appends steps (e.g. an off-contract slot)."""

    def respond(prompt: str, schema: dict | None) -> dict:
        factor = detect_factor(prompt, default)
        steps = contract_steps(factor, **step_kw)
        for s in steps:
            if replace_slot and s["slot"] in replace_slot:
                s.update(replace_slot[s["slot"]])
        steps += [dict(x) for x in (extra_steps or [])]
        return {"factor": factor.value, "round": 1, "budget_left": {"store_calls": 8, "tokens": 12000},
                "steps": steps, "assessment": {}, "next": None}

    return respond


FAVOURABLE = [Factor.PARITY_WITH_CO_ACCUSED, Factor.CHARGE_SHEET_FILED, Factor.CUSTODY_PERIOD, Factor.TRIAL_DELAY]


def factors_responder(favourable: list[Factor] | None = None):
    """Scripted factor picking: the given factors favourable, the rest not applicable (fat JSON)."""
    favourable = FAVOURABLE if favourable is None else favourable

    def respond(prompt: str, schema: dict | None) -> dict:
        rows = [
            {"factor": f.value, "stance": "favourable" if f in favourable else "not_applicable",
             "reason": "contract applies" if f in favourable else "does not apply", "slots": [], "open_issues": []}
            for f in Factor
        ]
        return fat(rows, "packs", "factors", "items", "picks")

    return respond


# =====================================================================================================================
# Vakeel / Abhiyojak scripted drafts
# =====================================================================================================================
G1_TEXT = "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail]; parity applies [A:DLHC-2022-1187#14]."
G2_TEXT = "The charge sheet was filed on 02.11.2024 [F:charge_sheet], so custodial interrogation is no longer required [A:SC-2014-0463#21]."
G3_TEXT = "The applicant has been in custody for 167 days [F:custody_days]; prolonged custody weighs for bail [A:DLHC-2021-0420#11]."

DRAFTS: dict[Factor, dict] = {
    Factor.PARITY_WITH_CO_ACCUSED: {
        "id": "G1", "factor": "parity_with_co_accused", "stance": "favourable", "argument": G1_TEXT,
        "authorities": [{"doc_id": "DLHC-2022-1187", "para": 14}], "notes": f"{VAKEEL_NOTE}: lead with parity",
    },
    Factor.CHARGE_SHEET_FILED: {
        "id": "G2", "factor": "charge_sheet_filed", "stance": "favourable", "argument": G2_TEXT,
        "authorities": [{"doc_id": "SC-2014-0463", "para": 21}],
    },
    Factor.CUSTODY_PERIOD: {
        "id": "G3", "factor": "custody_period", "stance": "favourable", "argument": G3_TEXT,
        "authorities": [{"doc_id": "DLHC-2021-0420", "para": 11}],
    },
}


def ground_responder(drafts: dict[Factor, dict] | None = None):
    """Scripted Vakeel drafting: the draft of the factor named in the prompt (fat: the ground's own fields plus
    `grounds`/`items` carrying every draft)."""
    drafts = DRAFTS if drafts is None else drafts

    def respond(prompt: str, schema: dict | None) -> dict:
        everything = list(drafts.values())
        mine = next((d for f, d in drafts.items() if f.value in prompt), everything[0] if everything else {})
        return {**mine, **fat(everything, "grounds", "items", "drafts")}

    return respond


O_UNGROUNDED_TEXT = "The applicant is a habitual offender with many pending cases."
OBJECTIONS: list[dict] = [
    {"id": "O1", "against": "G1", "factor": "parity_with_co_accused",
     "objection": "The applicant, unlike Co-accused-1, received the money into his own account.",
     "grounds": [{"store": "advocacy.objections", "doc_id": "DLHC-2023-0911", "para": 6}, {"fact": "fir"}]},
    {"id": "O2", "against": "G1", "factor": "parity_with_co_accused",
     "objection": "The role attributed to the applicant distinguishes him from the co-accused.",
     "grounds": [{"store": "caselaw.reasoning", "doc_id": "DLHC-2023-0911", "para": 12}]},
    {"id": "O3", "against": "G1", "factor": "parity_with_co_accused",
     "objection": "A third objection against the same ground, beyond the two allowed per ground.",
     "grounds": [{"fact": "co_accused_bail"}]},
    {"id": "O4", "against": "general", "factor": "witness_tampering",
     "objection": "Charges are not framed and the complainant is yet to be examined.",
     "grounds": [{"fact": "trial_stage"}]},
    {"id": "O5", "against": "general", "factor": "antecedents", "objection": O_UNGROUNDED_TEXT,
     "grounds": [{"store": "advocacy.objections", "doc_id": "DLHC-9999-0001", "para": 3}]},
]
REPLY_SUPPORTED = "Co-accused with an identical role has been enlarged on bail; parity requires the same relief."
REPLIES: dict[str, dict] = {
    "O1": {"text": REPLY_SUPPORTED, "authorities": [{"doc_id": "DLHC-2022-1187", "para": 14}]},
    # cites a paragraph nobody retrieved: must be flagged NEEDS_REVIEW (plan §9: same citation rules)
    "O2": {"text": "The role is identical on the record.", "authorities": [{"doc_id": "DLHC-1999-0000", "para": 7}]},
    "O4": {"text": "Trial has not begun; conditions can address the concern.", "authorities": []},
}
VERDICTS: dict[str, dict] = {
    "O1": {"id": "O1", "verdict": "ANSWERED", "reason": "the reply cites the parity paragraph"},
    "O2": {"id": "O2", "verdict": "PARTLY", "reason": "the citation is unverified"},
    "O4": {"id": "O4", "verdict": "UNANSWERED", "reason": "no authority offered for the trial stage"},
}


def objections_responder(objections: list[dict] | None = None):
    objs = OBJECTIONS if objections is None else objections

    def respond(prompt: str, schema: dict | None) -> dict:
        return fat(objs, "objections", "items", "round1")

    return respond


def reply_responder(replies: dict[str, dict] | None = None):
    replies = REPLIES if replies is None else replies

    def respond(prompt: str, schema: dict | None) -> dict:
        found = ids_in(prompt, list(replies)) or list(replies)
        rows = [{"id": i, **replies[i]} for i in found]
        return {**rows[0], **fat(rows, "replies", "items")}

    return respond


def judge_responder(verdicts: dict[str, dict] | None = None):
    verdicts = VERDICTS if verdicts is None else verdicts

    def respond(prompt: str, schema: dict | None) -> dict:
        found = ids_in(prompt, list(verdicts)) or list(verdicts)
        rows = [verdicts[i] for i in found]
        return {**rows[0], **fat(rows, "verdicts", "objections", "items")}

    return respond


def sparring_llm(**overrides: Any) -> ScriptedLLM:
    """One LLM that answers Vakeel's replies and Abhiyojak's objections and verdicts (plus Vakeel's drafting)."""
    handlers = {
        "ground": ground_responder(), "objections": objections_responder(), "reply": reply_responder(),
        "judge": judge_responder(), "free": "",
    }
    handlers.update(overrides)
    return make_llm(where="ada", **handlers)


def full_pipeline_llm(**overrides: Any) -> ScriptedLLM:
    """Sutradhar + Vakeel + Abhiyojak scripts: plans from the contracts, favourable factors, drafts, sparring."""
    handlers = {
        "plan": plan_responder(authority_court=None), "factors": factors_responder(),
        "ground": ground_responder(), "objections": objections_responder(), "reply": reply_responder(),
        "judge": judge_responder(), "free": "ok",
    }
    handlers.update(overrides)
    return make_llm(where="ada", **handlers)


def para_ids(items: list[dict]) -> set[str]:
    """'doc_id#para' of every paragraph-like item of a slot result."""
    return {f"{i['doc_id']}#{i['para']}" for i in items if "doc_id" in i and "para" in i}


# =====================================================================================================================
# patching ambient factories (agents / drivers that have no ctx parameter)
# =====================================================================================================================
def install_llm(monkeypatch: Any, llm: ScriptedLLM, nli: Any = None) -> None:
    """Make every `get_llm(...)` (factory and any module alias) return `llm`; same for `get_nli` when given."""
    from tests.unit.truth_maintenance._helpers import install_llm as _install

    _install(monkeypatch, llm, nli)


def patch_nodes(monkeypatch: Any, **nodes: Any) -> None:
    """Replace graph node functions by name (e.g. `intake_node=fake`) in `orchestration.graph` and in every module
    that imported the same name (ASSUMPTION: the state machine and the graph look nodes up in `orchestration.graph`,
    or import them by name; both are covered)."""
    from vakeel_sahayak.orchestration import graph

    for name, fn in nodes.items():
        monkeypatch.setattr(graph, name, fn)
        for mod_name, mod in list(sys.modules.items()):
            if mod_name.startswith("vakeel_sahayak") and mod is not None and mod is not graph and hasattr(mod, name):
                monkeypatch.setattr(mod, name, fn)


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)
