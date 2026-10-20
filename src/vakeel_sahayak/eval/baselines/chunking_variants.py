"""Chunking variants for B3 and the retrieval-only analysis (plan §15.3, §15.7).

Tokens are whitespace-separated words (the same estimate as `pipelines.text_utils.count_tokens`). Every variant keeps all the words of
its input in order (the overlap variant repeats the overlap on purpose), so no text is lost and nothing is invented.
"""

from __future__ import annotations

import re

SIZE = 512
OVERLAP = SIZE // 5  # 20% overlap = 102 tokens
_SENTENCE = re.compile(r"(?<=[.!?।])\s+")
_STOP = frozenset("a an the of in on at to and or but was were is are by for with that this it as be been has have had".split())


def _windows(tokens: list[str], size: int, stride: int) -> list[str]:
    """Windows of `size` tokens every `stride` tokens; the last window ends at the end of the text."""
    if not tokens:
        return []
    out, start = [], 0
    while True:
        out.append(" ".join(tokens[start : start + size]))
        if start + size >= len(tokens):
            return out
        start += stride


def fixed_512(text: str) -> list[str]:
    """Fixed 512-token chunks.

    Args:
        text: the text to cut

    Returns:
        Chunks of 512 tokens (the last one shorter), covering the text once.
    """
    return _windows(text.split(), SIZE, SIZE)


def fixed_512_overlap(text: str) -> list[str]:
    """512 with 20% overlap.

    Args:
        text: the text to cut

    Returns:
        Chunks of at most 512 tokens; neighbours share exactly 102 tokens.
    """
    return _windows(text.split(), SIZE, SIZE - OVERLAP)


def _pieces(text: str) -> list[str]:
    """Paragraphs, then sentences of paragraphs that are too long, then token windows of sentences that are still too long."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        if not para.strip():
            continue
        if len(para.split()) <= SIZE:
            out.append(" ".join(para.split()))
            continue
        for sent in _SENTENCE.split(para):
            if len(sent.split()) <= SIZE:
                if sent.strip():
                    out.append(" ".join(sent.split()))
            else:
                out.extend(_windows(sent.split(), SIZE, SIZE))
    return out


def _merge(pieces: list[str]) -> list[str]:
    """Greedily join neighbouring pieces while the chunk stays within 512 tokens."""
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for piece in pieces:
        n = len(piece.split())
        if current and size + n > SIZE:
            chunks.append(" ".join(current))
            current, size = [], 0
        current.append(piece)
        size += n
    if current:
        chunks.append(" ".join(current))
    return chunks


def recursive_split(text: str) -> list[str]:
    """Recursive splitter.

    Args:
        text: the text to cut

    Returns:
        Chunks of at most 512 tokens, cut on paragraph, then sentence, then token boundaries.
    """
    return _merge(_pieces(text))


def _content(sentence: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", sentence.lower()) if w not in _STOP}


def semantic_chunks(text: str) -> list[str]:
    """Semantic chunking.

    Args:
        text: the text to cut

    Returns:
        Chunks that break where neighbouring sentences share no content word (a lexical stand-in for an embedding-distance breakpoint), at most 512 tokens.
    """
    sentences = [s for s in _SENTENCE.split(" ".join(text.split())) if s.strip()]
    chunks: list[list[str]] = []
    for sent in sentences:
        if chunks and (_content(chunks[-1][-1]) & _content(sent)) and sum(len(s.split()) for s in chunks[-1]) + len(sent.split()) <= SIZE:
            chunks[-1].append(sent)
        else:
            chunks.append([sent])
    out: list[str] = []
    for group in chunks:
        joined = " ".join(group)
        out.extend([joined] if len(joined.split()) <= SIZE else _windows(joined.split(), SIZE, SIZE))
    return out


def page_chunks(pages: list[str]) -> list[str]:
    """One chunk per page.

    Args:
        pages: page texts in order

    Returns:
        The same pages as chunks.
    """
    return list(pages)
