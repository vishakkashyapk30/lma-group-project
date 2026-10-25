"""Feature evaluation F4: Pairokar vs no cache and FIFO order. Test set: T5. Metrics: missed-deadline rate; pairwise ranking accuracy; cases per node-hour; cache hit rate; output equality with single-case runs (plan §15.6).

Test set T5: 300 cases at one as-of date (2026-11-02): 200 T1 cases with no deadline and 100 T4 scenarios re-dated so a deadline falls 1 to 7 days later (a default-bail window opens or the
s.479 threshold is reached); the gold ranking is the plan §11 urgency rule. Arms (one directory each, one JSON file per case):

- `pairokar`: cards from the Rights Radar and `batch.urgency.assess`, ordered by the fixed urgency rule (`order_cards` policy `urgency`), full runs sharing one retrieval cache.
- `no_cache`: the same order, every full run on its own (also the single-case run that outputs are compared with).
- `fifo`: arrival order (`order_cards` policy `fifo`), the order of `cases.jsonl`.

Ranking and missed deadlines are computed from the order alone. A planted case MISSES its deadline when its full run starts after the deadline day: the desk serves `CASES_PER_DAY` = 20 cases a day (5 GPU
hours a day at the default 0.25 GPU-hours per full run, `batch.queue.DEFAULT_CASE_HOURS`); this capacity is an assumption of the evaluation, stated here and recorded in every file. Cases per node-hour, cache hit
rate and output equality need real full runs: set `VS_F4_STAGE2=N` to run the first N T1 cases (the unplanted ones, which carry facts text) through `eval.runners.driver.run_agents` with and without the cache
(offline stand-in models by default, so the seconds are the stand-in's); cases without a full run have no value for those three metrics and they are left out of the means. The urgency rule only knows a
default-bail window and an already-crossed s.479 threshold as deadlines (`batch/urgency.py`), so an s.479 threshold still days away is ranked by custody length: `planted_order_accuracy` (planted
pairs ordered as the gold deadline ranking) shows how far that departs from the plan §11 gold order. This is a finding of the evaluation, not a tuned result.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from typing import Any

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("pairokar", "no_cache", "fifo")
CASES_PER_DAY = 20


def radar_check(facts: dict[str, Any]) -> Any:
    """The Radar's check for a planted T5 case (default bail when the facts carry `day`, else the s.479 limit)."""
    from vakeel_sahayak.rights.inputs import RuleInputs
    from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
    from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule

    if "day" in facts:
        return DefaultBailRule().evaluate(RuleInputs(as_of=facts["as_of"], first_remand=facts["first_remand"], max_punishment=facts["max_punishment"],
                                                     charge_sheet_date=facts["charge_sheet"], charge_sheet_filed=bool(facts["charge_sheet"])))
    return UndertrialLimitRule().evaluate(RuleInputs(as_of=facts["as_of"], max_punishment=facts["max_punishment"], custody_days=facts["custody_days"], arrest_date=facts["arrest_date"],
                                                     antecedents_known=facts["first_time"] is not None, first_time_offender=facts["first_time"]))


def build_cards(rows: list[dict[str, Any]]) -> list[Any]:
    """One triage card per T5 row, in arrival order: planted cases from their Radar report and the urgency rule, the rest with no deadline."""
    from vakeel_sahayak.batch.urgency import assess
    from vakeel_sahayak.schemas.rights_report import RightsReport
    from vakeel_sahayak.schemas.triage import TriageCard

    cards = []
    for row in rows:
        reasons: list[str] = []
        if row.get("facts"):
            check = radar_check(row["facts"])
            report = RightsReport(case_id="case-0001", as_of=row["facts"]["as_of"], checks=[check])
            reasons = assess(report, row["facts"].get("custody_days"), []).texts()
        cards.append(TriageCard(case_id=row["case_id"], urgency_rank=0, reasons=reasons))
    return cards


def order_for(arm: str, cards: list[Any]) -> list[str]:
    """Case ids in the order an arm serves them."""
    from vakeel_sahayak.batch.urgency import order_cards

    if arm == "fifo":
        return [c.case_id for c in order_cards(cards, "fifo", arrival={c.case_id: i for i, c in enumerate(cards)})]
    return [c.case_id for c in order_cards(cards, "urgency")]


def stage2_sample(rows: list[dict[str, Any]], n: int, out_dir: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Full runs of the first `n` unplanted T1 cases with the shared cache and without it: seconds, cache hit, output equality. Saved under `out_dir/_stage2.json` (resumable)."""
    from pathlib import Path

    store = Path(out_dir) / "_stage2.json"
    store.parent.mkdir(parents=True, exist_ok=True)
    done: dict[str, dict[str, dict[str, Any]]] = json.loads(store.read_text()) if store.exists() else {}
    if n <= 0:
        return done
    from vakeel_sahayak.batch.cache import RetrievalCache
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.eval.runners.systems import system_runner

    t1 = {r["case_id"]: r for r in fc.read_jsonl(fc.testsets_dir() / "t1" / "cases.jsonl")}
    runner, switches = system_runner("full")
    cache = RetrievalCache()
    picks = [r for r in rows if r["source"] == "T1" and r["case_id"] in t1][:n]
    for row in picks:
        cid = row["case_id"]
        if cid in done:
            continue
        case = {**t1[cid], "case_id": cid}
        out: dict[str, dict[str, Any]] = {}
        for arm, shared in (("pairokar", cache), ("no_cache", None)):
            before = cache.stats()["hits"] if shared else 0.0
            ctx = driver.build_context(case, switches, cache=shared)
            t0 = time.monotonic()
            produced = runner(case, ctx)
            seconds = time.monotonic() - t0
            brief = produced.get("brief") if isinstance(produced, dict) else produced.model_dump(mode="json")
            canon = json.dumps([(g["factor"], g["stance"], g["argument"]) for g in (brief or {}).get("grounds", [])], sort_keys=True)
            out[arm] = {"seconds": seconds, "cache_hit": (cache.stats()["hits"] - before) > 0 if shared else False, "canon": canon}
        out["equal"] = {"value": out["pairokar"]["canon"] == out["no_cache"]["canon"]}
        done[cid] = out
        store.write_text(json.dumps(done))
    return done


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F4 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm (`pairokar`, `no_cache`, `fifo`), one `<case id>.json` per case
        shard: this shard's index
        n_shards: the number of shards (cases are dealt out by index; the order is always computed over the whole set)
    """
    path = os.environ.get("VS_FEATURE_CASES") or str(fc.testsets_dir() / "t5" / "cases.jsonl")
    rows = fc.read_jsonl(path)
    cards = build_cards(rows)
    by_id = {r["case_id"]: r for r in rows}
    stage2 = stage2_sample(rows, int(os.environ.get("VS_F4_STAGE2", "0") or 0), out_dir) if shard == 0 else {}
    mine = set(c["case_id"] for c in fc.shard_slice(rows, shard, n_shards))
    for arm in fc.selected_arms(ARMS):
        order = order_for(arm, cards)
        position = {cid: i + 1 for i, cid in enumerate(order)}
        for cid in order:
            if cid not in mine or fc.case_file(out_dir, arm, cid).exists():
                continue
            row = by_id[cid]
            planted = bool(row.get("urgent"))
            served_day = math.ceil(position[cid] / CASES_PER_DAY)
            s2 = stage2.get(cid, {})
            fc.save_case(out_dir, arm, cid, {
                "arm": arm, "planted": planted, "rank": position[cid], "gold_rank": row.get("rank"), "days_to_deadline": row.get("days_to_deadline"), "served_day": served_day,
                "missed_deadline": bool(planted and served_day > int(row["days_to_deadline"])), "cases_per_day_assumed": CASES_PER_DAY,
                "seconds": s2.get(arm if arm in ("pairokar", "no_cache") else "no_cache", {}).get("seconds") if s2 else None,
                "cache_hit": s2.get(arm, {}).get("cache_hit") if s2 and arm in ("pairokar", "no_cache") else None,
                "output_equal_single": s2.get("equal", {}).get("value") if s2 and arm in ("pairokar", "no_cache") else None,
                "models": "offline stand-in" if os.environ.get("VS_LLM_BACKEND", "offline") == "offline" else os.environ.get("VS_LLM_BACKEND"),
            })


def score(run_dir: str) -> dict[str, float]:
    """Compute F4 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (one JSON file per case with `planted`, `rank`, `missed_deadline`, and, where a full run was made, `cache_hit`, `output_equal_single`, `seconds`)

    Returns:
        `missed_deadline_rate` (over planted cases), `pairwise_ranking_accuracy` (over planted x unplanted pairs: the planted case is ranked ahead), `planted_order_accuracy` (extra: planted pairs ordered as the gold deadline ranking, when `gold_rank` is present), `cases_per_node_hour`,
        `cache_hit_rate`, `output_equality_rate` (each over the cases that have a value).

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    planted = [r for r in rows if r.get("planted")]
    others = [r for r in rows if not r.get("planted")]
    pairs = [(p["rank"], u["rank"]) for p in planted for u in others]
    ordered = [(a["rank"], b["rank"], a["gold_rank"], b["gold_rank"]) for a in planted for b in planted if a.get("gold_rank") and b.get("gold_rank") and a["gold_rank"] < b["gold_rank"]]
    secs = [r["seconds"] for r in rows if r.get("seconds") is not None]
    out = {
        "missed_deadline_rate": fc.rate(sum(bool(r.get("missed_deadline")) for r in planted), len(planted)),
        "pairwise_ranking_accuracy": fc.rate(sum(a < b for a, b in pairs), len(pairs)),
        "planted_order_accuracy": fc.rate(sum(x[0] < x[1] for x in ordered), len(ordered)),
        "cases_per_node_hour": fc.rate(len(secs), sum(secs) / 3600.0),
        "cache_hit_rate": fc.mean(float(bool(r["cache_hit"])) for r in rows if r.get("cache_hit") is not None),
        "output_equality_rate": fc.mean(float(bool(r["output_equal_single"])) for r in rows if r.get("output_equal_single") is not None),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
