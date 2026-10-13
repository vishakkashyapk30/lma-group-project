"""Shared retrieval cache (plan §11)."""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.schemas.enums import Factor


class RetrievalCache:
    """Cache shared across cases; key = factor, section family, before-date month and query (plan §11)."""

    def key(self, factor: Factor, section_family: list[str], before: str, query: str) -> str:
        """Build the cache key.

        Args:
            factor: see behaviour
            section_family: see behaviour
            before: see behaviour
            query: see behaviour

        Returns:
            Key string.
        """
        raise NotImplementedError

    def get(self, key: str) -> Any | None:
        """Cached result or None.

        Args:
            key: see behaviour
        """
        raise NotImplementedError

    def put(self, key: str, value: Any) -> None:
        """Store a result.

        Args:
            key: see behaviour
            value: see behaviour
        """
        raise NotImplementedError

    def stats(self) -> dict[str, float]:
        """Hit rate etc. for F4 (plan §15.6)."""
        raise NotImplementedError
