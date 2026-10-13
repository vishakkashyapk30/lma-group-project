"""Peshkar agent (plan §3.2). Dossier, List of Dates, Rights Radar, change detection (plan §7). Fine-tuned Qwen3-4B + rules, laptop."""

from __future__ import annotations

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.change_set import ChangeSet
from vakeel_sahayak.schemas.dossier import CaseDossier
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.schemas.rights_report import RightsReport
from vakeel_sahayak.schemas.store_rows import TimelineEvent


class PeshkarAgent(BaseAgent):
    """Dossier, List of Dates, Rights Radar, change detection (plan §7). Fine-tuned Qwen3-4B + rules, laptop."""

    NAME = AgentName.PESHKAR
    ROLE_MODEL = "extractor_4b"

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Peshkar's full job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def build_dossier(self, state: CaseGraphState) -> CaseDossier:
        """Extract, span-check, re-extract failed fields, put conflicts to counsel; stop when ready for Gate 1 (plan §7.1).

        Args:
            state: see behaviour

        Returns:
            CaseDossier.
        """
        raise NotImplementedError

    def build_list_of_dates(self, state: CaseGraphState) -> list[TimelineEvent]:
        """Build the List of Dates from case.timeline (plan §7.2).

        Args:
            state: see behaviour

        Returns:
            Events.
        """
        raise NotImplementedError

    def run_rights_radar(self, state: CaseGraphState) -> RightsReport:
        """Call the Rights Radar tool (plan §7.3).

        Args:
            state: see behaviour

        Returns:
            RightsReport.
        """
        raise NotImplementedError

    def detect_changes(self, state: CaseGraphState) -> ChangeSet:
        """On a new document or clock tick: re-extract touched fields, diff, re-run the radar, highlight for re-approval (plan §7.4).

        Args:
            state: see behaviour

        Returns:
            ChangeSet.
        """
        raise NotImplementedError
