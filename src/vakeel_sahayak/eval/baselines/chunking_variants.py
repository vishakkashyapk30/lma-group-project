"""Chunking variants for B3 and the retrieval-only analysis (plan §15.3, §15.7); `evaluate_strategy` / `compare_strategies` are the S16 retrieval-only hook (strategies of `stores.chunk_strategies`).

Tokens are whitespace-separated words (the same estimate as `pipelines.text_utils.count_tokens`). Every variant keeps all the words of
its input in order (the overlap variant repeats the overlap on purpose), so no text is lost and nothing is invented.
"""

from __future__ import annotations

import re
from typing import Any

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


# ----------------------------------------------------------------------------------------------- retrieval-only hook (S16)


def evaluate_strategy(strategy: str, docs: list[dict[str, Any]], queries: list[dict[str, Any]], *, ks: tuple[int, ...] = (5, 10, 20),
                      embedder: Any = None, max_tokens: int = 400) -> dict[str, Any]:
    """Recall@k of gold documents when a corpus is chunked with `strategy` (retrieval only: no agent, no drafting, no real store).

    Builds a small in-memory `HybridIndex` over the chunks of `docs`, runs each query and counts, at document level, how many gold documents appear among the
    first k distinct documents (the G2 convention of plan M10). Deterministic with the default hashed embedder. For `late` the chunk vectors come from
    `stores.chunk_strategies.LateChunkEmbedder` (per document; `late_mode` says whether token pooling or the blend approximation was used).

    Args:
        strategy: one of `stores.chunk_strategies.STRATEGIES`
        docs: `{doc_id, court, date, parts: {OrderPart: text}}` rows
        queries: `{query, gold: [doc_id, ...], before: optional date}` rows
        ks: cut-offs
        embedder: an embedder (default: the offline hashed one)
        max_tokens: size limit of the structure chunker

    Returns:
        `{strategy, queries, recall: {k: mean recall}, mrr, index: {chunks, tokens, mean_tokens}}` (+ `late_mode` for `late`).
    """
    from vakeel_sahayak.models.embeddings import HashedEmbeddingClient
    from vakeel_sahayak.pipelines.text_utils import count_tokens
    from vakeel_sahayak.stores.chunk_strategies import LateChunkEmbedder, chunk_order_with
    from vakeel_sahayak.stores.hybrid import HybridIndex, IndexRow

    base = embedder or HashedEmbeddingClient()
    late = LateChunkEmbedder(base) if strategy == "late" else None
    index = HybridIndex(":memory:", embedder=late or base)
    rows: list[IndexRow] = []
    for doc in docs:
        records = chunk_order_with(strategy, doc["parts"], max_tokens)
        if late is not None:
            late.prepare("\n".join(str(t) for t in doc["parts"].values()), [r.text for r in records])
        for i, r in enumerate(records):
            rows.append(IndexRow(key=f"{doc['doc_id']}#{i}", text=r.text, payload={"doc_id": doc["doc_id"], "para": r.para, "part": str(getattr(r.part, "value", r.part))},
                                 date=doc.get("date"), court=doc.get("court"), part=str(getattr(r.part, "value", r.part))))
    index.add(rows)
    sizes = [count_tokens(r.text) for r in rows]
    recall = {k: 0.0 for k in ks}
    rr = 0.0
    for q in queries:
        hits = index.search(q["query"], before=q.get("before"), k=max(ks) * 5)
        order = list(dict.fromkeys(h.payload["doc_id"] for h in hits))
        gold = set(q.get("gold") or [])
        for k in ks:
            recall[k] += len(gold & set(order[:k])) / len(gold) if gold else 0.0
        rank = next((i for i, d in enumerate(order, start=1) if d in gold), None)
        rr += 1.0 / rank if rank else 0.0
    index.close()
    n = max(1, len(queries))
    out: dict[str, Any] = {
        "strategy": strategy, "queries": len(queries), "recall": {str(k): round(v / n, 6) for k, v in recall.items()}, "mrr": round(rr / n, 6),
        "index": {"chunks": len(rows), "tokens": sum(sizes), "mean_tokens": round(sum(sizes) / len(sizes), 3) if sizes else 0.0},
    }
    if late is not None:
        out["late_mode"] = late.mode
    return out


def compare_strategies(docs: list[dict[str, Any]], queries: list[dict[str, Any]], *, ks: tuple[int, ...] = (5, 10, 20), strategies: tuple[str, ...] | None = None,
                       embedder: Any = None) -> list[dict[str, Any]]:
    """`evaluate_strategy` for each strategy (default: all of them, structure first), in a fixed order: the table of plan Table 2 row 'chunker choice'."""
    from vakeel_sahayak.stores.chunk_strategies import STRATEGIES

    return [evaluate_strategy(s, docs, queries, ks=ks, embedder=embedder) for s in (strategies or STRATEGIES)]
