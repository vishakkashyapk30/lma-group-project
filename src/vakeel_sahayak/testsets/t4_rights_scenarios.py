"""T4 rights scenarios: 500 scenarios from specs written from the bare acts by a team member who does not write the Radar code; dates either side of each threshold (day 59/60/61, one-third vs one-half, 7 vs 10 years, first-time vs repeat), rendered as bundles (plan §15.2).

The specs (`specs/rights_scenarios.yaml`, written by `rights_spec_writer.py` from the rule text) carry the designed answer; this builder only renders
them. This module does not import the Rights Radar, so the designed answer cannot be the Radar's output. Each scenario becomes a small bundle of plain
text documents under `out_dir/bundles/<id>/` (a remand order, a custody certificate, an arrest memo, a custody statement, as the rule needs) plus
`facts.json` with the same facts typed, so a system can be run on the documents (Munshi reads them) or on the typed facts. Parties are synthetic (Faker).

Outputs in `out_dir`: `scenarios.jsonl` (the spec row plus `bundle`, `as_of` and the document list; the designed answer is copied unchanged),
`bundles/`, `manifest.json` (counts per rule and per designed answer, threshold coverage, seed, spec hash).

CLI: `python -m vakeel_sahayak.testsets.t4_rights_scenarios [--spec PATH --out DIR]`.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from vakeel_sahayak.testsets.common import TestSetManifest, faker_names, rows_to_file, sha256_file, write_manifest

SEED = 20260424
REQUIRED = ("id", "rule", "inputs", "designed_answer")


def load_scenario_specs(spec_path: str) -> list[dict[str, Any]]:
    """Load testsets/specs/rights_scenarios.yaml.

    Args:
        spec_path: see behaviour

    Returns:
        Specs, in file order.

    Raises:
        ValueError: a spec lacks id, rule, inputs or designed_answer, or two specs share an id.
    """
    data = yaml.safe_load(Path(spec_path).read_text(encoding="utf-8")) or {}
    specs = list(data.get("scenarios") or [])
    seen: set[str] = set()
    for s in specs:
        missing = [k for k in REQUIRED if s.get(k) is None or s.get(k) == ""]
        if missing:
            raise ValueError(f"scenario {s.get('id')!r} lacks {missing}")
        if s["id"] in seen:
            raise ValueError(f"duplicate scenario id {s['id']!r}")
        seen.add(s["id"])
    return specs


def _dmy(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def _punishment_phrase(text: str) -> str:
    low = text.lower()
    if low in ("life", "imprisonment for life"):
        return "imprisonment for life"
    if low == "death":
        return "death"
    return f"imprisonment which {text}" if low.startswith("may extend") else f"imprisonment for {'a term of ' if 'or more' in low or 'not less' in low else 'up to '}{text}"


def _fir(i: int, inputs: dict[str, Any]) -> str:
    year = next((str(inputs[k])[:4] for k in ("first_remand", "arrest_date") if inputs.get(k)), "2024")
    return f"{100 + (i * 37) % 800}/{year}"


def _documents(spec: dict[str, Any], names: tuple[str, str], i: int) -> tuple[dict[str, str], str]:
    """(file name -> text, as-of date) for one scenario."""
    inp, rule = spec["inputs"], spec["rule"]
    accused, officer = names
    fir = _fir(i, inp)
    punish = _punishment_phrase(str(inp.get("max_punishment", "up to 3 years"))) if inp.get("max_punishment", "x") else "a punishment that is not recorded in the file"
    charged = f" Sections charged: {', '.join(inp['sections'])}." if inp.get("sections") else ""
    head = f"FIR No. {fir}, Police Station Kotwali. Accused: {accused}.{charged} The offence is punishable with {punish}."
    docs: dict[str, str] = {}
    if rule == "default_bail":
        fr = inp["first_remand"]
        as_of = (date.fromisoformat(fr) + timedelta(days=int(inp["day"]) - 1)).isoformat()
        docs["01_remand_order.txt"] = (
            f"IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE\nRemand order dated {_dmy(fr)}\n{head}\n"
            f"The accused {accused} was produced in custody and is remanded to judicial custody. This is the first remand order, dated {_dmy(fr)}.\n"
        )
        cs = inp.get("charge_sheet")
        status = (f"A charge sheet was filed in court on {_dmy(cs)}." if cs else "No charge sheet has been filed as on the date of this certificate.")
        docs["02_custody_certificate.txt"] = (
            f"CUSTODY CERTIFICATE\nIssued by the Superintendent, District Jail, on {_dmy(as_of)}.\n"
            f"{accused} is in judicial custody in FIR No. {fir}; first remand {_dmy(fr)}. {status}\n"
        )
    elif rule == "undertrial_limit":
        as_of = inp.get("as_of") or "2025-12-31"
        arrest = inp.get("arrest_date") or (date.fromisoformat(as_of) - timedelta(days=int(inp["custody_days"]))).isoformat()
        docs["01_arrest_memo.txt"] = f"ARREST MEMO\n{head}\n{accused} was arrested on {_dmy(arrest)} by {officer}.\n"
        docs["02_custody_certificate.txt"] = (
            f"CUSTODY CERTIFICATE issued on {_dmy(as_of)}.\n{accused} has been in custody since {_dmy(arrest)}, "
            f"which is {inp['custody_days']} days as on {_dmy(as_of)}.\n"
        )
        ft = inp.get("first_time")
        pending = inp.get("other_pending")
        state = {True: "has no previous conviction" + ("" if pending else " and no other case") + ": a first-time offender", False: "has previous convictions: not a first-time offender"}
        pend_text = {True: " One other case is pending against the accused (an FIR under investigation in another police station).", False: " No other case is pending against the accused."}.get(pending, "")
        docs["03_antecedents_report.txt"] = (
            f"ANTECEDENTS REPORT by {officer}.\n{accused} " + (state[ft] if ft is not None else "- the antecedents report is awaited and the record is not available") + f".{pend_text}\n"
        )
    elif rule == "notice_of_appearance":
        as_of = inp["arrest_date"]
        memo = inp.get("arrest_memo")
        docs["01_fir_extract.txt"] = f"FIR EXTRACT\n{head}\n"
        text = {True: "An arrest memo was prepared on arrest and records the reasons for arrest in writing.",
                False: "No notice of appearance was issued and no reasons for the arrest were recorded.",
                None: "The file does not contain an arrest memo or a notice of appearance."}[memo]
        docs["02_arrest_note.txt"] = f"ARREST NOTE of {_dmy(as_of)}\n{accused} was arrested by {officer} on {_dmy(as_of)}. {text}\n"
    elif rule in ("antil_category", "statutory_bar"):
        as_of = "2025-12-01"
        docs["01_fir_extract.txt"] = f"FIR EXTRACT\n{head}\n"
        docs["02_charge_note.txt"] = f"CHARGE NOTE of {_dmy(as_of)}\n{accused} is charged by {officer} under: {', '.join(inp['sections'])}.\n"
    else:  # production_24h
        as_of = inp["production_date"]
        docs["01_arrest_memo.txt"] = (
            f"ARREST MEMO\n{head}\n{accused} was arrested by {officer} on {_dmy(inp['arrest_date'])} at {inp['arrest_time']} hours.\n"
        )
        docs["02_production_memo.txt"] = (
            f"PRODUCTION MEMO\n{accused} was produced before the Magistrate on {_dmy(inp['production_date'])} at {inp['production_time']} hours.\n"
        )
    return docs, as_of


def render_scenario_documents(spec: dict[str, Any], names: tuple[str, str], index: int) -> tuple[dict[str, str], str]:
    """The plain-text documents of one scenario and its as-of date (also used by T5 for its planted scenarios)."""
    return _documents(spec, names, index)


def build_t4(spec_path: str, out_dir: str) -> TestSetManifest:
    """Render scenarios with designed answers.

    Args:
        spec_path: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    specs = load_scenario_specs(spec_path)
    out = Path(out_dir)
    names = faker_names(SEED, 2 * len(specs)) if specs else []
    rows: list[dict[str, Any]] = []
    for i, spec in enumerate(specs):
        docs, as_of = _documents(spec, (names[2 * i], names[2 * i + 1]), i)
        folder = out / "bundles" / spec["id"]
        folder.mkdir(parents=True, exist_ok=True)
        for fname, text in docs.items():
            (folder / fname).write_text(text, encoding="utf-8")
        facts = {"scenario": spec["id"], "as_of": as_of, **spec["inputs"]}
        (folder / "facts.json").write_text(json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=1), encoding="utf-8")
        rows.append({**spec, "as_of": as_of, "bundle": f"bundles/{spec['id']}", "documents": sorted([*docs, "facts.json"])})
    rows_to_file(out / "scenarios.jsonl", rows)
    by_rule = Counter(r["rule"] for r in rows)
    details = {
        "seed": SEED,
        "spec_sha256": sha256_file(spec_path),
        "per_rule": dict(by_rule),
        "per_designed_answer": {rule: dict(Counter(r["designed_answer"] for r in rows if r["rule"] == rule)) for rule in by_rule},
        "default_bail_days": sorted({r["inputs"]["day"] for r in rows if r["rule"] == "default_bail"}),
        "threshold_straddle": {
            "day_59_60_61": all(d in {r["inputs"].get("day") for r in rows if r["rule"] == "default_bail"} for d in (59, 60, 61)),
            "first_time_and_repeat": {str(r["inputs"].get("first_time")) for r in rows if r["rule"] == "undertrial_limit"} >= {"True", "False"},
            "max_punishments": sorted({str(r["inputs"].get("max_punishment")) for r in rows}),
        },
        "not_built": [],
        "notes": "documents are plain text (typed facts in facts.json); PDF renderings come from testsets.rendering when needed",
    }
    manifest = TestSetManifest(set_id="T4", size=len(rows), answers_from="designed answers derived from the bare-act rule text by the spec writer (not from the Rights Radar)",
                               used_for=["F3"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config
    from vakeel_sahayak.testsets.rights_spec_writer import SPEC_PATH

    ap = argparse.ArgumentParser(description="Build T4 (rights scenarios)")
    ap.add_argument("--spec", default=str(SPEC_PATH))
    ap.add_argument("--out", default=str(Path(load_config().paths.testsets_dir) / "t4"))
    args = ap.parse_args(argv)
    m = build_t4(args.spec, args.out)
    print(json.dumps({"size": m.size, **{k: m.details[k] for k in ("per_rule", "per_designed_answer")}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
