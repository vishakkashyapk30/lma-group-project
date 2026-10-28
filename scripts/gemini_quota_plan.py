#!/usr/bin/env python3
"""How many days a piece of work needs on a rate-limited free tier (default: Gemini), per model, at the configured limits. Calls no model.

    .venv/bin/python scripts/gemini_quota_plan.py --n 250 --calls-per-item 6 --tokens-per-call 2500          # gold labelling: 250 orders x 6 tasks
    .venv/bin/python scripts/gemini_quota_plan.py --n 50 --calls-per-item 47 --tokens-per-call 1580 --model gemma-4-31b-it
    .venv/bin/python scripts/gemini_quota_plan.py --sweep [--phase 2] [--keys 4]                               # the gemini arms of configs/eval/sweep_dev.yaml
    .venv/bin/python scripts/gemini_quota_plan.py --n 1000 --calls-per-item 1 --tokens-per-call 3000 --failover

Limits come from configs/models.yaml `providers.<name>.models` (for Gemini: as shown in Google AI Studio on 2026-10-28 for one free-tier project;
re-check there, they change) and env `VS_GEMINI_RPM/RPD/TPM`. They apply per PROJECT: `--keys K` multiplies them only when the K keys belong to K
different projects. Two daily bounds are printed: requests per day (RPD) and tokens per day (TPM x 1440). `--remaining-today` (default: read
from the local request ledger for the first model) makes today count as a partial first day.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from vakeel_sahayak.models.hosted import planner  # noqa: E402
from vakeel_sahayak.models.registry import get_provider  # noqa: E402

SWEEP = REPO / "configs/eval/sweep_dev.yaml"


def sweep_rows(phase: int | None, backend: str) -> tuple[list[dict], dict]:
    """(arms on `backend` still to run, the backend block) of configs/eval/sweep_dev.yaml."""
    cfg = yaml.safe_load(SWEEP.read_text(encoding="utf-8"))
    block = (cfg.get("backends") or {}).get(backend) or {}
    rows = [a for a in cfg.get("arms") or [] if a.get("backend") == backend and a.get("status") in ("planned", None) and (phase is None or a.get("phase") == phase)]
    return rows, block


def arm_requests(arm: dict, est: dict) -> tuple[int, float]:
    """(requests, tokens per request) of one arm: n cases x runs x calls per case; calls per case from the arm (`calls_per_case`), else 1 for a
    single-call baseline (`single_call: true`), else round(calls of a Full case x the arm's token ratio); tokens per call from the Full measurement."""
    full_calls = float(est.get("calls_per_full_case", 47))
    full_tokens = float(est.get("tokens_per_full_case", 74228))
    ratio = float(arm.get("ratio", 1.0) or 0.0)
    if arm.get("calls_per_case"):
        calls = float(arm["calls_per_case"])
    elif arm.get("single_call"):
        calls = 1.0 * float(est.get("single_call_overhead", 1.3))  # one drafting call plus the structured-output repairs
    else:
        calls = max(1.0, round(full_calls * ratio))
    tokens_case = full_tokens * ratio
    per_call = tokens_case / calls if calls else 0.0
    return int(math.ceil(int(arm.get("n", 0)) * int(arm.get("runs", 1)) * calls)), per_call


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--provider", default="gemini")
    ap.add_argument("--n", type=int, help="items (orders, cases)")
    ap.add_argument("--calls-per-item", type=float, default=1.0)
    ap.add_argument("--tokens-per-call", type=float, default=2000.0, help="prompt + answer tokens of one request")
    ap.add_argument("--model", default=None, help="one model (default: every configured model, soonest first)")
    ap.add_argument("--keys", type=int, default=1, help="keys of DIFFERENT projects (limits are per project)")
    ap.add_argument("--remaining-today", type=int, default=None)
    ap.add_argument("--failover", action="store_true", help="also print the day-by-day split over the configured failover order")
    ap.add_argument("--sweep", action="store_true", help="plan the gemini arms of configs/eval/sweep_dev.yaml")
    ap.add_argument("--phase", type=int, default=None)
    args = ap.parse_args()
    spec = get_provider(args.provider)
    if spec is None or spec.builtin:
        print(f"no generic provider {args.provider!r} in configs/models.yaml providers:", file=sys.stderr)
        return 2
    print(f"{spec.name}: limits from configs/models.yaml (as shown in AI Studio on 2026-10-28; re-check there), per project; keys counted: {args.keys}")
    if args.sweep:
        rows, block = sweep_rows(args.phase, args.provider)
        est = block.get("estimate") or {}
        model = args.model or block.get("model") or spec.default_model
        total, weighted = 0, 0.0
        print(f"\nsweep arms on backend {args.provider!r} (model {model}); calls and tokens per case from {est.get('source', 'the Full pilot')}")
        print(f"{'arm':<10}{'phase':>6}{'n':>5}{'runs':>5}{'requests':>10}{'tok/req':>9}  days on {model}")
        by_phase: dict[int, int] = {}
        for arm in rows:
            req, tok = arm_requests(arm, est)
            p = planner.plan_model(spec, model, req, tok, keys=args.keys)
            total += req
            weighted += req * tok
            by_phase[int(arm.get("phase", 0))] = by_phase.get(int(arm.get("phase", 0)), 0) + req
            print(f"{arm['id']:<10}{arm.get('phase', ''):>6}{arm.get('n', 0):>5}{arm.get('runs', 1):>5}{req:>10}{round(tok):>9}  {p['days'] if p['feasible'] else 'infeasible'}")
        print(f"\ntotal {total} requests ({', '.join(f'phase {k}: {v}' for k, v in sorted(by_phase.items()))}); mean {round(weighted / total) if total else 0} tokens per request")
        print(planner.format_plans(planner.rank_models(spec, total, weighted / total if total else 0, keys=args.keys)))
        warns = planner.paired_warnings([{"id": a["id"], "backend": args.provider, "model": a.get("model") or model, "failover": bool(a.get("failover"))} for a in rows])
        for w in warns:
            print("WARNING: " + w)
        return 0
    if args.n is None:
        ap.error("--n is required (or --sweep)")
    n_req = int(math.ceil(args.n * args.calls_per_item))
    remaining = args.remaining_today
    if remaining is None and args.model:
        try:
            from vakeel_sahayak.models.hosted.keys import pool
            from vakeel_sahayak.models.hosted.quota import QuotaLedger

            led = QuotaLedger()
            keys = pool(spec.key_env)
            if keys:
                remaining = sum(led.remaining_today(spec.name, k.fp, args.model, spec.limits_for(args.model), spec.quota_day_tz) for k in keys)
        except Exception:  # noqa: BLE001 - planning works without a ledger
            remaining = None
    print(f"work: {args.n} items x {args.calls_per_item} calls = {n_req} requests of about {round(args.tokens_per_call)} tokens")
    if args.model:
        p = planner.plan_model(spec, args.model, n_req, args.tokens_per_call, keys=args.keys, remaining_today=remaining)
        print(planner.format_plans([p]))
        if remaining is not None:
            print(f"today the ledger still allows {remaining} requests on {args.model}; the work needs {p['days']} quota day(s) counting today")
    else:
        print(planner.format_plans(planner.rank_models(spec, n_req, args.tokens_per_call, keys=args.keys)))
        best = planner.pick_model(spec, n_req, args.tokens_per_call, keys=args.keys)
        print(f"soonest: {best['model']} ({best['days']} day(s), bound by {best['binding']})" if best else "no configured model can take these requests")
    if args.failover:
        order = [args.model or spec.default_model, *spec.failover]
        for i, day in enumerate(planner.failover_schedule(spec, order, n_req, args.tokens_per_call, keys=args.keys), 1):
            print(f"day {i}: " + ", ".join(f"{m} {k}" for m, k in day.items()))
        print("failover mixes models: never use it inside a paired comparison (planner.paired_warnings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
