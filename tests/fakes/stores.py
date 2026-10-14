"""In-memory stand-ins for the ten stores (plan §5.1), duck-typed to the real store classes' public methods.

They implement just enough behaviour to exercise agents: metadata filters, the leakage rule (a `before` date is mandatory
for shared stores), reasoning-only authorities, and per-call logging so budget tests can count store calls.
"""

from __future__ import annotations

import importlib
import re
import sys
from typing import Any

from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import (
    ConcordanceEdgeType,
    DocumentType,
    Factor,
    GoodLawStatus,
    OrderPart,
    StoreName,
    TransferFlag,
    Treatment,
)
from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.store_rows import (
    CaseChunk,
    CitationEdge,
    ConcordanceEdge,
    FactSignature,
    ParagraphRecord,
    SimilarOrderRow,
    StatuteRow,
    TimelineEvent,
)
from vakeel_sahayak.tools.types import GoodLawResult, MapSectionResult, TransferCheckResult


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


class _Fake:
    name: StoreName

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _log(self, method: str, **kw: Any) -> None:
        self.calls.append((method, kw))

    def open(self, path: str | None = None) -> None:  # pragma: no cover - interface parity
        pass

    def close(self) -> None:  # pragma: no cover
        pass


class InMemoryParagraphStore(_Fake):
    """Shared paragraph store. `part_filter` fixes which order part the store holds (reasoning / defence / prosecution)."""

    part_filter: OrderPart | None = None

    def __init__(self, paragraphs: list[ParagraphRecord], excluded_doc_ids: set[str] | None = None) -> None:
        super().__init__()
        self.excluded = set(excluded_doc_ids or ())
        self.rows = [p for p in paragraphs if p.doc_id not in self.excluded]

    def count(self) -> int:
        return len(self.rows)

    def _search(self, query: str, factor, section_family, before, outcome, court, part, k) -> list[ParagraphRecord]:
        if not before:
            raise ValueError("leakage guard: every shared-store query needs a 'before' date (plan §2)")
        want = self.part_filter or part
        q = _tokens(query)
        hits = []
        for r in self.rows:
            if r.part != want or r.date >= before:
                continue
            if factor is not None and Factor(factor) not in r.factors:
                continue
            if section_family and not set(section_family) & set(r.section_family):
                continue
            if outcome and r.outcome != outcome:
                continue
            if court and court.lower() not in r.court.lower():
                continue
            hits.append((len(q & _tokens(r.text)) + 0.01 * r.authority, r))
        hits.sort(key=lambda t: (-t[0], t[1].doc_id, t[1].para))
        return [r for _, r in hits[:k]]


class InMemoryReasoningStore(InMemoryParagraphStore):
    name = StoreName.CASELAW_REASONING

    def search(self, query, factor=None, section_family=None, before=None, outcome=None, court=None,
               part=OrderPart.REASONING, k=10):
        self._log("search", query=query, factor=factor, section_family=section_family, before=before, outcome=outcome,
                  court=court, part=part, k=k)
        return self._search(query, factor, section_family, before, outcome, court, part, k)

    def get_paragraph(self, doc_id: str, para: int) -> ParagraphRecord:
        self._log("get_paragraph", doc_id=doc_id, para=para)
        for r in self.rows:
            if r.doc_id == doc_id and r.para == para:
                return r
        raise KeyError(f"unknown paragraph {doc_id}#{para}")


class InMemoryObjectionStore(InMemoryParagraphStore):
    name = StoreName.ADVOCACY_OBJECTIONS
    part_filter = OrderPart.PROSECUTION

    def search(self, query, factor=None, section_family=None, before=None, k=10):
        self._log("search", query=query, factor=factor, section_family=section_family, before=before, k=k)
        return self._search(query, factor, section_family, before, None, None, OrderPart.PROSECUTION, k)


class InMemoryArgumentStore(InMemoryParagraphStore):
    name = StoreName.ADVOCACY_ARGUMENTS
    part_filter = OrderPart.DEFENSE

    def search(self, query, factor=None, section_family=None, outcome=None, before=None, k=10):
        self._log("search", query=query, factor=factor, section_family=section_family, outcome=outcome, before=before, k=k)
        return self._search(query, factor, section_family, before, outcome, None, OrderPart.DEFENSE, k)


class InMemoryCitationStore(_Fake):
    name = StoreName.CASELAW_CITATIONS

    def __init__(self, edges: list[CitationEdge], authority: dict[str, float] | None = None,
                 sc_roots: dict[str, str] | None = None) -> None:
        super().__init__()
        self.edges, self.authority, self.roots = list(edges), dict(authority or {}), dict(sc_roots or {})

    def count(self) -> int:
        return len(self.edges)

    def cited_by(self, doc_id: str) -> list[CitationEdge]:
        self._log("cited_by", doc_id=doc_id)
        return [e for e in self.edges if e.cited_doc_id == doc_id]

    def cites(self, doc_id: str) -> list[CitationEdge]:
        self._log("cites", doc_id=doc_id)
        return [e for e in self.edges if e.citing_doc_id == doc_id]

    def authority_score(self, doc_id: str) -> float:
        return self.authority.get(doc_id, 0.0)

    def good_law(self, doc_id: str, as_of: str | None = None) -> GoodLawResult:
        self._log("good_law", doc_id=doc_id, as_of=as_of)
        for e in self.edges:
            if e.cited_doc_id == doc_id and e.treatment == Treatment.OVERRULED:
                return GoodLawResult(status=GoodLawStatus.OVERRULED, overruled_by=e.citing_doc_id, sc_root=self.roots.get(doc_id))
        for e in self.edges:
            if e.cited_doc_id == doc_id and e.treatment == Treatment.DISTINGUISHED:
                return GoodLawResult(status=GoodLawStatus.DISTINGUISHED, sc_root=self.roots.get(doc_id))
        return GoodLawResult(status=GoodLawStatus.OK, sc_root=self.roots.get(doc_id))

    def sc_root(self, doc_id: str) -> str | None:
        return self.roots.get(doc_id)


class InMemorySimilarStore(_Fake):
    name = StoreName.CASELAW_SIMILAR

    def __init__(self, rows: list[SimilarOrderRow]) -> None:
        super().__init__()
        self.rows = list(rows)

    def count(self) -> int:
        return len(self.rows)

    def similar(self, facts_text: str, signature: FactSignature | None = None, before: str | None = None, k: int = 10):
        self._log("similar", before=before, k=k)
        if not before:
            raise ValueError("leakage guard: 'before' required")
        rows = [r for r in self.rows if r.date < before]
        if signature and signature.sections:
            rows.sort(key=lambda r: -len(set(r.signature.sections) & set(signature.sections)))
        return rows[:k]


class InMemoryStatuteStore(_Fake):
    name = StoreName.LAW_STATUTES

    def __init__(self, rows: list[StatuteRow]) -> None:
        super().__init__()
        self.rows = list(rows)

    def count(self) -> int:
        return len(self.rows)

    def get(self, code: str, section: str) -> StatuteRow:
        self._log("get", code=code, section=section)
        for r in self.rows:
            if r.code.upper() == code.upper() and r.section == section:
                return r
        raise KeyError(f"unknown statute {code} {section}")

    def search(self, query: str, code: str | None = None, k: int = 5) -> list[StatuteRow]:
        self._log("search", query=query, code=code, k=k)
        q = _tokens(query)
        rows = [r for r in self.rows if code is None or r.code.upper() == code.upper()]
        rows.sort(key=lambda r: -len(q & _tokens(r.text)))
        return rows[:k]


class InMemoryConcordanceStore(_Fake):
    """Concordance with a deliberately small, readable mapping logic (the *fake*, not the product)."""

    name = StoreName.LAW_CONCORDANCE
    ERA_START = "2024-07-01"

    def __init__(self, edges: list[ConcordanceEdge]) -> None:
        super().__init__()
        self.edges = list(edges)

    def count(self) -> int:
        return len(self.edges)

    def edges_for(self, ref: str) -> list[ConcordanceEdge]:
        return [e for e in self.edges if ref in (e.old_ref, e.new_ref)]

    def map_section(self, code: str, section: str, offence_date: str) -> MapSectionResult:
        self._log("map_section", code=code, section=section, offence_date=offence_date)
        ref = f"{code.upper() if code.upper() in ('IPC', 'BNS', 'BNSS') else code} {section}"
        old_codes = ("IPC", "CrPC")
        forward = code in old_codes
        found = [e for e in self.edges if (e.old_ref if forward else e.new_ref) == ref]
        if not found:
            return MapSectionResult(equivalent=None, edge_type=None, ambiguous=True)
        targets = [e.new_ref if forward else e.old_ref for e in found]
        if len(targets) > 1:
            return MapSectionResult(equivalent=None, edge_type=found[0].type, ambiguous=True, candidates=targets)
        return MapSectionResult(equivalent=targets[0], edge_type=found[0].type, ambiguous=False, candidates=targets)

    def transfer_flag(self, old_ref: str, new_ref: str) -> TransferCheckResult:
        self._log("transfer_flag", old_ref=old_ref, new_ref=new_ref)
        for e in self.edges:
            if e.old_ref == old_ref and e.new_ref == new_ref:
                if e.type == ConcordanceEdgeType.SAME:
                    return TransferCheckResult(flag=TransferFlag.SAME_TEXT)
                if e.type == ConcordanceEdgeType.NEW:
                    return TransferCheckResult(flag=TransferFlag.NEW)
                return TransferCheckResult(flag=TransferFlag.CHANGED, text_diff=e.text_diff,
                                           qualification=f"{old_ref} was {e.type.value.lower()} into {new_ref}")
        return TransferCheckResult(flag=TransferFlag.NEW)

    def family(self, ref: str) -> list[str]:
        out = {ref}
        for e in self.edges_for(ref):
            out.update((e.old_ref, e.new_ref))
        return sorted(out)


class InMemoryTimelineStore(_Fake):
    name = StoreName.CASE_TIMELINE

    def __init__(self, events: list[TimelineEvent] | None = None) -> None:
        super().__init__()
        self.events = list(events or [])

    def count(self) -> int:
        return len(self.events)

    def add_event(self, event: TimelineEvent) -> None:
        self._log("add_event", event_id=event.event_id)
        self.events.append(event)

    def get(self, start: str | None = None, end: str | None = None) -> list[TimelineEvent]:
        self._log("get", start=start, end=end)
        return sorted((e for e in self.events if (not start or e.date >= start) and (not end or e.date <= end)),
                      key=lambda e: e.date)


class InMemoryFactsStore(_Fake):
    name = StoreName.CASE_FACTS

    def __init__(self, dossier: CaseDossier) -> None:
        super().__init__()
        self._dossier = dossier

    def count(self) -> int:
        return len(type(self._dossier.fields).model_fields)

    def get(self, field: str) -> TrackedField[Any]:
        self._log("get", field=field)
        return getattr(self._dossier.fields, field)

    def put(self, field: str, value: TrackedField[Any]) -> None:
        self._log("put", field=field)
        setattr(self._dossier.fields, field, value)

    def dossier(self) -> CaseDossier:
        return self._dossier


class InMemoryCaseDocsStore(_Fake):
    name = StoreName.CASE_DOCS

    def __init__(self, chunks: list[CaseChunk] | None = None) -> None:
        super().__init__()
        self.chunks = list(chunks or [])

    def count(self) -> int:
        return len(self.chunks)

    def add_chunks(self, chunks: list[CaseChunk]) -> None:
        self._log("add_chunks", n=len(chunks))
        self.chunks.extend(chunks)

    def search(self, query: str, doc_types: list[DocumentType] | None = None, k: int = 5) -> list[CaseChunk]:
        self._log("search", query=query, doc_types=doc_types, k=k)
        q = _tokens(query)
        rows = [c for c in self.chunks if not doc_types or c.doc_type in doc_types]
        rows.sort(key=lambda c: (-len(q & _tokens(c.text)), c.page))
        return rows[:k]


def install_fake_stores(monkeypatch: Any, stores: dict[StoreName, Any]) -> None:
    """Make `open_store(name)` return the given fakes everywhere (registry plus every module-level alias).

    All tool modules are imported first so their `open_store` aliases exist and can be patched.
    """
    from vakeel_sahayak.tools.registry import ALL_TOOL_MODULES

    for mod_name, _ in ALL_TOOL_MODULES:
        importlib.import_module(mod_name)

    def fake_open_store(name, path=None, case_id=None):
        key = StoreName(name)
        if key not in stores:
            raise KeyError(f"no fake store installed for {key.value}")
        return stores[key]

    monkeypatch.setattr("vakeel_sahayak.stores.registry.open_store", fake_open_store)
    for mod_name, mod in list(sys.modules.items()):
        if mod_name.startswith("vakeel_sahayak") and mod is not None and hasattr(mod, "open_store"):
            monkeypatch.setattr(mod, "open_store", fake_open_store)
