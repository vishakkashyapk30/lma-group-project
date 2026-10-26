"""Filing rules: what goes where in the case shelf (plan §4.4).

`Filer` writes Munshi's items to `case.docs`, `case.timeline` and `case.facts` with their source (document, page, box,
route, language), after pseudonymisation, and appends one STORE_WRITE event per write using the vocabulary of
`record/views.py`, so the dossier and timeline views can be rebuilt from the log. Confidence rides in the event
outputs, because the stored rows have no field for it. Text must be pseudonymised before it reaches a `file_*` method;
`learn` and `clean` are the two passes that do that (names are learned from every page first, so the first mention of
a name is replaced too).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from vakeel_sahayak.ingestion.classify import tag_paragraph
from vakeel_sahayak.ingestion.events import ExtractedEvent
from vakeel_sahayak.ingestion.hindi import translate_keeping_original
from vakeel_sahayak.pipelines.section_extract import charged_sections, extract_sections
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap, load_map, pseudonymise_text, save_map
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.dossier import PreviousBail, SectionValue
from vakeel_sahayak.schemas.enums import AgentName, DocumentType, EventKind, FieldStatus, InfoKind, StoreName
from vakeel_sahayak.schemas.events import Event
from vakeel_sahayak.schemas.ingestion_report import FiledCounts
from vakeel_sahayak.schemas.store_rows import CaseChunk, TimelineEvent
from vakeel_sahayak.stores.chunking import chunk_case_document

FILING_RULES: dict[str, str] = {
    "document_text": "case.docs",
    "dated_event": "case.timeline",
    "party": "case.facts",
    "section": "case.facts",
    "earlier_outcome": "case.timeline+case.facts",
    "custody_health_personal": "case.facts",
    "unreadable_or_missing": "open_questions",
}

_TARGETS: dict[InfoKind, list[StoreName]] = {
    InfoKind.DATED_EVENT: [StoreName.CASE_TIMELINE],
    InfoKind.PARTY: [StoreName.CASE_FACTS],
    InfoKind.SECTION: [StoreName.CASE_FACTS],
    InfoKind.EARLIER_OUTCOME: [StoreName.CASE_TIMELINE, StoreName.CASE_FACTS],
    InfoKind.CUSTODY: [StoreName.CASE_FACTS],
    InfoKind.PERSONAL: [StoreName.CASE_FACTS],
}
_ALIAS = re.compile(r"\b(?:Accused|Co-accused|Complainant|IO|Witness|Person)-\d+\b")
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
MAX_PERSONAL_PER_DOC = 5
# Registration and arrest procedure, not offences: a FIR "under section 173 BNSS" is not charged with section 173.
_PROCEDURAL_EXTRA = frozenset(
    {"CrPC 154", "CrPC 156", "CrPC 157", "CrPC 173", "CrPC 41", "CrPC 41A", "CrPC 50", "CrPC 57", "BNSS 173", "BNSS 193", "BNSS 35", "BNSS 47", "BNSS 58"}
)


def target_stores(info_kind: InfoKind) -> list[StoreName]:
    """Which case-shelf store(s) an item belongs in.

    Args:
        info_kind: see behaviour

    Returns:
        Stores: dated events to the timeline; parties, sections, custody and personal facts to the facts store; an
        earlier court outcome to both the timeline and the facts store.
    """
    return list(_TARGETS[InfoKind(info_kind)])


def event_id_for(doc_id: str, page: int | None, field: str, label: str, date: str) -> str:
    """A stable timeline event id, so filing the same page twice does not duplicate the event."""
    digest = hashlib.sha1(f"{doc_id}|{page}|{field}|{label}|{date}".encode()).hexdigest()[:10]
    return f"tl-{digest}"


class Filer:
    """Writes Munshi's items to the case shelf and the event log, one case at a time.

    Stores stay open until `close()`. Pass `case_path` (a folder, or ':memory:') to keep the case's files somewhere
    other than the configured cases folder.
    """

    def __init__(
        self,
        case_id: str,
        log: EventLog,
        *,
        case_path: str | None = None,
        mapping: PseudonymMap | None = None,
        cases_dir: str | None = None,
        actor: AgentName | str = AgentName.MUNSHI,
    ) -> None:
        """Bind to a case, its event log and its alias map (loaded from the laptop unless given)."""
        self.case_id, self.log, self.actor = case_id, log, actor
        self.case_path, self.cases_dir = case_path, cases_dir
        self.mapping = mapping if mapping is not None else load_map(case_id, cases_dir)
        self.counts = FiledCounts()
        self._stores: dict[StoreName, Any] = {}
        self._event_ids: set[str] | None = None

    # ---------------------------------------------------------------- privacy

    def learn(self, texts: list[str]) -> None:
        """First pass: learn every name in the raw texts so the same person gets the same alias everywhere."""
        for text in texts:
            pseudonymise_text(text, self.case_id, self.mapping)

    def clean(self, text: str) -> str:
        """Second pass: replace the names learned so far and mask emails, phone and ID numbers."""
        out, _ = pseudonymise_text(text, self.case_id, self.mapping)
        return out

    def pseudonymise_batch(self, texts: list[str]) -> list[str]:
        """Learn from all the texts, then clean each of them."""
        self.learn(texts)
        return [self.clean(t) for t in texts]

    def save_map(self) -> None:
        """Write the alias map next to the case's files (laptop only, never logged)."""
        save_map(self.case_id, self.mapping, self.cases_dir)

    def clean_value(self, value: Any) -> Any:
        """`clean` applied to every string inside a nested value."""
        if isinstance(value, str):
            return self.clean(value)
        if isinstance(value, list):
            return [self.clean_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self.clean_value(v) for k, v in value.items()}
        return value

    # ---------------------------------------------------------------- stores and events

    def _store(self, name: StoreName):  # noqa: ANN202
        if name not in self._stores:
            from vakeel_sahayak.stores.registry import open_store

            self._stores[name] = open_store(name, self.case_path, self.case_id)
        return self._stores[name]

    def close(self) -> None:
        """Close the stores."""
        for store in self._stores.values():
            store.close()
        self._stores.clear()

    def _write(self, inputs: dict[str, Any], outputs: dict[str, Any], sources: list[SourceRef]) -> None:
        self.log.append(
            Event(
                event_id="",
                case_id=self.case_id,
                ts="",
                kind=EventKind.STORE_WRITE,
                actor=self.actor,
                tool="file_item",
                inputs=inputs,
                outputs=outputs,
                sources=sources,
            )
        )

    def timeline_rows(self) -> list[TimelineEvent]:
        """The events now on the timeline."""
        return list(self._store(StoreName.CASE_TIMELINE).get())

    # ---------------------------------------------------------------- case.docs

    def file_chunks(
        self,
        doc_id: str,
        doc_type: DocumentType,
        pages: list[dict[str, Any]],
        revision: int = 0,
    ) -> int:
        """Chunk a document's pseudonymised pages and file the chunks with page, box, language, route and confidence.

        Args:
            doc_id: document id (d1, d2, ...)
            doc_type: the document's label
            pages: one dict per page with `page` (number in the file), `text`, `boxes`,
                `block_boxes` (True when the boxes are paragraph blocks), `route`, `lang`, `confidence`
            revision: 0 for the first filing; a re-read or re-typed document is filed again as revision 1, 2, ... (the
                store has no delete, so the new chunks get their own ids and sit beside the old ones)

        Returns:
            Number of new chunks.
        """
        store = self._store(StoreName.CASE_DOCS)
        before = store.count()
        texts = [p["text"] for p in pages]
        block_boxes = [p.get("boxes") if p.get("block_boxes") else None for p in pages]
        chunks = chunk_case_document(texts, doc_type, [b or [] for b in block_boxes], doc_id)
        rows: list[CaseChunk] = []
        sources: list[SourceRef] = []
        confidences: list[float | None] = []
        for chunk in chunks:
            info = pages[chunk.page - 1]
            real_page = int(info["page"])
            box = chunk.box
            if box is None and info.get("boxes"):
                boxes = info["boxes"]
                box = [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]
            text_en = None
            if _DEVANAGARI.search(chunk.text):
                text_en = translate_keeping_original(chunk.text).english
            row = chunk.model_copy(
                update={
                    "chunk_id": f"{doc_id}-p{real_page}-c{chunk.chunk_id.rsplit('-c', 1)[-1]}" + (f"-r{revision}" if revision else ""),
                    "page": real_page,
                    "box": box,
                    "text_en": text_en,
                    "info_kinds": tag_paragraph(text_en or chunk.text),
                }
            )
            rows.append(row)
            sources.append(SourceRef(doc=doc_id, page=real_page, box=box, lang=info.get("lang"), route=info.get("route")))
            confidences.append(info.get("confidence"))
        store.add_chunks(rows)
        new = store.count() - before
        self.counts.chunks += new
        self._write(
            {"store": StoreName.CASE_DOCS.value, "doc_id": doc_id},
            {"chunk_ids": [r.chunk_id for r in rows], "count": new, "confidence": confidences},
            sources,
        )
        return new

    # ---------------------------------------------------------------- case.timeline

    def file_event(
        self,
        ev: ExtractedEvent,
        source: SourceRef,
        status: FieldStatus = FieldStatus.VERIFIED,
    ) -> TimelineEvent | None:
        """File one dated event; returns it, or None when this document and page already gave it."""
        store = self._store(StoreName.CASE_TIMELINE)
        if self._event_ids is None:
            self._event_ids = {e.event_id for e in store.get()}
        event_id = event_id_for(source.doc or "-", source.page, ev.field, ev.label, ev.date)
        if event_id in self._event_ids:
            return None
        row = TimelineEvent(event_id=event_id, date=ev.date, label=ev.label, source=source, status=status)
        store.add_event(row)
        self._event_ids.add(event_id)
        self.counts.timeline_events += 1
        self._write({"store": StoreName.CASE_TIMELINE.value}, {"event": row.model_dump(mode="json")}, [source])
        return row

    def update_event(self, row: TimelineEvent) -> None:
        """Rewrite an existing event (conflict marking); counts are not changed."""
        self._store(StoreName.CASE_TIMELINE).add_event(row)
        self._write({"store": StoreName.CASE_TIMELINE.value}, {"event": row.model_dump(mode="json")}, [row.source] if row.source else [])

    # ---------------------------------------------------------------- case.facts

    def put_field(self, field: str, tracked: TrackedField[Any]) -> None:
        """Write one dossier field to the facts store and log it."""
        self._store(StoreName.CASE_FACTS).put(field, tracked)
        self._write(
            {"store": StoreName.CASE_FACTS.value, "field": field},
            {"tracked": tracked.model_dump(mode="json")},
            [tracked.source] if tracked.source else [],
        )

    def _merge(
        self, field: str, new: list[Any], source: SourceRef, key: Any = lambda x: x, status: FieldStatus = FieldStatus.VERIFIED
    ) -> int:
        """Add the values not yet in a list field and write the merged field; returns how many were new."""
        current = self._store(StoreName.CASE_FACTS).get(field)
        existing = list(current.value or [])
        have = {key(v) for v in existing}
        fresh = []
        for value in new:
            if key(value) not in have:
                fresh.append(value)
                have.add(key(value))
        if not fresh:
            return 0
        merged = [*existing, *fresh]
        self.put_field(field, TrackedField[Any](value=merged, source=source, status=status))
        return len(fresh)

    def file_parties(self, text: str, source: SourceRef, status: FieldStatus = FieldStatus.VERIFIED) -> int:
        """File the aliases (Accused-1, Complainant-1, IO-1, ...) that occur in pseudonymised text."""
        aliases = list(dict.fromkeys(_ALIAS.findall(text)))
        n = self._merge("parties", aliases, source, status=status) if aliases else 0
        self.counts.parties += n
        return n

    def file_sections(self, text: str, source: SourceRef, status: FieldStatus = FieldStatus.VERIFIED) -> int:
        """File the charged sections found in text (procedural bail provisions such as CrPC 439 are left out)."""
        from vakeel_sahayak.pipelines.concordance.refs import split_ref

        values = []
        for ref in charged_sections(extract_sections(text)):
            if ref.split("(")[0] in _PROCEDURAL_EXTRA:
                continue
            code, section = split_ref(ref)
            values.append(SectionValue(as_written=ref, code=code, section=section).model_dump(mode="json"))
        # existing values come back from the store as SectionValue models while new ones are dicts, so the key reads both.
        as_written = lambda v: v["as_written"] if isinstance(v, dict) else v.as_written  # noqa: E731
        n = self._merge("sections", values, source, key=as_written, status=status) if values else 0
        self.counts.sections += n
        return n

    def file_previous_bail(self, row: TimelineEvent) -> int:
        """File an earlier bail outcome from a 'Bail rejected (Sessions Court)' timeline event into `previous_bail`."""
        m = re.match(r"Bail (rejected|granted)(?: \((.+)\))?", row.label)
        if not m:
            return 0
        value = PreviousBail(court=m.group(2) or "court not stated", date=row.date, outcome=m.group(1)).model_dump(mode="json")
        return self._merge("previous_bail", [value], row.source or SourceRef(), key=lambda v: (v["court"], v["date"], v["outcome"]))

    def file_personal(self, sentences: list[str], source: SourceRef) -> int:
        """File custody, health and personal circumstances (pseudonymised sentences) into the `personal` field."""
        return self._merge("personal", [s[:240] for s in sentences], source) if sentences else 0

    def set_ambiguous(self, field: str, source: SourceRef | None) -> None:
        """Mark a dossier field AMBIGUOUS (documents disagree); both values stay on the timeline."""
        self.put_field(field, TrackedField[Any](value=None, source=source, status=FieldStatus.AMBIGUOUS))

    # ---------------------------------------------------------------- generic (the file_item tool)

    def file_raw_item(self, store: StoreName, item: dict[str, Any], source: SourceRef) -> str:
        """File one item given as plain data, after pseudonymising its strings (the `file_item` tool).

        Args:
            store: case.docs (item = CaseChunk fields), case.timeline (item = date, label, ...) or case.facts
                (item = field, value, status)
            item: the item
            source: where it came from

        Returns:
            The id of the filed row (chunk id, event id or field name).

        Raises:
            ValueError: for a store other than the three case stores, or an item that does not fit.
        """
        self.learn([s for s in _strings(item) + _strings(source.model_dump())])
        item, source = self.clean_value(item), SourceRef.model_validate(self.clean_value(source.model_dump()))
        if store == StoreName.CASE_DOCS:
            chunk = CaseChunk.model_validate({"page": source.page or 1, "box": source.box, "doc_id": source.doc or "doc", **item})
            self._store(store).add_chunks([chunk])
            self.counts.chunks += 1
            self._write({"store": store.value, "doc_id": chunk.doc_id}, {"chunk_ids": [chunk.chunk_id], "count": 1}, [source])
            return chunk.chunk_id
        if store == StoreName.CASE_TIMELINE:
            date, label = str(item.get("date", "")), str(item.get("label", ""))
            event_id = item.get("event_id") or event_id_for(source.doc or "-", source.page, "item", label, date)
            row = TimelineEvent(
                event_id=event_id,
                date=date,
                label=label,
                source=source,
                status=FieldStatus(item.get("status", FieldStatus.VERIFIED)),
                conflicts_with=list(item.get("conflicts_with", [])),
            )
            self._store(store).add_event(row)
            self.counts.timeline_events += 1
            self._write({"store": store.value}, {"event": row.model_dump(mode="json")}, [source])
            return row.event_id
        if store == StoreName.CASE_FACTS:
            field = str(item.get("field", ""))
            tracked = TrackedField[Any](
                value=item.get("value"), source=source, status=FieldStatus(item.get("status", FieldStatus.VERIFIED))
            )
            self.put_field(field, tracked)
            return field
        raise ValueError(f"file_item writes to case.docs, case.timeline or case.facts, not {store.value}")


def _strings(value: Any) -> list[str]:
    """All strings inside a nested value."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    return []
