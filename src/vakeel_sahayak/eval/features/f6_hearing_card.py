"""Feature evaluation F6: Hearing-prep card vs one-call 'what will the bench ask?'. Test set: T1, G5, G6. Metrics: recall/precision of court-discussed factors (G5); recall of imposed condition types (G6) (plan §15.6).

Test set: T1 dev cases (`data/testsets/t1/dev.jsonl`; `VS_FEATURE_CASES` points at another file) with a non-empty G5 gold. G6 is only scored where it
applies (grants with a condition the court imposed). Arms (one directory each, one JSON file per case):

- `hearing_card`: the Full pipeline (`system_runner("full")`), then the exported card (`export.hearing_card.card_from`) from the run's brief, sparring
  record and the evidence packs Sutradhar wrote to the run's event log. Predicted factors are the factors of its bench concerns; predicted conditions
  are its condition texts mapped to the G6 condition types by the G6 rules (`pipelines/gold/g6_conditions.CONDITION_RULES`).
- `one_call`: one structured call "what will the bench ask?" on the pseudonymised facts (no retrieval, no tools) that names checklist factors and
  condition types; condition texts it writes are mapped by the same G6 rules.

Offline stand-in models by default (the one-call arm then names the checklist factors whose words occur in the facts), so the numbers describe the
harness, not a model.

`score` reads one JSON file per case with `predicted_factors` and `gold_g5` (factors the court discussed), `predicted_conditions` and `gold_g6`
(condition types the court imposed).
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

from pydantic import BaseModel, Field

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("hearing_card", "one_call")
TASK = "f6.one_call_bench_questions"


class BenchConcern(BaseModel):
    """One concern the bench may raise: a checklist factor and the question."""

    factor: str
    question: str = ""


class OneCallCard(BaseModel):
    """The one-call answer: likely concerns and the conditions courts impose in similar grants."""

    concerns: list[BenchConcern] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)


def condition_types(texts: list[str]) -> list[str]:
    """G6 condition types named by condition texts (a type id itself, or text the G6 rules recognise)."""
    from vakeel_sahayak.pipelines.gold.g6_conditions import CONDITION_RULES, CONDITION_TYPES

    found: set[str] = set()
    for text in texts:
        t = str(text).strip()
        if t in CONDITION_TYPES:
            found.add(t)
        found.update(k for k, rule in CONDITION_RULES.items() if re.search(rule, t, re.IGNORECASE))
    return sorted(found)


def _gold(case: dict[str, Any], key: str) -> list[str]:
    return list((case.get("gold", {}).get(key) or {}).get("labels") or [])


def _g6(case: dict[str, Any]) -> list[str] | None:
    """G6 labels where the gold applies (a grant), else None (not scored)."""
    g6 = case.get("gold", {}).get("G6") or {}
    return list(g6.get("labels") or []) if g6.get("applicable") else None


def card_payload(card: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    """F6 payload of an exported hearing card."""
    out = {"predicted_factors": sorted({str(c["factor"]) for c in card.get("bench_concerns", []) if c.get("factor")}), "gold_g5": _gold(case, "G5"),
           "predicted_conditions": condition_types(card.get("conditions", [])), "concerns": len(card.get("bench_concerns", []))}  # fmt: skip
    if (g6 := _g6(case)) is not None:
        out["gold_g6"] = g6
    return out


def one_call_payload(value: OneCallCard, case: dict[str, Any]) -> dict[str, Any]:
    """F6 payload of the one-call answer (factors outside the checklist are dropped)."""
    from vakeel_sahayak.schemas.enums import Factor

    known = {f.value for f in Factor}
    out = {"predicted_factors": sorted({c.factor for c in value.concerns if c.factor in known}), "gold_g5": _gold(case, "G5"),
           "predicted_conditions": condition_types(value.conditions), "concerns": len(value.concerns)}  # fmt: skip
    if (g6 := _g6(case)) is not None:
        out["gold_g6"] = g6
    return out


def instructions() -> str:
    from vakeel_sahayak.pipelines.gold.g6_conditions import CONDITION_TYPES
    from vakeel_sahayak.schemas.enums import Factor

    return ("Counsel is preparing for a regular bail hearing in an Indian High Court. From the facts, list what the bench is likely to ask about: "
            f"each concern names one checklist factor ({', '.join(f.value for f in Factor)}) and the question. Also list the conditions courts "
            f"often impose when they grant bail in similar cases, as condition types ({', '.join(CONDITION_TYPES)}). Never predict the outcome.")  # fmt: skip


def _register_offline() -> None:
    from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler

    def handler(req: OfflineRequest) -> dict[str, Any]:
        """Rule stand-in: the checklist factors whose words occur in the facts; no conditions."""
        from vakeel_sahayak.schemas.enums import Factor

        facts = str(req.case.get("facts") or "").lower()
        hits = [f.value for f in Factor if all(w in facts for w in f.value.split("_") if len(w) > 3)]
        return {"concerns": [{"factor": f, "question": f"What about {f.replace('_', ' ')}?"} for f in hits], "conditions": []}

    register_offline_handler(TASK, handler)


_register_offline()


def one_call(case: dict[str, Any]) -> OneCallCard:
    """The one-call arm: pseudonymised facts (as the intake files them), one structured call, no retrieval and no tools."""
    from vakeel_sahayak.eval.baselines.common import resolve_llm
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.models.json_schema import schema_of
    from vakeel_sahayak.models.prompting import render_prompt
    from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, structured_call

    ctx = driver.build_context(case)
    facts = driver.file_facts(ctx, case, shelve=False)
    prompt = render_prompt(TASK, instructions(), {"case": {"case_id": case["case_id"], "facts": facts}},
                           system="You assist legal-aid counsel in India. You never predict outcomes.", schema=schema_of(OneCallCard))  # fmt: skip
    try:
        res = structured_call(resolve_llm(ctx), prompt, OneCallCard, max_tokens=1024, temperature=0.0, retries=2)
    except StructuredOutputError:
        return OneCallCard()
    return res.value if isinstance(res.value, OneCallCard) else OneCallCard.model_validate(res.value)


def hearing_card(case: dict[str, Any]) -> dict[str, Any]:
    """The system arm: the Full pipeline, then the exported card from its brief, sparring record and recorded evidence packs."""
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.eval.runners.systems import system_runner
    from vakeel_sahayak.export.hearing_card import card_from, recorded_packs
    from vakeel_sahayak.record.case_state import CaseState
    from vakeel_sahayak.schemas.bail_brief import BailBrief

    runner, switches = system_runner("full")
    ctx = driver.build_context(case, switches)
    produced = runner(case, ctx)
    brief = produced if isinstance(produced, BailBrief) else produced.get("_brief_obj") or BailBrief(case_id=case["case_id"])
    state = CaseState(case["case_id"], ctx.log)
    card = card_from(brief, state.sparring(), recorded_packs(case["case_id"], ctx.log))
    return {**card_payload(card, case), "errors": (getattr(ctx, "eval_record", None) or {}).get("errors", [])}


def pick_cases(n: int | None) -> list[dict[str, Any]]:
    """T1 cases with a non-empty G5 gold (the first `n`; default 3)."""
    path = os.environ.get("VS_FEATURE_CASES") or str(fc.t1_dir() / "dev.jsonl")
    return [r for r in fc.read_jsonl(path) if _gold(r, "G5")][: n or 3]


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F6 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm (`hearing_card`, `one_call`), one `<case id>.json` per case
        shard: this shard's index
        n_shards: the number of shards (cases are dealt out by index)
    """
    cases = fc.shard_slice(pick_cases(fc.env_limit()), shard, n_shards)
    for arm in fc.selected_arms(ARMS):
        for case in cases:
            if fc.case_file(out_dir, arm, case["case_id"]).exists():
                continue
            payload = hearing_card(case) if arm == "hearing_card" else {**one_call_payload(one_call(case), case), "llm": fc.llm_backend()}
            fc.save_case(out_dir, arm, case["case_id"], {"arm": arm, **payload})


def score(run_dir: str) -> dict[str, float]:
    """Compute F6 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (see the module docstring for the keys)

    Returns:
        `factor_recall` and `factor_precision` (card factors against G5, macro over cases), `condition_recall` (imposed condition types against G6, macro over cases with a gold condition).

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    factors = [fc.set_prf(r.get("predicted_factors", []), r.get("gold_g5", [])) for r in rows]
    conditions = [fc.set_prf(r.get("predicted_conditions", []), r.get("gold_g6", []))[0] for r in rows]
    out = {
        "factor_recall": fc.mean(p[0] for p in factors if p[0] is not None),
        "factor_precision": fc.mean(p[1] for p in factors if p[1] is not None),
        "condition_recall": fc.mean(c for c in conditions if c is not None),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
