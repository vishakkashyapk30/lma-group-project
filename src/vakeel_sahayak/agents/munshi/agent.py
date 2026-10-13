"""Munshi agent (plan §3.2). Intake agent: survey, categorise, file, check gaps, check conflicts, stop and report (plan §4.3). Runs on the laptop."""

from __future__ import annotations

from vakeel_sahayak.agents.base import BaseAgent
from vakeel_sahayak.orchestration.state import CaseGraphState
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, FiledCounts, Gap, IngestionReport, PageRoute


class MunshiAgent(BaseAgent):
    """Intake agent: survey, categorise, file, check gaps, check conflicts, stop and report (plan §4.3). Runs on the laptop."""

    NAME = AgentName.MUNSHI
    ROLE_MODEL = "munshi_4b"

    def run(self, state: CaseGraphState) -> CaseGraphState:
        """Run Munshi's full job for the current graph state.

        Args:
            state: see behaviour

        Returns:
            Updated state.
        """
        raise NotImplementedError

    def survey(self, state: CaseGraphState) -> list[PageRoute]:
        """Compute cheap signals for every page and run the cheapest acceptable route (plan §4.3 step 1).

        Args:
            state: see behaviour

        Returns:
            Page routes.
        """
        raise NotImplementedError

    def categorise(self, state: CaseGraphState) -> list[DocumentEntry]:
        """Split bundles, label documents, tag paragraphs by information kind (step 2).

        Args:
            state: see behaviour

        Returns:
            Documents.
        """
        raise NotImplementedError

    def file_items(self, state: CaseGraphState) -> FiledCounts:
        """Write items to the case shelf with sources; pseudonymise first (step 3).

        Args:
            state: see behaviour

        Returns:
            Counts.
        """
        raise NotImplementedError

    def check_gaps(self, state: CaseGraphState) -> list[Gap]:
        """Compare filed items with the checklist; re-read, search or ask (step 4). Skipped when switches.munshi_no_gap_check (P5).

        Args:
            state: see behaviour

        Returns:
            Gaps.
        """
        raise NotImplementedError

    def check_conflicts(self, state: CaseGraphState) -> list[str]:
        """Keep both values when documents disagree; mark AMBIGUOUS for Peshkar (step 5).

        Args:
            state: see behaviour

        Returns:
            Conflicting fields.
        """
        raise NotImplementedError

    def report(self, state: CaseGraphState) -> IngestionReport:
        """Stop when the checklist is met or nothing more can be done, and report (step 6).

        Args:
            state: see behaviour

        Returns:
            IngestionReport.
        """
        raise NotImplementedError
