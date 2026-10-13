"""Resolve citations against Open India Law metadata: exact on neutral citation, else fuzzy on parties, year, court; report the resolution rate (plan §5.3). Also used by T9/F7.

Metadata format (JSONL, one record per judgment; an `orders.jsonl` of the store builders works as is):
`doc_id` (required), `title` or `case_name` ('Sanjay Chandra v. Central Bureau of Investigation'), `court`, `date` (or
`year`), and the judgment's own citations in `neutral_citation` and/or `citations` (a list, or one string such as
'(2012) 1 SCC 40 : AIR 2012 SC 830'). Missing fields only reduce what can be resolved.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.citation_graph.extract import extract_citations, parse_citation
from vakeel_sahayak.pipelines.text_utils import normalise_date, read_jsonl, write_jsonl

_STOP = {"ors", "anr", "others", "another", "etc", "alias", "through", "the", "and", "&", "its", "his", "her", "rep", "by"}
FUZZY_MIN = 0.82
PARTY_MIN = 0.8
AMBIGUITY_MARGIN = 0.03


def _party_tokens(party: str) -> list[str]:
    """Lower-case content words of a party name."""
    return [w for w in re.findall(r"[a-z0-9]+", party.lower()) if w not in _STOP]


def _split_parties(name: str) -> tuple[str, str] | None:
    """('p1', 'p2') from 'p1 v. p2' (any of v, v., vs, versus)."""
    parts = re.split(r"\s+(?:v\.?|vs\.?|versus)\s+", re.sub(r"\(\s*(?:19|20)\d{2}\s*\)", "", name).strip(), maxsplit=1, flags=re.I)
    return (parts[0], parts[1]) if len(parts) == 2 else None


def _party_similarity(a: str, b: str) -> float:
    """Similarity of two party names: the better of sequence ratio and token containment (handles 'CBI' vs long forms poorly, by design)."""
    ta, tb = _party_tokens(a), _party_tokens(b)
    if not ta or not tb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    contain = sum(1 for w in shorter if w in longer) / len(shorter)
    return max(ratio, contain * 0.95)


def _court_level(court: str | None) -> int:
    """Rank used only to break ties between equally good name matches: Supreme Court first."""
    c = (court or "").lower()
    return 2 if "supreme" in c else 1 if "high" in c or c.endswith("hc") else 0


class CitationIndex:
    """Metadata lookup: exact keys for formal citations, fuzzy party/year/court matching for case names (plan §5.3)."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        """Index metadata records (see the module docstring for the fields)."""
        self._exact: dict[str, set[str]] = defaultdict(set)
        self._names: list[tuple[str, tuple[str, str], int | None, str | None]] = []
        self.docs: dict[str, dict[str, Any]] = {}
        for rec in records:
            doc_id = str(rec.get("doc_id") or "")
            if not doc_id:
                continue
            self._add(doc_id, rec)

    @classmethod
    def from_jsonl(cls, path: str | Path) -> CitationIndex:
        """Build from a metadata JSONL file (a missing file gives an empty index)."""
        return cls(list(read_jsonl(path)))

    def _add(self, doc_id: str, rec: dict[str, Any]) -> None:
        """Register one record's own citations, title and year."""
        date = normalise_date(rec.get("date"))
        year = int(date[:4]) if date else (int(rec["year"]) if str(rec.get("year") or "").isdigit() else None)
        court = rec.get("court")
        self.docs[doc_id] = {"court": court, "year": year}
        cites = rec.get("citations")
        blob = " ; ".join([str(rec.get("neutral_citation") or ""), *(cites if isinstance(cites, list) else [str(cites or "")])])
        for raw in extract_citations(blob):
            parsed = parse_citation(raw)
            if parsed and parsed.kind != "case_name":
                self._exact[parsed.key].add(doc_id)
        title = str(rec.get("title") or rec.get("case_name") or "")
        parties = _split_parties(title) if title else None
        if parties:
            self._names.append((doc_id, parties, year, court))

    def resolve(self, citation: str, year: int | None = None, court: str | None = None) -> str | None:
        """Resolve one raw citation to a doc id.

        Neutral, SCC, AIR, SCC OnLine and Cri LJ citations are matched exactly on their normalised key. A case name is
        matched fuzzily on both party names, then filtered by year (within one year) and court when those are known. A tie
        between different judgments is not resolved (None) unless the court level separates them.

        Args:
            citation: raw citation string
            year: year of the cited case if known elsewhere
            court: court of the cited case if known (substring match)

        Returns:
            Doc id, or None when nothing matches or the match is ambiguous.
        """
        parsed = parse_citation(citation)
        if not parsed:
            return None
        if parsed.kind != "case_name":
            ids = self._exact.get(parsed.key, set())
            return next(iter(ids)) if len(ids) == 1 else None
        return self._resolve_name(parsed.key, parsed.year or year, court)

    def _resolve_name(self, name: str, year: int | None, court: str | None) -> str | None:
        """Fuzzy match on party names with year and court filters."""
        wanted = _split_parties(name)
        if not wanted:
            return None
        scored: list[tuple[float, int, str]] = []
        for doc_id, parties, doc_year, doc_court in self._names:
            if year and doc_year and abs(year - doc_year) > 1:
                continue
            if court and doc_court and court.lower() not in str(doc_court).lower():
                continue
            s1 = _party_similarity(wanted[0], parties[0])
            s2 = _party_similarity(wanted[1], parties[1])
            if s1 >= PARTY_MIN and s2 >= PARTY_MIN and (score := 0.6 * s1 + 0.4 * s2) >= FUZZY_MIN:
                scored.append((score, _court_level(doc_court), doc_id))
        if not scored:
            return None
        scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
        best = scored[0]
        rivals = [t for t in scored[1:] if best[0] - t[0] < AMBIGUITY_MARGIN and t[1] >= best[1]]
        return None if rivals else best[2]


_CACHE: dict[tuple[str, float], CitationIndex] = {}


def load_index(metadata_path: str) -> CitationIndex:
    """CitationIndex for a metadata file, cached by path and modification time."""
    p = Path(metadata_path)
    key = (str(p.resolve()), p.stat().st_mtime if p.exists() else 0.0)
    if key not in _CACHE:
        _CACHE[key] = CitationIndex.from_jsonl(p)
    return _CACHE[key]


def resolve_citation(citation: str, metadata_path: str) -> str | None:
    """Return the doc id or None.

    Args:
        citation: see behaviour
        metadata_path: metadata JSONL (module docstring)

    Returns:
        Doc id.
    """
    return load_index(metadata_path).resolve(citation)


def resolve_all(extracted_path: str, metadata_path: str, out_path: str) -> int:
    """Resolve every extracted citation.

    Input JSONL: `{"citing_doc_id", "raw"}` per citation. Output JSONL: the same plus `kind` and `cited_doc_id` (null when unresolved).

    Args:
        extracted_path: see behaviour
        metadata_path: see behaviour
        out_path: see behaviour

    Returns:
        Rows written.
    """
    index = load_index(metadata_path)
    rows = []
    for row in read_jsonl(extracted_path):
        parsed = parse_citation(str(row.get("raw", "")))
        rows.append({**row, "kind": parsed.kind if parsed else "unknown", "cited_doc_id": index.resolve(str(row.get("raw", "")))})
    return write_jsonl(out_path, rows)


def resolution_rate(extracted_path: str, resolved_path: str) -> dict[str, float]:
    """Coverage by citation format.

    Args:
        extracted_path: JSONL of extracted citations (`raw`); gives the denominator when `resolved_path` lacks a row
        resolved_path: JSONL from `resolve_all` (`kind`, `cited_doc_id`)

    Returns:
        Rate per format (neutral, scc, scc_online, air, crilj, case_name) plus `overall`; formats never seen are absent.
    """
    total: dict[str, int] = defaultdict(int)
    hit: dict[str, int] = defaultdict(int)
    for row in read_jsonl(resolved_path):
        kind = str(row.get("kind") or (parse_citation(str(row.get("raw", ""))) or _UNKNOWN).kind)
        total[kind] += 1
        hit[kind] += 1 if row.get("cited_doc_id") else 0
    n_extracted = sum(1 for _ in read_jsonl(extracted_path))
    out = {k: hit[k] / total[k] for k in total}
    denom = max(sum(total.values()), n_extracted)
    out["overall"] = sum(hit.values()) / denom if denom else 0.0
    return out


class _Unknown:
    kind = "unknown"


_UNKNOWN = _Unknown()
