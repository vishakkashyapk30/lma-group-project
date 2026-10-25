"""Feature evaluation F3: Rights Radar vs LLM-only and LLM + date_calc. Test set: T4; G7 on T1. Metrics: accuracy per rule; false-ELIGIBLE rate; CHECK rate; agreement with G7 (plan §15.6).

Test set T4: 500 constructed scenarios (default bail, undertrial limit, notice of appearance, production within 24 hours) whose designed answer is derived from the
rule text by `testsets/rights_spec_writer.py`, independently of the Radar. Arms (one directory each under the output directory, one JSON file per scenario):

- `radar`: the deterministic rules engine (`rights.rules.*`) on the scenario inputs.
- `llm_only`: a language model reads the scenario's documents and decides the status itself; its day counts are its own arithmetic.
- `llm_date_calc`: the same, but day counts come from the exact `date_calc` arithmetic (the tool), the legal thresholds still from the model.

OFFLINE STAND-IN: with `VS_LLM_BACKEND=offline` the two LLM arms run a deliberately naive rule-based reader (`naive_reader`: the rules a hurried reader applies, such as 60 days or half the
maximum term, and no 90-day class, no first-time-offender third, no CHECK) registered as the offline handler of task `f3.judge_rights`. Its numbers say nothing about any real model; with a hosted
or local model the same prompt and schema go to that model. G7 agreement (T1) needs G7 labels, which are almost empty (docs/handoff/gold-labeler.md): it is reported only when a case file carries `g7_agree`.
"""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from vakeel_sahayak.eval import feature_common as fc

ARMS = ("radar", "llm_only", "llm_date_calc")
TASK = "f3.judge_rights"
STATUSES = ("ELIGIBLE", "NOT_YET", "WINDOW_CLOSED", "CHECK", "NOT_APPLICABLE", "FLAG", "OK", "UNKNOWN")


class RightsAnswer(BaseModel):
    """The model's answer for one scenario."""

    status: str
    reason: str = ""


# ---------------------------------------------------------------------------------------------- the radar arm
def radar_status(scenario: dict[str, Any]) -> str:
    """The Radar's status for a T4 scenario row (`rule`, `inputs`)."""
    from vakeel_sahayak.rights.inputs import RuleInputs
    from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
    from vakeel_sahayak.rights.rules.notice_of_appearance import NoticeOfAppearanceRule
    from vakeel_sahayak.rights.rules.production_24h import Production24hRule
    from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule

    i, rule = scenario["inputs"], scenario["rule"]
    if rule == "default_bail":
        as_of = (date.fromisoformat(i["first_remand"]) + timedelta(days=i["day"] - 1)).isoformat()
        inp = RuleInputs(as_of=as_of, first_remand=i["first_remand"], max_punishment=i["max_punishment"], charge_sheet_date=i["charge_sheet"], charge_sheet_filed=bool(i["charge_sheet"]))
        return DefaultBailRule().evaluate(inp).status.value
    if rule == "undertrial_limit":
        inp = RuleInputs(as_of=i["as_of"], max_punishment=i["max_punishment"], custody_days=i["custody_days"], arrest_date=i["arrest_date"],
                         antecedents_known=i["first_time"] is not None, first_time_offender=i["first_time"])
        return UndertrialLimitRule().evaluate(inp).status.value
    if rule == "notice_of_appearance":
        inp = RuleInputs(as_of=i["arrest_date"], max_punishment=i["max_punishment"], arrest_memo_present=i["arrest_memo"], arrest_date=i["arrest_date"])
        return NoticeOfAppearanceRule().evaluate(inp).status.value
    inp = RuleInputs(as_of=i["production_date"], arrest_date=i["arrest_date"], arrest_time=i["arrest_time"], production_date=i["production_date"], production_time=i["production_time"])
    return Production24hRule().evaluate(inp).status.value


# ---------------------------------------------------------------------------------------------- the LLM arms
_DMY = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_YEARS = re.compile(r"up to (?:up to )?(\d+)\s+years?")


def _dates(text: str) -> list[date]:
    return [date(int(y), int(m), int(d)) for d, m, y in _DMY.findall(text)]


def _years(text: str) -> int | None:
    m = _YEARS.search(text)
    return int(m.group(1)) if m else (1 if "up to 1 year" in text else None)


def naive_reader(documents: dict[str, str], use_date_calc: bool) -> str:
    """The offline stand-in judge: a hurried reader's rules over the documents' text (see the module docstring). Pure."""
    text = "\n".join(documents.values())
    low = text.lower()
    years = _years(text)
    if "custody certificate" in low and "no charge sheet" in low or "first remand" in low:  # default bail
        dates = _dates(text)
        if not dates:
            return "UNKNOWN"
        first, last = dates[0], dates[-1]
        days = (last - first).days + 1 if use_date_calc else int((last.year - first.year) * 12 + last.month - first.month) * 30 + (last.day - first.day) + 1
        filed = "no charge sheet" not in low and "charge sheet" in low
        return "ELIGIBLE" if (not filed and days >= 60) else "NOT_YET"
    if "antecedents report" in low or "which is" in low and "days" in low:  # undertrial limit
        m = re.search(r"which is (\d+) days", text)
        days = int(m.group(1)) if m else 0
        if years is None or years >= 99:
            return "NOT_APPLICABLE"
        return "ELIGIBLE" if days >= 0.5 * years * 365 else "NOT_YET"
    if "arrest memo" in low and "produced before the magistrate" in low:  # production within 24 hours: dates only
        dates = _dates(text)
        return "OK" if len(dates) >= 2 and (dates[-1] - dates[0]).days <= 1 else "FLAG"
    return "OK" if "arrest memo was prepared" in low else "UNKNOWN"


def _register_offline() -> None:
    from vakeel_sahayak.models.offline_llm import OfflineRequest, register_offline_handler

    def handler(req: OfflineRequest) -> dict[str, Any]:
        docs = {str(k): str(v) for k, v in (req.case.get("documents") or {}).items()}
        return {"status": naive_reader(docs, bool(req.case.get("date_calc"))), "reason": "offline stand-in reader"}

    register_offline_handler(TASK, handler)


_register_offline()


def llm_status(scenario: dict[str, Any], documents: dict[str, str], date_calc: bool) -> str:
    """Ask the configured model for the status (offline: the stand-in reader)."""
    from vakeel_sahayak.models.json_schema import schema_of
    from vakeel_sahayak.models.prompting import render_prompt
    from vakeel_sahayak.orchestration.structured_output import StructuredOutputError, structured_call

    instructions = ("Read the documents of one accused's file and decide the status of the right named in `rule`: one of " + ", ".join(STATUSES)
                    + ". " + ("Day counts are computed for you by an exact date calculator; use them. " if date_calc else "Count the days yourself. ")
                    + "Reply with the status and one sentence of reason.")
    data = {"case": {"case_id": scenario["id"], "rule": scenario["rule"], "documents": documents, "date_calc": date_calc}}
    prompt = render_prompt(TASK, instructions, data, system="You assist legal-aid counsel with the Indian bail rules. You never predict outcomes.", schema=schema_of(RightsAnswer))
    try:
        res = structured_call(resolve_llm_for_f3(), prompt, RightsAnswer, max_tokens=256, temperature=0.0, retries=1)
    except StructuredOutputError:
        return "UNKNOWN"
    val = res.value if isinstance(res.value, RightsAnswer) else RightsAnswer.model_validate(res.value)
    return val.status.strip().upper()


def resolve_llm_for_f3() -> Any:
    """The model of the LLM arms (the shared 14B role)."""
    from vakeel_sahayak.models.factory import get_llm

    return get_llm("agents_14b")


def _documents(root: Path, scenario: dict[str, Any]) -> dict[str, str]:
    d = root / scenario["bundle"]
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(d.glob("*.txt"))}


def _with_date_calc(documents: dict[str, str]) -> dict[str, str]:
    """Add the exact day count of the file (`date_calc`) as a line of the documents for the date_calc arm."""
    text = "\n".join(documents.values())
    dates = _dates(text)
    if len(dates) >= 2:
        documents = {**documents, "date_calc.txt": f"date_calc: {(dates[-1] - dates[0]).days + 1} days from {dates[0]:%d.%m.%Y} to {dates[-1]:%d.%m.%Y} inclusive"}
    return documents


def run(out_dir: str, shard: int = 0, n_shards: int = 1) -> None:
    """Run F3 (system and comparison arms), resumable.

    Args:
        out_dir: results directory; one sub-directory per arm (`radar`, `llm_only`, `llm_date_calc`), one `<scenario id>.json` per scenario
        shard: this shard's index
        n_shards: the number of shards (scenarios are dealt out by index)
    """
    import os

    root = fc.testsets_dir() / "t4"
    path = os.environ.get("VS_FEATURE_CASES") or str(root / "scenarios.jsonl")
    rows = fc.read_jsonl(path)[: fc.env_limit()]
    mine = fc.shard_slice(rows, shard, n_shards)
    for arm in fc.selected_arms(ARMS):
        for sc in mine:
            if fc.case_file(out_dir, arm, sc["id"]).exists():
                continue
            if arm == "radar":
                predicted = radar_status(sc)
            else:
                docs = _documents(root, sc)
                predicted = llm_status(sc, _with_date_calc(docs) if arm == "llm_date_calc" else docs, arm == "llm_date_calc")
            fc.save_case(out_dir, arm, sc["id"], {"rule": sc["rule"], "predicted": predicted, "designed": sc["designed_answer"], "arm": arm, "llm": None if arm == "radar" else fc.llm_backend()})


def score(run_dir: str) -> dict[str, float]:
    """Compute F3 metrics for one arm directory.

    Args:
        run_dir: an arm's directory (one JSON file per scenario with `rule`, `predicted`, `designed`)

    Returns:
        `accuracy/<rule>` per rule, `accuracy` overall, `false_eligible_rate` (predicted ELIGIBLE where the designed answer is not, over all scenarios), `check_rate` (share predicted CHECK),
        and `g7_agreement` when the files carry `g7_agree`.

    Raises:
        ValueError: the directory has no cases.
    """
    rows = fc.load_cases(run_dir)
    out: dict[str, float | None] = {}
    for rule in sorted({r["rule"] for r in rows}):
        rs = [r for r in rows if r["rule"] == rule]
        out[f"accuracy/{rule}"] = fc.rate(sum(r["predicted"] == r["designed"] for r in rs), len(rs))
    out["accuracy"] = fc.rate(sum(r["predicted"] == r["designed"] for r in rows), len(rows))
    out["false_eligible_rate"] = fc.rate(sum(r["predicted"] == "ELIGIBLE" and r["designed"] != "ELIGIBLE" for r in rows), len(rows))
    out["check_rate"] = fc.rate(sum(r["predicted"] == "CHECK" for r in rows), len(rows))
    g7 = [r["g7_agree"] for r in rows if "g7_agree" in r]
    out["g7_agreement"] = fc.mean(float(bool(x)) for x in g7)
    return fc.present(out)


if __name__ == "__main__":
    raise SystemExit(fc.cli(sys.modules[__name__]))
