"""Plan work on a rate-limited provider: how long it takes per model, which model finishes soonest, how a failover spreads it, and paired-arm checks.

Nothing here calls a model. The limits are the configured ones (configs/models.yaml `providers.<name>.models`; for Gemini as shown in AI Studio
on 2026-10-28, re-check there) and apply per key, i.e. per project, so `keys` multiplies them only when every key belongs to its own project.

Two daily bounds are reported side by side: requests per day (RPD) and tokens per day (TPM x 1440, the most the per-minute token limit lets
through in a day). A request larger than the model's TPM cannot be sent at all (`feasible: False`); the client refuses such a request before
sending (`HostedRequestTooLarge`).
"""

from __future__ import annotations

import math
from typing import Any

from vakeel_sahayak.models.registry import ProviderSpec

MIN_ANSWER_TOKENS = 256
MINUTES_PER_DAY = 1440


def plan_model(spec: ProviderSpec, model: str, n_requests: int, tokens_per_request: float, *, keys: int = 1, remaining_today: int | None = None) -> dict[str, Any]:
    """The plan of `n_requests` requests of about `tokens_per_request` tokens (prompt + answer) on one model.

    Returns model, limits, feasible (one request fits the TPM), days_by_rpd, days_by_tpd, days (the larger; today counts as day 1 when it
    still allows requests), binding ('rpd' | 'tpd'), hours_of_pacing (the per-minute limits alone), tokens_per_day_cap.
    """
    lim = spec.limits_for(model)
    k = max(1, int(keys))
    rpd, rpm, tpm = lim["rpd"] * k, lim["rpm"] * k, lim["tpm"] * k
    n = max(0, int(math.ceil(n_requests)))
    tok = max(0.0, float(tokens_per_request))
    feasible = lim["rpd"] > 0 and lim["rpm"] > 0 and (lim["tpm"] == 0 or tok <= lim["tpm"])
    tpd = tpm * MINUTES_PER_DAY
    per_day = min(rpd, int(tpd // tok) if tok and tpm else rpd) if feasible else 0
    if not feasible or per_day <= 0:
        return {"model": model, "limits": lim, "feasible": False, "requests": n, "tokens_per_request": round(tok), "days": math.inf, "binding": "infeasible",
                "days_by_rpd": math.inf, "days_by_tpd": math.inf, "tokens_per_day_cap": tpd, "requests_per_day": 0, "hours_of_pacing": math.inf}  # fmt: skip
    days_rpd = math.ceil(n / rpd) if n else 0
    days_tpd = math.ceil(n * tok / tpd) if n and tpm else 0
    today = per_day if remaining_today is None else max(0, min(int(remaining_today), per_day))
    if n == 0:
        days = 0
    elif today == 0:
        days = 1 + math.ceil(n / per_day)  # today is spent: the work starts tomorrow
    elif today >= n:
        days = 1
    else:
        days = 1 + math.ceil((n - today) / per_day)
    per_minute = min(rpm, (tpm / tok) if tok and tpm else rpm)
    return {
        "model": model, "limits": lim, "keys": k, "feasible": True, "requests": n, "tokens_per_request": round(tok),
        "requests_per_day": per_day, "tokens_per_day_cap": tpd, "days_by_rpd": days_rpd, "days_by_tpd": days_tpd, "days": days,
        "binding": "tpd" if days_tpd > days_rpd or per_day < rpd else "rpd", "hours_of_pacing": round(n / per_minute / 60, 2) if per_minute else math.inf,
    }  # fmt: skip


def rank_models(spec: ProviderSpec, n_requests: int, tokens_per_request: float, *, keys: int = 1, models: list[str] | None = None) -> list[dict[str, Any]]:
    """Every (or the given) model's plan, soonest finish first (feasible before infeasible; ties: fewer pacing hours)."""
    names = models or list(spec.models) or [spec.default_model]
    plans = [plan_model(spec, m, n_requests, tokens_per_request, keys=keys) for m in names]
    return sorted(plans, key=lambda p: (not p["feasible"], p["days"], p["hours_of_pacing"]))


def pick_model(spec: ProviderSpec, n_requests: int, tokens_per_request: float, *, keys: int = 1, models: list[str] | None = None) -> dict[str, Any] | None:
    """The plan of the model that finishes soonest, or None when no model can take the requests."""
    ranked = rank_models(spec, n_requests, tokens_per_request, keys=keys, models=models)
    return ranked[0] if ranked and ranked[0]["feasible"] else None


def failover_schedule(spec: ProviderSpec, order: list[str], n_requests: int, tokens_per_request: float, *, keys: int = 1, max_days: int = 60) -> list[dict[str, int]]:
    """Day by day, how many requests each model takes when the client fills one model's daily cap and fails over to the next (`VS_HOSTED_FAILOVER=1`).

    Returns one dict per day: model -> requests. Infeasible models are skipped."""
    plans = {m: plan_model(spec, m, 1, tokens_per_request, keys=keys) for m in order}
    left = max(0, int(n_requests))
    days: list[dict[str, int]] = []
    while left > 0 and len(days) < max_days:
        today: dict[str, int] = {}
        for m in order:
            cap = int(plans[m]["requests_per_day"]) if plans[m]["feasible"] else 0
            take = min(cap, left)
            if take:
                today[m] = take
                left -= take
            if not left:
                break
        if not today:
            break
        days.append(today)
    return days


def paired_warnings(arms: list[dict[str, Any]]) -> list[str]:
    """Warnings for paired comparisons that would mix models: arms of one comparison group (`group`, default the backend) must use ONE model.

    Each arm: {id, backend, model, group?, failover?}. A group with two models, or an arm allowed to fail over, is warned about."""
    out: list[str] = []
    groups: dict[str, dict[str, list[str]]] = {}
    for a in arms:
        g = str(a.get("group") or a.get("backend") or "")
        groups.setdefault(g, {}).setdefault(str(a.get("model") or ""), []).append(str(a.get("id")))
        if a.get("failover"):
            out.append(f"arm {a.get('id')} ({g}) may fail over to another model when the daily cap is hit: its outputs would mix models; run it without VS_HOSTED_FAILOVER")
    for g, models in groups.items():
        if len(models) > 1:
            parts = "; ".join(f"{m or '?'}: {', '.join(ids)}" for m, ids in sorted(models.items()))
            out.append(f"comparison group {g!r} mixes models ({parts}); paired comparisons need ONE model for every arm")
    return out


def format_plans(plans: list[dict[str, Any]]) -> str:
    """A table of plans."""
    lines = [f"{'model':<24}{'RPM':>5}{'TPM':>9}{'RPD':>7}  {'req/day':>8}{'tok/day cap':>13}  {'days RPD':>8}{'days TPD':>9}{'days':>6}  binding  pacing h"]
    for p in plans:
        lim = p["limits"]
        if not p["feasible"]:
            lines.append(f"{p['model']:<24}{lim['rpm']:>5}{lim['tpm']:>9}{lim['rpd']:>7}  infeasible: a request of ~{p['tokens_per_request']} tokens exceeds the TPM, or the model has no quota")
            continue
        lines.append(
            f"{p['model']:<24}{lim['rpm']:>5}{lim['tpm']:>9}{lim['rpd']:>7}  {p['requests_per_day']:>8}{p['tokens_per_day_cap']:>13}  "
            f"{p['days_by_rpd']:>8}{p['days_by_tpd']:>9}{p['days']:>6}  {p['binding']:<7}  {p['hours_of_pacing']:>8}"
        )
    return "\n".join(lines)
