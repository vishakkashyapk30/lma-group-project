"""Scenario driver and constructed inputs for the system tests (plan §13.6 user flows, §15.2 T7 safety scenarios).

`Scenario` wires, on a laptop and with no GPU, everything a flow needs:

* a `SystemToolbox` (the shared `FakeToolbox` plus bundle boundaries, a settable change set and a pseudonymiser hook)
  over a `CaseWorld` (in-memory stores of case-0007);
* two `ScriptedLLM` clients: `scenario.ada` (where="ada": Sutradhar, Vakeel, Abhiyojak, Pairokar) and
  `scenario.laptop` (where="laptop": Munshi, Peshkar), so a test can inspect everything an Ada-bound client ever saw;
* the real SQLite `EventLog` (default location under `$VS_DATA_DIR`, pointed at tmp_path), the real `GateGuard`, the real
  exporter and, on demand, the FastAPI app from `create_app()` behind a `TestClient`.

ASSUMPTIONS about wiring (all of them live in this file, in `Scenario.__init__`, `_patch_wiring`, `add_upload` and
`resolve`; if the implementation wires differently, adapt here, not in the tests):

* `GateGuard()` (no arguments) and the API find the case record through `EventLog()` whose default location derives from
  `$VS_DATA_DIR`; the same convention as tests/unit/orchestration/_helpers.py. The agents get the very same log object.
* Model clients are resolved through `vakeel_sahayak.models.factory.get_llm(role)` (role `agents_14b` is the Ada client,
  every other role the laptop client) and tools through `vakeel_sahayak.tools.registry.get_tool(name)`; both are
  patched everywhere they were imported, so code that has no `AgentContext` (the API routers, `redraft_incrementally`)
  also runs on the fakes.
* Uploaded raw files live in `$VS_DATA_DIR/cases/<case_id>/` (laptop only); Munshi ingests what is there.
* Counsel resolves a Gate 2 checklist item (NEEDS_REVIEW ground, UNANSWERED objection) by a USER_ACTION event with
  `actor="counsel"` and `inputs={"action": "resolve", "item": <ground or objection id>}`. The skeleton has no route for
  this yet (only `acknowledged_fields` on approve); see the report.
* Payload shapes of record events follow tests/unit/record/_helpers.py (STORE_WRITE of `case.facts` fields, `case.views`).
* The LLM scripts below encode an assumed call order of the agents (schema titles `RetrievalPlan`, `Ground`, `Objection`,
  `Reply`); they are the single place to adapt when an agent asks for its output differently.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from tests.fakes.context import make_context
from tests.fakes.data import CaseWorld, build_world
from tests.fakes.log import InMemoryEventLog
from tests.fakes.models import FakeAsr, ScriptedLLM, Seq
from tests.fakes.stores import install_fake_stores
from tests.fakes.toolbox import PSEUDONYM_ALIASES, FakePage, FakeToolbox
from tests.fixtures import pdfgen
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.models.base import LLMClient
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.privacy.injection_guard import wrap_untrusted
from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, Ground
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import (
    AgentName,
    ClaimCheck,
    DocumentType,
    EventKind,
    Factor,
    FactorStance,
    FieldStatus,
    GateId,
    RightsCheckName,
    RightsStatus,
    SparringVerdict,
    Stage,
    StoreName,
)
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, IngestionReport
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft, PlanStep, RetrievalPlan
from vakeel_sahayak.schemas.rights_report import RightsCheckResult, RightsReport
from vakeel_sahayak.schemas.sparring import Objection, ObjectionGround, Reply, SparringRecord

CASE_ID = "case-0007"
AS_OF = "2025-02-03"
G1 = GateId.GATE_1_DOSSIER
G2 = GateId.GATE_2_EXPORT

ADA_AGENTS = (AgentName.SUTRADHAR, AgentName.VAKEEL, AgentName.ABHIYOJAK, AgentName.PAIROKAR)
LAPTOP_AGENTS = (AgentName.MUNSHI, AgentName.PESHKAR)
ADA_ROLES = {"agents_14b", "teacher"}

# ASSUMPTION: refusals of a gate approval or an export raise one of these (NotImplementedError is deliberately absent).
REFUSED = (ValueError, PermissionError)
# ASSUMPTION: HTTP codes the plan does not fix. Export before Gate 2 is 403 (the router docstring says so); approving a gate
# whose checklist is not cleared is 409 Conflict.
HTTP_EXPORT_REFUSED = 403
HTTP_CHECKLIST_OPEN = 409

PSEUDONYM_ALIASES_HI = {"रमेश कुमार यादव": "Accused-1", "सुनीता देवी शर्मा": "Complainant-1"}

CHAT_SCHEMA_TITLES = ("RetrievalPlan", "Ground", "Objection", "Reply")


# --------------------------------------------------------------------------------------------------------------------
# Constructed pages and bundles
# --------------------------------------------------------------------------------------------------------------------
@dataclass
class BundlePage(FakePage):
    """A FakePage that can also start a new document inside a bundle (two consecutive remand orders)."""

    new_doc: bool = False


def page(text: str, doc_type: DocumentType = DocumentType.OTHER, *, new_doc: bool = False, lang: str = "en",
         scanned: bool = False, handwriting: bool = False, ocr_text: str | None = None, ocr_conf: float | None = None,
         vision_text: str | None = None) -> BundlePage:
    """One scripted page. Born-digital by default; `scanned=True` removes the text layer (OCR/vision routes only)."""
    if scanned:
        signals = PageSignals(has_text_layer=False, text_coverage=0.0, mean_ocr_conf=ocr_conf, handwriting_detected=handwriting)
    else:
        signals = PageSignals(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95)
    return BundlePage(text=text, signals=signals, ocr_text=ocr_text, ocr_conf=ocr_conf, vision_text=vision_text, lang=lang,
                      doc_type=doc_type, new_doc=new_doc)


HI_FIR_P1 = "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024\nधारा 318(4) बी.एन.एस.\nघटना दिनांक 10.08.2024"
HI_FIR_P2 = "हस्तलिखित प्रविष्टि: शिकायतकर्ता का बयान"
HI_FIR_P4 = "थाना प्रभारी के हस्ताक्षर और मुहर"
REMAND_PAGE_2 = pdfgen.REMAND_PAGE.replace("Next date of hearing is 04.09.2024.", "Next date of hearing is 18.09.2024.")


def messy_bundle_pages() -> list[BundlePage]:
    """The 14-page bundle of plan §13.6 flow 1: scanned Hindi FIR (p.1-4, p.3 unreadable), two remand orders (p.5-7, p.8-10),
    Sessions Court bail rejection with the order sheet (p.11-14)."""
    fir = [
        page(HI_FIR_P1, DocumentType.FIR, new_doc=True, lang="hi", scanned=True, ocr_text=HI_FIR_P1, ocr_conf=0.81),
        page(HI_FIR_P2, DocumentType.FIR, lang="hi", scanned=True, handwriting=True, ocr_text="", ocr_conf=0.42,
             vision_text=HI_FIR_P2),
        page("", DocumentType.FIR, lang="hi", scanned=True, ocr_text="", ocr_conf=0.08, vision_text=""),  # page 3: unreadable
        page(HI_FIR_P4, DocumentType.FIR, lang="hi", scanned=True, ocr_text=HI_FIR_P4, ocr_conf=0.78),
    ]
    remand_1 = [page(pdfgen.REMAND_PAGE, DocumentType.REMAND_ORDER, new_doc=(i == 0)) for i in range(3)]
    remand_2 = [page(REMAND_PAGE_2, DocumentType.REMAND_ORDER, new_doc=(i == 0)) for i in range(3)]
    bail = [page(pdfgen.BAIL_ORDER_PAGE, DocumentType.BAIL_ORDER, new_doc=(i == 0)) for i in range(3)]
    bail.append(page(pdfgen.ORDER_SHEET_PAGE, DocumentType.BAIL_ORDER))
    pages = fir + remand_1 + remand_2 + bail
    assert len(pages) == 14
    return pages


EXPECTED_BUNDLE_DOCS = [
    (DocumentType.FIR, [1, 4], "hi"),
    (DocumentType.REMAND_ORDER, [5, 7], "en"),
    (DocumentType.REMAND_ORDER, [8, 10], "en"),
    (DocumentType.BAIL_ORDER, [11, 14], "en"),
]

CHARGE_SHEET_ORDER_TEXT = (
    "IN THE COURT OF THE METROPOLITAN MAGISTRATE\nORDER SHEET\nFIR No. 112/2024 PS-1\n"
    "Charge sheet filed on 02.11.2024. Charges not framed."
)


# --------------------------------------------------------------------------------------------------------------------
# Toolboxes
# --------------------------------------------------------------------------------------------------------------------
class SystemToolbox(FakeToolbox):
    """FakeToolbox plus: bundle boundaries (`BundlePage.new_doc`), a settable change set for `diff_case_state`, Devanagari
    aliases and an optional pseudonymiser hook (`(text, case_id) -> text`) used by the leak scenarios."""

    def __init__(self, world: CaseWorld, pages=None, answers=None, gate2_approved: bool = False, pseudonymiser=None) -> None:
        self.pending_change: ChangeSet | None = None
        self.pseudonymiser: Callable[[str, str], str] | None = pseudonymiser
        super().__init__(world, pages=pages, answers=answers, gate2_approved=gate2_approved)

    def t_split_bundle(self, file_path: str) -> list[DocumentEntry]:
        docs: list[DocumentEntry] = []
        start, n = 1, len(self.pages)
        for i in range(1, n + 1):
            nxt = self._page(i + 1) if i < n else None
            boundary = nxt is None or getattr(nxt, "new_doc", False) or nxt.doc_type != self._page(i).doc_type
            if boundary:
                docs.append(DocumentEntry(doc_id=f"d{len(docs) + 1}", type=self._page(i).doc_type, pages=[start, i],
                                          lang=self._page(start).lang))
                start = i + 1
        return docs

    def t_diff_case_state(self, case_id: str, since_hash: str | None = None) -> ChangeSet:
        return self.pending_change or ChangeSet(case_id=case_id, trigger="new_document")

    def t_pseudonymise(self, text: str, case_id: str) -> str:
        if self.pseudonymiser is not None:
            return self.pseudonymiser(text, case_id)
        for name, alias in {**PSEUDONYM_ALIASES, **PSEUDONYM_ALIASES_HI}.items():
            text = text.replace(name, alias)
        return text


_PER_FILE_TOOLS = ("inspect_page", "read_text_layer", "parse_layout", "ocr_page", "vision_read_page", "split_bundle",
                   "classify_document", "search_pages")


class BatchToolbox(SystemToolbox):
    """Per-file and per-case dispatch for the batch desk: `files[path] -> pages`, `rights_by_case`, `dossier_by_case`.
    ASSUMPTION: file `<dir>/case-0042.pdf` becomes case id `case-0042` (the file stem)."""

    def __init__(self, world: CaseWorld, cases: list[BatchCase], **kw: Any) -> None:
        self.files = {c.path: c.pages for c in cases}
        self.rights_by_case = {c.case_id: c.rights for c in cases}
        self.dossier_by_case = {c.case_id: c.dossier for c in cases}
        super().__init__(world, **kw)

    def t_extract_dossier(self, case_id: str, fields: list[str] | None = None):
        return self.dossier_by_case.get(case_id, self.world.dossier)

    def t_rights_check(self, case_id: str, as_of: str | None = None):
        return self.rights_by_case.get(case_id, self.world.rights)


def _per_file(name: str):
    base = getattr(SystemToolbox, f"t_{name}")

    def method(self: BatchToolbox, file_path: str, *args: Any, **kwargs: Any):
        key = file_path if file_path in self.files else Path(file_path).name
        by_name = {Path(p).name: pages for p, pages in self.files.items()}
        self.pages = self.files.get(key) or by_name[Path(file_path).name]
        return base(self, file_path, *args, **kwargs)

    method.__name__ = f"t_{name}"
    return method


for _name in _PER_FILE_TOOLS:
    setattr(BatchToolbox, f"t_{_name}", _per_file(_name))


# --------------------------------------------------------------------------------------------------------------------
# Constructed batch of 120 files with planted deadlines (plan §11, §15.2 T5, §13.6 flow 6)
# --------------------------------------------------------------------------------------------------------------------
PLANTED_INDEXES = (7, 19, 31, 44, 58, 63, 77, 85, 98, 113)  # 10 of 120
PLANTED_DAYS_LEFT = (3, 1, 6, 2, 7, 4, 5, 1, 2, 3)  # all within 7 days of AS_OF


@dataclass
class BatchCase:
    case_id: str
    path: str
    planted: bool
    days_left: int | None
    custody_days: int
    missing_docs: list[str]
    rights: RightsReport
    dossier: CaseDossier
    pages: list[BundlePage]


def _rights(case_id: str, default_bail: RightsCheckResult, custody_days: int) -> RightsReport:
    undertrial = RightsCheckResult(
        check=RightsCheckName.UNDERTRIAL_LIMIT, status=RightsStatus.NOT_YET,
        detail=f"{custody_days} days in custody. The threshold is 852 days for a first-time offender.",
        uses=["custody_days", "sections", "antecedents"], rule="BNSS s.479")
    bar = RightsCheckResult(check=RightsCheckName.STATUTORY_BAR, status=RightsStatus.NOT_APPLICABLE,
                            rule="NDPS s.37; UAPA s.43D(5); PMLA s.45")
    return RightsReport(case_id=case_id, as_of=AS_OF, checks=[default_bail, undertrial, bar])


def build_batch(n: int = 120, planted_indexes: tuple[int, ...] = PLANTED_INDEXES,
                planted_days_left: tuple[int, ...] = PLANTED_DAYS_LEFT) -> list[BatchCase]:
    """`n` tiny constructed cases. Planted cases: default-bail window opens in 1-7 days and the custody is SHORT, so a
    custody-length sort would rank them last. Others: window far away (30+ days), closed, or CHECK; some with long custody or
    a missing custody certificate. No unplanted case has a legal deadline within 7 days."""
    base_dossier = build_world().dossier
    cases: list[BatchCase] = []
    planted_map = dict(zip(planted_indexes, planted_days_left))
    for i in range(1, n + 1):
        cid = f"case-{i:04d}"
        planted = i in planted_map
        missing: list[str] = []
        if planted:
            days_left = planted_map[i]
            custody = 55 + (i % 4)
            db = RightsCheckResult(
                check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.NOT_YET,
                detail=f"Default-bail window opens in {days_left} days (BNSS s.187(3)). Day 1 is the first remand.",
                uses=["first_remand", "charge_sheet", "sections"], rule="BNSS s.187(3)")
        else:
            days_left = None
            kind = i % 4
            if kind == 0:
                custody = 5 + (i * 13) % 50
                db = RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.NOT_YET,
                                       detail=f"Default-bail window opens in {30 + (i * 7) % 60} days (BNSS s.187(3)).",
                                       uses=["first_remand", "sections"], rule="BNSS s.187(3)")
            elif kind == 1:
                custody = 100 + (i * 17) % 500
                db = RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.WINDOW_CLOSED,
                                       detail="The charge sheet was filed on day 74.", uses=["first_remand", "charge_sheet"],
                                       rule="BNSS s.187(3)")
            elif kind == 2:
                custody = 40 + (i * 11) % 80
                db = RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.CHECK,
                                       detail="Offence may extend to ten years: 60 or 90 days is unsettled.",
                                       uses=["sections"], rule="BNSS s.187(3)")
            else:
                custody = 700 + i
                db = RightsCheckResult(check=RightsCheckName.DEFAULT_BAIL, status=RightsStatus.WINDOW_CLOSED,
                                       detail="The charge sheet was filed on day 80.", uses=["first_remand", "charge_sheet"],
                                       rule="BNSS s.187(3)")
            if i % 11 == 3:
                missing = ["custody certificate"]
        dossier = base_dossier.model_copy(deep=True, update={"case_id": cid})
        dossier.fields.custody_days = TrackedField[int](value=custody, source=SourceRef(tool="date_calc"),
                                                        status=FieldStatus.COMPUTED)
        pages = [page(f"FIR No. {i}/2024 PS-{i % 9} under Section 318(4) BNS", DocumentType.FIR, new_doc=True),
                 page(pdfgen.REMAND_PAGE, DocumentType.REMAND_ORDER, new_doc=True)]
        cases.append(BatchCase(cid, f"batch/{cid}.pdf", planted, days_left, custody, missing, _rights(cid, db, custody),
                               dossier, pages))
    assert sum(c.planted for c in cases) == len(planted_indexes)
    return cases


def zip_bytes(cases: list[BatchCase]) -> bytes:
    """A zip of stub files named like the batch (the fake toolbox ignores content)."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for c in cases:
            z.writestr(Path(c.path).name, b"%PDF-1.4\n% stub\n")
    return buf.getvalue()


def pairwise_ranking_accuracy(cards: list, planted_ids: set[str]) -> float:
    """Share of (planted, other) pairs where the planted case has the better (smaller) urgency_rank."""
    rank = {c.case_id: c.urgency_rank for c in cards}
    pairs = [rank[p] < rank[q] for p in planted_ids for q in rank if q not in planted_ids]
    return sum(pairs) / len(pairs)


# --------------------------------------------------------------------------------------------------------------------
# LLM scripts (single place to adapt when an agent requests its output differently)
# --------------------------------------------------------------------------------------------------------------------
G1_ARGUMENT = ("Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail]; "
               "parity applies [A:DLHC-2022-1187#14].")
G2_ARGUMENT = ("The charge sheet was filed on 02.11.2024 [F:charge_sheet]; custodial interrogation is no longer needed "
               "[A:SC-2014-0463#21].")
G2_ARGUMENT_UNFILED = "No charge sheet has been filed against the applicant yet [F:charge_sheet]; the investigation continues."
G3_ARGUMENT = ("The applicant has been in custody since 20.08.2024 [F:arrest_date], 167 days as of 03.02.2025 [F:custody_days] "
               "[A:DLHC-2021-0420#11].")
G_CUSTODY_DICTATED = "The applicant has been in custody since 20.08.2024 [F:arrest_date] [A:DLHC-2021-0420#11]."


def ground(gid: str, factor: Factor, argument: str, *authorities: tuple[str, int]) -> Ground:
    return Ground(id=gid, factor=factor, stance=FactorStance.FAVOURABLE, argument=argument,
                  authorities=[Authority(doc_id=d, para=p) for d, p in authorities])


GROUNDS = {
    "G1": ground("G1", Factor.PARITY_WITH_CO_ACCUSED, G1_ARGUMENT, ("DLHC-2022-1187", 14)),
    "G2": ground("G2", Factor.CHARGE_SHEET_FILED, G2_ARGUMENT, ("SC-2014-0463", 21)),
    "G3": ground("G3", Factor.CUSTODY_PERIOD, G3_ARGUMENT, ("DLHC-2021-0420", 11)),
}


def plan(factor: Factor, tool: str, args: dict[str, Any], slot: str = "authority") -> RetrievalPlan:
    return RetrievalPlan(factor=factor, round=1, budget_left=BudgetLeft(store_calls=6, tokens=9000),
                         steps=[PlanStep(slot=slot, tool=tool, args=args)])


O1_RAISED = Objection(
    id="O1", against="G1", factor="parity_with_co_accused",
    objection="The applicant, unlike Co-accused-1, received the money into his own account.",
    grounds=[ObjectionGround(store="advocacy.objections", doc_id="DLHC-2023-0911", para=6), ObjectionGround(fact="fir")])
O2_RAISED = Objection(id="O2", against="general", factor="witness_tampering",
                      objection="Charges are not framed and the complainant is yet to be examined.",
                      grounds=[ObjectionGround(fact="trial_stage")])
O3_UNGROUNDED = Objection(id="O3", against="G2", factor="gravity_and_punishment",
                          objection="Everyone knows this kind of accused absconds.", grounds=[])
O1_JUDGED = O1_RAISED.model_copy(update={
    "reply": Reply(text="Role comparison is on record [F:co_accused_bail] [A:DLHC-2022-1187#14].",
                   authorities=[Authority(doc_id="DLHC-2022-1187", para=14)], check=ClaimCheck.SUPPORTED),
    "verdict": SparringVerdict.ANSWERED, "reason": "The reply addresses the account point with a cited order."})
O2_JUDGED = O2_RAISED.model_copy(update={"reply": None, "verdict": SparringVerdict.UNANSWERED,
                                         "reason": "No reply was drafted."})


def ada_client(*, grounds: tuple[str, ...] = ("G1", "G2"), redraft: Ground | None = None,
               chat: list[tuple[str, Any]] | None = None, extra_grounds: list[Ground] | None = None) -> ScriptedLLM:
    """The Ada-side client: retrieval plans per factor, drafted grounds (then `redraft` for an incremental re-draft), the
    objections of sparring (raise, judge) and the scripted chat answers. Never strict: unscripted free text is ''."""
    drafted: list[Ground] = [GROUNDS[g] for g in grounds] + list(extra_grounds or [])
    if redraft is not None:
        drafted.append(redraft)
    plans = [plan(Factor.PARITY_WITH_CO_ACCUSED, "search_reasoning",
                  {"factor": "parity_with_co_accused", "section_family": ["BNS 318(4)", "IPC 420"], "before": AS_OF,
                   "outcome": "granted", "k": 10}),
             plan(Factor.CHARGE_SHEET_FILED, "search_reasoning",
                  {"factor": "charge_sheet_filed", "section_family": ["BNS 318(4)", "IPC 420"], "before": AS_OF, "k": 10})]
    return ScriptedLLM(
        by_schema={"RetrievalPlan": Seq(*plans), "Ground": Seq(*drafted),
                   "Objection": Seq(O1_RAISED, O2_RAISED, O3_UNGROUNDED, O1_JUDGED, O2_JUDGED),
                   "Reply": O1_JUDGED.reply},
        by_prompt=list(chat or []), strict=False, default="", where="ada")


def laptop_client() -> ScriptedLLM:
    """The laptop client (Munshi, Peshkar). Tool outputs carry the data; unscripted free text is ''."""
    return ScriptedLLM(strict=False, default="", where="laptop")


def prompt_must_contain(answer: str, *required: str) -> Callable[[str, dict | None], str]:
    """A chat responder that returns `answer` only if the prompt already carries the tool results (`required`), so a
    scripted answer cannot pass unless the evidence reached the model."""

    def respond(prompt: str, schema: dict | None) -> str:
        missing = [r for r in required if r not in prompt]
        assert not missing, f"tool results not in the prompt: {missing}"
        return answer

    return respond


class RecordingLLM(LLMClient):
    """Wraps a real client (the `models`/`gpu` variants) and records prompts like ScriptedLLM does."""

    def __init__(self, inner: LLMClient, where: str) -> None:
        self.inner, self.where, self.prompts = inner, where, []

    def generate(self, prompt: str, max_tokens: int = 1024, temperature: float = 0.0, json_schema: dict | None = None) -> str:
        self.prompts.append(prompt)
        return self.inner.generate(prompt, max_tokens, temperature, json_schema)

    def count_tokens(self, text: str) -> int:
        return self.inner.count_tokens(text)


class AnyPathAsr(FakeAsr):
    """FakeAsr whose transcript does not depend on where the API stored the audio file."""

    def transcribe(self, audio_path: str, lang_hint: str | None = None) -> str:
        return self.transcripts["*"]


# --------------------------------------------------------------------------------------------------------------------
# Event helpers (shapes follow tests/unit/record/_helpers.py)
# --------------------------------------------------------------------------------------------------------------------
def _actor(e: Event) -> str:
    return str(getattr(e.actor, "value", e.actor))


def make_event(case_id: str, kind: EventKind, actor: str, *, tool: str | None = None, inputs: dict | None = None,
               outputs: dict | None = None) -> Event:
    return Event(event_id="", case_id=case_id, ts="", kind=kind, actor=actor, tool=tool, inputs=inputs or {},
                 outputs=outputs or {})


def agent_approvals(events: list[Event]) -> list[Event]:
    """GATE_APPROVED events that were not made by counsel (must always be empty: gates are human)."""
    return [e for e in events if e.kind == EventKind.GATE_APPROVED and _actor(e).lower() != "counsel"]


def export_tool_calls(events: list[Event]) -> list[Event]:
    return [e for e in events if e.kind == EventKind.TOOL_CALL and e.tool == "export"]


def instruction_flags(events: list[Event]) -> list[Event]:
    """Audit notes left when `detect_instruction_like` fired. ASSUMPTION: an event whose outputs carry
    `instruction_like: true` (Munshi's AGENT_MESSAGE for the page)."""
    return [e for e in events if e.outputs.get("instruction_like") is True]


def declined_events(events: list[Event]) -> list[Event]:
    """ASSUMPTION: Munshi's decline is an AGENT_MESSAGE with outputs {declined: true, reason, excluded_from_evaluation}."""
    return [e for e in events if e.kind == EventKind.AGENT_MESSAGE and e.outputs.get("declined") is True]


def dump_events(events: list[Event]) -> str:
    return "\n".join(json.dumps(e.model_dump(mode="json"), ensure_ascii=False) for e in events)


_SHARED_STORES = {StoreName.LAW_STATUTES, StoreName.LAW_CONCORDANCE, StoreName.CASELAW_REASONING, StoreName.CASELAW_CITATIONS,
                  StoreName.CASELAW_SIMILAR, StoreName.ADVOCACY_ARGUMENTS, StoreName.ADVOCACY_OBJECTIONS}


def stores_text(world: CaseWorld, shared: bool) -> str:
    """Every row of the shared stores (law, case law, advocacy) or of the case shelf, as text."""
    parts: list[str] = []
    for name, store in world.stores.items():
        if (name in _SHARED_STORES) != shared:
            continue
        for attr in ("rows", "edges", "events", "chunks"):
            parts += [row.model_dump_json() for row in getattr(store, attr, [])]
        if hasattr(store, "dossier"):
            parts.append(store.dossier().model_dump_json())
    return "\n".join(parts)


# --------------------------------------------------------------------------------------------------------------------
# Safety helpers
# --------------------------------------------------------------------------------------------------------------------
PROBABILITY_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|per\s?cent|percent)|\b0\.\d+\b|\b\d+\s*(?:in|out of)\s*\d+\b", re.IGNORECASE)


def delimiter_markers() -> tuple[str, str]:
    """(opening, closing) marker of `wrap_untrusted`, read off the real function. ASSUMPTION: the first token of the opening
    delimiter and the last token of the closing delimiter do not depend on the source reference."""
    probe = "PROBE-TEXT-0001"
    wrapped = wrap_untrusted(probe, SourceRef(doc="d0", page=1))
    idx = wrapped.index(probe)
    before, after = wrapped[:idx].split(), wrapped[idx + len(probe):].split()
    assert before and after, "wrap_untrusted must put an opening and a closing delimiter around the text"
    return before[0], after[-1]


def occurrences(haystack: str, needle: str) -> list[int]:
    out, start = [], haystack.find(needle)
    while start != -1:
        out.append(start)
        start = haystack.find(needle, start + 1)
    return out


def outside_delimiter(prompt: str, needle: str, open_marker: str, close_marker: str) -> list[int]:
    """Positions of `needle` in `prompt` that are NOT between an opening and its closing marker."""
    bad = []
    for pos in occurrences(prompt, needle):
        last_open, last_close = prompt.rfind(open_marker, 0, pos), prompt.rfind(close_marker, 0, pos)
        if last_open == -1 or last_open < last_close:
            bad.append(pos)
    return bad


def refusal_rate(refused: list[bool]) -> float:
    """Share of requests that had to be refused and were (independent of eval.metrics.safety: it has no such function)."""
    return sum(refused) / len(refused) if refused else 1.0


def leak_rate(leaked: int, checked: int) -> float:
    """Leaked planted-name occurrences per checked artefact (independent of eval.metrics.safety)."""
    return leaked / checked if checked else 0.0


def walk_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(str(k).lower())
            keys |= walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= walk_keys(v)
    return keys


# --------------------------------------------------------------------------------------------------------------------
# The scenario driver
# --------------------------------------------------------------------------------------------------------------------
class Scenario:
    """One case on fakes. Build it inside the test body (not in a fixture) so a not-yet-implemented module fails the test,
    not the fixture setup."""

    def __init__(self, tmp_path: Path, monkeypatch, *, pages: list[FakePage] | None = None, answers: list[str] | None = None,
                 case_id: str = CASE_ID, world: CaseWorld | None = None, toolbox: SystemToolbox | None = None,
                 ada: Any = None, laptop: Any = None, pseudonymiser=None, memory_log: bool = False,
                 real_models: bool = False) -> None:
        self.tmp_path, self.mp, self.case_id = tmp_path, monkeypatch, case_id
        self.data_dir = tmp_path / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("VS_DATA_DIR", str(self.data_dir))
        monkeypatch.setenv("VS_CONFIG_DIR", str(Path(__file__).resolve().parents[2] / "configs"))
        monkeypatch.chdir(tmp_path)
        self.world = world or (toolbox.world if toolbox else build_world())
        self.toolbox = toolbox or SystemToolbox(self.world, pages=pages, answers=answers, pseudonymiser=pseudonymiser)
        self.real_models = real_models
        self.ada: Any = ada or ada_client()
        self.laptop: Any = laptop or laptop_client()
        self.tools: dict[str, Callable[..., Any]] = self.toolbox.tools
        if real_models:
            self._use_real_models()
        install_fake_stores(monkeypatch, self.world.stores)
        self._patch_wiring()
        if memory_log:
            self.log: Any = InMemoryEventLog()
        else:
            from vakeel_sahayak.api import deps  # the shared case record the API and the agents both use

            self.log = deps.get_event_log(case_id)
        self.guard = GateGuard(self.log)
        self.state = CaseGraphState(case_id=case_id)

    # -- wiring -----------------------------------------------------------------------------------------------
    def _use_real_models(self) -> None:
        from vakeel_sahayak.models.factory import get_llm
        from vakeel_sahayak.tools.registry import discover_tools, get_tool

        self.ada = RecordingLLM(get_llm("agents_14b"), "ada")
        self.laptop = RecordingLLM(get_llm("munshi_4b"), "laptop")
        self.tools = {name: get_tool(name) for name in discover_tools()}

    def _patch_everywhere(self, name: str, fn: Callable[..., Any]) -> None:
        for mod_name, mod in list(sys.modules.items()):
            if mod_name.startswith("vakeel_sahayak") and mod is not None and hasattr(mod, name):
                self.mp.setattr(mod, name, fn)

    def _patch_wiring(self) -> None:
        def get_llm(role: str) -> Any:
            return self.ada if role in ADA_ROLES else self.laptop

        def get_tool(name: str) -> Callable[..., Any]:
            return self.tools[name]

        self._patch_everywhere("get_llm", get_llm)
        self._patch_everywhere("get_tool", get_tool)

    def set_asr(self, transcript: str) -> None:
        asr = AnyPathAsr({"*": transcript})
        self._patch_everywhere("get_asr", lambda: asr)

    def client(self):
        """TestClient over `create_app()` (the UI backend), on the same log, stores, models and tools."""
        from fastapi.testclient import TestClient

        from vakeel_sahayak.api.app import create_app

        return TestClient(create_app())

    # -- agents -----------------------------------------------------------------------------------------------
    def ctx(self, name: AgentName):
        return make_context(llm=self.ada if name in ADA_AGENTS else self.laptop, toolbox=self.toolbox, world=self.world,
                            case_id=self.case_id, log=self.log)._replace_tools(self.tools) if False else self._ctx(name)

    def _ctx(self, name: AgentName):
        ctx = make_context(llm=self.ada if name in ADA_AGENTS else self.laptop, toolbox=self.toolbox, world=self.world,
                           case_id=self.case_id, log=self.log)
        ctx.tools = self.tools
        return ctx

    def agent(self, name: AgentName):
        from vakeel_sahayak.agents.registry import get_agent_class

        return get_agent_class(name)(self._ctx(name))

    def run(self, name: AgentName) -> CaseGraphState:
        self.state = self.agent(name).run(self.state)
        return self.state

    def chat(self, question: str):
        """Counsel's chat message answered by Sutradhar (plan §6.4)."""
        return self.agent(AgentName.SUTRADHAR).answer_chat(self.state, question)

    # -- files ------------------------------------------------------------------------------------------------
    def add_upload(self, name: str, content: bytes = b"%PDF-1.4\n% stub\n") -> Path:
        """Put a raw client file where Munshi ingests from (laptop only)."""
        target = self.data_dir / "cases" / self.case_id / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    # -- the record and the gates -----------------------------------------------------------------------------
    def events(self, kind: EventKind | None = None, actor: str | None = None, case_id: str | None = None) -> list[Event]:
        return self.log.read(case_id or self.case_id, kind=kind, actor=actor)

    def seed_record(self, case_id: str | None = None, *, dossier: CaseDossier | None = None,
                    rights: RightsReport | None = None, brief: BailBrief | None = None,
                    sparring: SparringRecord | None = None, ingestion: IngestionReport | None = None,
                    approve_gate1: bool = True) -> None:
        """Write a case record the way the agents would (field writes, timeline, views, gates) without running them."""
        cid = case_id or self.case_id
        dossier = dossier or self.world.dossier
        for fname in type(dossier.fields).model_fields:
            self.log.append(make_event(cid, EventKind.STORE_WRITE, "PESHKAR", tool="extract_dossier",
                                       inputs={"store": "case.facts", "field": fname},
                                       outputs={"tracked": getattr(dossier.fields, fname).model_dump(mode="json")}))
        for ev in self.world.timeline:
            self.log.append(make_event(cid, EventKind.STORE_WRITE, "MUNSHI", tool="file_item",
                                       inputs={"store": "case.timeline"}, outputs={"event": ev.model_dump(mode="json")}))

        def view(name: str, model: Any, actor: str) -> None:
            self.log.append(make_event(cid, EventKind.STORE_WRITE, actor, inputs={"store": "case.views", "view": name},
                                       outputs={"value": model.model_dump(mode="json")}))

        view("rights_report", (rights or self.world.rights).model_copy(update={"case_id": cid}), "PESHKAR")
        if ingestion is not None:
            view("ingestion_report", ingestion.model_copy(update={"case_id": cid}), "MUNSHI")
        self.log.append(make_event(cid, EventKind.GATE_OPENED, "PESHKAR", inputs={"gate": G1.value}))
        if approve_gate1:
            self.log.append(make_event(cid, EventKind.GATE_APPROVED, "counsel",
                                       inputs={"gate": G1.value, "acknowledged": ["antecedents"]},
                                       outputs={"dossier_hash": "h:0a1b"}))
        if brief is not None:
            view("brief", brief.model_copy(update={"case_id": cid}), "VAKEEL")
            view("sparring", (sparring or SparringRecord(case_id=cid)).model_copy(update={"case_id": cid}), "ABHIYOJAK")
            self.log.append(make_event(cid, EventKind.GATE_OPENED, "VAKEEL", inputs={"gate": G2.value}))

    def status(self, gate: GateId, case_id: str | None = None):
        return self.guard.status(case_id or self.case_id, gate)

    def resolve(self, item: str, case_id: str | None = None) -> None:
        """Counsel resolves one Gate 2 checklist item (ASSUMPTION: a USER_ACTION event, see the module docstring)."""
        self.log.append(make_event(case_id or self.case_id, EventKind.USER_ACTION, "counsel",
                                   inputs={"action": "resolve", "item": item}))

    def approve(self, gate: GateId, acknowledged: list[str] | None = None, case_id: str | None = None) -> None:
        cid = case_id or self.case_id
        self.guard.approve(cid, gate, acknowledged=acknowledged or [])
        if gate == G2 and cid == self.case_id:
            self.toolbox.gate2_approved = True

    def clear_and_approve(self, gate: GateId, case_id: str | None = None) -> None:
        """Counsel works through the checklist (acknowledges UNSUPPORTED fields, resolves every NEEDS_REVIEW and UNANSWERED
        item) and approves."""
        cid = case_id or self.case_id
        st = self.status(gate, cid)
        for item in list(st.unresolved_needs_review) + list(st.unresolved_unanswered):
            self.resolve(item, cid)
        self.approve(gate, list(st.unresolved_unsupported), cid)

    def with_case_state(self) -> None:
        """Quick-question mode: the case after Gate 1, without running Munshi and Peshkar."""
        self.seed_record()
        self.state = self.state.model_copy(update={"dossier": self.world.dossier, "rights": self.world.rights,
                                                   "stage": Stage.RIGHTS})

    def through_gate1(self) -> CaseGraphState:
        """Intake, dossier and counsel's Gate 1 approval (acknowledging UNSUPPORTED fields)."""
        self.add_upload("bundle_1.pdf")
        self.run(AgentName.MUNSHI)
        self.run(AgentName.PESHKAR)
        self.clear_and_approve(G1)
        return self.state

    def through_draft(self) -> CaseGraphState:
        """Sutradhar plans, Vakeel drafts, Abhiyojak spars (plan §6.2 step 3)."""
        return self.run(AgentName.SUTRADHAR)

    # -- what the Ada-bound clients saw -----------------------------------------------------------------------
    @property
    def ada_prompts(self) -> list[str]:
        return list(self.ada.prompts)

    @property
    def laptop_prompts(self) -> list[str]:
        return list(self.laptop.prompts)


def clean_brief(case_id: str) -> BailBrief:
    """A brief with nothing left for Gate 2 (all SUPPORTED, no open issue)."""
    g = GROUNDS["G1"].model_copy(update={"check": ClaimCheck.SUPPORTED})
    return BailBrief(case_id=case_id, grounds=[g])


def clean_sparring(case_id: str) -> SparringRecord:
    return SparringRecord(case_id=case_id, rounds=2, objections=[O1_JUDGED])


def ground_ids(brief: BailBrief) -> list[str]:
    return [g.id for g in brief.grounds]
