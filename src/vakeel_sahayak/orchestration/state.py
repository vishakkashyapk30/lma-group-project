"""Typed graph state (plan §3.3)."""

from __future__ import annotations

from pydantic import BaseModel

from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import GateId, Stage
from vakeel_sahayak.schemas.ingestion_report import IngestionReport
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.sparring import SparringRecord


class CaseGraphState(BaseModel):
    """State carried through the case graph."""

    case_id: str
    stage: Stage = Stage.INTAKE
    ingestion: IngestionReport | None = None
    dossier: CaseDossier | None = None
    rights: RightsReport | None = None
    brief: BailBrief | None = None
    sparring: SparringRecord | None = None
    pending_change_set: ChangeSet | None = None
    pending_gate: GateId | None = None
