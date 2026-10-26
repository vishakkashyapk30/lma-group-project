"""Feature evaluation F1: Abhiyojak sparring vs a one-call list; 2x2 with A2, A8, A9. Test set: T1, G4. Metrics: objection-factor recall/precision vs G4; unsupported-fact rate in replies; share of UNANSWERED flagged (plan §15.6).

Test set: T1 dev cases (`data/testsets/t1/dev.jsonl`; `VS_FEATURE_CASES` points at `cases.jsonl` or another file), restricted to cases whose G4 gold (the objection factors the court discussed) is not empty. G4 is rule-only
on this machine (docs/handoff/gold-labeler.md: the non-Qwen labeler was run for G1 and G3 only), so recall and precision are against a provisional gold. Arms (one directory each, one JSON file per case):

- `sparring`: the Full pipeline (Munshi-less text case through Peshkar, Gate 1, Sutradhar, Vakeel, Abhiyojak; `eval.runners.driver.run_agents`); the objections the critic kept, with replies and verdicts.
- `a2`: the 2x2 cell with sparring on and check-and-repair off (variant A2); `a8` (no sparring) and `a9` (neither) have no objections to score, so they are written as not applicable: their effect is on the brief, not on this feature.
- `one_call`: `AbhiyojakAgent.list_objections_one_call`: one ungrounded call "list the prosecution's likely objections", no stores, no replies, no verdicts.

Payload per case: `predicted_factors` (factors of the objections), `gold_g4`, `reply_sentences` and `unsupported_reply_sentences` (reply sentences the NLI checker finds unsupported by the objection, the brief's grounds and the objection's grounds it answers: the system's own NLI, not MiniCheck), `unanswered` (ids with verdict
UNANSWERED) and `flagged_unanswered` (those that counsel is shown: an open issue of the brief, or an item of the Gate 2 checklist). One-call files carry only the factors and the gold. Offline stand-in models by default: the objections and verdicts come from the rule-based handlers, so the numbers describe the harness, not a model.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("sparring", "a2", "one_call", "a8", "a9")
SYSTEM_OF = {"sparring": "full", "a2": "A2"}


def sparring_payload(record: dict[str, Any], gold: list[str]) -> dict[str, Any]:
    """The F1 payload of a driver record (`sparring`, `brief`)."""
    spar = record.get("sparring") or {}
    objections = spar.get("objections") or []
    brief = record.get("brief") or {}
    premise_parts = [g.get("argument", "") for g in brief.get("grounds", [])]
    sentences = unsupported = 0
    for o in objections:
        reply = (o.get("reply") or {}).get("text") or ""
        if not reply.strip():
            continue
        premise = " ".join([o.get("objection", ""), *premise_parts, *(g.get("fact") or "" for g in o.get("grounds", []))])
        n, bad = fc.unsupported_count(reply, premise)
        sentences += n
        unsupported += bad
    open_items = " ".join(i.get("item", "") for i in brief.get("open_issues", []))
    unanswered = [o["id"] for o in objections if o.get("verdict") == "UNANSWERED"]
    gate_items = [str(x) for c in record.get("counsel", []) for x in (c.get("unresolved") or {}).get("unanswered", [])]  # what the Gate 2 checklist shows counsel
    flagged = [i for i in unanswered if f"Objection {i} " in open_items or any(i == x or f"{i} " in x or f"{i}:" in x for x in gate_items)]
    return {"predicted_factors": sorted({o["factor"] for o in objections}), "gold_g4": gold, "reply_sentences": sentences, "unsupported_reply_sentences": unsupported,
            "unanswered": unanswered, "flagged_unanswered": flagged, "objections": len(objections), "errors": record.get("errors", []), "nli": fc.nli_backend()}


def one_call_payload(case: dict[str, Any], gold: list[str]) -> dict[str, Any]:
    """The one-call arm on a text-only case: facts pseudonymised like the intake, one ungrounded listing call."""
    from vakeel_sahayak.agents.abhiyojak.agent import AbhiyojakAgent
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.orchestration.state import CaseGraphState

    ctx = driver.build_context(case)
    facts = driver.file_facts(ctx, case, shelve=False)
    state = CaseGraphState(case_id=case["case_id"], before=case.get("before"), facts_text=facts)
    objections = AbhiyojakAgent(ctx).list_objections_one_call(state)
    return {"predicted_factors": sorted({o.factor for o in objections if o.factor != "general"}), "gold_g4": gold, "objections": len(objections), "nli": None}


def pick_cases(n: int | None) -> list[dict[str, Any]]:
    """T1 cases with a non-empty G4 gold (the first `n`; default 3)."""
    path = os.environ.get("VS_FEATURE_CASES") or str(fc.t1_dir() / "dev.jsonl")
    rows = [r for r in fc.read_jsonl(path) if (r.get("gold", {}).get("G4") or {}).get("labels")]
    return rows[: n or 3]


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F1 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm (`sparring`, `a2`, `one_call`, `a8`, `a9`), one `<case id>.json` per case
        shard: this shard's index
        n_shards: the number of shards (cases are dealt out by index)
    """
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.eval.runners.systems import system_runner

    cases = fc.shard_slice(pick_cases(fc.env_limit()), shard, n_shards)
    for arm in fc.selected_arms(ARMS):
        if arm in ("a8", "a9"):
            fc.mark_unavailable(out_dir, arm, f"not applicable: {arm.upper()} switches sparring off, so there are no objections to score (its effect is on the brief)")
            continue
        runner, switches = system_runner(SYSTEM_OF[arm]) if arm in SYSTEM_OF else (None, None)
        for case in cases:
            if fc.case_file(out_dir, arm, case["case_id"]).exists():
                continue
            gold = list(case["gold"]["G4"]["labels"])
            if arm == "one_call":
                payload = one_call_payload(case, gold)
            else:
                ctx = driver.build_context(case, switches)
                produced = runner(case, ctx)
                record = produced if isinstance(produced, dict) else {"brief": produced.model_dump(mode="json")}
                record.update(getattr(ctx, "eval_record", None) or {})
                payload = sparring_payload(record, gold)
            fc.save_case(out_dir, arm, case["case_id"], {"arm": arm, **payload})


def score(run_dir: str) -> dict[str, float]:
    """Compute F1 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (one JSON file per case; see the module docstring for the keys)

    Returns:
        `objection_recall` and `objection_precision` (macro means over cases with a non-empty gold or prediction), `unsupported_reply_rate` (reply sentences, micro),
        `unanswered_flagged_share` (UNANSWERED objections that were flagged, micro). A metric with nothing to measure is left out.

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    prf = [fc.set_prf(r.get("predicted_factors", []), r.get("gold_g4", [])) for r in rows]
    sent = sum(r.get("reply_sentences", 0) for r in rows)
    unanswered = sum(len(r.get("unanswered", [])) for r in rows)
    flagged = sum(len(set(r.get("flagged_unanswered", [])) & set(r.get("unanswered", []))) for r in rows)
    out = {
        "objection_recall": fc.mean(p[0] for p in prf if p[0] is not None),
        "objection_precision": fc.mean(p[1] for p in prf if p[1] is not None),
        "unsupported_reply_rate": fc.rate(sum(r.get("unsupported_reply_sentences", 0) for r in rows), sent),
        "unanswered_flagged_share": fc.rate(flagged, unanswered),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
