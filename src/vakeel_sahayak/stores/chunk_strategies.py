"""S16 / S16b: selectable chunking strategies (`Switches.chunking`), evaluation plan 3.3 (S16 proposition units, S16b late chunking, B3 naive chunkers).

`structure` is the control and the current behaviour: `stores.chunking.chunk_order` (order part, then numbered paragraphs, at most 400 tokens). The
others are alternatives for the retrieval-only runner and B3 (`eval/baselines/chunking_variants.evaluate_strategy`); the real stores are never rebuilt by this module.

| Strategy | Cuts | Source |
|---|---|---|
| `structure` | numbered paragraphs, short ones merged, long ones split at sentence ends | plan 5.2 (control) |
| `fixed` | fixed 512-token windows | B3 (`eval/baselines/chunking_variants.fixed_512`) |
| `recursive` | paragraph, then sentence, then token boundaries, merged up to 512 | B3 |
| `semantic` | breaks where neighbouring sentences share no content word (a lexical stand-in for embedding-distance breakpoints) | B3 |
| `page` | one chunk per part (an order has no pages; a client document keeps its pages in `chunk_case_document`) | B3 |
| `proposition` | atomic clause-level units, one per sentence clause, each remembering its paragraph | S16 |
| `late` | the structure boundaries, but each chunk is embedded with the context of the whole document (`LateChunkEmbedder`) | S16b |

Papers (what was taken, what changed; none of this is a reproduction):

* Chen et al., "Dense X Retrieval: What Retrieval Granularity Should We Use?", EMNLP 2024 (main), https://aclanthology.org/2024.emnlp-main.845 :
  index propositions (minimal, self-contained factoids) instead of passages. Taken: the unit of indexing and the paragraph it came from. Changed:
  the paper's Propositionizer is a fine-tuned Flan-T5-large; here a rule splits a paragraph into sentences and a sentence at semicolons and at
  ', and' / ', but' / ', while' / ', whereas' when both halves have enough words, losing no word and rewriting none (no decontextualisation).
  Pass `propositionizer=` (a callable, for example one backed by a hosted model) to use a model.
* Gunther, Mohr, Williams, Wang and Xiao, "Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models", arXiv 2409.04701 (2024,
  preprint; page checked): embed the whole text with a long-context model first and pool the token vectors inside each chunk span afterwards.
  Taken: pooling after contextualisation. Changed: true late chunking needs token vectors; `LateChunkEmbedder` uses them when the base embedder offers
  `embed_tokens(text)`, and otherwise blends each chunk's vector with the whole document's vector (`BLEND`), flagged `mode='approximation'`. The offline hashed embedder
  has no token vectors, so the offline run is the approximation. BGE-M3's token vectors are not wired in here (models/ is outside this change).
* Qu, Tu and Bao, "Is Semantic Chunking Worth the Computational Cost?", Findings of NAACL 2025, https://aclanthology.org/2025.findings-naacl.114/ (the evaluation
  plan links a preview mirror): no consistent gain of semantic over fixed chunks. Taken: fixed, recursive and semantic as the naive baselines and the lexical stand-in for the semantic breakpoint.

Every strategy returns the same `ParagraphRecord` rows as `chunk_order`, so a store builder or the retrieval-only runner treats them alike.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Sequence
from typing import Any

from vakeel_sahayak.pipelines.text_utils import count_tokens, paragraph_blocks, paragraph_number, split_sentences
from vakeel_sahayak.schemas.enums import OrderPart
from vakeel_sahayak.schemas.store_rows import ParagraphRecord
from vakeel_sahayak.stores.chunking import _PART_ORDER, chunk_order

STRATEGIES: tuple[str, ...] = ("structure", "proposition", "late", "fixed", "recursive", "semantic", "page")
BLEND = 0.3  # weight of the whole-document vector in the late-chunking approximation
MIN_CLAUSE_WORDS = 5  # a clause must have this many words on both sides of a split
_CLAUSE_SPLIT = re.compile(r";\s+|,\s+(?=(?:and|but|while|whereas|however|therefore)\b)", re.IGNORECASE)

Propositionizer = Callable[[str], list[str]]


def strategy_for(switches: Any) -> str:
    """The chunking strategy a switch set selects (`Switches.chunking`; 'structure' by default)."""
    return str(getattr(switches, "chunking", "structure"))


def propositions(paragraph: str) -> list[str]:
    """Rule-based propositions of one paragraph: sentences, split at semicolons and clause conjunctions, no word lost or changed.

    Args:
        paragraph: one paragraph (its number marker stays with the first proposition)

    Returns:
        Units in order; joined with spaces they give back the paragraph's words.
    """
    out: list[str] = []
    for sentence in split_sentences(paragraph):
        pieces: list[str] = []
        start = 0
        for m in _CLAUSE_SPLIT.finditer(sentence):
            left, right = sentence[start : m.start()], sentence[m.end() :]
            if count_tokens(left) >= MIN_CLAUSE_WORDS and count_tokens(right) >= MIN_CLAUSE_WORDS:
                pieces.append((left + (";" if m.group(0).startswith(";") else ",")).strip())
                start = m.end()
        pieces.append(sentence[start:].strip())
        out.extend(p for p in pieces if p)
    return out


def _baseline(strategy: str) -> Callable[[str], list[str]]:
    from vakeel_sahayak.eval.baselines import chunking_variants as cv  # lazy: the naive chunkers live with B3

    return {"fixed": cv.fixed_512, "recursive": cv.recursive_split, "semantic": cv.semantic_chunks, "page": lambda text: cv.page_chunks([text]) if text.strip() else []}[strategy]


def chunk_order_with(
    strategy: str, text_parts: dict[OrderPart, str], max_tokens: int = 400, *, propositionizer: Propositionizer | None = None
) -> list[ParagraphRecord]:
    """Chunk an already-split order with the chosen strategy.

    Args:
        strategy: one of `STRATEGIES`
        text_parts: part to text
        max_tokens: size limit of the structure chunker (and of `late`, which shares its boundaries)
        propositionizer: for `proposition`: a callable paragraph -> units (default: the rule-based `propositions`)

    Returns:
        Paragraph records. `structure` and `late` are exactly `chunk_order`'s; the others keep `part` and a non-decreasing `para`.

    Raises:
        ValueError: unknown strategy.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown chunking strategy {strategy!r}: use one of {', '.join(STRATEGIES)}")
    if strategy in ("structure", "late"):
        return chunk_order(text_parts, max_tokens)
    records: list[ParagraphRecord] = []
    last = 0
    for part in _PART_ORDER:
        text = text_parts.get(part, "")
        if not text.strip():
            continue
        if strategy == "proposition":
            split = propositionizer or propositions
            units = []
            for block in paragraph_blocks(text):
                number = paragraph_number(block)
                units.extend((u, number) for u in split(block))
        else:
            units = [(c, None) for c in _baseline(strategy)(text)]
        for unit, number in units:
            para = number if number is not None and number >= last and number >= 1 else (last if strategy == "proposition" and last else last + 1)
            last = para
            records.append(ParagraphRecord(doc_id="", para=para, court="", date="", part=part, text=unit))
    return records


class LateChunkEmbedder:
    """An embedder whose chunk vectors carry the context of the whole document (S16b, late chunking).

    Wraps a base embedder (`name`, `dim`, `embed`). `prepare(document, chunks)` computes a vector for each chunk text: with token vectors from the base
    (`embed_tokens(text) -> (spans, vectors)`, spans are character offsets) it mean-pools the vectors inside the chunk's span (true late chunking);
    without them it blends the chunk's own vector with the document's (`BLEND`). `embed(texts)` then returns the prepared vector of a known chunk text and the base
    vector of anything else (a query). A chunk text that occurs in two documents keeps the vector of the later one: prepare one document per index when that matters.
    """

    def __init__(self, base: Any, blend: float = BLEND) -> None:
        self.base, self.blend = base, blend
        self.dim = base.dim
        self.name = f"late({base.name})"
        self.mode = "token_pooling" if hasattr(base, "embed_tokens") else "approximation"
        self._vectors: dict[str, list[float]] = {}

    def prepare(self, document: str, chunks: Sequence[str]) -> int:
        """Compute and remember the contextual vector of each chunk of `document`; returns how many were prepared."""
        if not chunks:
            return 0
        if self.mode == "token_pooling":
            spans, vectors = self.base.embed_tokens(document)
            cursor = 0
            for chunk in chunks:
                start = document.find(chunk, cursor)
                if start < 0:
                    start = document.find(chunk)
                end = start + len(chunk)
                inside = [v for (s, e), v in zip(spans, vectors, strict=False) if start >= 0 and s >= start and e <= end]
                self._vectors[chunk] = _unit([sum(col) for col in zip(*inside, strict=False)]) if inside else self.base.embed([chunk])[0]
                cursor = max(cursor, end) if start >= 0 else cursor
            return len(chunks)
        whole = self.base.embed([document])[0]
        for chunk, own in zip(chunks, self.base.embed(list(chunks)), strict=True):
            self._vectors[chunk] = _unit([(1 - self.blend) * a + self.blend * b for a, b in zip(own, whole, strict=True)])
        return len(chunks)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Prepared vectors for known chunk texts, the base embedder's for the rest."""
        unknown = [t for t in texts if t not in self._vectors]
        fresh = dict(zip(unknown, self.base.embed(unknown), strict=True)) if unknown else {}
        return [self._vectors.get(t) or fresh[t] for t in texts]


def _unit(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec
