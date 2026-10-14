"""Naive chunking variants of B3 and the retrieval-only analysis (plan §15.3 B3, §15.7 configurations 1)."""

from hypothesis import given, settings
from hypothesis import strategies as st

from vakeel_sahayak.eval.baselines.chunking_variants import (
    fixed_512,
    fixed_512_overlap,
    page_chunks,
    recursive_split,
    semantic_chunks,
)

TEXT = " ".join(f"w{i}" for i in range(1300))  # 1,300 whitespace tokens


def n_tokens(chunk: str) -> int:
    return len(chunk.split())


def test_fixed_512_sizes():
    """Fixed 512-token chunks: 512, 512, 276 for a 1,300-token text; nothing lost, nothing duplicated."""
    chunks = fixed_512(TEXT)
    assert [n_tokens(c) for c in chunks] == [512, 512, 276]
    assert " ".join(chunks).split() == TEXT.split()


def test_fixed_512_with_20_percent_overlap():
    """512-token chunks with 20% overlap (ASSUMPTION: 102 tokens): every chunk <= 512 tokens, neighbours share exactly 102
    tokens, and the union covers the whole text."""
    chunks = fixed_512_overlap(TEXT)
    assert all(n_tokens(c) <= 512 for c in chunks)
    for a, b in zip(chunks, chunks[1:]):
        assert a.split()[-102:] == b.split()[:102]
    assert set(" ".join(chunks).split()) == set(TEXT.split())
    assert len(chunks) >= 3


def test_page_chunks_one_per_page():
    """Page chunking keeps one chunk per page, in order."""
    pages = ["page one text", "page two text", "page three text"]
    assert page_chunks(pages) == pages


def test_recursive_split_respects_size_and_content():
    """Recursive splitter: chunks within 512 tokens (ASSUMPTION), split on paragraph/sentence separators first."""
    text = "\n\n".join(" ".join(f"s{p}w{i}" for i in range(200)) + "." for p in range(5))
    chunks = recursive_split(text)
    assert all(n_tokens(c) <= 512 for c in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())


def test_semantic_chunks_cover_the_text():
    """Semantic chunking returns non-empty chunks whose concatenation preserves the words."""
    text = "Bail was granted. The co-accused had the same role. Separately, the weather was fine. Custody was long."
    chunks = semantic_chunks(text)
    assert chunks and all(c.strip() for c in chunks)
    assert " ".join(" ".join(chunks).split()) == " ".join(text.split())


@settings(max_examples=40, deadline=None)
@given(n=st.integers(1, 3000))
def test_property_fixed_512_never_exceeds_512(n):
    """No fixed chunk exceeds 512 tokens and the chunk count is ceil(n/512)."""
    chunks = fixed_512(" ".join("t" for _ in range(n)))
    assert all(n_tokens(c) <= 512 for c in chunks)
    assert len(chunks) == -(-n // 512)
