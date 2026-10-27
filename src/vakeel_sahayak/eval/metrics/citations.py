"""Citation, authority and abstention metrics of the evaluation plan (4.2, 4.3, 4.6): M9, M13, M15, M16, M17, M18, M33, M35.

All deterministic. Where a checker is needed (M16, M35) it is the same facade as the unsupported-fact rate (`unsupported_fact._scorer`: MiniCheck when installed, else
the repository's DeBERTa NLI, else the lexical offline stand-in) and the result says which one ran; no number here comes from an LLM judging text.

What a "citation" is in a brief: an inline marker `[A:<doc_id>#<para>]` written after a sentence (optionally right after a quotation in curly or straight quotes), and every
entry of a ground's `authorities` list that no inline marker covers. A paragraph is looked up through a `ParagraphIndex` (the reasoning, arguments and objections stores,
opened read-only); a precedent's good-law status through a `TreatmentIndex` (the citation graph, read-only).

Definitions (frozen in `docs/handoff/eval-complete.md`, to be copied into the pre-registration):
* M9 fabricated citation: a citation whose (doc_id, para) is not in the index, or whose quoted span is not found in the cited paragraph once whitespace is removed
  (an ellipsis splits a quotation into fragments, each of which must be found). Rate = fabricated / citations.
* M13 authority quality: over the distinct cited paragraphs present in the index, the share that are court reasoning (not counsel's submissions), the share whose judgment is a
  Supreme Court judgment or whose authority carries an `sc_root`, and the share dated strictly before the order.
* M15 good-law violation: a cited precedent the graph treats as OVERRULED, cited in a ground that carries no warning wording. Rate = violations / distinct (ground, precedent)
  pairs. Known-treatment share = pairs whose precedent has at least one incoming edge with a treatment label other than UNKNOWN ("unknown" is not "good").
* M16 citation precision: share of citations whose cited paragraph the checker judges to support the citing sentence (a citation to a missing paragraph counts as unsupported);
  recall: share of authority-claim sentences (a sentence with a marker, or one reporting what a court held) that carry at least one supported citation.
* M17 citation faithfulness by removal: share of cited claims whose text changes when the cited paragraph is deleted from the context and Vakeel redrafts. Lower bound only.
* M18 stopping quality, event-based: over-search = share of retrieval calls made in rounds after the first round in which no required slot was MISSING or WEAK;
  unfinished = share of factors that stopped with a slot still MISSING or WEAK (a proxy for "stopped too early": the full replay to the 16-call budget needs a re-run).
* M33 coverage-risk curve: claims are the factual sentences; a claim is emitted at threshold tau when its ground passed the gate and its support score is at least tau; risk is the
  share of emitted claims below the unsupported-fact cut (M6). AURC is the trapezoid area under risk over coverage.
* M35 confident-wrong: emitted claims that are unfaithful (not supported by the input facts) and uncorroborated (not supported by the rest of the order the system never saw).
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

MARKER = re.compile(r"\[A:(?P<doc>[^\]#\s]+)#(?P<para>\d+)(?:\.\d+)?\]")
_QUOTE_BEFORE = re.compile(r"[“\"‘]([^”\"’]{8,}?)[”\"’]\s*[.,;:]?\s*$")
_SPLIT = re.compile(r"(?<=[.!?])\s+|(?<=\])\.(?=[A-Z“\"])")
_WARNING = re.compile(r"warning:|overruled|no longer (?:good )?law|bad law|has been (?:doubted|distinguished|set aside)|superseded", re.IGNORECASE)
_AUTHORITY_CLAIM = re.compile(r"\b(?:held|holds|observed|ruled|laid down|has stated|states that|cited paragraph|relied on|followed|distinguished|precedent|judgment of|in the case of)\b|\bv(?:s)?\.\s", re.IGNORECASE)
_ELLIPSIS = re.compile(r"\.{3}|…")
UNSUPPORTED_GATES = {"NEEDS_REVIEW", "UNANSWERED", "REFUSED"}


# ---------------------------------------------------------------------------------------------------------------- extraction
@dataclass(frozen=True)
class Citation:
    """One citation of a brief: the ground, the cited paragraph, the quotation attached to it (if any) and the sentence that carries it (None: only in `authorities`)."""

    ground_id: str
    doc_id: str
    para: int
    quote: str | None
    sentence: str | None
    argument: str


def strip_markers(text: str) -> str:
    """The text without `[A:doc#para]` markers and the spaces they leave."""
    return re.sub(r"\s+", " ", MARKER.sub("", text)).strip()


def split_claims(argument: str) -> list[str]:
    """Sentences of a ground's argument, markers kept (a marker closes the sentence it follows even when no space follows the full stop)."""
    return [s.strip() for s in _SPLIT.split(argument or "") if s and s.strip()]


def extract_citations(brief: dict[str, Any]) -> list[Citation]:
    """Every citation of a brief (a `BailBrief` as a dict): inline markers first, then authorities no marker covers."""
    out: list[Citation] = []
    for g in (brief or {}).get("grounds") or []:
        gid, argument = str(g.get("id")), str(g.get("argument") or "")
        covered: set[tuple[str, int]] = set()
        for sentence in split_claims(argument):
            for m in MARKER.finditer(sentence):
                quote = None
                q = _QUOTE_BEFORE.search(sentence[: m.start()])
                if q:
                    quote = q.group(1)
                key = (m.group("doc"), int(m.group("para")))
                covered.add(key)
                out.append(Citation(gid, key[0], key[1], quote, sentence, argument))
        for a in g.get("authorities") or []:
            if a.get("doc_id") is None or a.get("para") is None:
                continue
            key = (str(a["doc_id"]), int(a["para"]))
            if key not in covered:
                out.append(Citation(gid, key[0], key[1], None, None, argument))
                covered.add(key)
    return out


# ---------------------------------------------------------------------------------------------------------------- indexes
class ParagraphIndex(Protocol):
    """Read-only access to the corpus paragraphs a citation points at."""

    def get(self, doc_id: str, para: int) -> dict[str, Any] | None:
        """`{"text", "part", "date", "court", "doc_id", "para"}` of the paragraph, or None when the document or paragraph is not in the index."""


class DictParagraphIndex:
    """An in-memory index (tests, fixtures): `{(doc_id, para): {"text": ..., "part": ..., "date": ..., "court": ...}}`."""

    def __init__(self, rows: dict[tuple[str, int], dict[str, Any]]) -> None:
        self.rows = rows

    def get(self, doc_id: str, para: int) -> dict[str, Any] | None:
        row = self.rows.get((str(doc_id), int(para)))
        return None if row is None else {"doc_id": doc_id, "para": para, **row}


class SqliteParagraphIndex:
    """The paragraph stores (`caselaw.reasoning`, `advocacy.arguments`, `advocacy.objections`) opened read-only; one document-paragraph key may be split into pieces `key.2`, ..."""

    STORES = ("caselaw.reasoning", "advocacy.arguments", "advocacy.objections")

    def __init__(self, paths: Iterable[str | Path]) -> None:
        self.paths = [Path(p) for p in paths if Path(p).is_file()]
        self._conns: list[sqlite3.Connection] = []

    @classmethod
    def from_config(cls, stores_dir: str | Path | None = None) -> SqliteParagraphIndex:
        """The stores under `stores_dir` (default: the configured stores directory); missing files are skipped."""
        if stores_dir is None:
            from vakeel_sahayak.config import load_config

            stores_dir = load_config().paths.stores_dir
        base = Path(stores_dir)
        return cls(base / "/".join(name.split(".")[:1] + [name.split(".")[1] + ".sqlite"]) for name in cls.STORES)

    def available(self) -> bool:
        """True when at least one store file exists."""
        return bool(self.paths)

    def _open(self) -> list[sqlite3.Connection]:
        if not self._conns:
            self._conns = [sqlite3.connect(f"file:{p}?mode=ro", uri=True) for p in self.paths]
        return self._conns

    def get(self, doc_id: str, para: int) -> dict[str, Any] | None:
        import json

        key = f"{doc_id}#{para}"
        for conn in self._open():
            rows = conn.execute("SELECT key, payload FROM items WHERE key = ? OR (key >= ? AND key < ?) ORDER BY key", (key, key + ".", key + "/")).fetchall()
            if rows:
                payloads = [json.loads(r[1]) for r in rows]
                first = payloads[0]
                return {"doc_id": doc_id, "para": para, "text": " ".join(str(p.get("text") or "") for p in payloads), "part": first.get("part"),
                        "date": first.get("date"), "court": first.get("court")}
        return None

    def close(self) -> None:
        for c in self._conns:
            c.close()
        self._conns = []


class TreatmentIndex(Protocol):
    """Good-law status and whether a precedent's treatment is known."""

    def status(self, doc_id: str, as_of: str | None = None) -> str:
        """OVERRULED, DISTINGUISHED, OK or UNKNOWN."""

    def known(self, doc_id: str, as_of: str | None = None) -> bool:
        """True when the precedent has at least one incoming citation with a treatment label other than UNKNOWN."""


class DictTreatmentIndex:
    """Tests and fixtures: `{doc_id: (status, known)}`; an absent document is UNKNOWN and not known."""

    def __init__(self, rows: dict[str, tuple[str, bool]]) -> None:
        self.rows = rows

    def status(self, doc_id: str, as_of: str | None = None) -> str:
        return self.rows.get(doc_id, ("UNKNOWN", False))[0]

    def known(self, doc_id: str, as_of: str | None = None) -> bool:
        return self.rows.get(doc_id, ("UNKNOWN", False))[1]


class GraphTreatmentIndex:
    """The citation graph of the `caselaw.citations` store (read-only); the graph is loaded once per process."""

    def __init__(self, store_path: str | Path | None = None) -> None:
        self.store_path = store_path
        self._graph: Any = None

    def _g(self) -> Any:
        if self._graph is None:
            from vakeel_sahayak.stores.caselaw_citations import CitationStore

            store = CitationStore()
            store.open(str(self.store_path) if self.store_path else None)
            self._graph = store.graph()
        return self._graph

    def status(self, doc_id: str, as_of: str | None = None) -> str:
        return self._g().good_law(doc_id, as_of).status.value

    def known(self, doc_id: str, as_of: str | None = None) -> bool:
        return any(str(getattr(e.treatment, "value", e.treatment)) != "UNKNOWN" for e in self._g().cited_by(doc_id, as_of))


# ---------------------------------------------------------------------------------------------------------------- M9
def _squash(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def quote_found(quote: str, paragraph: str) -> bool:
    """True when every fragment of the quotation (split at ellipses; fragments under 8 characters are ignored) occurs in the paragraph with whitespace removed."""
    para = _squash(paragraph)
    fragments = [_squash(f) for f in _ELLIPSIS.split(quote)]
    fragments = [f for f in fragments if len(f) >= 8]
    return bool(fragments) and all(f in para for f in fragments)


def fabricated_citations(citations: Sequence[Citation], index: ParagraphIndex) -> dict[str, Any]:
    """M9 over the citations of one brief: `n`, `n_fabricated`, `rate` (None with no citations) and the reasons per fabricated citation."""
    bad = []
    for c in citations:
        row = index.get(c.doc_id, c.para)
        if row is None:
            bad.append({"ground": c.ground_id, "doc_id": c.doc_id, "para": c.para, "reason": "not_in_index"})
        elif c.quote and not quote_found(c.quote, str(row.get("text") or "")):
            bad.append({"ground": c.ground_id, "doc_id": c.doc_id, "para": c.para, "reason": "quote_not_found"})
    n = len(citations)
    return {"n": n, "n_fabricated": len(bad), "rate": (len(bad) / n) if n else None, "items": bad}


# ---------------------------------------------------------------------------------------------------------------- M13
def authority_quality(citations: Sequence[Citation], index: ParagraphIndex, before: str | None, sc_roots: dict[tuple[str, str], str | None] | None = None) -> dict[str, Any]:
    """M13 over the distinct cited paragraphs that exist in the index: `n`, `reasoning_share`, `sc_share`, `before_share` (each None when n is 0).

    Args:
        citations: the brief's citations
        index: paragraph index
        before: the order date (ISO); a paragraph counts as before it when its date is strictly earlier
        sc_roots: `{(doc_id, ...): sc_root}` overrides for the SC share (the brief's `authorities[].sc_root`); a court name containing "Supreme" also counts
    """
    seen: dict[tuple[str, int], dict[str, Any]] = {}
    for c in citations:
        row = index.get(c.doc_id, c.para)
        if row is not None:
            seen[(c.doc_id, c.para)] = row
    n = len(seen)
    if not n:
        return {"n": 0, "reasoning_share": None, "sc_share": None, "before_share": None}
    reasoning = sum(1 for r in seen.values() if str(r.get("part")) == "reasoning")
    sc = sum(1 for (d, _), r in seen.items() if "supreme" in str(r.get("court") or "").lower() or (sc_roots or {}).get((d, "")))
    dated = [r for r in seen.values() if r.get("date")]
    before_n = sum(1 for r in dated if before and str(r["date"]) < before)
    return {"n": n, "reasoning_share": reasoning / n, "sc_share": sc / n, "before_share": (before_n / len(dated)) if (dated and before) else None}


# ---------------------------------------------------------------------------------------------------------------- M15
def good_law(brief: dict[str, Any], treatment: TreatmentIndex, as_of: str | None = None) -> dict[str, Any]:
    """M15 over one brief: `n` distinct (ground, precedent) pairs, `violations`, `violation_rate` and `known_share` (both None with no pairs)."""
    pairs: dict[tuple[str, str], str] = {}
    for c in extract_citations(brief):
        pairs[(c.ground_id, c.doc_id)] = c.argument
    violations = known = 0
    for (_, doc), argument in pairs.items():
        status = treatment.status(doc, as_of)
        known += int(treatment.known(doc, as_of))
        if status == "OVERRULED" and not _WARNING.search(MARKER.sub("", argument)):
            violations += 1
    n = len(pairs)
    return {"n": n, "violations": violations, "violation_rate": (violations / n) if n else None, "known_share": (known / n) if n else None}


# ---------------------------------------------------------------------------------------------------------------- checker facade
@dataclass
class Checker:
    """A support checker: `score(premise, hypothesis)` in [0, 1] and the cut that turns it into supported / unsupported."""

    name: str
    score: Callable[[str, str], float]
    cut: float

    @property
    def stand_in(self) -> bool:
        """True for the deterministic lexical stand-in (a plumbing check, not a validated judge)."""
        return "offline" in self.name

    def supported(self, premise: str, hypothesis: str) -> bool:
        return self.score(premise, hypothesis) >= self.cut


def get_checker() -> Checker:
    """MiniCheck when installed, else the repository's NLI client (DeBERTa or the offline lexical stand-in)."""
    from vakeel_sahayak.eval.metrics.unsupported_fact import _scorer

    name, score, cut = _scorer()
    return Checker(name, score, cut)


# ---------------------------------------------------------------------------------------------------------------- M16
def citation_precision_recall(brief: dict[str, Any], index: ParagraphIndex, checker: Checker) -> dict[str, Any]:
    """M16 over one brief (ALCE style): `n_citations`, `precision`, `n_claims`, `recall` (each None when its denominator is 0), `checker`, `stand_in`."""
    cites = extract_citations(brief)
    supported_sentences: set[tuple[str, str]] = set()
    ok = 0
    for c in cites:
        row = index.get(c.doc_id, c.para)
        hypothesis = strip_markers(c.sentence if c.sentence is not None else c.argument)
        if row is not None and hypothesis and checker.supported(str(row.get("text") or ""), hypothesis):
            ok += 1
            supported_sentences.add((c.ground_id, c.sentence if c.sentence is not None else c.argument))
    claims = []
    for g in (brief or {}).get("grounds") or []:
        argument = str(g.get("argument") or "")
        for s in split_claims(argument):
            if MARKER.search(s) or _AUTHORITY_CLAIM.search(s):
                claims.append((str(g.get("id")), s, argument))
    covered = sum(1 for gid, s, argument in claims if (gid, s) in supported_sentences or (gid, argument) in supported_sentences)
    return {"n_citations": len(cites), "precision": (ok / len(cites)) if cites else None, "n_claims": len(claims), "recall": (covered / len(claims)) if claims else None,
            "checker": checker.name, "stand_in": checker.stand_in}


# ---------------------------------------------------------------------------------------------------------------- M17
def _norm(text: str) -> str:
    return re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", MARKER.sub("", text or ""))).strip().lower()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"\w+", _norm(text)))


def removal_change(removal: dict[str, Any] | None, threshold: float = 1.0) -> dict[str, Any]:
    """M17 from one record's `removal` block: `n` (cited claims redrafted without their paragraph), `changed`, `rate` (None when n is 0).

    The block is `{"claims": [{"ground_id", "doc_id", "para", "original": <argument>, "redraft": <argument or None>}]}` written by `eval.runners.m17_removal`. A claim is unchanged
    when the redraft's token set is at least `threshold` similar (Jaccard) to the original after markers are removed; threshold 1.0 means identical wording. A claim the redraft no
    longer makes counts as changed. A high unchanged share means the citations were attached after the fact (a lower bound on post-hoc citation).
    """
    claims = (removal or {}).get("claims") or []
    changed = 0
    for c in claims:
        red = c.get("redraft")
        if red is None:
            changed += 1
            continue
        orig = str(c.get("original") or "")
        a, b = _tokens(orig), _tokens(str(red))
        sim = len(a & b) / len(a | b) if (a | b) else 1.0
        unchanged = _norm(orig) == _norm(str(red)) or (threshold < 1.0 and sim >= threshold)
        changed += int(not unchanged)
    n = len(claims)
    return {"n": n, "changed": changed, "rate": (changed / n) if n else None}


# ---------------------------------------------------------------------------------------------------------------- M18
def stopping_quality(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """M18 (event-based) from one case's Sutradhar events: `calls`, `over_calls`, `over_search_rate`, `factors`, `unfinished`, `unfinished_share` (None where undefined).

    A round's call count comes from its `plan` message (the steps kept), its pass state from the `assess` message that follows: passed when no slot is MISSING or WEAK.
    """
    calls: dict[str, dict[int, int]] = {}
    passed: dict[str, dict[int, bool]] = {}
    last: dict[str, dict[str, str]] = {}
    for ev in events:
        out = ev.get("outputs") or {}
        if ev.get("actor") != "SUTRADHAR" or ev.get("kind") != "AGENT_MESSAGE" or not isinstance(out, dict):
            continue
        factor, rnd = out.get("factor"), out.get("round")
        if factor is None or rnd is None:
            continue
        if out.get("type") == "plan":
            calls.setdefault(str(factor), {})[int(rnd)] = len(out.get("steps") or [])
        elif out.get("type") == "assess":
            a = {str(k): str(v) for k, v in (out.get("assessment") or {}).items()}
            passed.setdefault(str(factor), {})[int(rnd)] = not any(v.startswith(("MISSING", "WEAK")) for v in a.values())
            last[str(factor)] = a
    total = over = 0
    for factor, by_round in calls.items():
        first = next((r for r in sorted(by_round) if passed.get(factor, {}).get(r)), None)
        total += sum(by_round.values())
        if first is not None:
            over += sum(n for r, n in by_round.items() if r > first)
    factors = list(last)
    unfinished = sum(1 for a in last.values() if any(v.startswith(("MISSING", "WEAK")) for v in a.values()))
    return {"calls": total, "over_calls": over, "over_search_rate": (over / total) if total else None, "factors": len(factors), "unfinished": unfinished,
            "unfinished_share": (unfinished / len(factors)) if factors else None}


def _rounds(events: Sequence[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Per factor, its rounds in order: `{"round", "calls" (cumulative planned calls up to and including the round), "assessment"}` from the Sutradhar plan and assess messages."""
    calls: dict[str, dict[int, int]] = {}
    assessed: dict[str, dict[int, dict[str, str]]] = {}
    for ev in events:
        out = ev.get("outputs") or {}
        if ev.get("actor") != "SUTRADHAR" or ev.get("kind") != "AGENT_MESSAGE" or not isinstance(out, dict) or out.get("factor") is None or out.get("round") is None:
            continue
        factor, rnd = str(out["factor"]), int(out["round"])
        if out.get("type") == "plan":
            calls.setdefault(factor, {})[rnd] = len(out.get("steps") or [])
        elif out.get("type") == "assess":
            assessed.setdefault(factor, {})[rnd] = {str(k): str(v) for k, v in (out.get("assessment") or {}).items()}
    result: dict[str, list[dict[str, Any]]] = {}
    for factor, by_round in calls.items():
        total, rows = 0, []
        for rnd in sorted(by_round):
            total += by_round[rnd]
            rows.append({"round": rnd, "calls": total, "assessment": assessed.get(factor, {}).get(rnd)})
        result[factor] = rows
    return result


def _unfilled(assessment: dict[str, str] | None) -> list[str]:
    return sorted(k for k, v in (assessment or {}).items() if v.startswith(("MISSING", "WEAK")))


def stopped_too_early(events: Sequence[dict[str, Any]], reference_events: Sequence[dict[str, Any]], budget: int = 16) -> dict[str, Any]:
    """M18, the stopped-too-early half: replay each stopped factor towards the call budget from the STORED retrieval trajectory of a deeper run of the same case; no model, no store call.

    `events` are the Sutradhar events of the run under test; `reference_events` those of a run of the same case that was allowed to go on (the reference trajectory: what retrieving
    further produced, round by round, with its slot assessments). A factor of the run under test *stopped early* when its last assessment leaves a slot MISSING or WEAK while it had
    used fewer than `budget` planned calls. It *would have gained from a later call* (`too_early`) when the reference trajectory of the same factor has, within `budget` calls and beyond the
    calls the run used, a round whose assessment has one of those slots FILLED. A factor the reference never reached is `no_reference`: it is neither counted too early nor excluded from
    `factors`. This is the slot half of the plan's definition (M18); "would add a G1-correct factor or a G2 hit" needs the briefs and the gold, scored separately.

    Returns:
        `factors`, `stopped_early` (candidates), `too_early`, `no_reference`, `rate` (too_early / factors; None with no factor), `case_too_early` (any factor), `details` (per factor: calls used, missing
        slots, the reference round and call count that filled one).
    """
    run, ref = _rounds(events), _rounds(reference_events)
    details: list[dict[str, Any]] = []
    stopped = early = no_ref = 0
    for factor, rows in run.items():
        last = rows[-1]
        missing = _unfilled(last["assessment"])
        if not missing or last["calls"] >= budget:
            continue
        stopped += 1
        deeper = [r for r in ref.get(factor, []) if last["calls"] < r["calls"] <= budget]
        if factor not in ref:
            no_ref += 1
            continue
        hit = next((r for r in deeper if any(str((r["assessment"] or {}).get(slot, "")).startswith("FILLED") for slot in missing)), None)
        if hit is not None:
            early += 1
            details.append({"factor": factor, "calls_used": last["calls"], "missing": missing, "filled_at_round": hit["round"], "filled_at_calls": hit["calls"],
                            "slots": [s for s in missing if str((hit["assessment"] or {}).get(s, "")).startswith("FILLED")]})
    n = len(run)
    return {"factors": n, "stopped_early": stopped, "too_early": early, "no_reference": no_ref, "rate": (early / n) if n else None, "case_too_early": early > 0, "details": details}


def stopped_too_early_rate(per_case: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """The pooled M18 stopped-too-early rate over cases (the results of `stopped_too_early`): `case_rate` (cases with a factor that would have gained / cases with a factor), `factor_rate`."""
    rows = [r for r in per_case if r.get("factors")]
    cases = sum(1 for r in rows if r["case_too_early"])
    factors, early = sum(r["factors"] for r in rows), sum(r["too_early"] for r in rows)
    return {"cases": len(rows), "case_rate": (cases / len(rows)) if rows else None, "factors": factors, "too_early": early, "factor_rate": (early / factors) if factors else None}


# ---------------------------------------------------------------------------------------------------------------- M33 and M35
def claim_records(sentences: Sequence[dict[str, Any]], gate_pass: bool = True) -> list[dict[str, Any]]:
    """Claims for the curve from `unsupported_fact.sentence_support` rows: `emitted` is True when the ground's check is not a decline (NEEDS_REVIEW, UNANSWERED, REFUSED)."""
    return [{"emitted": bool(gate_pass) and str(s["check"]) not in UNSUPPORTED_GATES, "score": float(s["score"]), "cut": float(s["cut"])} for s in sentences]


def coverage_risk_curve(claims: Sequence[dict[str, Any]], cut: float | None = None) -> dict[str, Any]:
    """M33: the risk-coverage curve over pooled claims `{"emitted", "score", "cut"}`.

    Coverage(tau) = emitted claims with score >= tau over all claims; risk(tau) = share of those below the unsupported cut. The points are the distinct scores (plus tau = 0, every
    emitted claim, which is the system's own operating point when the gate is the only filter). Returns `points` ([[tau, coverage, risk], ...] by rising tau), `aurc` (trapezoid
    area of risk over coverage, coverage from the lowest to the highest reached; None with fewer than 2 distinct coverages), `n_claims`, `operating` (tau = the cut: coverage and risk
    of the claims the checker itself would keep) and `one_point` (the single point of a system that cannot decline).
    """
    n = len(claims)
    if not n:
        return {"points": [], "aurc": None, "n_claims": 0, "operating": None, "one_point": None}
    thr = cut if cut is not None else float(claims[0].get("cut", 0.5))
    emitted = [c for c in claims if c["emitted"]]

    def at(tau: float) -> tuple[float, float | None]:
        kept = [c for c in emitted if c["score"] >= tau]
        return len(kept) / n, (sum(1 for c in kept if c["score"] < thr) / len(kept)) if kept else None

    taus = sorted({0.0, *(round(c["score"], 6) for c in emitted)})
    points = []
    for t in taus:
        cov, risk = at(t)
        if risk is not None:
            points.append([t, cov, risk])
    by_cov = sorted(points, key=lambda p: (p[1], p[2]))
    aurc = None
    if len({p[1] for p in by_cov}) >= 2:
        aurc = sum((b[1] - a[1]) * (a[2] + b[2]) / 2 for a, b in zip(by_cov, by_cov[1:], strict=False))
    cov_op, risk_op = at(thr)
    cov_all, risk_all = at(0.0)
    return {"points": points, "aurc": aurc, "n_claims": n, "operating": {"tau": thr, "coverage": cov_op, "risk": risk_op},
            "one_point": {"coverage": cov_all, "risk": risk_all}}


def confident_wrong(sentences: Sequence[dict[str, Any]], rest_of_order: str | None, checker: Checker, gate_pass: bool = True) -> dict[str, Any]:
    """M35 and the four cells of plan 4.2 over the emitted claims: faithful (F) = supported by the input (the sentence's score is at least its cut), corroborated (C) = supported by the part of the order the system never saw.

    Returns `n` emitted claims, `cells` ({FC, F_notC, notF_C, notF_notC}), `rate` (notF_notC / n; None when n is 0 or there is no rest of the order) and the checker's name.
    """
    cells = {"FC": 0, "F_notC": 0, "notF_C": 0, "notF_notC": 0}
    if not rest_of_order:
        return {"n": 0, "cells": cells, "rate": None, "checker": checker.name}
    n = 0
    for s in sentences:
        if not gate_pass or str(s["check"]) in UNSUPPORTED_GATES:
            continue
        n += 1
        f = float(s["score"]) >= float(s["cut"])
        c = checker.supported(rest_of_order, str(s["sentence"]))
        cells[{(True, True): "FC", (True, False): "F_notC", (False, True): "notF_C", (False, False): "notF_notC"}[(f, c)]] += 1
    return {"n": n, "cells": cells, "rate": (cells["notF_notC"] / n) if n else None, "checker": checker.name}


@dataclass
class ScoreEnv:
    """The read-only resources the citation metrics need; every field may be None (the metric is then pending, with the reason)."""

    paragraphs: ParagraphIndex | None = None
    treatment: TreatmentIndex | None = None
    checker: Checker | None = None
    rest_of_order: Callable[[str], str | None] | None = None
    reasons: dict[str, str] = field(default_factory=dict)
    checker_used: str | None = None

    @classmethod
    def from_config(cls, stores_dir: str | Path | None = None, parts_path: str | Path | None = None) -> ScoreEnv:
        """The stores under the configured stores directory and the splitter's parts file (`data/interim/t1_work/parts.jsonl`); absent resources are recorded in `reasons`."""
        env = cls()
        idx = SqliteParagraphIndex.from_config(stores_dir)
        if idx.available():
            env.paragraphs = idx
        else:
            env.reasons["paragraphs"] = "the paragraph stores (data/stores/caselaw/reasoning.sqlite and the advocacy stores) are not present"
        try:
            from vakeel_sahayak.config import load_config

            base = Path(stores_dir) if stores_dir else Path(load_config().paths.stores_dir)
            cit = base / "caselaw" / "citations.sqlite"
            if cit.is_file():
                env.treatment = GraphTreatmentIndex(cit)
            else:
                env.reasons["treatment"] = "the citation graph (data/stores/caselaw/citations.sqlite) is not present"
            interim = Path(load_config().paths.data_dir) / "interim" / "t1_work" / "parts.jsonl"
        except Exception as exc:  # noqa: BLE001 - a missing config only removes the optional resources
            env.reasons["config"] = f"{type(exc).__name__}: {exc}"
            interim = Path("data/interim/t1_work/parts.jsonl")
        parts = Path(parts_path) if parts_path else interim
        if parts.is_file():
            env.rest_of_order = RestOfOrder(parts)
        else:
            env.reasons["rest_of_order"] = f"the order parts file {parts} is not present"
        return env

    def get_checker(self) -> Checker:
        if self.checker is None:
            self.checker = get_checker()
        self.checker_used = self.checker.name
        return self.checker


class RestOfOrder:
    """The text of every order part except the facts (defense, prosecution, reasoning, operative order), read lazily from the splitter's JSONL, one pass for all wanted documents."""

    def __init__(self, parts_path: str | Path) -> None:
        self.path = Path(parts_path)
        self._cache: dict[str, str] | None = None
        self._wanted: set[str] | None = None

    def prefetch(self, doc_ids: Iterable[str]) -> None:
        """Name the documents that will be asked for, so the one pass over the file keeps only those."""
        self._wanted = {str(d) for d in doc_ids}
        self._cache = None

    def _load(self) -> dict[str, str]:
        import json

        out: dict[str, str] = {}
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                parts = row.get("parts")
                if self._wanted is not None and str(row.get("doc_id")) not in self._wanted:
                    continue
                if isinstance(parts, dict):
                    out[str(row.get("doc_id"))] = "\n".join(str(v) for k, v in parts.items() if k != "facts" and v)
        return out

    def __call__(self, doc_id: str) -> str | None:
        if self._cache is None:
            self._cache = self._load()
        return self._cache.get(str(doc_id)) or None
