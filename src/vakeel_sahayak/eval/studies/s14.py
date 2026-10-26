"""S14b and S14c: batch scheduling policies in a simulation on the batch test set T5 (evaluation plan 3.3 row S14 (c), claim C31).

Policies (`batch.urgency.order_cards`): `fifo` first come first served (S14b), `urgency` the fixed legal-urgency rule (the desk's default), `urgency_least_work` the same rule with ties
going to the case that has received the least service so far (S14c, least attained service as in Autellix, arXiv 2502.13965); `shortest_first` (shortest job first) is printed as a
reference. Nothing is run through a model: the study replays the order in which a desk with one worker would serve the 300 T5 cases.

Service model (assumptions, recorded in the result):
* a full run of a case is `stages` stages of equal length (the factors a case works through; a constructed number, 3 to 8 from a hash of the case id, unless the row gives `stages`);
  the mean full run is `case_hours` = 0.25 GPU-hours (`batch.queue.DEFAULT_CASE_HOURS`), so a stage is `case_hours / mean stages`;
* one worker serves one stage at a time and picks, before every stage, the pending case with the smallest policy key (so equal-urgency cases interleave under `urgency_least_work` and are
  served one after the other under `urgency`);
* the desk works `hours_per_day` = 5 hours a day (F4's 20 cases a day at 0.25 hours);
* a planted case (a legal deadline `days_to_deadline` days after the as-of date) MISSES it when its full run STARTS after the deadline day (the F4 convention) and, separately, when it FINISHES after it.

Metrics: missed-deadline rate (start and finish), pairwise ranking accuracy (planted before unplanted by first service), planted order accuracy (planted pairs in the gold deadline order),
mean first-service delay and mean finish time of planted cases, makespan, and cases per node-hour (the model is work-conserving, so every policy has the same throughput; the number is
there because C31 asks for cases per node-hour with the same G1 recall, and the scheduling policies cannot change recall: they change only the order). The plan cache (S14a) changes
throughput through `cache_saving`, a fraction of stage time saved on cache hits (0 here: measured on real runs by `driver run --system S14`).

Run: `python -m vakeel_sahayak.eval.studies s14 --out <dir> [--n 300]`.
"""

from __future__ import annotations

import json
import math
import zlib
from pathlib import Path
from typing import Any

from vakeel_sahayak.eval.scoring import stats_extra as sx
from vakeel_sahayak.eval.studies.common import write_result

POLICIES = ("fifo", "urgency", "urgency_least_work", "shortest_first")
ARM_OF = {"fifo": "S14b", "urgency": "default (Full desk)", "urgency_least_work": "S14c", "shortest_first": "reference"}
MEAN_STAGES = 5.5


def stages_of(case_id: str, given: int | None = None) -> int:
    """Stages of a case's full run: the row's own number, else 3 to 8 from a CRC of the case id (a constructed, reproducible spread)."""
    return int(given) if given else 3 + zlib.crc32(case_id.encode()) % 6


def simulate(cases: list[dict[str, Any]], policy: str, *, stage_hours: float, hours_per_day: float = 5.0, nodes: int = 1) -> dict[str, Any]:
    """One policy on prepared cases (arrival order = list order).

    Each case: `case_id`, `key` (the urgency key, smaller is more urgent), `planted`, `days_to_deadline`, `gold_rank`, `stages`.

    Returns:
        Per-case `first`, `finish` (hours) and the metrics listed in the module docstring.
    """
    if policy not in POLICIES:
        raise ValueError(f"unknown policy {policy!r}: use one of {', '.join(POLICIES)}")
    left = {c["case_id"]: int(c["stages"]) for c in cases}
    attained = dict.fromkeys(left, 0)
    arrival = {c["case_id"]: i for i, c in enumerate(cases)}
    key_of = {c["case_id"]: tuple(c["key"]) for c in cases}

    def key(cid: str) -> tuple:
        if policy == "fifo":
            return (arrival[cid],)
        if policy == "urgency":
            return (*key_of[cid], cid)
        if policy == "urgency_least_work":
            return (*key_of[cid], attained[cid], cid)
        return (int(next(c["stages"] for c in cases if c["case_id"] == cid)), *key_of[cid], cid)

    t = 0.0
    first: dict[str, float] = {}
    finish: dict[str, float] = {}
    pending = set(left)
    while pending:
        cid = min(pending, key=key)
        first.setdefault(cid, t)
        t += stage_hours / nodes
        attained[cid] += 1
        left[cid] -= 1
        if left[cid] == 0:
            finish[cid] = t
            pending.discard(cid)
    planted = [c for c in cases if c["planted"]]
    others = [c for c in cases if not c["planted"]]

    def day_start(h: float) -> int:
        return int(h // hours_per_day) + 1

    def day_finish(h: float) -> int:
        return max(1, math.ceil(h / hours_per_day - 1e-12))

    miss_start = [day_start(first[c["case_id"]]) > int(c["days_to_deadline"]) for c in planted]
    miss_finish = [day_finish(finish[c["case_id"]]) > int(c["days_to_deadline"]) for c in planted]
    pairs = [(first[p["case_id"]] < first[u["case_id"]]) for p in planted for u in others]
    gold_pairs = [first[a["case_id"]] < first[b["case_id"]] for a in planted for b in planted if a.get("gold_rank") and b.get("gold_rank") and a["gold_rank"] < b["gold_rank"]]

    def rate(xs: list[bool]) -> dict[str, Any]:
        k, n = sum(xs), len(xs)
        p, lo, hi = sx.wilson_interval(k, n)
        return {"value": (k / n) if n else None, "lo": None if not n else lo, "hi": None if not n else hi, "k": k, "n": n}

    return {"policy": policy, "missed_start": rate(miss_start), "missed_finish": rate(miss_finish), "pairwise_ranking_accuracy": rate(pairs), "planted_order_accuracy": rate(gold_pairs),
            "mean_planted_first_service_h": (sum(first[c["case_id"]] for c in planted) / len(planted)) if planted else None,
            "mean_planted_finish_h": (sum(finish[c["case_id"]] for c in planted) / len(planted)) if planted else None,
            "makespan_h": t, "cases_per_node_hour": len(cases) / (t * nodes) if t else None, "first": first, "finish": finish, "missed_start_flags": miss_start}


def prepare(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Simulation cases from T5 rows: the urgency key of each case's triage card (`batch.urgency.card_key`, from the Rights Radar report and the reasons) and the planted flag."""
    from vakeel_sahayak.batch.urgency import card_key
    from vakeel_sahayak.eval.features.f4_batch_desk import build_cards

    cards = build_cards(rows)
    return [{"case_id": r["case_id"], "key": card_key(c), "planted": bool(r.get("urgent")), "days_to_deadline": r.get("days_to_deadline"), "gold_rank": r.get("rank"),
             "stages": stages_of(r["case_id"], r.get("stages"))} for r, c in zip(rows, cards, strict=True)]


def run(out_dir: str, n: int | None = None, seed: int = 0, *, cases_path: str | None = None, case_hours: float = 0.25, hours_per_day: float = 5.0, cache_saving: float = 0.0) -> dict[str, Any]:
    """The S14b / S14c scheduling simulation on T5; writes `s14.json` and `s14.md` under `out_dir`.

    Args:
        out_dir: output directory
        n: first n cases of the file (default all 300; a smaller n keeps the planted share only if the file is ordered that way, so leave it unset for a result)
        seed: unused (the simulation is deterministic); kept for the common signature
        cases_path: T5 `cases.jsonl` (default `<testsets>/t5/cases.jsonl`)
        case_hours, hours_per_day: service model (see the module docstring)
        cache_saving: fraction of stage time saved by the plan cache (0 = no cache)
    """
    from vakeel_sahayak.eval import feature_common as fc

    path = Path(cases_path) if cases_path else fc.testsets_dir() / "t5" / "cases.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"no T5 case file at {path}: build it with `python -m vakeel_sahayak.testsets.t5_batch`")
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if n:
        rows = rows[:n]
    cases = prepare(rows)
    stage_hours = case_hours / MEAN_STAGES * (1.0 - cache_saving)
    sims = {p: simulate(cases, p, stage_hours=stage_hours, hours_per_day=hours_per_day) for p in POLICIES}
    base = sims["fifo"]["missed_start_flags"]
    comparison = {}
    for p in ("urgency", "urgency_least_work"):
        m = sx.mcnemar_exact([not x for x in sims[p]["missed_start_flags"]], [not x for x in base])
        comparison[p + " vs fifo (met deadline, McNemar exact)"] = {"b10": m["b10"], "b01": m["b01"], "p": m["p"]}
    out = {"n_cases": len(cases), "n_planted": sum(1 for c in cases if c["planted"]),
           "assumptions": {"case_hours": case_hours, "mean_stages": MEAN_STAGES, "stage_hours": stage_hours, "hours_per_day": hours_per_day, "workers": 1, "cache_saving": cache_saving,
                           "stages": "3 to 8 from a CRC of the case id (constructed, not measured)", "deadline_rule": "start day > days_to_deadline (F4 convention); finish day reported separately"},
           "policies": {p: {k: v for k, v in s.items() if k not in ("first", "finish", "missed_start_flags")} for p, s in sims.items()}, "comparison": comparison}

    def cell(r: dict[str, Any]) -> str:
        return "n/a" if r["value"] is None else f"{r['value']:.3f} [{r['lo']:.3f}, {r['hi']:.3f}] ({r['k']}/{r['n']})"

    rows_out = [[f"{p} ({ARM_OF[p]})", cell(s["missed_start"]), cell(s["missed_finish"]), cell(s["pairwise_ranking_accuracy"]), cell(s["planted_order_accuracy"]),
                 s["mean_planted_first_service_h"], s["cases_per_node_hour"]] for p, s in out["policies"].items()]
    notes = ["Simulation, not a measurement: service times are constructed (stages per case from a hash of the case id), one worker, 5 working hours a day. The policies change only the order of service, so recall is untouched and throughput (cases per node-hour) is identical by construction; the plan cache (S14, run with the driver) is what moves throughput.",
             "Intervals are Wilson 95%. Planted = the 100 T5 cases with a legal deadline 1 to 7 days after the as-of date; unplanted = 200 T1 cases with none.",
             "McNemar (met-deadline, policy vs fifo): " + "; ".join(f"{k}: discordant {v['b10']}/{v['b01']}, p={v['p']:.4f}" for k, v in comparison.items())]
    return write_result(out_dir, "s14", out, "S14b/S14c: scheduling policies on T5 (simulation, preliminary)",
                        "Order of service of the batch desk replayed under three policies and a reference; offline, no model; constructed service times.",
                        ["Policy (arm)", "Missed deadline, start [95% CI]", "Missed deadline, finish", "Pairwise ranking accuracy", "Planted order accuracy", "Mean planted first service (h)", "Cases per node-hour"],
                        rows_out, notes)
