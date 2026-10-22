"""Citation index for the full store build: the same rules as `CitationIndex`, but case-name matching is blocked on shared party words.

`CitationIndex._resolve_name` scores a cited case name against every indexed title (about 116K), at several seconds per unique name,
which makes a full build take hours. A match needs both party similarities to reach `PARTY_MIN`, so a candidate title must share at
least one content word with each cited party; the inverted index below only scores those candidates (and ignores pure
spelling-variant matches that share no whole word, a small bounded loss). Results are memoised per (name, year, court), so a
repeated citation string is resolved once. Exact (neutral, SCC, AIR) lookups are unchanged.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from vakeel_sahayak.pipelines.citation_graph import resolve as _r
from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex


class FastCitationIndex(CitationIndex):
    """`CitationIndex` with word-blocked, memoised case-name resolution."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        """Index the records, then the inverted party-word index."""
        super().__init__(records)
        self._by_word: tuple[dict[str, list[int]], dict[str, list[int]]] = (defaultdict(list), defaultdict(list))
        for i, (_, parties, _, _) in enumerate(self._names):
            for side in (0, 1):
                for w in set(_r._party_tokens(parties[side])):
                    self._by_word[side][w].append(i)
        self._memo: dict[tuple[str, int | None, str | None], str | None] = {}

    def _candidates(self, wanted: tuple[str, str]) -> list[int]:
        sets = []
        for side in (0, 1):
            ids: set[int] = set()
            for w in set(_r._party_tokens(wanted[side])):
                ids.update(self._by_word[side].get(w, ()))
            sets.append(ids)
        return sorted(sets[0] & sets[1])

    def _resolve_name(self, name: str, year: int | None, court: str | None) -> str | None:
        """Blocked and memoised version of the parent's fuzzy match (same scoring, year, court and ambiguity rules)."""
        key = (name, year, court)
        if key in self._memo:
            return self._memo[key]
        wanted = _r._split_parties(name)
        result: str | None = None
        if wanted:
            scored: list[tuple[float, int, str]] = []
            for i in self._candidates(wanted):
                doc_id, parties, doc_year, doc_court = self._names[i]
                if year and doc_year and abs(year - doc_year) > 1:
                    continue
                if court and doc_court and court.lower() not in str(doc_court).lower():
                    continue
                s1 = _r._party_similarity(wanted[0], parties[0])
                s2 = _r._party_similarity(wanted[1], parties[1])
                if s1 >= _r.PARTY_MIN and s2 >= _r.PARTY_MIN and (score := 0.6 * s1 + 0.4 * s2) >= _r.FUZZY_MIN:
                    scored.append((score, _r._court_level(doc_court), doc_id))
            if scored:
                scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
                best = scored[0]
                rivals = [t for t in scored[1:] if best[0] - t[0] < _r.AMBIGUITY_MARGIN and t[1] >= best[1]]
                result = None if rivals else best[2]
        self._memo[key] = result
        return result
