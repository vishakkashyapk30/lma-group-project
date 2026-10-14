"""Loaders for the JSON fixtures and a builder for a fully populated set of in-memory stores for case-0007."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.fakes import stores as fs
from vakeel_sahayak.schemas import CaseDossier, Event, RightsReport
from vakeel_sahayak.schemas.enums import StoreName, Treatment
from vakeel_sahayak.schemas.store_rows import (
    CitationEdge,
    ConcordanceEdge,
    FactSignature,
    ParagraphRecord,
    SimilarOrderRow,
    StatuteRow,
    TimelineEvent,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

# Synthetic names planted to test pseudonymisation and leaks (plan §15.2 T7). Not real people.
PLANTED_NAMES = ["Ramesh Kumar Yadav", "Sunita Devi Sharma", "Mohd. Irfan Qureshi", "Anil Pratap Singh"]
PLANTED_NAMES_HI = ["रमेश कुमार यादव", "सुनीता देवी शर्मा"]


def read_json(*parts: str) -> Any:
    return json.loads(FIXTURES.joinpath(*parts).read_text(encoding="utf-8"))


def load_case_meta() -> dict:
    return read_json("case_0007", "case_0007.json")


def load_dossier() -> CaseDossier:
    return CaseDossier.model_validate(read_json("case_0007", "dossier.json"))


def load_timeline() -> list[TimelineEvent]:
    return [TimelineEvent.model_validate(x) for x in read_json("case_0007", "timeline.json")]


def load_rights_report() -> RightsReport:
    return RightsReport.model_validate(read_json("case_0007", "rights_report.json"))


def load_events() -> list[Event]:
    text = (FIXTURES / "case_0007" / "events.jsonl").read_text(encoding="utf-8")
    return [Event.model_validate_json(line) for line in text.splitlines() if line.strip()]


def load_statutes() -> list[StatuteRow]:
    return [StatuteRow.model_validate(x) for x in read_json("law", "statutes.json")]


def load_concordance() -> list[ConcordanceEdge]:
    return [ConcordanceEdge.model_validate(x) for x in read_json("law", "concordance.json")]


def load_paragraphs() -> list[ParagraphRecord]:
    return [ParagraphRecord.model_validate(x) for x in read_json("caselaw", "paragraphs.json")]


def load_orders() -> list[dict]:
    text = (FIXTURES / "caselaw" / "orders.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


@dataclass
class CaseWorld:
    """Everything a scenario needs: stores keyed by StoreName plus the raw rows."""

    stores: dict[StoreName, Any]
    dossier: CaseDossier
    timeline: list[TimelineEvent]
    rights: RightsReport
    meta: dict = field(default_factory=dict)

    @property
    def case_date(self) -> str:
        return self.meta["as_of"]


def build_world(excluded_doc_ids: set[str] | None = None) -> CaseWorld:
    """In-memory stores for case-0007. The test-split order TESTORD-2024-0001 and the same-FIR order are excluded by
    default, as the real shared stores must do (plan §2); DLHC-2025-0099 is dated after the case and must never surface."""
    excluded = {"TESTORD-2024-0001", "SAMEFIR-2024-0002"} if excluded_doc_ids is None else excluded_doc_ids
    paragraphs = load_paragraphs()
    dossier, timeline = load_dossier(), load_timeline()
    citation_edges = [
        CitationEdge(citing_doc_id="DLHC-2022-1187", cited_doc_id="SC-2014-0463", treatment=Treatment.RELIED_ON, court_level="HC"),
        CitationEdge(citing_doc_id="DLHC-2021-0420", cited_doc_id="SC-2014-0463", treatment=Treatment.FOLLOWED, court_level="HC"),
        CitationEdge(citing_doc_id="SC-2020-0100", cited_doc_id="DLHC-2023-0911", treatment=Treatment.OVERRULED, court_level="SC"),
    ]
    similar = [
        SimilarOrderRow(doc_id="DLHC-2022-1187", court="Delhi HC", date="2022-06-03",
                        signature=FactSignature(sections=["IPC 420"], custody_band="3-6 months",
                                                charge_sheet_status="filed", co_accused_outcome="granted")),
    ]
    stores: dict[StoreName, Any] = {
        StoreName.LAW_STATUTES: fs.InMemoryStatuteStore(load_statutes()),
        StoreName.LAW_CONCORDANCE: fs.InMemoryConcordanceStore(load_concordance()),
        StoreName.CASELAW_REASONING: fs.InMemoryReasoningStore(paragraphs, excluded),
        StoreName.CASELAW_CITATIONS: fs.InMemoryCitationStore(
            citation_edges, {"SC-2014-0463": 0.95, "DLHC-2022-1187": 0.71}, {"DLHC-2022-1187": "SC-2014-0463"}),
        StoreName.CASELAW_SIMILAR: fs.InMemorySimilarStore(similar),
        StoreName.ADVOCACY_ARGUMENTS: fs.InMemoryArgumentStore(paragraphs, excluded),
        StoreName.ADVOCACY_OBJECTIONS: fs.InMemoryObjectionStore(paragraphs, excluded),
        StoreName.CASE_DOCS: fs.InMemoryCaseDocsStore(),
        StoreName.CASE_TIMELINE: fs.InMemoryTimelineStore(timeline),
        StoreName.CASE_FACTS: fs.InMemoryFactsStore(dossier),
    }
    return CaseWorld(stores=stores, dossier=dossier, timeline=timeline, rights=load_rights_report(), meta=load_case_meta())
