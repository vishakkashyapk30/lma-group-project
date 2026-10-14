"""Chunking variants for B3 and the retrieval-only analysis (plan §15.3, §15.7)."""

from __future__ import annotations


def fixed_512(text: str) -> list[str]:
    """Fixed 512-token chunks.

    Args:
        text: see behaviour

    Returns:
        Chunks.
    """
    raise NotImplementedError


def fixed_512_overlap(text: str) -> list[str]:
    """512 with 20% overlap.

    Args:
        text: see behaviour

    Returns:
        Chunks.
    """
    raise NotImplementedError


def recursive_split(text: str) -> list[str]:
    """Recursive splitter.

    Args:
        text: see behaviour

    Returns:
        Chunks.
    """
    raise NotImplementedError


def semantic_chunks(text: str) -> list[str]:
    """Semantic chunking.

    Args:
        text: see behaviour

    Returns:
        Chunks.
    """
    raise NotImplementedError


def page_chunks(pages: list[str]) -> list[str]:
    """One chunk per page.

    Args:
        pages: see behaviour

    Returns:
        Chunks.
    """
    raise NotImplementedError
