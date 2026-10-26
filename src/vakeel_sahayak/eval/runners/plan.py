"""Describe an evaluation job without running it: cases, systems, runs, estimated tokens, dollars and hours (`driver plan --job <name>`).

The estimate is arithmetic on the measured numbers in `configs/eval/runs.yaml` (`estimate:`, copied from `data/eval/token_measure.json`: the Full system on
`gpt-6-luna`, three T1 dev cases, cache off) times a per-system token ratio (`estimate.token_ratio`, relative to Full, from the evaluation plan 7.2 token basis; an
unlisted system counts as 1.0, so its figure is an upper bound or a guess and is flagged `unmeasured`). Nothing here calls a model, reads a store or writes a file.
`plan_all` walks the jobs in priority order and says which ones still fit the OpenAI cap once the earlier ones are paid, so the cap is not spent twice.
"""

from __future__ import annotations

from typing import Any

from vakeel_sahayak.eval.runners.systems import canonical_system, split_system_id

NO_MODEL = {"b6"}  # B6 is a rule baseline: no model call, no cost


def runs_config() -> dict[str, Any]:
    """configs/eval/runs.yaml (the same file `shard_runner` reads)."""
    from vakeel_sahayak.eval.runners.shard_runner import runs_config as load

    return load()


def job_systems(job: dict[str, Any]) -> list[str]:
    """The system ids a job runs: `systems`, or the ablation `ids`, or the arms of an ablation job written as `variants` (A5)."""
    if job.get("systems"):
        return [str(s) for s in job["systems"]]
    if job.get("ids"):
        return [str(s) for s in job["ids"]]
    return []


def covered_variants(name: str, job: dict[str, Any], meta: dict[str, Any] | None = None) -> set[str]:
    """Canonical variant ids (and baseline ids) a job covers: from its systems, plus the explicit `covers` of `job_meta` (A5 and A10 have jobs of their own shape)."""
    out: set[str] = set()
    for system in job_systems(job):
        canon = canonical_system(system)
        out.add(split_system_id(canon)[0])
    for ident in (meta or {}).get("covers", []):
        out.add(canonical_system(str(ident)).split(":")[0])
    return out


def token_ratio(cfg: dict[str, Any], system: str) -> tuple[float, bool]:
    """The token ratio of a system against Full and whether it is a guess (not listed in `estimate.token_ratio`)."""
    ratios = (cfg.get("estimate") or {}).get("token_ratio") or {}
    base = split_system_id(canonical_system(system))[0]
    for key in (base, base.lower(), base.upper()):
        if key in ratios:
            return float(ratios[key]), False
    return float(ratios.get("default", 1.0)), True


def case_runs_of(job: dict[str, Any]) -> tuple[int | None, int, int]:
    """`(cases, runs, case_runs_per_system)`; the size key is `cases`, else `inputs`, `bundles`, `scenarios`, `pages`, `questions` (None when the job has none)."""
    n = None
    for key in ("cases", "inputs", "bundles", "scenarios", "questions", "updates", "pages"):
        if job.get(key) is not None:
            n = int(job[key])
            break
    runs = int(job.get("runs", 1))
    return n, runs, (n or 0) * runs


def sarvam_inr_per_case(cfg: dict[str, Any], model: str | None = None) -> float:
    """INR of one Full case on a Sarvam-hosted model: measured tokens (uncached input, cached input, output) times the dashboard price per 1M tokens (`budgets`)."""
    est, bud = cfg.get("estimate") or {}, cfg.get("budgets") or {}
    price = (bud.get("sarvam_prices_inr_per_1m") or {})[model or bud.get("sarvam_model", "sarvam-105b")]
    tin, tout = float(est.get("tokens_in_per_case", 0)), float(est.get("tokens_out_per_case", 0))
    cached = tin * float(est.get("cached_input_share", 0.0))
    return ((tin - cached) * price["input"] + cached * price["cached"] + tout * price["output"]) / 1e6


def sarvam_cap_inr(cfg: dict[str, Any] | None = None) -> float:
    """The Sarvam cap in INR: env `VS_SARVAM_CAP_INR` when set, else `budgets.sarvam_cap_inr` (default 25). The plan sizes against this value, never a constant."""
    import os

    cfg = cfg or runs_config()
    raw = (os.environ.get("VS_SARVAM_CAP_INR") or "").strip()
    return float(raw) if raw else float((cfg.get("budgets") or {}).get("sarvam_cap_inr", 0.0))


def estimate_job(name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """The plan of one job as a dict (see `format_plan` for the printed form).

    Raises:
        ValueError: unknown job.
    """
    cfg = cfg or runs_config()
    jobs = cfg["jobs"]
    if name not in jobs:
        raise ValueError(f"unknown job {name!r}: use one of {sorted(jobs)}")
    job = jobs[name]
    meta = (cfg.get("job_meta") or {}).get(name, {})
    est = cfg.get("estimate") or {}
    systems = job_systems(job)
    n, runs, per_system = case_runs_of(job)
    per_case_usd, per_case_in = float(est.get("usd_per_case", 0.0)), float(est.get("tokens_in_per_case", 0))
    per_case_out, per_case_s = float(est.get("tokens_out_per_case", 0)), float(est.get("seconds_per_case", 0))
    inr_case = sarvam_inr_per_case(cfg) if (cfg.get("budgets") or {}).get("sarvam_prices_inr_per_1m") else None
    rows, usd, tin, tout, seconds, unmeasured, inr = [], 0.0, 0.0, 0.0, 0.0, False, 0.0
    for system in systems:
        ratio, guess = token_ratio(cfg, system)
        modelless = split_system_id(canonical_system(system))[0] in NO_MODEL
        r = 0.0 if modelless else ratio
        unmeasured = unmeasured or (guess and not modelless)
        k = per_system
        rows.append({"system": system, "case_runs": k, "token_ratio": r, "unmeasured": guess and not modelless,
                     "tokens_in": round(k * per_case_in * r), "usd": round(k * per_case_usd * r, 4),
                     "inr": round(k * (inr_case or 0.0) * r, 2)})
        inr += k * (inr_case or 0.0) * r
        usd += k * per_case_usd * r
        tin += k * per_case_in * r
        tout += k * per_case_out * r
        seconds += k * per_case_s * r
    modelled = bool(systems) and n is not None
    rescoring = bool(job.get("rescoring")) and int(job.get("model_calls", 0)) == 0  # rescoring only: no model call, cost 0
    cap = float(est.get("openai_cap_usd", 0.0))
    out = {
        "job": name, "where": job.get("where"), "testset": job.get("testset"), "tier": meta.get("tier"), "backend": meta.get("backend"),
        "cases": n, "runs": runs, "systems": systems, "case_runs": per_system * len(systems), "per_system": rows,
        "tokens_in": round(tin), "tokens_out": round(tout), "usd_if_openai": round(usd, 4) if modelled else None,
        "inr_if_sarvam": round(inr, 2) if modelled and inr_case is not None else None,
        "hours_if_serial": round(seconds / 3600, 2) if modelled else None, "node_hours": job.get("node_hours"),
        "unmeasured": unmeasured, "openai_cap_usd": cap,
        "fits_openai_cap": (usd <= cap) if modelled else None,
        "note": meta.get("note"),
    }
    if rescoring:
        out.update(usd_if_openai=0.0, inr_if_sarvam=0.0, hours_if_serial=0.0, fits_openai_cap=True, kind="rescoring only: no model call, cost 0 "
                   f"(gold sources {', '.join(job.get('gold_sources') or [])}; systems: {job.get('systems_from', 'existing outputs')})")
    elif not systems:
        out["kind"] = "not a systems job: sized by its own keys (" + ", ".join(k for k in job if k not in {"where"}) + ")"
    return out


def plan_all(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Every job in `priority` order (jobs not listed last), with the running estimated spend of the jobs planned on each hosted backend (`openai_running_usd`, `sarvam_running_inr`)
    and `cum_usd_if_all_openai` (the running total if every priced job ran on gpt-6-luna)."""
    cfg = cfg or runs_config()
    order = list(cfg.get("priority") or [])
    return jobs_plan(order + [j for j in cfg["jobs"] if j not in order], cfg)


def jobs_plan(names: list[str], cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The plans of the named jobs in order, with running totals per backend."""
    cfg = cfg or runs_config()
    usd = inr = cum = 0.0
    rows = []
    for name in names:
        p = estimate_job(name, cfg)
        if p["usd_if_openai"] is not None:
            cum += p["usd_if_openai"]
            if p.get("backend") == "openai":
                usd += p["usd_if_openai"]
        if p["inr_if_sarvam"] is not None and p.get("backend") == "sarvam":
            inr += p["inr_if_sarvam"]
        p.update(openai_running_usd=round(usd, 4), sarvam_running_inr=round(inr, 2), cum_usd_if_all_openai=round(cum, 4))
        rows.append(p)
    return rows


def spend_summary(rows: list[dict[str, Any]], cfg: dict[str, Any] | None = None) -> tuple[dict[str, float], list[str]]:
    """Estimated spend per hosted backend over `rows` (jobs planned on `openai` in USD, on `sarvam` in INR) and the warnings for a cap that is exceeded."""
    cfg = cfg or runs_config()
    bud = cfg.get("budgets") or {}
    spend = {"openai_usd": round(sum(p["usd_if_openai"] or 0 for p in rows if p.get("backend") == "openai"), 4),
             "sarvam_inr": round(sum(p["inr_if_sarvam"] or 0 for p in rows if p.get("backend") == "sarvam"), 2)}
    warnings = []
    for key, cap_key, unit in (("openai_usd", "openai_usd_code_default", "USD"), ("sarvam_inr", "sarvam_cap_inr", "INR")):
        cap = sarvam_cap_inr(cfg) if key == "sarvam_inr" else bud.get(cap_key)
        if cap is not None and spend[key] > float(cap):
            warnings.append(f"WARNING: planned {key.split('_')[0]} spend {spend[key]:.2f} {unit} exceeds the cap of {float(cap):.2f} {unit}: reduce cases or move jobs to Ada")
    return spend, warnings


def sarvam_full_view(cfg: dict[str, Any] | None = None) -> str:
    """The full intended Sarvam plan: every generative job priced on Sarvam-105B whatever its planned backend, with totals by tier and how many Full case-runs the cap buys.
    This is the credit total needed to run everything on Sarvam instead of reducing floor sizes; the `fits` column is against the cap now set."""
    cfg = cfg or runs_config()
    rows = [p for p in plan_all(cfg) if p["inr_if_sarvam"] is not None and p["job"] not in {"openai_sparring_block"}]
    cap = sarvam_cap_inr(cfg)
    run, lines = 0.0, [f"{'job':<26}{'tier':<5}{'status':<10}{'planned on':<11}{'case-runs':>10}{'INR':>10}{'running INR':>13}  fits cap {cap:g}"]
    meta = cfg.get("job_meta") or {}
    tot = {"A": 0.0, "B": 0.0, "C": 0.0, "X": 0.0}
    for p in rows:
        run += p["inr_if_sarvam"]
        tot[str(p["tier"] or "X")] = tot.get(str(p["tier"] or "X"), 0.0) + p["inr_if_sarvam"]
        status = (meta.get(p["job"]) or {}).get("status", "committed")
        lines.append(f"{p['job']:<26}{str(p['tier'] or '-'):<5}{status:<10}{str(p['backend']):<11}{p['case_runs']:>10}{p['inr_if_sarvam']:>10.1f}{run:>13.1f}  {'yes' if run <= cap else 'no'}")
    per = sarvam_inr_per_case(cfg)
    lines.append(f"total INR {run:.0f} (tier A {tot['A']:.0f}, B {tot['B']:.0f}, C {tot['C']:.0f}, not in plan {tot['X']:.0f}); Full case = INR {per:.2f}; the cap of INR {cap:g} buys about {int(cap / per)} Full case-runs")
    lines.append("jobs counted once each; openai_sparring_block is left out (its A2, A8, A9, S8, S9 arms are in `ablations`, `s8_self_critique`, `s9_sampling_critic`); jobs with no case-run size are not priced")
    return "\n".join(lines)


def format_plan(p: dict[str, Any]) -> str:
    """The printed plan of one job (also what `driver plan` writes to stdout)."""
    lines = [f"job {p['job']}: where={p['where']} testset={p['testset']} tier={p['tier']} backend={p['backend']}"]
    if p.get("kind"):
        lines.append("  " + p["kind"])
    lines.append(f"  cases={p['cases']} runs={p['runs']} systems={', '.join(p['systems']) or '-'}  case-runs={p['case_runs']}")
    for r in p["per_system"]:
        lines.append(f"    {r['system']:<22} case-runs={r['case_runs']:<5} token-ratio={r['token_ratio']:<5} tokens-in={r['tokens_in']:>10,} usd={r['usd']:.4f} inr={r['inr']:.2f}"
                     + ("  (ratio is a default: unmeasured)" if r["unmeasured"] else ""))
    if p["usd_if_openai"] is not None:
        lines.append(f"  estimate: tokens in {p['tokens_in']:,}, out {p['tokens_out']:,}; {p['usd_if_openai']:.2f} USD if run on gpt-6-luna "
                     f"(cap {p['openai_cap_usd']:.2f} USD: {'fits' if p['fits_openai_cap'] else 'does NOT fit'}); {p['hours_if_serial']} h serial wall-clock at the measured 172 s per Full case")
    if p.get("inr_if_sarvam") is not None:
        lines.append(f"  Sarvam-105B (dashboard prices, budgets.sarvam_prices_inr_per_1m): INR {p['inr_if_sarvam']:.2f} if run there")
    if p.get("node_hours") is not None:
        lines.append(f"  Ada node-hours (plan): {p['node_hours']}")
    if p.get("note"):
        lines.append(f"  note: {p['note']}")
    lines.append("  nothing was run")
    return "\n".join(lines)


def format_table(rows: list[dict[str, Any]]) -> str:
    """One line per job (`plan --all`)."""
    head = f"{'job':<26}{'tier':<5}{'backend':<9}{'case-runs':>10}{'tokens in':>13}{'usd (oai)':>10}{'inr (sar)':>10}{'node-h':>8}"
    out = [head, "-" * len(head)]
    for p in rows:
        usd = "-" if p["usd_if_openai"] is None else f"{p['usd_if_openai']:.2f}"
        inr = "-" if p["inr_if_sarvam"] is None else f"{p['inr_if_sarvam']:.1f}"
        out.append(f"{p['job']:<26}{str(p['tier'] or '-'):<5}{str(p['backend'] or '-'):<9}{p['case_runs']:>10}{p['tokens_in']:>13,}{usd:>10}{inr:>10}{str(p['node_hours'] or '-'):>8}")
    spend, warnings = spend_summary(rows)
    out.append(f"planned on openai: {spend['openai_usd']:.2f} USD; planned on sarvam: INR {spend['sarvam_inr']:.2f}")
    return "\n".join(out + warnings)
