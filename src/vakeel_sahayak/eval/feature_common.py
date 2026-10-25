"""Shared plumbing of the feature evaluations F1-F8 (`eval/features/*`, plan §15.6).

Result contract (the ASSUMPTION stated in `tests/unit/eval/test_features.py`): a feature's `run(out_dir, shard, n_shards)` writes one arm per
sub-directory, `out_dir/<arm>/<case_id>.json`, one file per case with `case_id` and the payload keys that feature's `score` reads; an arm whose backend is
missing writes `out_dir/<arm>/ARM_UNAVAILABLE.json` (reason) instead of numbers. `score(arm_dir)` is the macro mean over the case files and raises
ValueError on a directory without cases. Runs are resumable (a case file that exists is skipped) and sharded by case index.

Environment knobs (so `run` keeps the plan's three-argument signature): `VS_FEATURE_N` (first N cases/items), `VS_FEATURE_ARMS` (comma list), `VS_FEATURE_CASES`
(a cases file overriding the feature's default test set).

Everything here runs offline with the stand-in models; what that means for each arm is in the feature module's docstring and in docs/handoff/eval-features.md.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any


def testsets_dir() -> Path:
    """`data/testsets` (read-only for the evaluation)."""
    from vakeel_sahayak.config import load_config

    return Path(load_config().paths.testsets_dir)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Rows of a JSON-lines file."""
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def env_limit() -> int | None:
    """`VS_FEATURE_N` as an int (None: all)."""
    raw = os.environ.get("VS_FEATURE_N", "").strip()
    return int(raw) if raw else None


def selected_arms(default: Iterable[str]) -> list[str]:
    """Arms named by `VS_FEATURE_ARMS`, else `default`."""
    raw = os.environ.get("VS_FEATURE_ARMS", "").strip()
    return [a.strip() for a in raw.split(",") if a.strip()] or list(default)


def shard_slice(items: list[Any], shard: int, n_shards: int) -> list[Any]:
    """The items of this shard (dealt by index)."""
    if not 0 <= shard < n_shards:
        raise ValueError(f"shard {shard} is outside 0..{n_shards - 1}")
    return [x for i, x in enumerate(items) if i % n_shards == shard]


def arm_dir(out_dir: str | Path, arm: str) -> Path:
    """`out_dir/<arm>` (created)."""
    d = Path(out_dir) / arm
    d.mkdir(parents=True, exist_ok=True)
    return d


def case_file(out_dir: str | Path, arm: str, case_id: str) -> Path:
    """Where a case's payload of an arm lives."""
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in str(case_id))
    return arm_dir(out_dir, arm) / f"{safe}.json"


def save_case(out_dir: str | Path, arm: str, case_id: str, payload: dict[str, Any]) -> Path:
    """Write one case payload (with `case_id`), UTF-8, stable key order."""
    path = case_file(out_dir, arm, case_id)
    path.write_text(json.dumps({"case_id": case_id, **payload}, ensure_ascii=False, indent=1, sort_keys=True, default=str), encoding="utf-8")
    return path


def mark_unavailable(out_dir: str | Path, arm: str, reason: str) -> None:
    """Record that an arm could not run here (no numbers are made up)."""
    (arm_dir(out_dir, arm) / "ARM_UNAVAILABLE.json").write_text(json.dumps({"arm": arm, "reason": reason}, indent=1), encoding="utf-8")


def load_cases(run_dir: str | Path) -> list[dict[str, Any]]:
    """The case payloads of an arm directory.

    Raises:
        ValueError: no case files (an empty run is an error, never a made-up number).
    """
    d = Path(run_dir)
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("*.json")) if not p.name.startswith(("ARM_", "_", "MANIFEST"))]
    if not rows:
        extra = f" ({(d / 'ARM_UNAVAILABLE.json').read_text(encoding='utf-8')})" if (d / "ARM_UNAVAILABLE.json").exists() else ""
        raise ValueError(f"no saved cases in {run_dir}{extra}: nothing to score")
    return rows


def mean(values: Iterable[float]) -> float | None:
    """Arithmetic mean (None for no values)."""
    vals = list(values)
    return sum(vals) / len(vals) if vals else None


def rate(num: float, den: float) -> float | None:
    """num/den, None when den is 0."""
    return num / den if den else None


def present(metrics: dict[str, float | None]) -> dict[str, float]:
    """The metrics that have a value (a metric with nothing to measure is left out, not reported as 0)."""
    return {k: float(v) for k, v in metrics.items() if v is not None}


def set_prf(pred: Iterable[str], gold: Iterable[str]) -> tuple[float | None, float | None]:
    """(recall, precision) of a predicted set against a gold set; None where the denominator is empty."""
    p, g = set(pred), set(gold)
    hit = len(p & g)
    return rate(hit, len(g)), rate(hit, len(p))


def score_arms(out_dir: str | Path, score: Callable[[str], dict[str, float]], arms: list[str] | None = None) -> dict[str, dict[str, float] | str]:
    """`score` of every arm directory under `out_dir`; an unavailable or empty arm maps to its reason string."""
    out: dict[str, dict[str, float] | str] = {}
    for d in sorted(p for p in Path(out_dir).iterdir() if p.is_dir() and not p.name.startswith("_")):
        if arms and d.name not in arms:
            continue
        try:
            out[d.name] = score(str(d))
        except ValueError as exc:
            out[d.name] = str(exc)[:200]
    return out


def format_scores(results: dict[str, dict[str, float] | str]) -> str:
    """A plain-text table: one block per arm."""
    lines: list[str] = []
    for arm, res in results.items():
        if isinstance(res, str):
            lines.append(f"{arm}: {res}")
            continue
        lines.append(f"{arm}: " + ", ".join(f"{k}={v:.3f}" for k, v in sorted(res.items())))
    return "\n".join(lines)


def sentences_of(text: str) -> list[str]:
    """Sentences of a reply (the repository's splitter)."""
    from vakeel_sahayak.pipelines.text_utils import split_sentences

    return [s for s in split_sentences(text or "") if len(s.split()) >= 3]


def unsupported_count(text: str, premise: str) -> tuple[int, int]:
    """(sentences, sentences the NLI client finds unsupported by `premise`): the offline lexical checker, or DeBERTa when installed.

    This is the system's own NLI, not the evaluation-only MiniCheck of plan §15.9 (not available here); the arm records which backend it was.
    """
    from vakeel_sahayak.models.factory import get_nli
    from vakeel_sahayak.models.nli import nli_threshold

    client = get_nli()
    cut = nli_threshold("fact_support", client)
    sents = sentences_of(text)
    bad = sum(1 for s in sents if client.entails(premise, s) < cut)
    return len(sents), bad


def nli_backend() -> str:
    """Name of the NLI backend in use (recorded with the arm)."""
    from vakeel_sahayak.models.factory import get_nli

    return getattr(get_nli(), "name", "nli")


def llm_backend() -> str:
    """Name of the LLM backend a run would use (recorded in notes; 'offline' for the stand-in)."""
    from vakeel_sahayak.models.factory import get_llm

    c = get_llm("agents_14b")
    return f"{getattr(c, 'name', 'llm')}{' (offline stand-in)' if getattr(c, 'is_offline', False) else ''}"


def cli(module: Any, argv: list[str] | None = None) -> int:
    """`python -m <feature module> run --out DIR [--shard i --n-shards n]` or `score --out DIR` (reads `VS_FEATURE_*`)."""
    ap = argparse.ArgumentParser(description=module.__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--shard", type=int, default=0)
    r.add_argument("--n-shards", type=int, default=1)
    s = sub.add_parser("score")
    s.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "run":
        module.run(args.out, args.shard, args.n_shards)
    print(format_scores(score_arms(args.out, module.score)))
    return 0
