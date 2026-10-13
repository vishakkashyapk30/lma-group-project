"""Structure-aware chunking: split by order part, then numbered paragraphs; merge short, split long at sentence ends, up to 400 tokens (plan §5.2). Naive baselines (B3) live in eval/baselines."""

from __future__ import annotations

from vakeel_sahayak.pipelines.text_utils import count_tokens, paragraph_blocks, paragraph_number, split_sentences
from vakeel_sahayak.schemas.enums import DocumentType, OrderPart
from vakeel_sahayak.schemas.store_rows import CaseChunk, ParagraphRecord

MIN_TOKENS = 40  # paragraphs shorter than this are merged with their neighbour (plan §5.2)
_PART_ORDER = (OrderPart.FACTS, OrderPart.DEFENSE, OrderPart.PROSECUTION, OrderPart.REASONING, OrderPart.OPERATIVE)


def split_long(text: str, max_tokens: int) -> list[str]:
    """Split a long paragraph at sentence ends into pieces of at most `max_tokens` (a single longer sentence is cut by words).

    Args:
        text: one paragraph
        max_tokens: size limit per piece

    Returns:
        Pieces in order.
    """
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for sentence in split_sentences(text):
        n = count_tokens(sentence)
        if n > max_tokens:  # one huge sentence: cut at word boundaries
            if current:
                pieces.append(" ".join(current))
                current, size = [], 0
            words = sentence.split()
            pieces.extend(" ".join(words[i : i + max_tokens]) for i in range(0, len(words), max_tokens))
            continue
        if size + n > max_tokens and current:
            pieces.append(" ".join(current))
            current, size = [], 0
        current.append(sentence)
        size += n
    if current:
        pieces.append(" ".join(current))
    return pieces


def _chunk_numbered(text: str, max_tokens: int, min_tokens: int) -> list[tuple[str, int | None]]:
    """Chunks of one part with the source paragraph number each starts at (None for unnumbered text)."""
    pieces: list[tuple[str, int | None]] = []
    for block in paragraph_blocks(text):
        number = paragraph_number(block)
        for piece in split_long(block, max_tokens) if count_tokens(block) > max_tokens else [block]:
            pieces.append((piece, number))
    chunks: list[tuple[str, int | None]] = []
    buffer, buffer_no = "", None
    for piece, number in pieces:
        if buffer:
            candidate = f"{buffer}\n{piece}"
            if count_tokens(candidate) > max_tokens:
                chunks.append((buffer, buffer_no))
                buffer, buffer_no = piece, number
            else:
                buffer = candidate
        else:
            buffer, buffer_no = piece, number
        if count_tokens(buffer) >= min_tokens:
            chunks.append((buffer, buffer_no))
            buffer, buffer_no = "", None
    if buffer:
        if chunks and count_tokens(f"{chunks[-1][0]}\n{buffer}") <= max_tokens:
            chunks[-1] = (f"{chunks[-1][0]}\n{buffer}", chunks[-1][1])
        else:
            chunks.append((buffer, buffer_no))
    return chunks


def chunk_text(text: str, max_tokens: int = 400, min_tokens: int = MIN_TOKENS) -> list[str]:
    """Chunks of one part: at numbered paragraphs, short ones merged with the following one, long ones split at sentence ends.

    Args:
        text: text of one order part
        max_tokens: size limit per chunk
        min_tokens: paragraphs below this size are merged (never past `max_tokens`)

    Returns:
        Chunk texts in order.
    """
    return [chunk for chunk, _ in _chunk_numbered(text, max_tokens, min_tokens)]


def chunk_order(text_parts: dict[OrderPart, str], max_tokens: int = 400) -> list[ParagraphRecord]:
    """Chunk an already-split order.

    Parts are chunked separately, in order-part order, so a chunk never mixes parts. `para` is the source paragraph
    number the chunk starts at (pieces of one long paragraph share it; a merged chunk takes its first paragraph's). For
    unnumbered text, or numbering that restarts, `para` continues from the previous chunk, so it never decreases along
    the order. Several chunks can share a `para`; the stores key them apart (`paragraph_index_rows`).

    Args:
        text_parts: part to text (missing or empty parts are skipped)
        max_tokens: size limit per chunk (configs/stores.yaml `chunk_max_tokens`)

    Returns:
        Paragraph records with `part`, `para` and `text`; `doc_id`, `court`, `date` and the other metadata are filled
        later by the builders.
    """
    records: list[ParagraphRecord] = []
    last = 0
    for part in _PART_ORDER:
        for text, number in _chunk_numbered(text_parts.get(part, ""), max_tokens, MIN_TOKENS):
            para = number if number is not None and number >= last and number >= 1 else last + 1
            last = para
            records.append(ParagraphRecord(doc_id="", para=para, court="", date="", part=part, text=text))
    return records


def chunk_case_document(
    pages: list[str],
    doc_type: DocumentType,
    boxes: list[list[list[float]]] | None = None,
    doc_id: str = "doc",
) -> list[CaseChunk]:
    """Structure-aware chunks of a client document with page and box (plan §4.4).

    Each page is chunked on its own, so a chunk keeps one page number. `boxes[p]` lists the layout boxes of page p in
    reading order, one per paragraph block; a chunk takes the box of its first block, or None when no box matches.

    Args:
        pages: text of each page (page numbers start at 1)
        doc_type: label assigned by Munshi
        boxes: optional per-page lists of [x0, y0, x1, y1] boxes, aligned with the paragraph blocks of the page
        doc_id: id of the document, used in chunk ids

    Returns:
        Chunks with page and box.
    """
    chunks: list[CaseChunk] = []
    for page_no, text in enumerate(pages, start=1):
        page_boxes = boxes[page_no - 1] if boxes and page_no <= len(boxes) else []
        block_index = 0
        for n, piece in enumerate(chunk_text(text), start=1):
            box = page_boxes[block_index] if block_index < len(page_boxes) else None
            block_index += max(1, len(paragraph_blocks(piece)))
            chunks.append(
                CaseChunk(chunk_id=f"{doc_id}-p{page_no}-c{n}", doc_id=doc_id, doc_type=doc_type, page=page_no, box=box, text=piece)
            )
    return chunks
