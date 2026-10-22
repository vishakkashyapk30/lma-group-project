"""Hierarchy-ranked choice of the pages to re-read for a missing checklist item (variant S7 / A11a, `Switches.munshi_gap_policy='hierarchy'`).

Paper (adapted, not reproduced): Ma et al., "IntrAgent", ACL 2026 (Long Papers), pp. 674-715, https://aclanthology.org/2026.acl-long.29/ (confirmed on the
Anthology by the literature review, `docs/literature-review-and-usage.md`). IntrAgent reads STEM papers by first building an intent-aware, hierarchical outline of
the document and then reading the sections that best answer a question, instead of scanning in order. Related, cited in the review only: Su et al., DRAGIN,
ACL 2024, https://aclanthology.org/2024.acl-long.702 (decides when and what to retrieve from the model's own uncertainty).

What we took: the idea of choosing WHERE to look from a document hierarchy before reading, ranked by relevance to the open question (here: the missing checklist
item), and stopping when the field is filled. What we changed, and why: (1) our "hierarchy" is the case page index, three levels that already exist: the
document type of the page's document (level 1), the page's heading lines (level 2), and the page's position inside its document (level 3), plus a
TF-IDF overlap with the item's name; there is no model-built outline, because a bail file is short and typed. (2) The unit that is read is a page and the "reading" is
a re-read with a stronger route (the vision model), which costs one model call per page; IntrAgent's reading is cheap text. (3) The weights below are an untuned
assumption (TODO: tune on the dev bundles). (4) The sequential policy it is compared with is today's: weak OCR pages of the expected document types, in file order.

Differences from sequential, by construction: hierarchy may re-read a weak page of ANY document type (a mislabelled or unlabelled page whose heading matches), orders
the candidates by evidence instead of by file order, and re-reads nothing when no candidate reaches `MIN_SCORE`. Both policies stop at the first re-read that
shows the item's cue and re-read at most `gaps.MAX_REREAD_PAGES` pages for one item.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vakeel_sahayak.ingestion.checklist import ITEM_NAMES
from vakeel_sahayak.ingestion.pageindex import IndexedPage, PageIndex

W_TYPE, W_HEADING, W_TEXT, W_POSITION = 0.50, 0.25, 0.15, 0.10  # untuned assumptions
MIN_SCORE = 0.30  # below this a page is not worth a vision call
HEADING_LINES = 3  # the first non-empty lines of a page are its heading
OTHER_TYPE_SCORE = 0.2  # a page of a document with no type may still be the one (its heading must then show it)


@dataclass(frozen=True)
class RankedPage:
    """A candidate page with its score and the parts of it."""

    page: IndexedPage
    score: float
    parts: dict[str, float] = field(default_factory=dict)


def _heading(page: IndexedPage) -> list[str]:
    return [ln for ln in page.text.split("\n") if ln.strip()][:HEADING_LINES]


def rank_pages(item: str, index: PageIndex, likely_types: set[str], cue, thresholds: dict[str, float] | None = None) -> list[RankedPage]:
    """Weak pages ordered by how likely they hold the missing item (best first, pages under `MIN_SCORE` left out).

    Args:
        item: checklist key ('first_remand', ...)
        index: the case's page index
        likely_types: document types where the item is expected (`gaps.LIKELY_TYPES[item]`)
        cue: compiled pattern of what the item looks like in text (`gaps.GAP_CUES[item]`)
        thresholds: dev-tuned values (the weak-page bar)

    Returns:
        RankedPage list; deterministic (ties by file, then page).
    """
    from vakeel_sahayak.ingestion.gaps import is_weak

    weak = [p for p in index.pages if is_weak(p, thresholds)]
    if not weak:
        return []
    firsts: dict[str | None, int] = {}
    for p in index.pages:
        firsts[p.doc_id] = min(p.page, firsts.get(p.doc_id, p.page))
    overlap = {(p.file, p.page): s for p, s in index.search(ITEM_NAMES[item], k=max(1, len(index.pages)))}
    top = max(overlap.values(), default=0.0) or 1.0
    ranked = []
    for p in weak:
        type_score = 1.0 if p.doc_type in likely_types else OTHER_TYPE_SCORE if p.doc_type in (None, "OTHER") else 0.0
        heading = 1.0 if any(cue.search(ln) for ln in _heading(p)) else 0.5 if cue.search(p.text) else 0.0
        text = overlap.get((p.file, p.page), 0.0) / top
        position = 1.0 / (1 + p.page - firsts.get(p.doc_id, p.page)) if p.doc_id else 0.0
        parts = {"type": type_score, "heading": heading, "text": round(text, 4), "position": round(position, 4)}
        score = round(W_TYPE * type_score + W_HEADING * heading + W_TEXT * text + W_POSITION * position, 4)
        if score >= MIN_SCORE:
            ranked.append(RankedPage(p, score, parts))
    return sorted(ranked, key=lambda r: (-r.score, r.page.file, r.page.page))


def oracle_regret(record: dict) -> int:
    """Re-reads beyond the least an oracle needs for one gap record (`reads` minus 1 when a re-read found the item, else minus 0).

    The oracle is a lower bound: it knows which page holds the item, so it reads that page alone; when no re-read found the item the bound is 0 reads
    (the item may sit on a page no candidate list contained, so the bound is not tight).
    """
    return int(record.get("reads", 0)) - (1 if record.get("resolved_by") == "reread" else 0)


def summarise(records: list[dict]) -> dict:
    """Signals over a run's gap records: pages re-read, gaps resolved by re-reading, resolved per page read, total oracle regret.

    Args:
        records: the records `gaps.resolve_gap` appends to its `signals` list (one per missing item)

    Returns:
        dict with `policy`, `items`, `pages_reread`, `gaps_resolved_by_reread`, `gaps_resolved`, `resolved_per_page_read` (None without re-reads),
        `oracle_regret`, and the per-item `records`.
    """
    reads = sum(int(r.get("reads", 0)) for r in records)
    by_reread = sum(1 for r in records if r.get("resolved_by") == "reread")
    return {
        "policy": records[0]["policy"] if records else None,
        "items": len(records),
        "pages_reread": reads,
        "gaps_resolved_by_reread": by_reread,
        "gaps_resolved": sum(1 for r in records if r.get("resolved_by")),
        "resolved_per_page_read": round(by_reread / reads, 4) if reads else None,
        "oracle_regret": sum(oracle_regret(r) for r in records),
        "records": records,
    }
