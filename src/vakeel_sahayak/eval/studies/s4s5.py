"""S4 and S5: retrieval-only studies on the real `caselaw.reasoning` and `caselaw.citations` stores (evaluation plan 3.3 rows S4 and S5; M19). No model, no Ada.

* S4 (score-skew weak signal): AUROC, over queries, of the skew statistics of the top-10 hybrid scores (`agents/sutradhar/skew.py`: Gini and relative top gap) for the event "the top-10
  contains a paragraph of a gold document" (M19). A skew that works as a weak-evidence signal gives an AUROC above 0.5 for a statistic where higher means "more peaked"; the flatness flag
  of the variant (`skew_of(...)["weak"]`) is reported with its precision and recall for "no gold in the top-10".
* S5 (graph expansion): recall@10 at document level with and without personalised-PageRank expansion over the citation graph (`search_reasoning(expand_graph=True)`), the share of
  Supreme Court judgments in the top-10, and the paired difference with a bootstrap interval and an exact McNemar test on "found at least one gold document".

Two query sets, both printed with their n:
* `g2` (the real target): the facts of T1 dev and open orders that have a resolved court-cited precedent. COVERAGE IS THIN (the gold is 19 judgments in 14 of 250 orders at the last
  build, and few of them have paragraphs in the store), so n is small and an AUROC on it carries a wide interval or is undefined; the table says so.
* `proxy` (self-supervised, NOT G2): a sample of reasoning paragraphs in the store that cite a judgment which is itself in the store and dated before the paragraph; the query is the paragraph with
  citation-like strings masked (case names with "v.", reporter citations), the gold is the cited judgments in the store, `before` is the paragraph's date. It asks whether the retriever
  finds the authorities a court relied on given the passage that relied on them. The masking is a regex and leaves traces, so the level is optimistic; the comparison across arms is what counts.

Run: `python -m vakeel_sahayak.eval.studies s4s5 --out <dir> [--n 150]` (about 2 seconds a query).
"""

from __future__ import annotations

import json
import re
import sqlite3
import zlib
from pathlib import Path
from typing import Any

import numpy as np

from vakeel_sahayak.eval.metrics.retrieval import auroc
from vakeel_sahayak.eval.scoring import stats_extra as sx
from vakeel_sahayak.eval.studies.common import write_result

_MASK = [re.compile(p) for p in (r"\(\d{4}\)\s*\d+\s*(?:SCC|SCR|AIR)[\w .-]*\d+", r"\b(?:AIR|SCC|SCR)\s*\d{4}[\w .-]*\d+", r"\b\d{4}\s*(?:SCC|INSC)\s*(?:OnLine\s*)?\w*\s*\d+",
                                  r"\b[A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,4}\s+(?:v\.?|vs\.?|versus)\s+[A-Z][\w.&'-]*(?:\s+[A-Z&][\w.&'-]*){0,5}")]
SC_MARK = "_INSC_"


def mask_citations(text: str) -> str:
    """The text with case names (`X v. Y`), reporter citations and neutral citations replaced by a space."""
    for p in _MASK:
        text = p.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def stores_dir() -> Path:
    from vakeel_sahayak.config import load_config

    return Path(load_config().paths.stores_dir)


def proxy_cases(n: int, db: Path | None = None) -> list[dict[str, Any]]:
    """Up to `n` self-supervised cases (see the module docstring), chosen by a CRC of the paragraph key so the sample is reproducible."""
    path = db or stores_dir() / "caselaw" / "reasoning.sqlite"
    if not path.is_file():
        raise FileNotFoundError(f"no reasoning store at {path}: build the stores first (make stores, or make data)")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        docs = {r[0] for r in con.execute("SELECT DISTINCT substr(key, 1, instr(key, '#') - 1) FROM items")}
        rows = con.execute("SELECT key, payload FROM items WHERE payload LIKE '%\"cites\": [\"%'").fetchall()
        rows.sort(key=lambda r: zlib.crc32(r[0].encode()))
        out: list[dict[str, Any]] = []
        for key, payload in rows:
            d = json.loads(payload)
            cited = [c for c in dict.fromkeys(d.get("cites") or []) if c in docs and c != d["doc_id"]]
            gold = []
            for c in cited:
                got = con.execute("SELECT date FROM items WHERE key >= ? AND key < ? LIMIT 1", (c + "#", c + "$")).fetchone()
                if got and got[0] and d.get("date") and str(got[0]) < str(d["date"]):
                    gold.append(c)
            query = mask_citations(str(d.get("text") or ""))[:600]
            if gold and len(query.split()) >= 12:
                out.append({"id": key, "query": query, "gold": gold, "before": d["date"]})
            if len(out) >= n:
                break
        return out
    finally:
        con.close()


def g2_cases(limit: int | None = None) -> list[dict[str, Any]]:
    """T1 dev and open orders with a resolved G2: facts as the query, `before` the order date (never the blind slice)."""
    from vakeel_sahayak.eval import feature_common as fc
    from vakeel_sahayak.eval.scoring.loader import resolve_slice_ids

    ids = resolve_slice_ids("dev", "agreed") | resolve_slice_ids("open", "agreed")
    out = []
    for name in ("dev.jsonl", "cases.jsonl"):
        for r in fc.read_jsonl(fc.t1_dir() / name):
            gold = list((r.get("gold", {}).get("G2", {}) or {}).get("labels") or [])
            if str(r["case_id"]) in ids and gold:
                out.append({"id": str(r["case_id"]), "query": str(r.get("facts_text") or "")[:600], "gold": gold, "before": r.get("before")})
    return out[:limit] if limit else out


def retrieve(case: dict[str, Any]) -> dict[str, Any]:
    """Plain scored top-10 and graph-expanded top-10 for one case: docs in rank order, scores, skew statistics."""
    from vakeel_sahayak.agents.sutradhar.skew import scores_of, skew_of
    from vakeel_sahayak.tools.caselaw.reasoning import search_reasoning

    plain = search_reasoning(case["query"], before=case["before"], k=10, with_scores=True)
    expanded = search_reasoning(case["query"], before=case["before"], k=10, expand_graph=True)
    if not isinstance(plain, list) or not isinstance(expanded, list):
        raise RuntimeError(f"search failed for {case.get('id')}: {plain if not isinstance(plain, list) else expanded}")
    docs = list(dict.fromkeys(r.doc_id for r in plain))
    edocs = list(dict.fromkeys(r.doc_id for r in expanded))
    items = [{"score": float(r.score)} for r in plain]
    return {"docs": docs, "edocs": edocs, "skew": skew_of(scores_of(items)), "n_expanded": sum(1 for r in expanded if getattr(r, "expanded", False))}


def summarise(results: list[dict[str, Any]], n_boot: int = 2000) -> dict[str, Any]:
    """The S4 and S5 numbers of one query set from per-case `gold`, `docs`, `edocs`, `skew`."""
    n = len(results)
    if not n:
        return {"n": 0}
    hit = [bool(set(r["gold"]) & set(r["docs"])) for r in results]
    ehit = [bool(set(r["gold"]) & set(r["edocs"])) for r in results]
    rec = [len(set(r["gold"]) & set(r["docs"])) / len(set(r["gold"])) for r in results]
    erec = [len(set(r["gold"]) & set(r["edocs"])) / len(set(r["gold"])) for r in results]
    diff = [b - a for a, b in zip(rec, erec, strict=True)]
    m, lo, hi = sx.bootstrap_mean_ci(diff, n_boot)
    mc = sx.mcnemar_exact(ehit, hit)
    sc_share = [sum(1 for d in r["docs"] if SC_MARK in d) / max(1, len(r["docs"])) for r in results]
    esc_share = [sum(1 for d in r["edocs"] if SC_MARK in d) / max(1, len(r["edocs"])) for r in results]
    s5 = {"recall_at_10_plain": sum(rec) / n, "recall_at_10_expanded": sum(erec) / n, "diff": m, "diff_lo": lo, "diff_hi": hi, "hit_plain": sum(hit), "hit_expanded": sum(ehit),
          "mcnemar_p": mc["p"], "discordant_expanded_only": mc["b10"], "discordant_plain_only": mc["b01"], "sc_share_plain": sum(sc_share) / n, "sc_share_expanded": sum(esc_share) / n,
          "mean_docs_added": sum(len(set(r["edocs"]) - set(r["docs"])) for r in results) / n}
    gini = [r["skew"]["gini"] if r["skew"]["gini"] is not None else float("nan") for r in results]
    gap = [r["skew"]["top_gap"] if r["skew"]["top_gap"] is not None else float("nan") for r in results]
    keep = [i for i in range(n) if not (np.isnan(gini[i]) or np.isnan(gap[i]))]

    def with_ci(stat: str, scores: list[float]) -> dict[str, Any]:
        xs, ys = [scores[i] for i in keep], [hit[i] for i in keep]
        point = auroc(xs, ys)
        ci = None
        if point is not None and len(xs) >= 10:
            rng = np.random.default_rng(sx.SEED)
            vals = []
            for _ in range(500):
                idx = rng.integers(0, len(xs), size=len(xs))
                v = auroc([xs[i] for i in idx], [ys[i] for i in idx])
                if v is not None:
                    vals.append(v)
            ci = [float(np.quantile(vals, 0.025)), float(np.quantile(vals, 0.975))] if vals else None
        return {"statistic": stat, "auroc": point, "ci95": ci, "n": len(xs), "n_positive": sum(ys), "n_negative": len(xs) - sum(ys)}

    weak = [bool(r["skew"]["weak"]) for r in results]
    tp = sum(1 for w, h in zip(weak, hit, strict=True) if w and not h)
    s4 = {"gini": with_ci("gini (higher = more peaked)", gini), "top_gap": with_ci("top gap (higher = more peaked)", gap),
          "weak_flag": {"flagged": sum(weak), "no_gold_in_top10": sum(1 for h in hit if not h), "precision_for_no_gold": (tp / sum(weak)) if sum(weak) else None,
                        "recall_for_no_gold": (tp / sum(1 for h in hit if not h)) if any(not h for h in hit) else None}}
    return {"n": n, "s4": s4, "s5": s5}


def run(out_dir: str, n: int | None = None, seed: int = 0, *, cases: dict[str, list[dict[str, Any]]] | None = None, retrieve_fn: Any = None) -> dict[str, Any]:
    """The S4 and S5 retrieval studies; writes `s4s5.json` and `s4s5.md`. `cases` and `retrieve_fn` replace the real stores (tests)."""
    n_proxy = n or 150
    sets = cases if cases is not None else {"g2": g2_cases(), "proxy": proxy_cases(n_proxy)}
    fn = retrieve_fn or retrieve
    out: dict[str, Any] = {"sets": {}, "seed_note": "sampling is by a CRC of the paragraph key; no randomness"}
    rows = []
    for name, cs in sets.items():
        res = [{**c, **fn(c)} for c in cs]
        summary = summarise(res)
        out["sets"][name] = summary
        if not summary["n"]:
            rows.append([name, 0, "n/a", "n/a", "n/a", "n/a", "n/a", "n/a", "n/a"])
            continue
        s4, s5 = summary["s4"], summary["s5"]

        def au(x: dict[str, Any]) -> str:
            return "undefined" if x["auroc"] is None else f"{x['auroc']:.3f}" + ("" if not x["ci95"] else f" [{x['ci95'][0]:.3f}, {x['ci95'][1]:.3f}]") + f" (pos {x['n_positive']}, neg {x['n_negative']})"

        rows.append([name, summary["n"], au(s4["gini"]), au(s4["top_gap"]), f"{s5['recall_at_10_plain']:.3f}", f"{s5['recall_at_10_expanded']:.3f}",
                     f"{s5['diff']:+.3f} [{s5['diff_lo']:+.3f}, {s5['diff_hi']:+.3f}]", f"{s5['mcnemar_p']:.3f} ({s5['discordant_expanded_only']}/{s5['discordant_plain_only']})",
                     f"{s5['sc_share_plain']:.3f} -> {s5['sc_share_expanded']:.3f}"])
    notes = ["g2 = the real target (facts of T1 dev/open orders with a resolved court-cited precedent). Its coverage is thin: read the n, and an AUROC with few positives or negatives is wide or undefined.",
             "proxy = self-supervised, NOT G2: reasoning paragraphs in the store that cite a judgment in the store; query = the paragraph with citation strings masked; gold = the cited judgments dated before it.",
             "S4: AUROC of the Gini and the top gap of the top-10 hybrid scores for 'the top-10 contains a gold document' (0.5 = no signal). S5: recall@10 at document level, plain vs personalised-PageRank expansion; McNemar on 'at least one gold document found' (expansion-only/plain-only discordant counts).",
             "The proxy gold is the cited-by relation of the same citation graph that S5 walks, so the proxy favours S5 by construction; the G2 row is the independent target and is thin.",
             "Offline: the stores' embedder is the hashed n-gram one (the build recorded `embedder: hashed-ngram`), so these are retrieval numbers of that index, not of BGE-M3."]
    return write_result(out_dir, "s4s5", out, "S4 and S5: retrieval-only studies (preliminary)",
                        "Score-skew AUROC (S4) and graph-expansion recall@10 (S5) on the real stores; offline; two query sets with their n.",
                        ["Query set", "n", "S4 AUROC, Gini", "S4 AUROC, top gap", "S5 recall@10 plain", "S5 recall@10 expanded", "S5 difference [95% CI]", "S5 McNemar p (exp-only/plain-only)", "SC share of top-10"], rows, notes)
