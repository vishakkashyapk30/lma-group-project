"""Step 1: the teacher reads the facts section of about 4K train orders and outputs a CaseDossier quoting a source sentence per field. Runs as an Ada interactive shard with resume (plan §12, §17).

Also the week-1 teacher pilot and its decision rule (plan §17): Qwen3-32B-AWQ on Ada against a Mistral API model on the same orders; whichever gives
more verified pairs per day wins, but the API only if its terms allow training use, it is free or within a stated budget, and versions are pinned with
outputs cached. A tie, a missing API measurement or any unrecorded condition goes to the open model on Ada. The teacher and the evaluation labeler
must not be the same model family.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from vakeel_sahayak.finetune._io import read_rows

QWEN_ARM = "qwen3-32b-awq-ada"
API_ARM = "mistral-api"
API_CONDITIONS = ("terms_allow_training_use", "free_or_stated_budget", "versions_pinned_and_outputs_cached")
TOKENS_PER_ORDER = 12_000  # plan §17: "4K orders x 12K tokens"
METRICS = ("share_all_fields_pass_span_check", "tokens_per_hour", "rate_limit_stalls")


def _make_teacher(backend: str | None = None):
    from vakeel_sahayak.models.teacher import TeacherClient

    return TeacherClient(backend=backend)


def run_shard(orders_path: str, out_path: str, shard: int, n_shards: int) -> int:
    """Generate dossiers for one shard, saving each output as it finishes.

    A shard is the orders whose position i satisfies i % n_shards == shard. Rows already in `out_path` are kept and skipped, so a session that
    ends (or is killed) loses nothing and a re-run continues where it stopped.

    Args:
        orders_path: JSONL of {"doc_id", "facts"} public train orders
        out_path: JSONL of {"doc_id", "facts", "dossier"} rows, appended one line at a time
        shard: this shard's index, 0 <= shard < n_shards
        n_shards: number of shards

    Returns:
        Number completed (rows for this shard on disk when the run ends).
    """
    if n_shards < 1 or not 0 <= shard < n_shards:
        raise ValueError(f"shard {shard} is outside 0..{n_shards - 1}")
    mine = [o for i, o in enumerate(read_rows(orders_path)) if i % n_shards == shard]
    done = {str(r.get("doc_id")) for r in read_rows(out_path)}
    todo = [o for o in mine if str(o["doc_id"]) not in done]
    if todo:
        teacher = _make_teacher()
        out = Path(out_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for order in todo:
                dossier = teacher.dossier_from_facts(order["facts"])
                row = {"doc_id": order["doc_id"], "facts": order["facts"], "dossier": dossier.model_dump(mode="json")}
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                fh.flush()
    return len(mine)


def _is_rate_limit(exc: BaseException) -> bool:
    text = f"{type(exc).__name__} {exc}".lower()
    return "429" in text or "rate" in text and "limit" in text


def _measure(backend: str, orders: list[dict[str, Any]]) -> dict[str, float]:
    """Run one arm over the orders: share with every field passing span_check, tokens per hour, rate-limit stalls."""
    from vakeel_sahayak.finetune.span_filter import all_fields_pass
    from vakeel_sahayak.models.base import approx_tokens

    teacher = _make_teacher(backend)
    passed = tokens = stalls = 0
    start = time.perf_counter()
    for order in orders:
        try:
            dossier = teacher.dossier_from_facts(order["facts"]).model_dump(mode="json")
        except Exception as exc:  # a failed call counts as a failed order; rate limits are counted separately
            stalls += _is_rate_limit(exc)
            continue
        tokens += approx_tokens(order["facts"]) + approx_tokens(json.dumps(dossier, ensure_ascii=False))
        passed += bool(all_fields_pass(dossier))
    hours = max(time.perf_counter() - start, 1e-6) / 3600.0
    return {
        "share_all_fields_pass_span_check": float(passed / len(orders)) if orders else 0.0,
        "tokens_per_hour": float(tokens / hours),
        "rate_limit_stalls": float(stalls),
    }


def teacher_pilot(orders_path: str, n: int = 50) -> dict[str, float]:
    """Week-1 pilot: Qwen3-32B-AWQ vs a Mistral API model on the same 50 train orders; measure the share of outputs passing span_check, tokens per hour, rate-limit stalls (plan §17).

    Args:
        orders_path: JSONL of {"doc_id", "facts"} train orders; the first `n` are used by both arms
        n: number of orders

    Returns:
        Pilot metrics as '<arm>/<metric>' -> float.
    """
    orders = list(read_rows(orders_path))[:n]
    result: dict[str, float] = {}
    for arm, backend in ((QWEN_ARM, "vllm"), (API_ARM, "mistral")):
        for metric, value in _measure(backend, orders).items():
            result[f"{arm}/{metric}"] = float(value)
    return result


def verified_pairs_per_day(
    share_all_pass: float, tokens_per_hour: float, tokens_per_order: float = TOKENS_PER_ORDER
) -> float:
    """Share passing x orders per day: 800K tokens/h at 12K tokens per order is 66.7 orders/h, 1,600 a day."""
    return float(share_all_pass) * float(tokens_per_hour) / float(tokens_per_order) * 24.0


def choose_teacher(
    metrics: dict[str, dict[str, float]], api_conditions: dict[str, bool], tokens_per_order: float = TOKENS_PER_ORDER
) -> str:
    """Plan §17 decision rule: the arm with more verified pairs per day, the API only if all three conditions are recorded as True.

    A tie, a missing API measurement, or a failed or unrecorded condition gives the Qwen3-32B arm on Ada.
    """
    if API_ARM not in metrics or QWEN_ARM not in metrics:
        return QWEN_ARM
    if not all(api_conditions.get(c) is True for c in API_CONDITIONS):
        return QWEN_ARM

    def rate(arm: str) -> float:
        m = metrics[arm]
        return verified_pairs_per_day(m["share_all_fields_pass_span_check"], m["tokens_per_hour"], tokens_per_order)

    return API_ARM if rate(API_ARM) > rate(QWEN_ARM) else QWEN_ARM


def assert_family_rule(teacher_model: str, labeler_model: str) -> None:
    """Raise ValueError when the teacher and the evaluation labeler are the same model family (plan §17)."""
    from vakeel_sahayak.models.teacher import assert_families_differ

    assert_families_differ(teacher_model, labeler_model)


def main(argv: list[str] | None = None) -> int:
    """CLI: `shard ORDERS OUT SHARD N_SHARDS` or `pilot ORDERS [N]` (prints the metrics as JSON)."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["shard"] and len(args) == 5:
        print(f"{run_shard(args[1], args[2], int(args[3]), int(args[4]))} dossiers on disk")
        return 0
    if args[:1] == ["pilot"] and len(args) in (2, 3):
        print(json.dumps(teacher_pilot(args[1], int(args[2]) if len(args) == 3 else 50), indent=2))
        return 0
    print(
        "usage: python -m vakeel_sahayak.finetune.teacher_dossiers shard ORDERS OUT SHARD N_SHARDS | pilot ORDERS [N]"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
