"""Feature evaluation F7: Citation resolver and good-law check vs regex-only resolver and B0-B4. Test set: T9; labeler agreement; T1 runs. Metrics: resolution accuracy by format; coverage; treatment agreement (kappa); rate of citing overruled precedents (plan §15.6).

Test set T9: 2,095 citation strings drawn from 500 Supreme Court judgments (neutral, SCC, AIR, SCC OnLine, Cri LJ and case-name forms) plus near-miss distractors that match no judgment.
`data/testsets/t9/metadata_used.jsonl` is the index; its SCC, AIR, SCC OnLine and Cri LJ numbers are constructed (the metadata has only neutral and SCR numbers), so this set tests format handling, not
real reporter numbers. Arms (one directory each, one JSON file per string):

- `resolver`: `CitationIndex.resolve` (exact normalised keys for formal citations, fuzzy party matching for case names).
- `regex_only`: the comparison resolver: the string is looked up as written (case and spacing folded), with no format parsing or key normalisation; case names must equal the title.

Metrics: `resolution_accuracy/<format>` (a true string resolved to its judgment), `coverage` (true strings resolved at all), `false_resolution_rate` (distractors wrongly resolved), and on briefs
`overruled_cited_rate` (share of briefs that cite an overruled precedent without a warning). The brief rows come from T1 runs of Full and B0-B4 (`VS_F7_BRIEFS_N=N` runs the first N dev cases of `full`, `b0`, `b1`
offline and writes arms `brief_full`, `brief_b0`, `brief_b1`; the offline stores hold few good-law flags, so a rate of 0 there is no evidence). Treatment agreement (kappa) needs labeled
treatment pairs (the non-Qwen labeler of docs/handoff/gold-labeler.md has not labeled treatments); `score` computes Cohen's kappa when files carry `treatment_pred` and `treatment_gold`, and no arm writes them yet.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("resolver", "regex_only")
BRIEF_SYSTEMS = ("full", "b0", "b1")


def _fold(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


class RegexOnly:
    """The comparison resolver: literal lookup of the string among each judgment's citation strings (folded), nothing else."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.by_string: dict[str, set[str]] = {}
        for rec in records:
            strings = [rec.get("neutral_citation"), rec.get("title"), *(rec.get("citations") or [])]
            for s in strings:
                if s:
                    self.by_string.setdefault(_fold(str(s)), set()).add(str(rec["doc_id"]))

    def resolve(self, citation: str) -> str | None:
        """The one judgment that has this exact string, else None."""
        ids = self.by_string.get(_fold(citation), set())
        return next(iter(ids)) if len(ids) == 1 else None


def brief_rows(system: str, cases: list[dict[str, Any]], out_dir: str) -> None:
    """Run `system` on the cases offline and write one `brief` row per case: did it cite an overruled precedent without a warning."""
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.eval.runners.systems import system_runner

    runner, switches = system_runner(system)
    arm = f"brief_{system}"
    for case in cases:
        if fc.case_file(out_dir, arm, case["case_id"]).exists():
            continue
        ctx = driver.build_context(case, switches)
        produced = runner(case, ctx)
        brief = produced.get("brief") if isinstance(produced, dict) else produced.model_dump(mode="json")
        flagged = False
        for g in (brief or {}).get("grounds", []):
            for a in g.get("authorities", []):
                if a.get("good_law") == "OVERRULED" and "warning:" not in str(g.get("argument", "")).lower():
                    flagged = True
        fc.save_case(out_dir, arm, case["case_id"], {"brief": True, "cited_overruled_without_warning": flagged, "system": system})


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F7 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; arms `resolver` and `regex_only` (one JSON file per T9 string) and, with `VS_F7_BRIEFS_N`, `brief_<system>` arms
        shard: this shard's index
        n_shards: the number of shards (strings are dealt out by index)
    """
    from vakeel_sahayak.pipelines.citation_graph.resolve import CitationIndex

    root = fc.testsets_dir() / "t9"
    records = fc.read_jsonl(root / "metadata_used.jsonl")
    rows = fc.read_jsonl(os.environ.get("VS_FEATURE_CASES") or root / "strings.jsonl")[: fc.env_limit()]
    resolvers = {"resolver": CitationIndex(records), "regex_only": RegexOnly(records)}
    for arm in fc.selected_arms(ARMS):
        if arm not in resolvers:
            continue
        for i, row in fc.shard_slice(list(enumerate(rows)), shard, n_shards):
            cid = f"s{i:05d}"
            if fc.case_file(out_dir, arm, cid).exists():
                continue
            fc.save_case(out_dir, arm, cid, {"format": row["format"], "doc_id": row["doc_id"], "predicted_doc_id": resolvers[arm].resolve(row["string"]),
                                              "distractor": bool(row["distractor"]), "string": row["string"], "arm": arm})
    n = int(os.environ.get("VS_F7_BRIEFS_N", "0") or 0)
    if n and shard == 0:
        dev = fc.read_jsonl(fc.testsets_dir() / "t1" / "dev.jsonl")[:n]
        for system in BRIEF_SYSTEMS:
            brief_rows(system, dev, out_dir)


def kappa(pred: list[str], gold: list[str]) -> float | None:
    """Cohen's kappa of two label lists (None when chance agreement is 1)."""
    n = len(gold)
    if not n:
        return None
    labels = sorted(set(pred) | set(gold))
    po = sum(p == g for p, g in zip(pred, gold, strict=True)) / n
    pe = sum((pred.count(x) / n) * (gold.count(x) / n) for x in labels)
    return None if pe == 1 else (po - pe) / (1 - pe)


def score(run_dir: str) -> dict[str, float]:
    """Compute F7 metrics for one arm directory.

    Args:
        run_dir: an arm's directory: citation-string files (`format`, `doc_id`, `predicted_doc_id`, `distractor`), brief files (`brief`, `cited_overruled_without_warning`), treatment files

    Returns:
        `resolution_accuracy/<format>` and `coverage` over the true (non-distractor) strings, `false_resolution_rate` over the distractors, `overruled_cited_rate` over briefs,
        `treatment_kappa` when treatment pairs are present; a metric with nothing to measure is left out.

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    strings = [r for r in rows if "format" in r]
    true = [r for r in strings if not r.get("distractor")]
    fake = [r for r in strings if r.get("distractor")]
    out: dict[str, float | None] = {}
    for f in sorted({r["format"] for r in true}):
        rs = [r for r in true if r["format"] == f]
        out[f"resolution_accuracy/{f}"] = fc.rate(sum(r["predicted_doc_id"] == r["doc_id"] for r in rs), len(rs))
    out["coverage"] = fc.rate(sum(r["predicted_doc_id"] is not None for r in true), len(true))
    out["false_resolution_rate"] = fc.rate(sum(r["predicted_doc_id"] is not None for r in fake), len(fake))
    briefs = [r for r in rows if r.get("brief")]
    out["overruled_cited_rate"] = fc.rate(sum(bool(r["cited_overruled_without_warning"]) for r in briefs), len(briefs))
    tre = [r for r in rows if "treatment_pred" in r and "treatment_gold" in r]
    out["treatment_kappa"] = kappa([r["treatment_pred"] for r in tre], [r["treatment_gold"] for r in tre]) if tre else None
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
