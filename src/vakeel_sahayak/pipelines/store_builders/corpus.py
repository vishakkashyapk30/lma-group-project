"""Read Open India Law-style order records and process them once for all store builders (plan §2, §5.2, §5.3).

**Expected input**: `<interim_dir>/orders.jsonl`, one JSON object per order (UTF-8). Field names are matched
case-insensitively against these aliases; every field except the id and the text is optional.

| meaning | accepted keys |
|---|---|
| id (required) | `doc_id`, `id`, `case_id` |
| full order text (required) | `text`, `full_text`, `judgment`, `content` |
| court | `court`, `court_name` ('Delhi High Court', 'Supreme Court of India') |
| decision date (required to enter a store) | `date`, `decision_date`, `judgment_date` (ISO, 'dd-mm-yyyy', '12 March 2023') |
| outcome | `outcome` ('granted', 'rejected'...); read from the operative order when absent |
| title | `title`, `case_name`, `case_title` ('A v. State of B') |
| the order's own citations | `neutral_citation`, `citations` (list or string) |
| bench size | `bench_size` (int), or `bench` (list of judges) |
| offence date | `offence_date` (ISO or written date) |
| FIR | `fir` (`{police_station, number, year, district}`) or `fir_key` |
| pre-split parts | `parts`: `{facts, defense_submissions, prosecution_submissions, reasoning, operative_order}` (skips the splitter) |

Optional `<interim_dir>/citation_edges.jsonl` holds already-resolved `CitationEdge` rows (the output of the citation-graph
pipeline); they are added to the edges found by resolving the citations in the reasoning paragraphs.

Records without an id or text, or without a parseable date, are skipped and counted in the build report (an undated
order cannot obey the 'before' rule). Everything else missing only narrows what the stores can filter on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.citation_graph.authority import configured_weights
from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations, parse_citation
from vakeel_sahayak.pipelines.citation_graph.graph import CitationGraph, NodeMeta, court_level_of
from vakeel_sahayak.pipelines.citation_graph.treatment import (
    TreatmentLabeler,
    agree_treatment,
    label_treatment,
    strongest,
)
from vakeel_sahayak.pipelines.order_facts import fact_signature
from vakeel_sahayak.pipelines.order_splitter import PART_ORDER, analyse_split, infer_outcome
from vakeel_sahayak.pipelines.section_extract import charged_sections, expand_family, extract_sections
from vakeel_sahayak.pipelines.store_builders.fast_index import FastCitationIndex as CitationIndex
from vakeel_sahayak.pipelines.text_utils import normalise_date, read_jsonl, split_sentences
from vakeel_sahayak.schemas.enums import OrderPart, Treatment
from vakeel_sahayak.schemas.store_rows import CitationEdge, FactSignature, ParagraphRecord
from vakeel_sahayak.stores.chunking import chunk_order

ORDERS_FILE = "orders.jsonl"
CITATION_EDGES_FILE = "citation_edges.jsonl"
_ID = ("doc_id", "id", "case_id")
_TEXT = ("text", "full_text", "judgment", "content")
_COURT = ("court", "court_name")
_DATE = ("date", "decision_date", "judgment_date")
_TITLE = ("title", "case_name", "case_title")


@dataclass
class Order:
    """A normalised input record."""

    doc_id: str
    text: str
    date: str
    court: str = "unknown"
    outcome: str | None = None
    title: str | None = None
    citations: list[str] = field(default_factory=list)
    bench_size: int | None = None
    offence_date: str | None = None
    parts: dict[OrderPart, str] | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessedOrder:
    """An order after splitting, chunking and tagging (everything except citation-derived fields is final)."""

    order: Order
    parts: dict[OrderPart, str]
    clean_split: bool
    outcome: str | None
    paragraphs: list[ParagraphRecord]
    signature: FactSignature
    section_family: list[str]


@dataclass
class Corpus:
    """All processed orders, the citation graph over them and a report of what was read, skipped and resolved."""

    orders: list[ProcessedOrder]
    graph: CitationGraph
    report: dict[str, Any]


def _first(raw: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """First non-empty value among alias keys (case-insensitive)."""
    lowered = {k.lower(): v for k, v in raw.items()}
    for key in keys:
        if lowered.get(key) not in (None, ""):
            return lowered[key]
    return None


def normalise_order(raw: dict[str, Any]) -> tuple[Order | None, str | None]:
    """Normalise one input record.

    Returns:
        (Order, None), or (None, reason) with reason one of 'no_id', 'no_text', 'no_date'.
    """
    doc_id, text = _first(raw, _ID), _first(raw, _TEXT)
    if doc_id is None:
        return None, "no_id"
    if not isinstance(text, str) or not text.strip():
        return None, "no_text"
    date = normalise_date(_first(raw, _DATE))
    if not date:
        return None, "no_date"
    cites = _first(raw, ("citations",))
    blob = [str(_first(raw, ("neutral_citation",)) or ""), *(cites if isinstance(cites, list) else [str(cites or "")])]
    bench = _first(raw, ("bench_size",))
    bench_list = _first(raw, ("bench",))
    parts_raw = raw.get("parts")
    parts = None
    if isinstance(parts_raw, dict):
        parts = {OrderPart(k): str(v) for k, v in parts_raw.items() if k in {p.value for p in OrderPart}} or None
    outcome = _first(raw, ("outcome",))
    return (
        Order(
            doc_id=str(doc_id), text=text, date=date, court=str(_first(raw, _COURT) or "unknown"),
            outcome=str(outcome).lower() if outcome else None, title=_first(raw, _TITLE),
            citations=[c for c in blob if c], bench_size=int(bench) if str(bench or "").isdigit() else (len(bench_list) if isinstance(bench_list, list) else None),
            offence_date=normalise_date(_first(raw, ("offence_date",))), parts=parts, raw=raw,
        ),
        None,
    )  # fmt: skip


def load_orders(interim_dir: str) -> tuple[list[Order], dict[str, int]]:
    """Read `<interim_dir>/orders.jsonl`.

    Returns:
        (orders, skipped counts by reason). A missing file gives no orders.
    """
    orders: list[Order] = []
    skipped: dict[str, int] = {}
    for raw in read_jsonl(Path(interim_dir) / ORDERS_FILE):
        order, reason = normalise_order(raw)
        if order:
            orders.append(order)
        else:
            skipped[reason or "invalid"] = skipped.get(reason or "invalid", 0) + 1
    return orders, skipped


def _process_order(order: Order, family_of, max_tokens: int) -> ProcessedOrder:  # noqa: ANN001
    """Split, chunk and tag one order (no citation-derived fields yet)."""
    from vakeel_sahayak.pipelines.factor_tagger import tag_factors

    if order.parts:
        parts, clean = {p: order.parts.get(p, "") for p in PART_ORDER}, all(order.parts.get(p, "").strip() for p in PART_ORDER)
    else:
        result = analyse_split(order.text)
        parts, clean = result.parts, result.clean
    charged = charged_sections(extract_sections(parts.get(OrderPart.FACTS, ""))) or charged_sections(extract_sections(order.text))
    paragraphs = chunk_order(parts, max_tokens)
    outcome = order.outcome or infer_outcome(parts.get(OrderPart.OPERATIVE, ""))
    for rec in paragraphs:
        own = extract_sections(rec.text)
        sections = list(dict.fromkeys([*own, *charged]))
        rec.doc_id, rec.court, rec.date, rec.outcome = order.doc_id, order.court, order.date, outcome
        rec.sections, rec.section_family = sections, family_of(sections)
        rec.factors = tag_factors(rec.text)
    signature = fact_signature(parts.get(OrderPart.FACTS, "") or order.text, order.date)
    return ProcessedOrder(order, parts, clean, outcome, paragraphs, signature, family_of(charged))


def _add_resolved_edges(
    graph: CitationGraph, processed: list[ProcessedOrder], path: Path, excluded: set[str], report: dict[str, Any]
) -> None:
    """Add the already-resolved `CitationEdge` rows of `citation_edges.jsonl` (output of the citation-graph pipeline).

    An edge into or out of an excluded order is dropped (it would leak the order's existence). A cited or citing judgment
    outside the corpus stays in the graph with the court level the edge records for the citing side. The edge sets
    `cites` on the citing order's reasoning paragraphs that mention the cited judgment or the edge sentence, or on all
    of them when none does (the edge is then known only at order level).
    """
    by_doc = {p.order.doc_id: p for p in processed}
    n = 0
    for raw in read_jsonl(path):
        edge = CitationEdge.model_validate(raw)
        if edge.citing_doc_id in excluded or edge.cited_doc_id in excluded:
            continue
        if edge.citing_doc_id not in graph.nodes:
            graph.nodes[edge.citing_doc_id] = NodeMeta(edge.citing_doc_id, court_level=edge.court_level or "OTHER")
        graph.add_edge(edge)
        n += 1
        citing = by_doc.get(edge.citing_doc_id)
        if citing:
            reasoning = [r for r in citing.paragraphs if r.part == OrderPart.REASONING]
            hits = [r for r in reasoning if edge.cited_doc_id in r.text or (edge.sentence and edge.sentence in r.text)]
            for rec in hits or reasoning:
                rec.cites = sorted({*rec.cites, edge.cited_doc_id})
    report["edges_from_file"] = n


def _build_graph(
    processed: list[ProcessedOrder], index: CitationIndex, labeler: TreatmentLabeler | None, report: dict[str, Any]
) -> CitationGraph:
    """Resolve citations in reasoning paragraphs, label their treatment, and build the graph (plan §5.3)."""
    graph = CitationGraph(
        [
            NodeMeta(p.order.doc_id, p.order.court, court_level_of(p.order.court), p.order.bench_size, p.order.date)
            for p in processed
        ]
    )
    tally: dict[str, list[int]] = {}
    for n, p in enumerate(processed, 1):
        if n % 5000 == 0:
            print(f"[corpus] citations resolved for {n}/{len(processed)} orders", flush=True)
        treatments: dict[str, list[tuple[Treatment, str]]] = {}
        for rec in p.paragraphs:
            if rec.part != OrderPart.REASONING:
                continue
            cited_here: set[str] = set()
            for sentence in split_sentences(rec.text):
                for raw in extract_citations(sentence):
                    parsed = parse_citation(raw)
                    kind = parsed.kind if parsed else "unknown"
                    cited = index.resolve(raw)
                    slot = tally.setdefault(kind, [0, 0])
                    slot[0] += 1
                    slot[1] += 1 if cited else 0
                    if cited and cited != p.order.doc_id:
                        cited_here.add(cited)
                        treatments.setdefault(cited, []).append((_treat(sentence, labeler), sentence))
            rec.cites = sorted(cited_here)
        for cited, items in treatments.items():
            best = strongest(t for t, _ in items)
            sentence = next((s for t, s in items if t == best), items[0][1])
            graph.add_edge(CitationEdge(
                citing_doc_id=p.order.doc_id, cited_doc_id=cited, treatment=best,
                court_level=court_level_of(p.order.court), sentence=sentence[:400],
            ))  # fmt: skip
    report["citations_by_format"] = {k: {"extracted": v[0], "resolved": v[1]} for k, v in sorted(tally.items())}
    total = sum(v[0] for v in tally.values())
    report["citation_resolution_rate"] = (sum(v[1] for v in tally.values()) / total) if total else None
    return graph


def _treat(sentence: str, labeler: TreatmentLabeler | None) -> Treatment:
    """Cue-word label; with a labeler, only labels both agree on (plan §5.3)."""
    cue = label_treatment(sentence)
    return cue if labeler is None else agree_treatment(cue, labeler.label_treatment(sentence))


_CACHE: dict[tuple[Any, ...], Corpus] = {}


def clear_cache() -> None:
    """Forget processed corpora (call when the input files changed within one process)."""
    _CACHE.clear()


def process_corpus(
    interim_dir: str,
    exclude_doc_ids: set[str] | None = None,
    *,
    concordance_path: str | None = None,
    labeler: TreatmentLabeler | None = None,
    max_tokens: int = 400,
) -> Corpus:
    """Read, split, chunk, tag and cite-resolve every order, leaving out excluded ones (plan §2 leakage rules).

    Excluded orders (test orders and same-FIR orders) are removed before anything else, so they enter no store, no
    citation edge and no citation index. Results are cached per input file and arguments.

    Args:
        interim_dir: folder with `orders.jsonl` (see the module docstring)
        exclude_doc_ids: doc ids to leave out
        concordance_path: concordance SQLite (file or folder) for section families; default store, offline seed if absent
        labeler: evaluation labeler for treatment agreement; None keeps cue-word labels (cue-only, reported)
        max_tokens: chunk size limit

    Returns:
        Corpus with the processed orders, the citation graph and a report dict.
    """
    src = Path(interim_dir) / ORDERS_FILE
    stat = (src.stat().st_mtime, src.stat().st_size) if src.is_file() else None
    key = (str(src.resolve()), stat, frozenset(exclude_doc_ids or ()), concordance_path, id(labeler), max_tokens)
    if key in _CACHE:
        return _CACHE[key]
    orders, skipped = load_orders(interim_dir)
    excluded = exclude_doc_ids or set()
    kept = [o for o in orders if o.doc_id not in excluded]
    from vakeel_sahayak.stores.law_concordance import ConcordanceStore

    concordance = ConcordanceStore()
    concordance.open(concordance_path)
    cache: dict[tuple[str, ...], list[str]] = {}

    def family_of(sections: list[str]) -> list[str]:
        k = tuple(sections)
        if k not in cache:
            cache[k] = expand_family(sections, store=concordance)
        return cache[k]

    processed = []
    for n, o in enumerate(kept, 1):
        processed.append(_process_order(o, family_of, max_tokens))
        if n % 5000 == 0:
            print(f"[corpus] processed {n}/{len(kept)} orders", flush=True)
    report: dict[str, Any] = {
        "orders_read": len(orders), "skipped": skipped, "excluded": len(orders) - len(kept),
        "orders_used": len(processed), "clean_splits": sum(1 for p in processed if p.clean_split),
        "orders_without_reasoning": sum(1 for p in processed if not p.parts.get(OrderPart.REASONING, "").strip()),
        "treatment_mode": "agreed_with_labeler" if labeler else "cue_only",
    }  # fmt: skip
    index = CitationIndex([{**o.raw, "doc_id": o.doc_id, "date": o.date, "court": o.court, "title": o.title,
                            "citations": o.citations} for o in kept])  # fmt: skip
    graph = _build_graph(processed, index, labeler, report)
    resolved_edges = Path(interim_dir) / CITATION_EDGES_FILE
    if resolved_edges.is_file():
        _add_resolved_edges(graph, processed, resolved_edges, excluded, report)
    scores = graph.all_authority(configured_weights())
    for p in processed:
        for rec in p.paragraphs:
            rec.authority = scores.get(p.order.doc_id, 0.0)
    corpus = Corpus(processed, graph, report)
    _CACHE[key] = corpus
    return corpus
