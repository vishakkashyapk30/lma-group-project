"""M17, citation faithfulness by removal (evaluation plan 4.3): redraft claims with their cited paragraph deleted from the evidence.

Per case the Full pipeline runs as usual (the record is the Full record). Then, for up to `max_claims` grounds that cite a paragraph (the first cited paragraph of each ground, grounds in
brief order), the evidence pack of that factor is rebuilt without that paragraph (every item with the same document id and paragraph number is dropped from every slot; a slot left
empty becomes MISSING) and a fresh Vakeel drafts the factor again from it. The record gains

    "removal": {"claims": [{"ground_id", "factor", "stance", "doc_id", "para", "original", "redraft"}], "n_cited_grounds": k, "max_claims": N}

where `redraft` is the argument Vakeel writes without the paragraph (None when it no longer makes the claim). The scoring step turns the block into the share of claims that
changed (`eval.metrics.citations.removal_change`, column M17 of the citations table). A claim that survives word for word was probably written from memory and its citation attached
afterwards; the number is a lower bound on post-hoc citation (a changed claim may still be partly from memory).

Offline it runs on the stand-in models (the template drafter reads the pack, so a removed paragraph changes the quotation it builds). The hosted-model arm is run later under the
same code. CLI (resumable, shardable; writes `MANIFEST.json` and one JSON per case like `driver run`):

    python -m vakeel_sahayak.eval.runners.m17_removal --cases data/testsets/t1/dev.jsonl --out <dir> [--n 10] [--max-claims 3] [--shard i --n-shards k]
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from vakeel_sahayak.schemas.enums import AgentName, SlotStatus

SYSTEM = "m17"
MAX_CLAIMS = 3


def remove_paragraph(packs: list[Any], factor: Any, doc_id: str, para: int) -> list[Any]:
    """The pack of `factor` without the paragraph (`doc_id`, `para`); other factors' packs are not part of the redraft. A slot that loses its last item becomes MISSING."""
    out = []
    for pack in packs:
        if pack.factor != factor:
            continue
        slots = []
        for slot in pack.slots:
            items = [i for i in slot.items if not (str(i.get("doc_id")) == str(doc_id) and str(i.get("para")) == str(para))]
            emptied = bool(slot.items) and not items
            slots.append(slot.model_copy(update={"items": items, "status": SlotStatus.MISSING if emptied else slot.status}))
        out.append(pack.model_copy(update={"slots": slots}))
    return out


def cited_targets(brief: Any, max_claims: int) -> list[Any]:
    """Up to `max_claims` (ground, authority) pairs: the first authority of each ground that has one, in brief order."""
    return [(g, g.authorities[0]) for g in brief.grounds if g.authorities][:max_claims]


def make_sutradhar(captured: dict[str, Any]) -> Any:
    """A Sutradhar factory for `driver.run_agents(sutradhar=...)` that remembers the state and the evidence packs `delegate` receives (nothing else changes)."""
    def factory(ctx: Any) -> Any:
        from vakeel_sahayak.agents.registry import create_agent

        agent = create_agent(AgentName.SUTRADHAR, ctx)
        original = agent.delegate

        def delegate(state: Any, packs: list[Any]) -> Any:
            captured["state"], captured["packs"] = state, list(packs)
            return original(state, packs)

        agent.delegate = delegate
        return agent

    return factory


def redraft_without(ctx: Any, state: Any, packs: list[Any], ground: Any, authority: Any) -> str | None:
    """Vakeel's argument for the ground's factor when the cited paragraph is gone; None when no ground for that factor and stance comes back."""
    from vakeel_sahayak.agents.registry import create_agent

    new_packs = remove_paragraph(packs, ground.factor, authority.doc_id, authority.para)
    if not new_packs:
        return None
    vakeel = create_agent(AgentName.VAKEEL, ctx)
    try:
        out = vakeel.run(state.model_copy(update={"evidence_packs": new_packs, "brief": None, "sparring": None}))
    finally:
        vakeel.close()
    brief = getattr(out, "brief", None)
    for g in (brief.grounds if brief is not None else []):
        if g.factor == ground.factor and g.stance == ground.stance:
            return g.argument
    return None


def run_case(case: dict[str, Any], ctx: Any, max_claims: int = MAX_CLAIMS) -> dict[str, Any]:
    """The Full pipeline on the case, then the removal redrafts; returns the Full result record plus `removal` (see the module docstring)."""
    from vakeel_sahayak.eval.runners.driver import run_agents

    captured: dict[str, Any] = {}
    result = run_agents(case, ctx, sutradhar=make_sutradhar(captured))
    brief = result["_brief_obj"]
    claims = []
    targets = cited_targets(brief, max_claims) if captured else []
    for ground, authority in targets:
        try:
            redraft = redraft_without(ctx, captured["state"], captured["packs"], ground, authority)
            error = None
        except Exception as exc:  # noqa: BLE001 - one failed redraft is recorded and the case goes on
            redraft, error = None, f"{type(exc).__name__}: {str(exc)[:200]}"
        claim = {"ground_id": ground.id, "factor": ground.factor.value, "stance": ground.stance.value, "doc_id": authority.doc_id, "para": authority.para,
                 "original": ground.argument, "redraft": redraft}
        if error:
            claim["error"] = error
        claims.append(claim)
    result["removal"] = {"claims": claims, "n_cited_grounds": sum(1 for g in brief.grounds if g.authorities), "max_claims": max_claims}
    return result


def main(argv: list[str] | None = None) -> int:
    """CLI: run the removal arm on a case file, offline unless the environment names a hosted model (not to be done without the owner's go-ahead)."""
    from vakeel_sahayak.eval.runners import driver
    from vakeel_sahayak.orchestration.switches import Switches

    ap = argparse.ArgumentParser(prog="m17_removal")
    ap.add_argument("--cases", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--max-claims", type=int, default=MAX_CLAIMS)
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args(argv)
    done = driver.run_cases(a.cases, a.out, SYSTEM, lambda case, ctx: run_case(case, ctx, a.max_claims), Switches(), shard=a.shard, n_shards=a.n_shards, seed=a.seed, limit=a.n)
    print(f"{SYSTEM}: {done} case(s) completed now, {len(driver.load_progress(a.out))} saved in {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
