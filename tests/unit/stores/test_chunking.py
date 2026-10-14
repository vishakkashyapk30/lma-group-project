"""Structure-aware chunking (plan §5.2, §4.4).

Contract encoded for chunk_order(text_parts, max_tokens=400): within each order part, split at numbered paragraphs
('1.', '2.', ...); merge short paragraphs; split a long paragraph only at sentence ends; every chunk has at most 400
(whitespace) tokens; chunks never cross an OrderPart boundary; no text is lost.

ASSUMPTION: token = whitespace-separated token. ASSUMPTION: 'short' is well below 100 tokens (tests use 6-token paragraphs
as short and 150-token paragraphs as not short, and never probe the threshold between). ASSUMPTION: chunk text keeps the
paragraph number markers, so concatenating the chunk texts of a part gives back the input (whitespace-normalised).
ASSUMPTION: `para` of a chunk made from numbered paragraph k is k (or, equivalently here, a running count).

chunk_case_document(pages, doc_type, boxes): one or more CaseChunk per non-empty page, `page` is the 1-based source page,
`box` comes from `boxes` for that page (None when boxes is None), `doc_type` is kept.
"""

from __future__ import annotations

import re

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.stores._helpers import long_paragraph, norm, ntok, paragraph, sentence
from vakeel_sahayak.schemas.enums import DocumentType, OrderPart
from vakeel_sahayak.schemas.store_rows import CaseChunk, ParagraphRecord
from vakeel_sahayak.stores.chunking import chunk_case_document, chunk_order

NUMBER_START = re.compile(r"^\d+\.(\s|$)")
PARTS_IN_ORDER = [OrderPart.FACTS, OrderPart.DEFENSE, OrderPart.PROSECUTION, OrderPart.REASONING, OrderPart.OPERATIVE]


def joined(*paras: str) -> str:
    return " ".join(paras)


def text_of(chunks: list[ParagraphRecord], part: OrderPart) -> str:
    return " ".join(c.text for c in chunks if c.part == part)


# ------------------------------------------------------------------ numbered paragraphs
def test_each_long_numbered_paragraph_is_its_own_chunk():
    """Three 150-token numbered paragraphs give three chunks, each starting at its number."""
    parts = {OrderPart.REASONING: joined(*(paragraph(n, 150) for n in (1, 2, 3)))}
    chunks = chunk_order(parts)
    assert len(chunks) == 3
    assert [c.text.split()[0] for c in chunks] == ["1.", "2.", "3."]
    assert all(ntok(c.text) == 150 for c in chunks)


def test_para_numbers_follow_the_source_numbering():
    """ParagraphRecord.para is 1, 2, 3 for three unmerged paragraphs."""
    parts = {OrderPart.REASONING: joined(*(paragraph(n, 150) for n in (1, 2, 3)))}
    assert [c.para for c in chunk_order(parts)] == [1, 2, 3]


def test_para_numbers_increase_across_parts():
    """Numbering continues across parts of one order (facts 1-2, reasoning 3-4) and never goes backwards."""
    parts = {
        OrderPart.FACTS: joined(paragraph(1, 150), paragraph(2, 150)),
        OrderPart.REASONING: joined(paragraph(3, 150), paragraph(4, 150)),
    }
    chunks = chunk_order(parts)
    assert [c.para for c in chunks] == [1, 2, 3, 4]


def test_short_paragraphs_are_merged():
    """Three 6-token paragraphs are merged into one chunk (short ones are merged, plan §5.2)."""
    parts = {OrderPart.REASONING: joined(paragraph(1, 6), paragraph(2, 6), paragraph(3, 6))}
    chunks = chunk_order(parts)
    assert len(chunks) == 1
    assert norm(chunks[0].text) == norm(parts[OrderPart.REASONING])


def test_short_paragraph_between_long_ones_is_merged_into_a_neighbour():
    """[150, 6, 150] tokens: the short middle paragraph does not get its own chunk."""
    parts = {OrderPart.REASONING: joined(paragraph(1, 150), paragraph(2, 6), paragraph(3, 150))}
    chunks = chunk_order(parts)
    assert len(chunks) == 2
    assert all(ntok(c.text) <= 400 for c in chunks)
    assert sum(ntok(c.text) for c in chunks) == 306


def test_merging_short_paragraphs_never_exceeds_the_limit():
    """100 short paragraphs of 6 tokens (600 tokens) become several chunks, none above 400 tokens."""
    parts = {OrderPart.REASONING: joined(*(paragraph(n, 6) for n in range(1, 101)))}
    chunks = chunk_order(parts)
    assert len(chunks) >= 2
    assert all(ntok(c.text) <= 400 for c in chunks)
    assert norm(text_of(chunks, OrderPart.REASONING)) == norm(parts[OrderPart.REASONING])


def test_unnumbered_part_is_one_chunk():
    """An unnumbered operative order ('The application is allowed.') is a single chunk."""
    text = "The bail application is allowed on furnishing a personal bond."
    chunks = chunk_order({OrderPart.OPERATIVE: text})
    assert len(chunks) == 1 and chunks[0].part == OrderPart.OPERATIVE
    assert norm(chunks[0].text) == text


def test_empty_parts_produce_no_chunks():
    """Missing or blank parts yield no records."""
    assert chunk_order({}) == []
    assert chunk_order({OrderPart.FACTS: "", OrderPart.REASONING: "   \n "}) == []


def test_returns_paragraph_records():
    """Chunks are ParagraphRecord instances."""
    chunks = chunk_order({OrderPart.REASONING: paragraph(1, 50)})
    assert chunks and all(isinstance(c, ParagraphRecord) for c in chunks)


# ------------------------------------------------------------------ parts
def test_chunks_never_cross_a_part_boundary_and_carry_their_part():
    """Short paragraphs at the end of one part and the start of the next are not merged; `part` is set per chunk."""
    parts = {
        OrderPart.FACTS: joined(paragraph(1, 6), paragraph(2, 6)),
        OrderPart.DEFENSE: paragraph(3, 6),
        OrderPart.PROSECUTION: paragraph(4, 6),
        OrderPart.REASONING: joined(paragraph(5, 6), paragraph(6, 6)),
        OrderPart.OPERATIVE: "Bail granted.",
    }
    chunks = chunk_order(parts)
    assert [c.part for c in chunks] == PARTS_IN_ORDER
    for part, text in parts.items():
        assert norm(text_of(chunks, part)) == norm(text)


@pytest.mark.parametrize("part", PARTS_IN_ORDER)
def test_part_is_set_from_the_input_key(part):
    """Every chunk of a single-part order has that part."""
    chunks = chunk_order({part: joined(paragraph(1, 150), paragraph(2, 150))})
    assert len(chunks) == 2 and {c.part for c in chunks} == {part}


# ------------------------------------------------------------------ long paragraphs
def test_long_paragraph_is_split_only_at_sentence_ends():
    """A 20x30-token paragraph (600 tokens) splits into several pieces; each piece ends with a full stop and, after the first, starts at a sentence start."""
    text = long_paragraph(1, n_sentences=20, words_per_sentence=30)
    assert ntok(text) > 400
    chunks = chunk_order({OrderPart.REASONING: text})
    assert len(chunks) >= 2
    for c in chunks:
        assert ntok(c.text) <= 400
        assert c.text.rstrip().endswith(".")
    for c in chunks[1:]:
        assert c.text.split()[0] == "Sentence"
    assert norm(" ".join(c.text for c in chunks)) == norm(text)


def test_long_paragraph_pieces_stay_within_the_part_and_keep_para_number():
    """Pieces of paragraph 7 all carry para 7 (non-decreasing) and the reasoning part."""
    text = long_paragraph(7, n_sentences=20, words_per_sentence=30)
    chunks = chunk_order({OrderPart.REASONING: text})
    assert {c.para for c in chunks} == {7}
    assert {c.part for c in chunks} == {OrderPart.REASONING}


def test_exactly_400_tokens_is_not_split():
    """A 400-token paragraph fits in one chunk (boundary: limit is inclusive)."""
    chunks = chunk_order({OrderPart.REASONING: paragraph(1, 400)})
    assert len(chunks) == 1 and ntok(chunks[0].text) == 400


def test_401_tokens_is_split_at_a_sentence_end():
    """401 tokens in two sentences (201 + 200) is split between them."""
    text = "1. " + sentence(200, "a") + " " + sentence(200, "b")
    assert ntok(text) == 401
    chunks = chunk_order({OrderPart.REASONING: text})
    assert len(chunks) == 2
    assert chunks[0].text.rstrip().endswith("aend.")
    assert chunks[1].text.split()[0] == "Sentence"


def test_custom_max_tokens_is_honoured():
    """max_tokens=50 limits every chunk to 50 tokens."""
    text = long_paragraph(1, n_sentences=10, words_per_sentence=20)
    chunks = chunk_order({OrderPart.REASONING: text}, max_tokens=50)
    assert len(chunks) >= 4
    assert all(ntok(c.text) <= 50 for c in chunks)


# ------------------------------------------------------------------ property tests
@st.composite
def order_parts(draw):
    parts: dict[OrderPart, str] = {}
    number = 1
    for part in PARTS_IN_ORDER:
        if not draw(st.booleans()):
            continue
        paras = []
        for _ in range(draw(st.integers(1, 6))):
            n_sent = draw(st.integers(1, 25))
            words = draw(st.integers(3, 40))
            paras.append(f"{number}. " + " ".join(sentence(words, f"p{number}_") for _ in range(n_sent)))
            number += 1
        parts[part] = " ".join(paras)
    return parts


@settings(max_examples=60, deadline=None)
@given(order_parts())
def test_property_every_chunk_at_most_400_tokens(parts):
    """For any order, no chunk has more than 400 whitespace tokens."""
    chunks = chunk_order(parts)
    assert all(ntok(c.text) <= 400 for c in chunks)


@settings(max_examples=60, deadline=None)
@given(order_parts())
def test_property_text_preserved_per_part(parts):
    """For any order, the chunks of each part concatenate to that part's normalised text, and no empty chunks appear."""
    chunks = chunk_order(parts)
    assert all(c.text.strip() for c in chunks)
    for part, text in parts.items():
        assert norm(text_of(chunks, part)) == norm(text)
    assert {c.part for c in chunks} <= set(parts)


@settings(max_examples=60, deadline=None)
@given(order_parts())
def test_property_parts_stay_in_input_order_and_paras_do_not_decrease(parts):
    """Chunks come grouped by part in input order, and para numbers never decrease along the output."""
    chunks = chunk_order(parts)
    seen: list[OrderPart] = []
    for c in chunks:
        if not seen or seen[-1] != c.part:
            seen.append(c.part)
    assert seen == [p for p in parts if any(c.part == p for c in chunks)]
    paras = [c.para for c in chunks]
    assert paras == sorted(paras)


@settings(max_examples=40, deadline=None)
@given(order_parts())
def test_property_chunk_starts_at_a_number_or_a_sentence(parts):
    """A chunk starts at a paragraph number or (after a split) at a sentence start; never mid-sentence."""
    for c in chunk_order(parts):
        first = c.text.split()[0]
        assert NUMBER_START.match(first + " ") or first == "Sentence"


# ------------------------------------------------------------------ client documents
def test_case_document_one_chunk_per_short_page_with_one_based_page():
    """Each page of a client document yields at least one chunk tagged with its 1-based page number."""
    pages = ["FIR No. 123/2024 registered at PS Sample.", "Arrest memo dated 2024-03-01.", "Remand order."]
    chunks = chunk_order_case(pages)
    assert all(isinstance(c, CaseChunk) for c in chunks)
    assert sorted({c.page for c in chunks}) == [1, 2, 3]
    for i, page in enumerate(pages, start=1):
        assert norm(" ".join(c.text for c in chunks if c.page == i)) == page


def chunk_order_case(pages, doc_type=DocumentType.FIR, boxes=None):
    return chunk_case_document(pages, doc_type, boxes)


@pytest.mark.parametrize("doc_type", [DocumentType.FIR, DocumentType.BAIL_ORDER, DocumentType.CUSTODY_CERTIFICATE])
def test_case_document_keeps_doc_type(doc_type):
    """Every chunk carries the doc_type passed in."""
    chunks = chunk_case_document(["Some page text.", "More text."], doc_type)
    assert chunks and {c.doc_type for c in chunks} == {doc_type}


def test_case_document_without_boxes_has_no_box():
    """boxes=None gives box=None on every chunk."""
    chunks = chunk_case_document(["Some page text."], DocumentType.FIR, None)
    assert chunks and all(c.box is None for c in chunks)


def test_case_document_box_copied_from_boxes_argument():
    """With one box on page 1 and two on page 2, a one-paragraph page's chunk gets that page's box (copied)."""
    pages = ["Arrested on 2024-03-01.", "Remanded to judicial custody."]
    boxes = [[[10.0, 20.0, 300.0, 40.0]], [[11.0, 22.0, 310.0, 44.0]]]
    chunks = chunk_case_document(pages, DocumentType.ARREST_MEMO, boxes)
    by_page = {c.page: c for c in chunks}
    assert by_page[1].box == [10.0, 20.0, 300.0, 40.0]
    assert by_page[2].box == [11.0, 22.0, 310.0, 44.0]


def test_case_document_box_belongs_to_the_chunks_page():
    """A chunk's box is always one of the boxes given for its own page, never from another page."""
    pages = ["1. First paragraph of the remand order stating the grounds. " * 3, "2. Second page paragraph about custody. " * 3]
    boxes = [[[0.0, 0.0, 100.0, 50.0], [0.0, 60.0, 100.0, 110.0]], [[5.0, 5.0, 105.0, 55.0]]]
    chunks = chunk_case_document(pages, DocumentType.REMAND_ORDER, boxes)
    for c in chunks:
        assert c.box in boxes[c.page - 1]


def test_case_document_long_page_gives_several_chunks_within_limit():
    """A 1000-token page is split into at least three chunks of at most 400 tokens, all on page 1."""
    page = " ".join(sentence(25, f"x{i}_") for i in range(40))
    chunks = chunk_case_document([page], DocumentType.AFFIDAVIT)
    assert len(chunks) >= 3
    assert {c.page for c in chunks} == {1}
    assert all(ntok(c.text) <= 400 for c in chunks)
    assert norm(" ".join(c.text for c in chunks)) == norm(page)


def test_case_document_chunk_ids_are_unique():
    """chunk_id is unique within a document."""
    chunks = chunk_case_document(["Page one text.", "Page two text.", "Page three text."], DocumentType.FIR)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)) and all(ids)
