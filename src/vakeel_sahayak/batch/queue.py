"""Persistent job queue for the batch desk (plan §11)."""

from __future__ import annotations


class TriageQueue:
    """Queue of files and full-run jobs; each case's output saved as soon as done so sessions resume (plan §11, §17)."""

    def __init__(self, db_path: str | None = None) -> None:
        """Open or create the queue.

        Args:
            db_path: SQLite file holding queued and finished cases, so a session that ends resumes (plan §11, §17)
        """
        raise NotImplementedError

    def enqueue_files(self, paths: list[str]) -> list[str]:
        """Add uploaded files (folder or zip contents) and return case ids.

        Args:
            paths: see behaviour

        Returns:
            Case ids.
        """
        raise NotImplementedError

    def next_stage2(self, gpu_budget_hours: float) -> list[str]:
        """Pick cases for full runs within the session's GPU budget, in urgency order.

        Args:
            gpu_budget_hours: see behaviour

        Returns:
            Case ids.
        """
        raise NotImplementedError

    def mark_done(self, case_id: str) -> None:
        """Persist completion.

        Args:
            case_id: see behaviour
        """
        raise NotImplementedError
