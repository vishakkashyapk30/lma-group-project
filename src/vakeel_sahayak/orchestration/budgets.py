"""Per-case and per-factor budgets (plan §6.2)."""

from __future__ import annotations

from vakeel_sahayak.schemas.case import BudgetState
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft


class BudgetTracker:
    """Tracks tokens and store calls per case and per factor; logs every time a budget is hit (plan §6.2)."""

    def __init__(
        self, tokens_per_case: int = 150000, store_calls_per_factor: int = 8, tokens_per_factor: int = 12000
    ) -> None:
        """Create a tracker.

        Args:
            tokens_per_case: see behaviour
            store_calls_per_factor: see behaviour
            tokens_per_factor: see behaviour
        """
        raise NotImplementedError

    def charge(self, factor: str | None, tokens: int = 0, store_calls: int = 0) -> None:
        """Record spend.

        Args:
            factor: see behaviour
            tokens: see behaviour
            store_calls: see behaviour
        """
        raise NotImplementedError

    def left(self, factor: str | None = None) -> BudgetLeft:
        """Remaining budget (for RetrievalPlan.budget_left).

        Args:
            factor: see behaviour

        Returns:
            BudgetLeft.
        """
        raise NotImplementedError

    def exhausted(self, factor: str | None = None) -> bool:
        """True when the budget for the factor or case is spent; emits a BUDGET_HIT event.

        Args:
            factor: see behaviour

        Returns:
            bool.
        """
        raise NotImplementedError

    def snapshot(self) -> BudgetState:
        """Spend shown in the UI.

        Returns:
            BudgetState.
        """
        raise NotImplementedError
