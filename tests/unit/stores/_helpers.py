"""Helpers for the stores tests: build synthetic order text with exact whitespace-token counts."""

from __future__ import annotations


def ntok(text: str) -> int:
    """Whitespace token count (the unit of the 400-token limit in plan §5.2; ASSUMPTION: whitespace tokens)."""
    return len(text.split())


def norm(text: str) -> str:
    """Whitespace-normalised text."""
    return " ".join(text.split())


def sentence(n_words: int, tag: str = "w") -> str:
    """One sentence of exactly `n_words` whitespace tokens: 'Sentence tag1 tag2 ... tagN.' (starts upper-case, ends with '.')."""
    assert n_words >= 2
    words = ["Sentence"] + [f"{tag}{i}" for i in range(1, n_words - 1)] + [f"{tag}end."]
    return " ".join(words)


def paragraph(number: int, n_tokens: int, tag: str = "w") -> str:
    """Numbered paragraph '<number>. ...' with exactly `n_tokens` whitespace tokens (the number counts as one), a single sentence."""
    assert n_tokens >= 3
    return f"{number}. " + sentence(n_tokens - 1, tag)


def long_paragraph(number: int, n_sentences: int, words_per_sentence: int) -> str:
    """Numbered paragraph of many sentences, so it can only be split at sentence ends."""
    body = " ".join(sentence(words_per_sentence, f"s{i}_") for i in range(n_sentences))
    return f"{number}. {body}"
