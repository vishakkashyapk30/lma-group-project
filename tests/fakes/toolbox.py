"""A fake tool registry: callables with the real tool signatures, backed by the in-memory stores and canned data.

`FakeToolbox(world).tools` is what tests put in `AgentContext.tools`. It records every call (`.calls`), can inject
failures (`inject_error`), and simulates the gated `export` tool (`.exports`, raises PermissionError before Gate 2).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from tests.fakes.data import CaseWorld, PLANTED_NAMES
from tests.fakes.models import FakeNli, FakeTranslator
from vakeel_sahayak.ingestion.signals import PageSignals
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.common import SourceRef
from vakeel_sahayak.schemas.enums import (
    DocumentType,
    ExportFormat,
    Factor,
    GateId,
    StoreName,
)
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry
from vakeel_sahayak.schemas.store_rows import CaseChunk, TimelineEvent
from vakeel_sahayak.tools.types import (
    ApprovalRequest,
    ClaimCheckResult,
    DateCalcResult,
    FileItemResult,
    OcrResult,
    ScriptInfo,
    SpanCheckResult,
    TextLayerResult,
    TranscriptResult,
)


@dataclass
class FakePage:
    """One scripted page of a constructed bundle (what the page 'really' contains and how each route would read it)."""

    text: str
    signals: PageSignals = field(default_factory=lambda: PageSignals(has_text_layer=True, text_coverage=0.95, dict_word_share=0.95))
    ocr_text: str | None = None
    ocr_conf: float | None = None
    vision_text: str | None = None
    lang: str = "en"
    doc_type: DocumentType = DocumentType.OTHER


@dataclass
class ToolCall:
    name: str
    kwargs: dict[str, Any]


PSEUDONYM_ALIASES = {
    "Ramesh Kumar Yadav": "Accused-1",
    "Sunita Devi Sharma": "Complainant-1",
    "Mohd. Irfan Qureshi": "Co-accused-1",
    "Anil Pratap Singh": "IO-1",
}


class FakeToolbox:
    def __init__(self, world: CaseWorld, pages: list[FakePage] | None = None, answers: list[str] | None = None,
                 gate2_approved: bool = False) -> None:
        self.world = world
        self.pages = pages or []
        self.answers = list(answers or [])
        self.gate2_approved = gate2_approved
        self.calls: list[ToolCall] = []
        self.questions: list[list[str]] = []
        self.exports: list[tuple[str, ExportFormat]] = []
        self._errors: dict[str, list[Exception]] = {}
        self.nli = FakeNli()
        self.translator = FakeTranslator()
        self.tools: dict[str, Callable[..., Any]] = {}
        for name in dir(self):
            if name.startswith("t_"):
                self.tools[name[2:]] = self._wrap(name[2:], getattr(self, name))

    # -- plumbing ----------------------------------------------------------------------------------------------
    def _wrap(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def call(*args: Any, **kwargs: Any) -> Any:
            self.calls.append(ToolCall(name, kwargs))
            if self._errors.get(name):
                raise self._errors[name].pop(0)
            return fn(*args, **kwargs)

        call.__name__ = name
        return call

    def inject_error(self, tool: str, exc: Exception, times: int = 1) -> None:
        """Make the next `times` calls of `tool` raise `exc` (OCR crash, store timeout, malformed date: plan §15.8)."""
        self._errors.setdefault(tool, []).extend([exc] * times)

    def count(self, tool: str) -> int:
        return sum(1 for c in self.calls if c.name == tool)

    def store_calls(self) -> int:
        return sum(len(s.calls) for s in self.world.stores.values())

    def _store(self, name: StoreName) -> Any:
        return self.world.stores[name]

    # -- intake ------------------------------------------------------------------------------------------------
    def _page(self, page: int) -> FakePage:
        return self.pages[page - 1]

    def t_inspect_page(self, file_path: str, page: int) -> PageSignals:
        return self._page(page).signals

    def t_read_text_layer(self, file_path: str, page: int) -> TextLayerResult:
        p = self._page(page)
        return TextLayerResult(text=p.text if p.signals.has_text_layer else "")

    def t_parse_layout(self, file_path: str, page: int):
        from vakeel_sahayak.tools.types import LayoutResult

        return LayoutResult(text=self._page(page).text)

    def t_clean_image(self, image: bytes, ops: list[str] | None = None) -> bytes:
        return image

    def t_ocr_page(self, file_path: str, page: int, lang: str = "eng") -> OcrResult:
        p = self._page(page)
        return OcrResult(text=p.ocr_text or "", mean_conf=p.ocr_conf or 0.0, lang=lang)

    def t_vision_read_page(self, file_path: str, page: int) -> str:
        return self._page(page).vision_text or ""

    def t_detect_script(self, text: str | None = None, image: bytes | None = None) -> ScriptInfo:
        dev = sum("ऀ" <= c <= "ॿ" for c in (text or ""))
        return ScriptInfo(script="devanagari" if dev > len(text or "") / 2 else "latin", confidence=0.9)

    def t_translate(self, text: str, src: str = "hi", tgt: str = "en") -> str:
        return self.translator.translate(text, src, tgt)

    def t_transcribe(self, audio_path: str, lang_hint: str | None = None) -> TranscriptResult:
        return TranscriptResult(text=self.answers.pop(0) if self.answers else "", lang=lang_hint)

    def t_split_bundle(self, file_path: str) -> list[DocumentEntry]:
        docs: list[DocumentEntry] = []
        start = 1
        for i in range(1, len(self.pages) + 1):
            last = i == len(self.pages) or self._page(i + 1).doc_type != self._page(i).doc_type
            if last:
                docs.append(DocumentEntry(doc_id=f"d{len(docs) + 1}", type=self._page(i).doc_type, pages=[start, i],
                                          lang=self._page(i).lang))
                start = i + 1
        return docs

    def t_classify_document(self, file_path: str, pages: list[int]):
        return self._page(pages[0]).doc_type, 0.94

    def t_pseudonymise(self, text: str, case_id: str) -> str:
        for name, alias in PSEUDONYM_ALIASES.items():
            text = text.replace(name, alias)
        return text

    def t_file_item(self, store: StoreName, item: dict[str, Any], source: SourceRef) -> FileItemResult:
        store = StoreName(store)
        if store == StoreName.CASE_TIMELINE:
            self._store(store).add_event(TimelineEvent(event_id=item["event_id"], date=item["date"], label=item["label"], source=source))
        elif store == StoreName.CASE_DOCS:
            self._store(store).add_chunks([CaseChunk.model_validate(item)])
        return FileItemResult(store=store, item_id=str(item.get("event_id") or item.get("chunk_id") or "item"))

    def t_search_pages(self, case_id: str, query: str, k: int = 5) -> list[dict[str, Any]]:
        hits = [{"page": i, "text": p.text} for i, p in enumerate(self.pages, start=1) if query.lower() in p.text.lower()]
        return hits[:k]

    def t_ask_user(self, questions: list[str], case_id: str) -> list[str]:
        self.questions.append(list(questions))
        return [self.answers.pop(0) if self.answers else "" for _ in questions]

    # -- dossier and rights ------------------------------------------------------------------------------------
    def t_extract_dossier(self, case_id: str, fields: list[str] | None = None):
        return self.world.dossier

    def t_span_check(self, value: Any, quote: str) -> SpanCheckResult:
        score = self.nli.entails(quote, str(value))
        return SpanCheckResult(supported=score >= 0.5, score=score, quote=quote)

    def t_rights_check(self, case_id: str, as_of: str | None = None):
        return self.world.rights

    def t_diff_case_state(self, case_id: str, since_hash: str | None = None) -> ChangeSet:
        return ChangeSet(case_id=case_id, trigger="new_document")

    def t_date_calc(self, start: str, end: str, rule: str = "inclusive_day_1") -> DateCalcResult:
        d = (date.fromisoformat(end) - date.fromisoformat(start)).days
        r = rule.lower()
        return DateCalcResult(value=d + 1 if r == "inclusive_day_1" else d, rule=rule, start=start, end=end)

    # -- case shelf --------------------------------------------------------------------------------------------
    def t_get_timeline(self, case_id: str, start: str | None = None, end: str | None = None):
        return self._store(StoreName.CASE_TIMELINE).get(start, end)

    def t_get_fact(self, case_id: str, field: str):
        return self._store(StoreName.CASE_FACTS).get(field)

    def t_search_case_docs(self, case_id: str = "", query: str = "", doc_types: list[DocumentType] | None = None, k: int = 5):
        return self._store(StoreName.CASE_DOCS).search(query, doc_types, k)

    # -- law ---------------------------------------------------------------------------------------------------
    def t_get_statute(self, code: str, section: str):
        return self._store(StoreName.LAW_STATUTES).get(code, section)

    def t_search_statutes(self, query: str, code: str | None = None, k: int = 5):
        return self._store(StoreName.LAW_STATUTES).search(query, code, k)

    def t_map_section(self, code: str, section: str, offence_date: str):
        return self._store(StoreName.LAW_CONCORDANCE).map_section(code, section, offence_date)

    def t_transfer_check(self, old_ref: str, new_ref: str):
        return self._store(StoreName.LAW_CONCORDANCE).transfer_flag(old_ref, new_ref)

    # -- case law and advocacy ---------------------------------------------------------------------------------
    def t_search_reasoning(self, query: str, factor: Factor | None = None, section_family: list[str] | None = None,
                           before: str | None = None, outcome: str | None = None, court: str | None = None, k: int = 10):
        return self._store(StoreName.CASELAW_REASONING).search(query, factor, section_family, before, outcome, court, k=k)

    def t_get_paragraph(self, doc_id: str, para: int):
        return self._store(StoreName.CASELAW_REASONING).get_paragraph(doc_id, para)

    def t_citations(self, doc_ids: list[str], want: list[str] | None = None) -> dict[str, Any]:
        cs = self._store(StoreName.CASELAW_CITATIONS)
        return {d: {"cited_by": cs.cited_by(d), "cites": cs.cites(d), "authority": cs.authority_score(d),
                    "sc_root": cs.sc_root(d), "good_law": cs.good_law(d)} for d in doc_ids}

    def t_good_law_check(self, doc_id: str, as_of: str | None = None):
        return self._store(StoreName.CASELAW_CITATIONS).good_law(doc_id, as_of)

    def t_similar_orders(self, facts_text: str, signature=None, before: str | None = None, k: int = 10):
        return self._store(StoreName.CASELAW_SIMILAR).similar(facts_text, signature, before, k)

    def t_search_arguments(self, query: str, factor=None, section_family=None, before=None, k: int = 10):
        return self._store(StoreName.ADVOCACY_ARGUMENTS).search(query, factor, section_family, None, before, k)

    def t_search_objections(self, query: str, factor=None, section_family=None, before=None, k: int = 10):
        return self._store(StoreName.ADVOCACY_OBJECTIONS).search(query, factor, section_family, before, k)

    # -- drafting and gates ------------------------------------------------------------------------------------
    def t_check_claim(self, claim: str, refs: list[str] | None = None) -> ClaimCheckResult:
        rs = self._store(StoreName.CASELAW_REASONING)
        bad, best = [], 0.0
        for ref in refs or []:
            if ref.startswith("A:"):
                doc, _, para = ref[2:].partition("#")
                try:
                    best = max(best, self.nli.entails(rs.get_paragraph(doc, int(para)).text, claim))
                except KeyError:
                    bad.append(ref)
        return ClaimCheckResult(supported=not bad and (best >= 0.5 or not refs), authority_support=best or None,
                                unretrieved_citations=bad)

    def t_render_citation(self, doc_id: str, para: int | None = None) -> str:
        rs = self._store(StoreName.CASELAW_REASONING)
        for r in rs.rows:
            if r.doc_id == doc_id and (para is None or r.para == para):
                return f"{r.doc_id}, {r.court} ({r.date[:4]}), para {r.para}"
        raise KeyError(f"unknown doc_id {doc_id}")

    def t_assemble_application(self, case_id: str) -> str:
        return f"/tmp/{case_id}_application.docx"

    def t_request_approval(self, case_id: str, gate: GateId) -> ApprovalRequest:
        return ApprovalRequest(gate=GateId(gate), checklist_open=True)

    def t_export(self, case_id: str, format: ExportFormat) -> list[str]:
        if not self.gate2_approved:
            raise PermissionError("export blocked: Gate 2 not approved")
        self.exports.append((case_id, ExportFormat(format)))
        return [f"/tmp/{case_id}.{ExportFormat(format).value.lower()}"]


def leaked_names(texts: list[str], names: list[str] | None = None) -> list[str]:
    """Planted names found in any of the texts (independent of `privacy.leak_check`, which is under test)."""
    names = names or PLANTED_NAMES
    return sorted({n for n in names for t in texts if n in t})
