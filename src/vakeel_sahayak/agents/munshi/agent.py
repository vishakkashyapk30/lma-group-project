"""Munshi agent (plan §3.2). Intake agent: survey, categorise, file, check gaps, check conflicts, stop and report (plan §4.3). Runs on the laptop.

The loop is deterministic: the ladder, the splitter, the classifier, the filer, the gap checks and the conflict check are
rules over the ingestion modules, and a language model is consulted only for a low-confidence document label
(`decisions.LlmAdvisor`). Munshi is callable on its own, without the case graph (Phase 4 wires it in):

    munshi = MunshiAgent(case_id="case-0007", log=EventLog(...))
    report = munshi.ingest(["bundle_1.pdf"])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.agents.base import AgentContext, BaseAgent
from vakeel_sahayak.agents.munshi.decisions import LlmAdvisor
from vakeel_sahayak.agents.munshi.toolkit import ToolFiler, route_page_with_tools
from vakeel_sahayak.ingestion.checklist import ITEM_NAMES, QUESTION_PRIORITY, missing_items
from vakeel_sahayak.ingestion.classify import tag_paragraph
from vakeel_sahayak.ingestion.conflicts import DOSSIER_FIELD, detect_conflicts, mark_ambiguous
from vakeel_sahayak.ingestion.events import ExtractedEvent, extract_events
from vakeel_sahayak.ingestion.filing import MAX_PERSONAL_PER_DOC, Filer
from vakeel_sahayak.ingestion.gaps import ADOPT_AS, resolve_gap
from vakeel_sahayak.ingestion.hindi import lang_of, normalise_for_extraction, translate_keeping_original
from vakeel_sahayak.ingestion.kinds import file_kind
from vakeel_sahayak.ingestion.pageindex import IndexedPage, PageIndex, index_path
from vakeel_sahayak.ingestion.pipeline import (
    DocRead,
    FileRead,
    PageRead,
    page_read,
    read_file,
    read_page,
    split_and_label,
)
from vakeel_sahayak.ingestion.questions import (
    QuestionBook,
    put_to_counsel,
    question_limit,
    questions_used_this_round,
    record_questions,
    unreadable_question,
)
from vakeel_sahayak.ingestion.report import build_report
from vakeel_sahayak.ingestion.thresholds import load_thresholds, threshold
from vakeel_sahayak.ingestion.voice import delete_audio, readback, readback_question, transcribe_dictation
from vakeel_sahayak.models.base import AsrClient, LLMClient, ModelUnavailable
from vakeel_sahayak.models.sarvam.policy import DataClass, sarvam_scope
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.pipelines.order_facts import charge_sheet_status, co_accused_outcome
from vakeel_sahayak.pipelines.section_extract import extract_sections
from vakeel_sahayak.pipelines.text_utils import paragraph_blocks, split_sentences
from vakeel_sahayak.privacy.sensitive_matters import is_declined_matter
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.enums import (
    AgentName,
    DocumentType,
    EventKind,
    FieldStatus,
    InfoKind,
    ParseRoute,
    StoreName,
)
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.ids import check_case_id
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, FiledCounts, Gap, IngestionReport, PageRoute
from vakeel_sahayak.tools.base import ToolError

_TEXT_ROUTES = {ParseRoute.TEXT_LAYER, ParseRoute.LAYOUT}
_DIRECT_FIELDS = ("arrest_date", "offence_date", "first_remand")  # single-string dossier fields a dated event can fill
_LABEL_FOR_SENTENCES = {DocumentType.CUSTODY_CERTIFICATE: "custody certificate", DocumentType.MEDICAL_RECORD: "medical record"}


@dataclass
class DictationResult:
    """What a dictated voice note produced (plan §4.5)."""

    transcript: str  # pseudonymised
    readback: list[str]
    question: str | None
    filed: FiledCounts
    audio_kept: bool


@dataclass
class _Run:
    """Working state of one ingestion run (raw page text lives here only until it is pseudonymised and filed)."""

    reads: list[FileRead] = field(default_factory=list)
    docs: list[DocRead] = field(default_factory=list)
    entries: list[DocumentEntry] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    stated: set[str] = field(default_factory=set)
    declined: str | None = None
    revisions: dict[str, int] = field(default_factory=dict)
    book: QuestionBook = field(default_factory=QuestionBook)
    gap_records: list[dict[str, Any]] = field(default_factory=list)  # one per missing item handled (S7 signals, kept for either policy)


class MunshiAgent(BaseAgent):
    """Intake agent: survey, categorise, file, check gaps, check conflicts, stop and report (plan §4.3). Runs on the laptop."""

    NAME = AgentName.MUNSHI
    ROLE_MODEL = "munshi_4b"

    def __init__(
        self,
        ctx: AgentContext | None = None,
        *,
        case_id: str | None = None,
        log: EventLog | None = None,
        switches: Switches | None = None,
        thresholds: dict[str, float] | None = None,
        llm: LLMClient | None = None,
        asr: AsrClient | None = None,
        case_path: str | None = None,
        cases_dir: str | None = None,
        max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
    ) -> None:
        """Create Munshi, from an AgentContext or from plain arguments (the graph is optional).

        Args:
            ctx: the injected context (Phase 4); its case id, log, switches and LLM are used
            case_id: the case (default: taken from the state passed to `run`)
            log: the case's event log (default: the configured per-case log)
            switches: ablation switches (`munshi_no_bundle_split`, `munshi_no_gap_check`)
            thresholds: dev-tuned values (default: `load_thresholds()`)
            llm: the `munshi_4b` client, used only as the fallback document classifier
            asr: speech client for dictation (default: the configured one)
            case_path: where the case stores live (a folder or ':memory:'); default: the cases folder
            cases_dir: cases folder for the event log, the alias map and the page index
            max_route: ladder cap (baselines P1-P3)
        """
        self.ctx = ctx
        self.tooled = ctx is not None  # with a context, the steps go through the registered tools (plan §4.3)
        self.tools = ctx.tools if ctx else {}
        self.budgets = ctx.budgets if ctx else None
        self.config = ctx.config if ctx else None
        self.nli = ctx.nli if ctx else None
        self.case_id = case_id or (ctx.case_id if ctx else None)
        self.log = log or (ctx.log if ctx else None)
        self.switches = switches or (ctx.switches if ctx else Switches())
        self.llm = llm or (ctx.llm if ctx else None)
        self.thresholds = thresholds if thresholds is not None else load_thresholds(config=ctx.config if ctx else None)
        self.asr, self.case_path, self.cases_dir, self.max_route = asr, case_path, cases_dir, max_route
        self.files: list[str] = []
        self.answers: list[str] = []
        self._filer: Filer | None = None
        self._index: PageIndex | None = None
        self._run: _Run = _Run()
        self._voice_no = 1
        self._alias = "file-1"

    # ---------------------------------------------------------------- plumbing

    def _sarvam_scope(self, data: DataClass, purpose: str):  # noqa: ANN202
        """Declare to the Sarvam policy what the enclosed calls carry (no effect while Sarvam is off; plan §16)."""
        return sarvam_scope(data, case_id=str(self.case_id), event_log=self.log, purpose=purpose)

    def _bind(self, case_id: str) -> None:
        """Fix the case id and open its log, alias map, stores and page index on first use."""
        if self.case_id and self.case_id != case_id and self._filer is not None:
            raise ValueError(f"this Munshi works on {self.case_id}, not {case_id}")
        self.case_id = check_case_id(case_id)
        if self.log is None:
            self.log = EventLog.for_case(case_id, self.cases_dir)
        if self._filer is None:
            if self.tooled:
                self._sync_runtime()  # the tools read the case's log and current case from the runtime
                self._filer = ToolFiler(case_id, self.log, cases_dir=self.cases_dir, sink=self._file_item, pseudonymise=self._pseudonymise)
            else:
                self._filer = Filer(case_id, self.log, case_path=self.case_path, cases_dir=self.cases_dir)
        if self._index is None:
            self._index = PageIndex.load(index_path(case_id, self.cases_dir))

    def _file_item(self, store: StoreName, item: dict[str, Any], source: SourceRef) -> Any:
        """File one pseudonymised item through the `file_item` tool (plan §4.3 step 3)."""
        return self.call_tool("file_item", store=store, item=item, source=source)

    def _pseudonymise(self, text: str) -> str:
        """The `pseudonymise` tool over text the alias map has already cleaned (unlogged: its input is still client text)."""
        got = self._raw_tool("pseudonymise", text=text, case_id=self.case_id)
        return got if isinstance(got, str) else text

    def _raw_tool(self, name: str, **kwargs: Any) -> Any:
        """Call a page-reading tool with the agent's permission but without logging its result.

        Page reads return client text before it is pseudonymised and the log holds pseudonymised text only (plan §16),
        so these calls bypass `call_tool`'s TOOL_RESULT; the route of each page is logged by `_log_page` instead.

        Returns:
            The tool's result, or a ToolError.

        Raises:
            ToolPermissionError: Munshi may not call this tool.
        """
        from vakeel_sahayak.tools.registry import check_permission, get_tool

        try:
            check_permission(self.NAME, name)
        except Exception as exc:  # noqa: BLE001 - logged like call_tool does, then raised
            self.error("permission_denied", str(exc), tool=name)
            raise
        try:
            return (self.tools.get(name) or get_tool(name))(**kwargs)
        except Exception as exc:  # noqa: BLE001 - a crashing tool is an error the ladder moves past (plan §15.8)
            return ToolError(tool=name, kind="tool_failed", message=type(exc).__name__, retryable=True)

    def _read_page(self, path: str, page: int, min_route: ParseRoute | None = None) -> PageRead | ToolError:
        """Route one page: through the tools when Munshi has a context, else straight through the ladder. P7 (`munshi_image_only`): every page starts at the vision model."""
        min_route = min_route or self._floor()
        if not self.tooled:
            return read_page(path, page, self.thresholds, self.max_route, min_route=min_route, guard=self.defences().guard, keep_weak=self.switches.munshi_keep_weak_text)
        out = route_page_with_tools(self._raw_tool, path, page, self.thresholds, self.max_route, min_route, self.switches.munshi_keep_weak_text)
        if isinstance(out, ToolError):
            return out
        return page_read(path, page, out, self.defences().guard)

    def _floor(self) -> ParseRoute | None:
        """The weakest rung every page may start at: the vision model under P7 `munshi_image_only` (no text layer, no OCR), else no floor."""
        return ParseRoute.VISION if self.switches.munshi_image_only else None

    def image_only_signals(self) -> dict[str, Any]:
        """P7 signals: pages read, pages that went to the vision model, pages no route could read (counts over this run's surveyed pages)."""
        pages = [p for r in self._run.reads for p in r.pages]
        vision = [p for p in pages if any(step.split(":")[0] == "vision" for step in p.outcome.log)]
        return {"pages": len(pages), "vision_pages": len(vision), "unreadable": sum(1 for p in pages if p.unreadable), "image_only": self.switches.munshi_image_only}

    def _read_file_with_tools(self, path: str) -> FileRead:
        """Survey a file page by page through the tools; the first page `inspect_page` refuses ends the file."""
        name, pages = Path(path).name, []
        while True:
            read = self._read_page(path, len(pages) + 1)
            if isinstance(read, ToolError):
                if pages:
                    break
                kind = "unavailable" if read.kind == "model_unavailable" else "unsupported" if read.kind == "unsupported" else "broken"
                return FileRead(path, name, None, error=read.message, error_kind=kind)
            self._log_page(read)
            pages.append(read)
        return FileRead(path, name, None, pages)

    @property
    def filer(self) -> Filer:
        """The filer of the bound case."""
        assert self._filer is not None, "call run(), ingest() or dictate() first"
        return self._filer

    @property
    def index(self) -> PageIndex:
        """The case's page index."""
        assert self._index is not None
        return self._index

    def close(self) -> None:
        """Close the case stores and save the alias map and the page index."""
        if self._filer is not None:
            self._filer.save_map()
            self._filer.close()
            self._filer = None
        if self._index is not None and self.case_id and self._run.declined is None:
            self._index.save(index_path(self.case_id, self.cases_dir))

    def emit(self, kind: EventKind, payload: dict[str, Any]) -> Event:
        """Append an event to the log.

        Args:
            kind: see behaviour
            payload: keys `tool`, `inputs`, `outputs` and `sources` are used; the log holds pseudonymised text only

        Returns:
            The event.
        """
        assert self.log is not None and self.case_id
        return self.log.append(
            Event(
                event_id="",
                case_id=self.case_id,
                ts="",
                kind=kind,
                actor=self.NAME,
                tool=payload.get("tool"),
                inputs=payload.get("inputs", {}),
                outputs=payload.get("outputs", {}),
                sources=payload.get("sources", []),
            )
        )

    def _logname(self, name: str) -> str:
        """A file name safe for the log and the report: names the alias map knows are replaced (file names are not scanned for new names)."""
        spaced = name.replace("_", " ")
        cleaned = self.filer.clean(spaced) if self._filer is not None else spaced
        return name if cleaned == spaced else cleaned.replace(" ", "_")

    def add_files(self, paths: list[str]) -> None:
        """Queue files for the next run."""
        self.files.extend(str(p) for p in paths)

    def _inbox(self) -> list[str]:
        """Files counsel has put in the case's inbox folder and Munshi has not read yet."""
        from vakeel_sahayak.config import load_config

        folder = Path(self.cases_dir or load_config().paths.cases_dir) / str(self.case_id) / "inbox"
        seen = {p.file for p in self.index.pages}
        return sorted(str(p) for p in folder.glob("*") if p.is_file() and self._logname(p.name) not in seen) if folder.is_dir() else []

    # ---------------------------------------------------------------- the loop

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Munshi's full job for the current graph state.

        Reads the files added with `add_files`, or else the files in the case's inbox folder, and puts the
        IngestionReport on the state. The stage is left for the graph to advance.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        self._bind(state.case_id)
        files = self.files or self._inbox()
        report = self.ingest(files, state)
        out = self._with_injection(state.model_copy(update={"ingestion": report}))
        if self.switches.munshi_image_only:
            out = out.model_copy(update={"variant_signals": {**out.variant_signals, "munshi": {**out.variant_signals.get("munshi", {}), "image_only": self.image_only_signals()}}})
        if self.switches.munshi_gap_policy == "hierarchy":
            out = out.model_copy(update={"variant_signals": {**out.variant_signals, "munshi": {**out.variant_signals.get("munshi", {}), "gaps": self.gap_signals()}}})
        return out

    def ingest(self, files: list[str] | None = None, state: CaseGraphState | None = None) -> IngestionReport:
        """Survey, categorise, file, check gaps, check conflicts, stop and report, for one or more files.

        Args:
            files: paths (default: the queued files)
            state: the graph state, or None when Munshi runs on its own (then `case_id` must be set)

        Returns:
            IngestionReport; the file name is the files' names joined by ', '.
        """
        if state is None and not self.case_id:
            raise ValueError("Munshi needs a case_id (constructor argument or a graph state)")
        state = state or CaseGraphState(case_id=str(self.case_id))
        self._bind(state.case_id)
        if files is not None:
            self.files = list(files)
        self._run = _Run(book=QuestionBook(limit=question_limit(), used=questions_used_this_round(self.log, state.case_id)))  # type: ignore[arg-type]
        try:
            self.survey(state)
            self.categorise(state)
            if self._run.declined is None:
                self.file_items(state)
                self.check_gaps(state)
                self.check_conflicts(state)
            return self.report(state)
        finally:
            self.close()

    def survey(self, state: CaseGraphState) -> list[PageRoute]:
        """Compute cheap signals for every page and run the cheapest acceptable route (plan §4.3 step 1).

        Args:
            state: see behaviour

        Returns:
            Page routes.
        """
        self._bind(state.case_id)
        routes: list[PageRoute] = []
        paths = self.files
        if self.tooled and not paths and state.ingestion and state.ingestion.file and not state.ingestion.documents:
            paths = [state.ingestion.file]  # a context without queued files: the file the state names
        for number, path in enumerate(paths, start=1):
            self._alias = f"file-{number}{Path(path).suffix.lower()}"  # before names are learned the log names files by number
            try:
                with self._sarvam_scope(DataClass.CLIENT_RAW, "munshi.read_file"):  # raw pages: Sarvam only with counsel's consent
                    if self.tooled:
                        read = self._read_file_with_tools(path)
                    else:
                        read = read_file(path, self.thresholds, self.max_route, on_page=self._log_page, guard=self.defences().guard, min_route=self._floor(), keep_weak=self.switches.munshi_keep_weak_text)
            except ModelUnavailable as exc:
                read = FileRead(path, Path(path).name, file_kind(path), error=str(exc), error_kind="unavailable")
            if read.error:
                self.emit(EventKind.ERROR, {"tool": "read_file", "inputs": {"file": self._alias}, "outputs": {"error": read.error, "kind": read.error_kind}})
            self._run.reads.append(read)
            routes.extend(p.page_route() for p in read.pages)
            _, tally = self._defence_state()  # S17 signals: lines the guard kept out of the extraction view, or would have (arm no_guard)
            tally.lines_dropped += sum(len(p.flagged_lines) for p in read.pages)
            tally.missed += sum(len(p.missed_lines) for p in read.pages)
        if self.switches.munshi_image_only:  # P7: the cost reference of the RQ2 comparison; the default path logs nothing extra
            self.emit(EventKind.AGENT_MESSAGE, {"tool": "image_only", "outputs": {"type": "image_only", **self.image_only_signals()}})
        return routes

    def _log_page(self, read: PageRead) -> None:
        """One TOOL_CALL and one TOOL_RESULT per page: the route log for the UI badges. No page text is logged."""
        inputs = {"file": self._alias, "page": read.page}
        self.emit(EventKind.TOOL_CALL, {"tool": "route_page", "inputs": inputs})
        sig = read.outcome.signals
        self.emit(
            EventKind.TOOL_RESULT,
            {
                "tool": "route_page",
                "inputs": inputs,
                "outputs": {
                    "route": read.outcome.route.value,
                    "log": read.outcome.log,
                    "status": read.outcome.status.value,
                    "kind": read.outcome.kind.value if read.outcome.kind else None,
                    "ocr_conf": read.outcome.ocr_conf,
                    "chars": len(read.raw),
                    "signals": sig.model_dump(mode="json") if sig else None,
                },
            },
        )
        if read.flagged_lines:
            self.emit(
                EventKind.AGENT_MESSAGE,
                {
                    "tool": "injection_guard",
                    "inputs": inputs,
                    "outputs": {"instruction_like_lines": len(read.flagged_lines), "action": "kept as data, never acted on"},
                },
            )

    def categorise(self, state: CaseGraphState) -> list[DocumentEntry]:
        """Split bundles, label documents, tag paragraphs by information kind (step 2).

        Also the sensitive-matter check (plan §16): if the charged sections or the documents show a sexual-offence,
        POCSO or juvenile matter, the matter is declined, logged, and nothing is filed.

        Args:
            state: see behaviour

        Returns:
            Documents (empty when the matter is declined).
        """
        self._bind(state.case_id)
        run, classifier = self._run, (LlmAdvisor(self.llm, spotlight=self.defences().spotlighting) if self.llm is not None else None)
        counter = self._next_doc_number()
        for read in run.reads:
            docs = self._docs_with_tools(read, classifier) if self.tooled else None
            if docs is None:
                docs = split_and_label(read, self.thresholds, split=not self.switches.munshi_no_bundle_split, fallback=classifier)
            for doc in docs:
                doc.doc_id = f"d{counter}"
                counter += 1
                run.docs.append(doc)
        self._check_sensitive()
        if run.declined is not None:
            run.entries = []
            return []
        self._refresh_entries()
        return run.entries

    def _docs_with_tools(self, read: FileRead, classifier: LlmAdvisor | None) -> list[DocRead] | None:
        """The documents of a surveyed file from `split_bundle` (or `classify_document` for the whole file under P6).

        Returns:
            Documents, or None when the tool gave nothing usable (the caller splits and labels locally).
        """
        n = len(read.pages)
        if not n:
            return []
        if self.switches.munshi_no_bundle_split:
            got = self.call_tool("classify_document", file_path=read.path, pages=list(range(1, n + 1)))
            doc_type, confidence = (DocumentType.OTHER, 0.3) if isinstance(got, ToolError) else (DocumentType(got[0]), float(got[1]))
            return [DocRead("", read, doc_type, confidence, 1, n, read.pages)]
        entries = self.call_tool("split_bundle", file_path=read.path)
        ranges = [] if isinstance(entries, ToolError) else [tuple(e.pages) for e in entries]
        if not ranges or ranges[0][0] != 1 or ranges[-1][1] != n or any(b[0] != a[1] + 1 for a, b in zip(ranges, ranges[1:], strict=False)):
            return None  # the tool's ranges do not cover the pages read
        docs = []
        for entry in entries:  # type: ignore[union-attr]
            first, last = entry.pages
            doc_type, confidence = entry.type, entry.type_confidence if entry.type_confidence is not None else 0.5
            pages = read.pages[first - 1 : last]
            opening = next((p.raw for p in pages if p.raw.strip()), "")
            if classifier is not None and confidence < threshold(self.thresholds, "doc_type_conf_min"):
                guess = classifier(opening[:2000])  # the language model only when the tool was unsure (as label_document does)
                if guess is not None and guess[1] > confidence:
                    doc_type, confidence = DocumentType(guess[0]), float(guess[1])
            docs.append(DocRead("", read, doc_type, confidence, first, last, pages))
        return docs

    def _refresh_entries(self) -> None:
        """Rebuild the report's document entries from the documents as they stand (types, languages, page routes)."""
        self._run.entries = [
            DocumentEntry(
                doc_id=d.doc_id,
                type=d.doc_type,
                pages=[d.first, d.last],
                lang=d.lang,
                type_confidence=d.confidence,
                page_routes=[p.page_route() for p in d.pages],
            )
            for d in self._run.docs
        ]

    def _next_doc_number(self) -> int:
        """Next free document number, continuing after documents already in the page index."""
        used = [int(p.doc_id[1:]) for p in self.index.pages if p.doc_id and p.doc_id[1:].isdigit()]
        return max(used, default=0) + 1

    def _check_sensitive(self) -> None:
        """Decline sexual-offence, POCSO and juvenile matters at intake (plan §16): check sections and document cues."""
        texts = [normalise_for_extraction(p.raw) for d in self._run.docs for p in d.pages]
        sections = [s for t in texts for s in extract_sections(t)]
        cues = [t[:300].replace("\n", " ") for t in texts]  # titles and opening lines catch 'Juvenile Justice Board' and the like
        declined, reason = is_declined_matter(sections, [*(d.doc_type.value for d in self._run.docs), *cues])
        if declined:
            self._run.declined = reason
            self.emit(EventKind.AGENT_MESSAGE, {"tool": "sensitive_matters", "outputs": {"declined": True, "reason": reason}})

    def file_items(self, state: CaseGraphState) -> FiledCounts:
        """Write items to the case shelf with sources; pseudonymise first (step 3).

        Args:
            state: see behaviour

        Returns:
            Counts.
        """
        self._bind(state.case_id)
        if self._run.declined is not None:
            return self.filer.counts
        self.filer.learn([p.raw for d in self._run.docs for p in d.pages if p.raw.strip()])  # names first, so alias numbering is stable
        for doc in self._run.docs:
            self._file_doc(doc)
        self.filer.save_map()
        self._refresh_entries()  # the pages now carry their translation notes
        return self.filer.counts

    # ---------------------------------------------------------------- filing one document

    @staticmethod
    def _route_label(read: PageRead) -> str:
        """The route that gave the page's text, for the source: 'text_layer', 'ocr: surya-hi', 'vision: qwen3-vl'."""
        wanted = read.outcome.route.value
        return next((e for e in reversed(read.outcome.log) if e.split(":")[0] == wanted), wanted)

    def _prepare_page(self, read: PageRead) -> dict[str, Any] | None:
        """Pseudonymise a page, translate it when it is Hindi, and drop instruction-like lines from the extraction view.

        Returns:
            None for an unreadable page, else a dict with `text` (pseudonymised original), `view` (English view
            for extraction, instruction-like lines removed), `lang`, `route`, `confidence`, `boxes`.
        """
        if read.unreadable or not read.raw.strip():
            return None
        flagged = set(read.flagged_lines)
        kept = "\n".join(ln for ln in read.raw.split("\n") if ln not in flagged)
        text = self.filer.clean(read.raw)
        view_src = self.filer.clean(kept)
        lang = lang_of(read.raw)
        view = view_src
        if lang in ("hi", "mixed"):
            with self._sarvam_scope(DataClass.CLIENT_TEXT, "munshi.translate"):  # pseudonymised text: boundary-checked before Sarvam
                tr = translate_keeping_original(view_src)
            view = tr.english
            tag = f"translate: {tr.engine}" + (" (identity: not translated)" if tr.is_identity else "")
            if tag not in read.extra_log:
                read.extra_log.append(tag)
        return {
            "page": read.page,
            "text": text,
            "view": view,
            "orig_lines": view_src.split("\n"),
            "lang": lang,
            "route": self._route_label(read),
            "confidence": read.outcome.confidence,
            "boxes": read.outcome.boxes,
            "block_boxes": read.outcome.route in _TEXT_ROUTES,
        }

    @staticmethod
    def _quote_pair(sentence: str, page: dict[str, Any]) -> tuple[str, str | None]:
        """(quote, quote_en): for a Hindi page the Hindi line that the English sentence came from, and the sentence itself."""
        if page["lang"] == "en":
            return sentence, None
        en_lines, orig = page["view"].split("\n"), page["orig_lines"]
        if len(en_lines) == len(orig):
            probe = sentence[:30]
            for i, line in enumerate(en_lines):
                if probe in line:
                    j, covered = i, len(en_lines[i])
                    while covered < len(sentence) and j + 1 < len(en_lines):  # the sentence runs over several lines
                        j += 1
                        covered += len(en_lines[j]) + 1
                    return " ".join(ln.strip() for ln in orig[i : j + 1])[:300], sentence
        return sentence, sentence

    @staticmethod
    def _box_for(sentence: str, page: dict[str, Any]) -> list[float] | None:
        """The paragraph box a sentence sits in, when the page's boxes are paragraph blocks."""
        boxes = page["boxes"]
        if not boxes or not page["block_boxes"]:
            return None
        blocks = paragraph_blocks(page["view"])
        for i, block in enumerate(blocks):
            if sentence[:30] in block and i < len(boxes):
                return boxes[i]
        return None

    def _file_doc(self, doc: DocRead, only_pages: set[int] | None = None) -> None:
        """File one document: chunks, dated events, parties, sections, earlier outcomes and personal facts (plan §4.4)."""
        prepared = [(p, self._prepare_page(p)) for p in doc.pages if only_pages is None or p.page in only_pages]
        readable = [(p, pg) for p, pg in prepared if pg is not None]
        for p, pg in prepared:
            self.index.add(
                IndexedPage(
                    file=self._logname(doc.file.name),
                    page=p.page,
                    doc_id=doc.doc_id,
                    doc_type=doc.doc_type.value,
                    status=p.outcome.status.value,
                    route=p.outcome.route.value,
                    ocr_conf=p.outcome.ocr_conf,
                    text=pg["text"] if pg else "",
                )
            )
        if not readable:
            return
        revision = self._run.revisions.get(doc.doc_id, 0)
        self.filer.file_chunks(doc.doc_id, doc.doc_type, [dict(pg, page=p.page) for p, pg in readable], revision=revision)
        doc_view = "\n\n".join(pg["view"] for _, pg in readable)
        self._file_events(doc, readable, doc_view)
        personal: list[str] = []
        for p, pg in readable:
            source = SourceRef(doc=doc.doc_id, page=p.page, lang=pg["lang"], route=pg["route"], quote=pg["view"][:200])
            self.filer.file_parties(pg["text"], source)
            self.filer.file_sections(pg["view"], source)
            personal += self._personal_sentences(doc, pg)
        if personal:
            first = readable[0]
            self.filer.file_personal(personal[:MAX_PERSONAL_PER_DOC], SourceRef(doc=doc.doc_id, page=first[0].page, route=first[1]["route"]))
        self._note_stated_facts(doc_view)

    def _personal_sentences(self, doc: DocRead, page: dict[str, Any]) -> list[str]:
        """Custody, health and personal-circumstance sentences of a page (plan §4.4), with the document label."""
        label = _LABEL_FOR_SENTENCES.get(doc.doc_type)
        out = []
        for sentence in split_sentences(page["view"]):
            kinds = tag_paragraph(sentence)
            if InfoKind.PERSONAL in kinds or (label and len(sentence) > 30):
                out.append(f"[{doc.doc_type.value.lower().replace('_', ' ')}, p.{page['page']}] {sentence}")
        return out[:2] if label else out

    def _file_events(self, doc: DocRead, readable: list[tuple[PageRead, dict[str, Any]]], doc_view: str) -> None:
        """File the dated events of a document: sentence-level per page, plus the document's own event."""
        found: list[tuple[ExtractedEvent, dict[str, Any], PageRead]] = []
        for p, pg in readable:
            found += [(e, pg, p) for e in extract_events(pg["view"], None)]
        keys = {(e.field, e.date) for e, _, _ in found}
        first_p, first_pg = readable[0]
        for e in extract_events(doc_view, doc.doc_type):
            if (e.field, e.date) not in keys:
                found.append((e, first_pg, first_p))
        for e, pg, p in found:
            quote, quote_en = self._quote_pair(e.sentence, pg)
            source = SourceRef(
                doc=doc.doc_id,
                page=p.page,
                box=self._box_for(e.sentence, pg),
                lang=pg["lang"],
                route=pg["route"],
                quote=quote,
                quote_en=quote_en,
            )
            row = self.filer.file_event(e, source)
            if row is not None and e.field == "bail_outcome":
                self.filer.file_previous_bail(row)

    def _note_stated_facts(self, doc_view: str) -> None:
        """Remember statuses the text states without a date (charge sheet not filed, a co-accused's bail outcome)."""
        if charge_sheet_status(doc_view):
            self._run.stated.add("charge_sheet_status")
        if co_accused_outcome(doc_view):
            self._run.stated.add("co_accused_outcome")

    # ---------------------------------------------------------------- gaps, conflicts, report

    def check_gaps(self, state: CaseGraphState) -> list[Gap]:
        """Compare filed items with the checklist; re-read, search or ask (step 4). Skipped when switches.munshi_no_gap_check (P5).

        Args:
            state: see behaviour

        Returns:
            Gaps.
        """
        self._bind(state.case_id)
        run = self._run
        if self.switches.munshi_no_gap_check or run.declined is not None:
            return []
        self._queue_file_questions()
        for read in run.reads:
            if read.error_kind == "unavailable":
                run.gaps.append(Gap(item=f"file {self._logname(read.name)}", action=f"not read: {read.error}"))
            elif read.error:
                run.gaps.append(Gap(item=f"file {self._logname(read.name)}", action=f"not opened ({read.error_kind}: {read.error}); asked counsel for an intact copy"))
        if self.switches.munshi_keep_weak_text:  # flagged to counsel in the intake report: kept pages are read at low confidence
            for read in run.reads:
                weak = [p for p in read.pages if p.outcome.low_confidence]
                if weak:
                    shares = ", ".join(f"p.{p.page} {p.outcome.confidence:.0%}" for p in weak)
                    run.gaps.append(Gap(item=f"file {self._logname(read.name)}: {len(weak)} page(s) read from a rejected text layer",
                                        action=f"kept as a low-confidence read (dictionary-word share {shares}, bar 85%); counsel to check the extracted facts against the original"))
        hierarchy = self.switches.munshi_gap_policy == "hierarchy"
        for item in self._missing():
            if hierarchy and run.gap_records and item not in self._missing():  # S7: stop when the field is filled (an earlier re-read filed it)
                run.gap_records.append({"item": item, "policy": "hierarchy", "candidates": [], "read": [], "reads": 0, "resolved_by": "earlier_reread"})
                run.gaps.append(Gap(item=ITEM_NAMES[item], action="filed by an earlier re-read; nothing more to do"))
                continue
            run.gaps.append(
                resolve_gap(
                    item,
                    state.case_id,
                    index=self.index,
                    reread=self._reread,
                    adopt=self._adopt,
                    ask=self._ask_cb,
                    search=self._search_pages if self.tooled else None,
                    thresholds=self.thresholds,
                    cases_dir=self.cases_dir,
                    policy=self.switches.munshi_gap_policy,
                    signals=run.gap_records,
                )
            )
        if self.switches.munshi_gap_policy == "hierarchy":  # S7: the signals of the policy go to the log (the default policy leaves the log unchanged)
            self.emit(EventKind.AGENT_MESSAGE, {"tool": "gap_policy", "outputs": {"type": "gap_policy", **self.gap_signals(records=False)}})
        return run.gaps

    def gap_signals(self, records: bool = True) -> dict[str, Any]:
        """Signals of this run's gap re-reading under either policy (S7): pages re-read, gaps resolved per page read, oracle-regret inputs, per-item records.

        Args:
            records: include the per-item records (candidate pages in order, pages read); False for the short form logged in the event

        Returns:
            dict (see `ingestion.hierarchy.summarise`); `policy` is None when no gap was handled.
        """
        from vakeel_sahayak.ingestion.hierarchy import summarise

        out = summarise(self._run.gap_records)
        return out if records else {k: v for k, v in out.items() if k != "records"}

    def _missing(self) -> list[str]:
        """Checklist items still missing, in the order questions are worth asking."""
        types = [p.doc_type for p in self.index.pages if p.doc_type]
        labels = [e.label for e in self.filer.timeline_rows()]
        missing = set(missing_items(types, labels, self._run.stated))
        return [i for i in QUESTION_PRIORITY if i in missing]

    def _queue_file_questions(self) -> None:
        """Queue the questions about files that could not be opened and pages that could not be read (grouped)."""
        book = self._run.book
        broken = [r for r in self._run.reads if r.error_kind in ("locked", "broken", "unsupported")]
        if broken:
            names = ", ".join(self._logname(r.name) for r in broken)
            why = "password-protected or damaged" if any(r.error_kind in ("locked", "broken") for r in broken) else "not a readable format"
            book.add(f"{names} could not be opened ({why}). Can you upload an unlocked or intact copy?", "files", 0)
        unreadable = [
            (self._logname(d.file.name), p.page, d.doc_type.value.replace("_", " ").title() if d.doc_type != DocumentType.OTHER else None)
            for d in self._run.docs
            for p in d.pages
            if p.unreadable
        ]
        if unreadable:
            book.add(unreadable_question(unreadable), "unreadable", 0)

    def _search_pages(self, query: str) -> list[dict[str, Any]]:
        """The `search_pages` tool over the case's pages (hits are empty when the tool fails)."""
        got = self.call_tool("search_pages", case_id=self.case_id, query=query, k=5)
        return [] if isinstance(got, ToolError) else list(got)

    def _ask_cb(self, item: str, question: str) -> bool:
        """Add a gap question to the round's book; True when it fits in the room left."""
        book = self._run.book
        book.add(question, item, QUESTION_PRIORITY.index(item) + 1)
        return book.is_asked(item)

    def _find(self, page: IndexedPage) -> tuple[DocRead, PageRead] | None:
        """The document and page read behind an index entry."""
        for doc in self._run.docs:
            if doc.doc_id == page.doc_id:
                for read in doc.pages:
                    if read.page == page.page and self._logname(read.file) == page.file:
                        return doc, read
        return None

    def _reread(self, page: IndexedPage) -> str | None:
        """Re-read a weak page with a stronger route (the vision model), refile its items, and return its new clean text."""
        found = self._find(page)
        if found is None:
            return None
        doc, old = found
        try:
            new = self._read_page(old.path, old.page, ParseRoute.VISION)
        except ModelUnavailable:
            return None
        if isinstance(new, ToolError):
            return None
        self._log_page(new)
        if new.unreadable or not new.raw.strip():
            return None
        doc.pages[doc.pages.index(old)] = new
        self._run.revisions[doc.doc_id] = self._run.revisions.get(doc.doc_id, 0) + 1
        self.filer.learn([new.raw])
        self._file_doc(doc, only_pages={new.page})
        self._refresh_entries()
        return self.filer.clean(new.raw)

    def _adopt(self, page: IndexedPage, item: str) -> bool:
        """File a document found by the page search under the type the missing item expects (an OTHER document that is that paper)."""
        found = self._find(page)
        target = ADOPT_AS.get(item)
        if found is None or target is None:
            return False
        doc, _ = found
        before = self.filer.counts.model_copy(deep=True)
        doc.doc_type, doc.confidence = target, max(doc.confidence, 0.5)
        self._run.revisions[doc.doc_id] = self._run.revisions.get(doc.doc_id, 0) + 1
        self._file_doc(doc)
        self._refresh_entries()
        after = self.filer.counts
        return (after.timeline_events, after.chunks) != (before.timeline_events, before.chunks) or item not in self._missing()

    def check_conflicts(self, state: CaseGraphState) -> list[str]:
        """Keep both values when documents disagree; mark AMBIGUOUS for Peshkar (step 5).

        Args:
            state: see behaviour

        Returns:
            Conflicting fields.
        """
        self._bind(state.case_id)
        run = self._run
        if self.switches.munshi_no_gap_check or run.declined is not None:
            return []
        rows = self.filer.timeline_rows()
        conflicts = detect_conflicts(rows)
        by_id = {r.event_id: r for r in rows}
        for row in mark_ambiguous(rows, conflicts):
            if by_id[row.event_id].status != FieldStatus.AMBIGUOUS or by_id[row.event_id].conflicts_with != row.conflicts_with:
                self.filer.update_event(row)
        for field_name, ids in conflicts:
            values = sorted({by_id[i].date for i in ids})
            first = by_id[ids[0]]
            if (dossier_field := DOSSIER_FIELD.get(field_name)) is not None:
                self.filer.set_ambiguous(dossier_field, first.source)
            self.emit(
                EventKind.AGENT_MESSAGE,
                {
                    "tool": "check_conflicts",
                    "outputs": {"conflict": field_name, "values": values, "event_ids": ids, "status": FieldStatus.AMBIGUOUS.value},
                    "sources": [by_id[i].source for i in ids if by_id[i].source],
                },
            )
        run.conflicts = [f for f, _ in conflicts]
        return run.conflicts

    def report(self, state: CaseGraphState) -> IngestionReport:
        """Stop when the checklist is met or nothing more can be done, and report (step 6).

        The questions that fit in the round are logged and put to counsel through the ask handler; the report is also
        written to the event log as the `ingestion_report` view.

        Args:
            state: see behaviour

        Returns:
            IngestionReport.
        """
        self._bind(state.case_id)
        run = self._run
        names = ", ".join(self._logname(r.name) for r in run.reads) or ", ".join(self._logname(Path(f).name) for f in self.files)
        if run.declined is not None:
            report = build_report(state.case_id, names, [], FiledCounts(), [Gap(item="sensitive matter", action=f"declined at intake: {run.declined}")], [])
        else:
            if self.switches.munshi_no_gap_check:  # P5: no gap check, but unreadable pages and broken files still go to counsel
                self._queue_file_questions()
            questions = run.book.asked()
            report = build_report(state.case_id, names, run.entries, self.filer.counts, run.gaps, questions)
            if questions and self.tooled:  # the tool logs the questions, applies the shared limit and waits for counsel
                got = self.call_tool("ask_user", questions=questions, case_id=state.case_id)
                self.answers = [] if isinstance(got, ToolError) else [str(a) for a in got]
            elif questions:
                record_questions(self.log, state.case_id, questions, self.NAME)  # type: ignore[arg-type]
                self.answers = put_to_counsel(questions, state.case_id)
        self.emit(
            EventKind.STORE_WRITE,
            {"tool": "build_report", "inputs": {"store": "case.views", "view": "ingestion_report"}, "outputs": {"value": report.model_dump(mode="json")}},
        )
        return report

    # ---------------------------------------------------------------- voice

    def dictate(self, audio_path: str, keep_audio: bool = False, lang_hint: str | None = None, case_id: str | None = None) -> DictationResult:
        """Take a dictated voice note: transcribe, file the facts as USER_STATED, read back dates, sections and numbers (plan §4.5).

        The audio is deleted after transcription unless counsel keeps it. The read-back is one question to counsel
        (it counts toward the round's limit). Dictated facts are filed with source `chat` and status USER_STATED.

        Args:
            audio_path: the recording, on the laptop
            keep_audio: counsel chose to keep the audio
            lang_hint: 'hi', 'en' or None for mixed
            case_id: the case (default: this agent's)

        Returns:
            DictationResult with the pseudonymised transcript, the read-back items and the question asked.

        Raises:
            ModelUnavailable: no speech-recognition model is installed (the audio is not deleted).
        """
        self._bind(case_id or str(self.case_id))
        cid = str(self.case_id)
        try:
            with self._sarvam_scope(DataClass.CLIENT_RAW, "munshi.dictation"):  # audio: Sarvam only with counsel's consent
                raw = transcribe_dictation(audio_path, lang_hint, self.asr)
            delete_audio(audio_path, keep_audio)  # the transcript exists: the audio goes unless counsel keeps it
            items = readback(raw)
            self.filer.learn([raw])
            text = self.filer.clean(raw)
            lang = lang_of(raw)
            if lang in ("hi", "mixed"):
                with self._sarvam_scope(DataClass.CLIENT_TEXT, "munshi.translate"):
                    view = translate_keeping_original(text).english
            else:
                view = text
            before = self.filer.counts.model_copy(deep=True)
            self._voice_no = self._run_voice_number()
            self.emit(EventKind.AGENT_MESSAGE, {"tool": "dictate", "outputs": {"chars": len(text), "readback_items": len(items), "audio_kept": keep_audio}})
            self._file_dictated(view, text, lang)
            self.check_conflicts(CaseGraphState(case_id=cid))
            question = readback_question(items) if items else None
            if question and questions_used_this_round(self.log, cid) + 1 <= question_limit():  # type: ignore[arg-type]
                record_questions(self.log, cid, [question], self.NAME)  # type: ignore[arg-type]
                self.answers = put_to_counsel([question], cid)
            else:
                question = None
            delta = FiledCounts(**{k: getattr(self.filer.counts, k) - getattr(before, k) for k in FiledCounts.model_fields})
            return DictationResult(text, items, question, delta, keep_audio)
        finally:
            self.close()

    def _file_dictated(self, view: str, text: str, lang: str) -> None:
        """File the dated events, sections and parties of a transcript as USER_STATED facts."""
        note = f"voice note {self._voice_no}"
        base = SourceRef(chat=note, lang=lang, route="voice", quote=text[:200])
        for e in extract_events(view, None):
            row = self.filer.file_event(e, base.model_copy(update={"quote": e.sentence[:200]}), FieldStatus.USER_STATED)
            if row is not None and e.field in _DIRECT_FIELDS:
                self.filer.put_field(e.field, TrackedField[Any](value=e.date, source=row.source, status=FieldStatus.USER_STATED))
        self.filer.file_sections(view, base, status=FieldStatus.USER_STATED)
        self.filer.file_parties(text, base, status=FieldStatus.USER_STATED)

    def _run_voice_number(self) -> int:
        """Number of the next voice note of this case (from earlier dictation events)."""
        return 1 + sum(1 for e in self.log.read(str(self.case_id)) if e.tool == "dictate")  # type: ignore[union-attr]
