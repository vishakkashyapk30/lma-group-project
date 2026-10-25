"""Feature evaluation F2: Incremental redrafting vs full regeneration. Test set: T3. Metrics: stale-claim rate; unchanged-claim stability; tokens and wall time; factor recall and unsupported rate vs full regeneration; no edits on no-op controls (plan §15.6).

Test set T3: 60 T1 cases with four updates each (charge sheet filed, a co-accused granted bail, a clock crossing of default-bail day 61 or the s.479 third, and a no-op that re-supplies the case's own facts):
180 real changes and 60 no-op controls. A row carries the baseline field values (G3 where the order has them, else constructed), the new value, the factors the dependency model says to reopen, and the fields that must stay byte-identical.

Harness (all agents are the repository's own; offline stand-in models by default): the baseline dossier is built from the row's `baseline`, with the Rights Radar run on it; a baseline brief is drafted by `truth_maintenance.redraft.full_regeneration` over
the row's reopened factors plus parity, antecedents, flight risk and gravity (bare evidence packs: stance only, no retrieval, so the arms differ in drafting, not retrieval); the new dossier applies `new_value`; the change set is
`staleness.compute_change_set`. Arms (one directory each, one JSON file per update):

- `incremental`: `redraft_incrementally(state, change_set)`: only the stale claims are redrafted, the rest stay word for word, a no-op costs no model call.
- `full_regen`: `full_regeneration(state)`: every ground drafted afresh (the comparison arm).

Per update: `claims_total`; `claims_stale` = grounds that still depend on the OLD hash of a changed field and are not marked STALE (the dependency bookkeeping of `Ground.depends_on`, so it measures whether the brief has caught up with the change, not whether the text is right);
`unchanged_total` and `unchanged_identical` = grounds whose factor is not reopened, and how many are word for word equal (whole ground record) to the baseline; `tokens` (usage of the model clients during the arm's call) and `wall_s`; `edited` = the brief differs from the baseline in any ground. Factor recall and the unsupported-fact rate
against full regeneration are not computed (they need the evaluation-only MiniCheck, plan §15.9, and the metrics modules are stubs). The stand-in model gives the same drafts whatever it is asked, so tokens and wall time are the stand-in's, not a model's.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Any

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("incremental", "full_regen")
BASE_FACTORS = ("parity_with_co_accused", "antecedents", "flight_risk", "gravity_and_punishment")
SOURCE = {"doc": "t3-baseline", "page": 1}


def _typed(values: dict[str, Any], as_of: str | None, custody_days: int | None) -> Any:
    """A `CaseDossier` with each known field VERIFIED from a T3 value dict."""
    from datetime import date

    from vakeel_sahayak.schemas.dossier import CaseDossier, DossierFields

    spec: dict[str, Any] = {}
    for name in ("fir", "offence_date", "arrest_date", "first_remand", "charge_sheet", "co_accused_bail"):
        if name in values:
            spec[name] = values[name]
    if "sections" in values:
        spec["sections"] = [{"as_written": s, "code": s.split()[0], "section": s.split()[-1]} for s in values["sections"]]
    if custody_days is None and "arrest_date" in values and as_of:
        custody_days = (date.fromisoformat(as_of) - date.fromisoformat(values["arrest_date"])).days + 1
    if custody_days is not None:
        spec["custody_days"] = custody_days
    fields = DossierFields.model_validate({k: {"value": v, "source": SOURCE, "status": "VERIFIED"} for k, v in spec.items()})
    return CaseDossier(case_id="case-0007", as_of=as_of, fields=fields)


def tokens_used() -> int:
    """Tokens recorded so far by every cached model client."""
    from vakeel_sahayak.models import factory

    return sum(int(c.usage.total) for c in list(factory._LLM_CACHE.values()) if hasattr(c, "usage"))  # noqa: SLF001


def build_states(row: dict[str, Any]) -> tuple[Any, Any, Any]:
    """(baseline state with its brief, state after the update, change set) for a T3 row."""
    from vakeel_sahayak.orchestration.state import CaseGraphState
    from vakeel_sahayak.rights.engine import RightsEngine
    from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
    from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance
    from vakeel_sahayak.schemas.retrieval_plan import EvidencePack
    from vakeel_sahayak.truth_maintenance.redraft import full_regeneration
    from vakeel_sahayak.truth_maintenance.staleness import compute_change_set

    base_vals = dict(row["baseline"])
    new_vals = {**base_vals, **(row.get("new_value") or {})}
    new_custody = (row.get("new_value") or {}).get("custody_days")
    base_as_of = row.get("baseline_as_of") or row.get("as_of")
    new_as_of = row.get("as_of") or base_as_of
    old = _typed(base_vals, base_as_of, int(new_custody) - 1 if new_custody else None)
    new = _typed(new_vals, new_as_of, int(new_custody) if new_custody else None)
    engine = RightsEngine()
    old_rights = engine.run(old, [], base_as_of or "2025-01-01")
    new_rights = engine.run(new, [], new_as_of or "2025-01-01")
    factors = list(dict.fromkeys([*(row.get("reopened_factors") or []), *BASE_FACTORS]))
    packs = [EvidencePack(factor=Factor(f), stance=FactorStance.FAVOURABLE) for f in factors]
    shell = BailBrief(case_id="case-0007", grounds=[Ground(id=f"G{i}", factor=Factor(f), stance=FactorStance.FAVOURABLE, argument="", check=ClaimCheck.NEEDS_REVIEW)
                                                    for i, f in enumerate(factors, 1)])
    state0 = CaseGraphState(case_id="case-0007", dossier=old, rights=old_rights, brief=shell, evidence_packs=packs)
    baseline = full_regeneration(state0)
    state0 = state0.model_copy(update={"brief": baseline})
    change = compute_change_set(old, new, old_rights, new_rights, trigger=row.get("trigger", "new_document"))
    return state0, state0.model_copy(update={"dossier": new, "rights": new_rights}), change


def old_hashes(change: Any) -> dict[str, str | None]:
    """Changed field -> its old value hash."""
    return {f.field: f.old_hash for f in change.fields if f.old_hash != f.new_hash}


def measure(arm: str, row: dict[str, Any]) -> dict[str, Any]:
    """Run one arm on one T3 row and return the case payload."""
    from vakeel_sahayak.truth_maintenance.redraft import full_regeneration, redraft_incrementally

    base_state, state, change = build_states(row)
    baseline = base_state.brief
    reopened = set(row.get("reopened_factors") or [])
    t0, k0 = time.monotonic(), tokens_used()
    brief = redraft_incrementally(state, change) if arm == "incremental" else full_regeneration(state)
    wall, tokens = time.monotonic() - t0, tokens_used() - k0
    stale_hashes = old_hashes(change)
    stale = [g for g in brief.grounds if g.state.value == "CURRENT" and any(g.depends_on.facts.get(f) == h and h is not None for f, h in stale_hashes.items())]
    before = {g.id: g.model_dump(mode="json") for g in baseline.grounds}
    unchanged = [g for g in baseline.grounds if g.factor.value not in reopened]
    same = [g for g in unchanged if any(n.id == g.id and n.model_dump(mode="json") == before[g.id] for n in brief.grounds)]
    edited = [g.model_dump(mode="json") for g in brief.grounds] != [g.model_dump(mode="json") for g in baseline.grounds]
    return {"arm": arm, "noop": row["change_type"] == "noop", "change_type": row["change_type"], "claims_total": len(brief.grounds), "claims_stale": len(stale),
            "unchanged_total": len(unchanged), "unchanged_identical": len(same), "tokens": tokens, "wall_s": wall, "edited": edited, "models": "offline stand-in" if os.environ.get("VS_LLM_BACKEND", "offline") == "offline" else os.environ.get("VS_LLM_BACKEND")}


def pick_rows(rows: list[dict[str, Any]], n: int | None) -> list[dict[str, Any]]:
    """The first `n` rows, drawn evenly over the four change types so a small run covers each."""
    if not n:
        return rows
    kinds = sorted({r["change_type"] for r in rows})
    out: list[dict[str, Any]] = []
    per = max(1, n // len(kinds))
    for k in kinds:
        out += [r for r in rows if r["change_type"] == k][:per]
    return out[:max(n, len(kinds))]


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F2 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm (`incremental`, `full_regen`), one `<update id>.json` per update
        shard: this shard's index
        n_shards: the number of shards (updates are dealt out by index)
    """
    rows = pick_rows(fc.read_jsonl(os.environ.get("VS_FEATURE_CASES") or fc.testsets_dir() / "t3" / "updates.jsonl"), fc.env_limit())
    for arm in fc.selected_arms(ARMS):
        for row in fc.shard_slice(rows, shard, n_shards):
            if fc.case_file(out_dir, arm, row["update_id"]).exists():
                continue
            fc.save_case(out_dir, arm, row["update_id"], measure(arm, row))


def score(run_dir: str) -> dict[str, float]:
    """Compute F2 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (one JSON file per update: `noop`, `claims_total`, `claims_stale`, `unchanged_total`, `unchanged_identical`, `tokens`, `wall_s`, `edited`)

    Returns:
        `stale_claim_rate` (stale claims over all claims, real changes), `unchanged_claim_stability` (identical over unchanged claims, real changes), `tokens` and `wall_s` (means over real changes),
        `noop_edit_rate` (share of no-op controls whose brief was edited). A metric with nothing to measure is left out.

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    real = [r for r in rows if not r.get("noop")]
    noop = [r for r in rows if r.get("noop")]
    out = {
        "stale_claim_rate": fc.rate(sum(r["claims_stale"] for r in real), sum(r["claims_total"] for r in real)),
        "unchanged_claim_stability": fc.rate(sum(r["unchanged_identical"] for r in real), sum(r["unchanged_total"] for r in real)),
        "tokens": fc.mean(float(r["tokens"]) for r in real),
        "wall_s": fc.mean(float(r["wall_s"]) for r in real),
        "noop_edit_rate": fc.rate(sum(bool(r["edited"]) for r in noop), len(noop)),
    }
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
