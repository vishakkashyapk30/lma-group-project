"""S13 (could): automatically designed workflows as a small search over the existing switches on the dev split (evaluation plan 3.3, S13).

Papers (adapted, not reproduced; page details are as listed in the evaluation plan and were not re-checked here):

* Zhang et al., "AFlow: Automating Agentic Workflow Generation", ICLR 2025 (oral),
  https://proceedings.iclr.cc/paper_files/paper/2025/hash/5492ecbce4439401798dcd2c90be94cd-Abstract-Conference.html : workflows as searchable
  structures scored on a dev set with the score as reward.
* Hu, Lu and Clune, "Automated Design of Agentic Systems" (ADAS, Meta Agent Search), ICLR 2025, https://arxiv.org/abs/2408.08435 : a search loop
  that keeps an archive of evaluated designs.
* Zhang et al., "Multi-agent Architecture Search via Agentic Supernet" (MaAS), ICML 2025 (oral), https://proceedings.mlr.press/v267/zhang25bi.html : related only.

What is taken: evaluate candidate workflows on dev, rank by dev score, test only the winner. What is changed: the search space is a hand-written
grid over our own switches (stopping, retrieval policy, weak signal, store prior, topology, critic), not code written by a meta-agent, and the search
is an exhaustive or seeded random enumeration, not an LLM-guided tree search. Nothing here calls a hosted model by itself; the model-backed arm is `model_backed_search`
(CLI `--model-backed`, opt-in, ledger-capped, resumable, writes a manifest).

Honest limits. The offline smoke (`slot_fill_evaluator` with the fixture toolbox) scores slot-fill rate of the retrieval stage on the offline stand-ins:
it proves the harness (determinism, budget cap, ranking, dev-only guard, saved report), not that any workflow is better. A real search scores G1 recall
on the dev cases (plan `T1` dev, 50 cases) with a hosted or local model and needs about 30 search runs (36 hours in the plan); it is the first job to cut.

Guards: only dev cases are evaluated (`assert_dev_only`: a case marked test or blind, or whose id looks like a test case, is refused); the winner is chosen on dev
alone and the report carries `test: 'pending'`; `max_configs` and `max_tokens` cap the search, and the report says which cap stopped it.
"""

from __future__ import annotations

import itertools
import json
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vakeel_sahayak.orchestration.switches import Switches, assert_variant_implemented

# the search space: the switches of plan 3.3 that change a workflow (stage order, budgets and critic on/off are the plan's examples)
DEFAULT_GRID: dict[str, list[Any]] = {
    "stopping": ["rules", "rules_llm"],
    "retrieval_policy": ["contract", "adaptive"],
    "weak_signal": ["rules", "skew"],
    "store_prior": ["off", "order"],
    "topology": ["orchestrated", "sequential"],
    "critic_mode": ["abhiyojak", "none"],
}
Evaluator = Callable[[Switches, list[dict[str, Any]]], dict[str, Any]]


class WorkflowSearchError(ValueError):
    """The search was asked to do something it must not (non-dev case, empty grid)."""


def config_key(fields: dict[str, Any]) -> str:
    """Canonical string of a grid point (sorted fields), used for ties and de-duplication."""
    return json.dumps(fields, sort_keys=True, default=str)


def valid_point(fields: dict[str, Any]) -> Switches | None:
    """The `Switches` of a grid point, or None when the combination is invalid (the switch validators decide)."""
    try:
        return Switches(**fields)
    except ValueError:
        return None


def enumerate_grid(grid: dict[str, list[Any]] | None = None) -> list[dict[str, Any]]:
    """Every valid grid point in a fixed order (the product in field order; the all-default point first when the first value of each field is the default).

    Raises:
        WorkflowSearchError: an empty grid.
    """
    grid = grid or DEFAULT_GRID
    if not grid or any(not v for v in grid.values()):
        raise WorkflowSearchError("the grid is empty")
    names = list(grid)
    points = [dict(zip(names, combo, strict=True)) for combo in itertools.product(*(grid[n] for n in names))]
    return [p for p in points if valid_point(p) is not None]


def sample_grid(n: int, grid: dict[str, list[Any]] | None = None, seed: int = 0) -> list[dict[str, Any]]:
    """`n` distinct valid points chosen by a seeded shuffle (the same seed gives the same list)."""
    points = enumerate_grid(grid)
    random.Random(seed).shuffle(points)
    return points[: max(0, n)]


def assert_dev_only(cases: list[dict[str, Any]]) -> None:
    """Refuse a case that is not dev: `split` of test or blind, or an id of the form `t1test-*` / `t1blind-*`.

    Raises:
        WorkflowSearchError: naming the offending cases.
    """
    bad = [str(c.get("case_id")) for c in cases if str(c.get("split") or "").lower() in {"test", "blind"} or str(c.get("case_id") or "").lower().startswith(("t1test", "t1blind", "test-", "blind-"))]
    if bad:
        raise WorkflowSearchError(f"workflow search runs on dev cases only; refused: {', '.join(bad[:5])}")


def search(
    cases: list[dict[str, Any]],
    evaluate: Evaluator,
    *,
    grid: dict[str, list[Any]] | None = None,
    mode: str = "grid",
    max_configs: int = 12,
    max_tokens: int | None = None,
    seed: int = 0,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate grid points on the dev cases, rank them and save a report.

    Args:
        cases: dev cases (`case_id`, `facts`, `before`, ...); a non-dev case raises
        evaluate: `(switches, cases) -> {"score": float, "tokens": int, ...}`; higher score is better
        grid: switch values to search (default `DEFAULT_GRID`)
        mode: 'grid' (all valid points in order) or 'random' (seeded sample)
        max_configs: most configurations to evaluate
        max_tokens: stop before a configuration once the tokens already spent reach this cap (None: no cap)
        seed: for `mode='random'`
        report_path: where to save the JSON report (None: do not save)

    Returns:
        `{mode, seed, evaluated, stopped_by, tokens, ranking: [{rank, fields, variant, score, tokens}], winner, test: 'pending'}`; ranked by score
        (descending), ties by cost then by canonical key, so the report is deterministic.

    Raises:
        WorkflowSearchError: a non-dev case, an unknown mode or an empty grid.
    """
    assert_dev_only(cases)
    if mode not in ("grid", "random"):
        raise WorkflowSearchError(f"unknown mode {mode!r}: use 'grid' or 'random'")
    points = enumerate_grid(grid) if mode == "grid" else sample_grid(max_configs, grid, seed)
    results: list[dict[str, Any]] = []
    spent = 0
    stopped = "exhausted"
    for point in points:
        if len(results) >= max_configs:
            stopped = "max_configs"
            break
        if max_tokens is not None and spent >= max_tokens:
            stopped = "max_tokens"
            break
        switches = valid_point(point)
        assert switches is not None
        out = evaluate(switches, cases)
        spent += int(out.get("tokens", 0))
        results.append({"fields": point, "variant": switches.variant(), "score": float(out["score"]), "tokens": int(out.get("tokens", 0)), **{k: v for k, v in out.items() if k not in ("score", "tokens")}})
    ranked = sorted(results, key=lambda r: (-r["score"], r["tokens"], config_key(r["fields"])))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    report = {"mode": mode, "seed": seed, "cases": [str(c.get("case_id")) for c in cases], "evaluated": len(ranked), "stopped_by": stopped, "tokens": spent,
              "ranking": ranked, "winner": ranked[0]["fields"] if ranked else None, "test": "pending"}
    if report_path:
        p = Path(report_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    return report


def slot_fill_evaluator(tools: dict[str, Any] | None = None, llm: Any = None) -> Evaluator:
    """An offline evaluator over the driver: retrieval-only runs (`driver.run_agents(stop_after='retrieval')`), score = share of slots FILLED in the
    `factor_done` events, tokens from the budget tracker. A smoke for the harness; the real reward is G1 recall with a model (see the module docstring).

    Args:
        tools: a toolbox replacing the registry (the fixture toolbox in tests); None uses the real stores
        llm: one client for every agent (tests); None lets each agent resolve its role
    """
    from vakeel_sahayak.eval.runners.driver import build_context, run_agents
    from vakeel_sahayak.schemas.enums import EventKind

    def evaluate(switches: Switches, cases: list[dict[str, Any]]) -> dict[str, Any]:
        filled = total = tokens = 0
        for case in cases:
            ctx = build_context(case, switches, tools=dict(tools or {}), llm=llm)
            run_agents(case, ctx, stop_after="retrieval")
            for e in ctx.log.read(case["case_id"]):
                if e.kind == EventKind.AGENT_MESSAGE and e.tool == "factor_done":
                    parts = str((e.outputs or {}).get("text", "")).split(": ", 1)[-1].split(", ")
                    total += len(parts)
                    filled += sum(1 for p in parts if p.split(" ", 1)[-1].startswith("FILLED"))
            tokens += int(ctx.budgets.spent(None)[0])
        return {"score": round(filled / total, 6) if total else 0.0, "tokens": tokens, "slots": total}

    return evaluate


def recall_evaluator(tools: dict[str, Any] | None = None, llm: Any = None, stances: tuple[str, ...] = ("favourable", "adverse")) -> Evaluator:
    """The dev reward of the plan: factor recall (M1) against the agreed G1 of the dev cases, from the whole pipeline (`driver.run_agents`), tokens from the budget tracker.

    Each case must be a T1 dev row (`gold`, `facts_text`); recall is the mean over the cases where it is defined (a case with no agreed answerable factor is left out, as in the
    headline table), so a grid point is scored exactly like a system in `eval.scoring`. Offline this scores the stand-in models and says nothing about any workflow with a real model;
    with a hosted or local model it is the evaluator of the plan's S13 arm (not run here).

    Args:
        tools: a toolbox replacing the registry (tests); None uses the real stores
        llm: one client for every agent (tests); None lets each agent resolve its role
        stances: ground stances that count as arguing a factor (as in scoring)
    """
    from vakeel_sahayak.eval.runners.driver import build_context, run_agents
    from vakeel_sahayak.eval.scoring import case_metrics as cm

    def evaluate(switches: Switches, cases: list[dict[str, Any]]) -> dict[str, Any]:
        values: list[float] = []
        tokens = 0
        for case in cases:
            ctx = build_context(case, switches, tools=dict(tools or {}), llm=llm)
            result = run_agents(case, ctx)
            gold = cm._factors(((case.get("gold") or {}).get("G1") or {}).get("labels"))
            recall, _, _ = cm._prf(cm.argued_factors(result.get("brief") or {}, stances), gold, cm.answerable_of(case))
            if recall is not None:
                values.append(recall)
            tokens += int(ctx.budgets.spent(None)[0])
        return {"score": round(sum(values) / len(values), 6) if values else 0.0, "tokens": tokens, "cases_scored": len(values), "reward": "factor recall (M1) vs agreed G1 on dev"}

    return evaluate


def assert_offline() -> None:
    """The model-backed S13 arm is planned, not run: refuse a hosted or local model backend (`VS_LLM_BACKEND` other than offline) so no paid call is made by accident.

    Raises:
        NotImplementedError: naming the backend; the search itself (`search`) takes any evaluator, so the arm needs only an evaluator wired to the model and the owner's go-ahead.
    """
    import os

    backend = (os.environ.get("VS_LLM_BACKEND") or "offline").lower()
    if backend != "offline":
        raise NotImplementedError(f"the S13 workflow search is run offline only here (VS_LLM_BACKEND={backend!r}): the model-backed arm is planned; it uses `recall_evaluator` under that backend "
                                  "after the owner's go-ahead and the pinned code tag")


def ledger_state(backend: str) -> tuple[float, float, str] | None:
    """`(spent, remaining, unit)` of the spend ledger of a hosted backend ('openai': USD, 'sarvam': INR), None for any other backend (no ledger)."""
    if backend == "openai":
        from vakeel_sahayak.models.openai.ledger import report

        rep = report()
        return float(rep["spent_usd"]), float(rep["remaining_usd"]), "USD"
    if backend == "sarvam":
        from vakeel_sahayak.models.sarvam.spend import report as sarvam_report

        rep = sarvam_report()
        return float(rep["spent_inr"]), float(rep["remaining_inr"]), "INR"
    return None


CAP_ENVS = {"openai": "VS_OPENAI_CAP_USD", "sarvam": "VS_SARVAM_CAP_INR"}


def model_backed_search(
    cases: list[dict[str, Any]],
    out_dir: str | Path,
    *,
    evaluator: Evaluator | None = None,
    grid: dict[str, list[Any]] | None = None,
    mode: str = "grid",
    max_configs: int = 12,
    max_tokens: int | None = None,
    seed: int = 0,
    min_remaining: float = 0.5,
    state_fn: Callable[[str], tuple[float, float, str] | None] = ledger_state,
) -> dict[str, Any]:
    """The model-backed S13 arm (opt-in, never run by default): the grid search with the whole pipeline on the dev cases, reward = factor recall (M1) against the agreed G1.

    It uses whatever backend `VS_LLM_BACKEND` names (`recall_evaluator`: the production agents, so a hosted run passes the pseudonymisation boundary and the spend ledger as every
    driver run does). Guards: dev cases only; every configuration is stored as `<out_dir>/configs/<n>.json` the moment it finishes, so a rerun skips the finished ones (resume);
    before each configuration the ledger is read and the search stops (`stopped_by: ledger`) when the remaining budget is below `min_remaining` or below 1.25 times the dearest configuration
    so far (a hosted call over the cap would silently fall back to the local client, so the search must stop before it, not rely on the refusal); `max_tokens` and `max_configs` as in `search`.
    Writes `<out_dir>/MANIFEST.json` (backend, models, code, cases, grid, ledger before and after) and `<out_dir>/search_report.json` (same shape as `search`, plus `backend` and `resumed`).

    Args:
        cases: dev cases (T1 dev rows with `gold`); a non-dev case raises
        out_dir: output folder
        evaluator: `(switches, cases) -> {"score", "tokens"}`; default `recall_evaluator()`
        min_remaining: least ledger budget (USD or INR by backend) to start a configuration
        state_fn: `backend -> (spent, remaining, unit) | None`; replaced in tests

    Raises:
        WorkflowSearchError: a non-dev case, an unknown mode, an empty grid.
    """
    import os

    from vakeel_sahayak.eval.runners.driver import git_sha, models_stamp

    assert_dev_only(cases)
    if mode not in ("grid", "random"):
        raise WorkflowSearchError(f"unknown mode {mode!r}: use 'grid' or 'random'")
    out = Path(out_dir)
    (out / "configs").mkdir(parents=True, exist_ok=True)
    evaluate = evaluator or recall_evaluator()
    backend = (os.environ.get("VS_LLM_BACKEND") or "offline").lower()
    points = enumerate_grid(grid) if mode == "grid" else sample_grid(max_configs, grid, seed)
    before = state_fn(backend)
    case_ids = [str(c.get("case_id")) for c in cases]
    results: list[dict[str, Any]] = []
    spent_tokens, resumed, dearest, stopped = 0, 0, 0.0, "exhausted"
    for n, point in enumerate(points):
        if len(results) >= max_configs:
            stopped = "max_configs"
            break
        saved = out / "configs" / f"{n:03d}.json"
        if saved.is_file():
            try:
                row = json.loads(saved.read_text(encoding="utf-8"))
            except ValueError:
                row = None
            if row and row.get("fields") == point and row.get("cases") == case_ids:
                results.append(row["result"])
                spent_tokens += int(row["result"].get("tokens", 0))
                dearest = max(dearest, float(row.get("ledger_cost") or 0.0))
                resumed += 1
                continue
        if max_tokens is not None and spent_tokens >= max_tokens:
            stopped = "max_tokens"
            break
        state = state_fn(backend)
        if state is not None and state[1] < max(min_remaining, 1.25 * dearest):
            stopped = "ledger"
            break
        switches = valid_point(point)
        assert switches is not None
        out_row = evaluate(switches, cases)
        after = state_fn(backend)
        cost = round(after[0] - state[0], 6) if state is not None and after is not None else 0.0
        dearest = max(dearest, cost)
        tokens = int(out_row.get("tokens", 0))
        spent_tokens += tokens
        result = {"fields": point, "variant": switches.variant(), "score": float(out_row["score"]), "tokens": tokens,
                  **{k: v for k, v in out_row.items() if k not in ("score", "tokens")}}
        results.append(result)
        saved.write_text(json.dumps({"fields": point, "cases": case_ids, "result": result, "ledger_cost": cost}, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    ranked = sorted(results, key=lambda r: (-r["score"], r["tokens"], config_key(r["fields"])))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    after_all = state_fn(backend)
    report = {"mode": mode, "seed": seed, "backend": backend, "cases": case_ids, "evaluated": len(ranked), "resumed": resumed, "stopped_by": stopped, "tokens": spent_tokens,
              "ranking": ranked, "winner": ranked[0]["fields"] if ranked else None, "test": "pending"}
    manifest = {"arm": "S13", "kind": "model-backed workflow search", "backend": backend, "models": models_stamp(), "git_sha": git_sha(), "cases": case_ids, "mode": mode, "seed": seed,
                "grid": grid or DEFAULT_GRID, "max_configs": max_configs, "max_tokens": max_tokens, "min_remaining": min_remaining, "reward": "factor recall (M1) vs agreed G1 on dev",
                "ledger_before": before, "ledger_after": after_all, "stopped_by": stopped, "test": "pending"}
    (out / "search_report.json").write_text(json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    (out / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True, indent=1, default=str) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    """`python -m vakeel_sahayak.eval.runners.workflow_search --cases <dev.jsonl> --n 3 --evaluator recall|slot_fill --max-configs 4 --out <report.json> [--mode grid|random] [--seed 0] [--grid small]`.

    Runs the search on the first n dev cases offline (stand-in models, real stores unless `VS_DATA_DIR` points elsewhere), prints the ranking and writes the report. `--grid small` searches only
    stopping and topology (4 points); the default grid is `DEFAULT_GRID` (64 points less the invalid ones, capped by `--max-configs`).
    """
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="workflow_search")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--evaluator", choices=["recall", "slot_fill"], default="recall")
    ap.add_argument("--mode", choices=["grid", "random"], default="grid")
    ap.add_argument("--max-configs", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--grid", choices=["default", "small"], default="default")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model-backed", action="store_true", help="the model-backed S13 arm (opt-in): the pipeline under VS_LLM_BACKEND, ledger-capped, resumable; --out is then a folder")
    ap.add_argument("--min-remaining", type=float, default=0.5, help="model-backed: least ledger budget (USD for openai, INR for sarvam) to start a configuration")
    a = ap.parse_args(argv)
    if a.model_backed:
        return _main_model_backed(a)
    try:
        assert_offline()
    except NotImplementedError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    rows = [json.loads(ln) for ln in Path(a.cases).read_text(encoding="utf-8").splitlines() if ln.strip()][: a.n]
    grid = {"stopping": ["rules", "rules_llm"], "topology": ["orchestrated", "sequential"]} if a.grid == "small" else None
    evaluate = recall_evaluator() if a.evaluator == "recall" else slot_fill_evaluator()
    report = search(rows, evaluate, grid=grid, mode=a.mode, max_configs=a.max_configs, max_tokens=a.max_tokens, seed=a.seed, report_path=a.out)
    report["note"] = "offline stand-in models: the ranking checks the harness, it is not a result about workflows"
    Path(a.out).write_text(json.dumps(report, sort_keys=True, indent=1) + "\n", encoding="utf-8")
    for r in report["ranking"]:
        print(f"{r['rank']:>2}  score={r['score']:.3f}  tokens={r['tokens']}  {config_key(r['fields'])}")
    print(f"evaluated {report['evaluated']} (stopped by {report['stopped_by']}); winner {report['winner']}; test pending; report {a.out}")
    return 0


def _main_model_backed(a: Any) -> int:
    """The `--model-backed` path of `main`: a hosted backend needs its cap variable set (the ledger is then the budget); the offline stand-in runs without one (tests, smoke)."""
    import os
    import sys

    backend = (os.environ.get("VS_LLM_BACKEND") or "offline").lower()
    if backend in CAP_ENVS and not os.environ.get(CAP_ENVS[backend]):
        print(f"REFUSED: set {CAP_ENVS[backend]} first (the search stops by itself when the ledger's remaining budget runs out); backend {backend!r}", file=sys.stderr)
        return 2
    rows = [json.loads(ln) for ln in Path(a.cases).read_text(encoding="utf-8").splitlines() if ln.strip()][: a.n]
    grid = {"stopping": ["rules", "rules_llm"], "topology": ["orchestrated", "sequential"]} if a.grid == "small" else None
    try:
        report = model_backed_search(rows, a.out, grid=grid, mode=a.mode, max_configs=a.max_configs, max_tokens=a.max_tokens, seed=a.seed, min_remaining=a.min_remaining)
    except WorkflowSearchError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    for r in report["ranking"]:
        print(f"{r['rank']:>2}  score={r['score']:.3f}  tokens={r['tokens']}  {config_key(r['fields'])}")
    print(f"evaluated {report['evaluated']} ({report['resumed']} resumed; stopped by {report['stopped_by']}); winner {report['winner']}; test pending; report {a.out}/search_report.json")
    return 0


def assert_grid_implemented(grid: dict[str, list[Any]] | None = None) -> None:
    """Fail loudly when a grid point selects a named variant that no agent reads (every searched field is a plain switch, so this is a guard for custom grids)."""
    for point in enumerate_grid(grid):
        name = Switches(**point).variant()
        if name != "custom":
            assert_variant_implemented(name)


if __name__ == "__main__":
    raise SystemExit(main())
