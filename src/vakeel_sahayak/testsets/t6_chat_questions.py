"""T6 chat questions: about 150 templated questions over T1/T2 cases incl. routing questions (plan §15.2, §6.4).

Two kinds. `fact` questions have a checkable answer taken from G3 (the case's dossier values), from the timeline (a date, or custody days computed from
two dated events) or from the IPC-to-BNS concordance. `routing` questions are the chat routes of plan §6.4 (custody days -> `get_timeline` + `date_calc`;
BNS equivalent -> `map_section`; s.479 -> `rights_check`; Supreme Court parity case -> `search_reasoning` + `citations`; how the State opposes bail ->
`search_objections` + `get_statute`; what a court said in this case -> `search_case_docs`); what is scored is whether the right tools are called with valid
arguments, and where an answer is known (custody days, a BNS section) it is stored too. No question is written by hand: each comes from a template filled
from the case, so the expected tools and answers are known by construction.

Cases come from the open part of T1 (the blind slice stays sealed) and from T2 truth rows (`t2_dir/truth.jsonl`, whose `fields` are the values the T2
documents were built from; a missing T2 directory just means T1-only questions, recorded in the manifest). The concordance answers are read from
`data/interim/concordance_edges.jsonl` when it exists (single-target sections only) and from a built-in table of the same sections otherwise; the manifest
says which.

Outputs in `out_dir`: `questions.jsonl` (qid, case_id, source T1|T2, bundle_id, question, expected_answer, answer_source G3|timeline|concordance|None,
expected_tools, kind, route), `manifest.json`. CLI: `python -m vakeel_sahayak.testsets.t6_chat_questions [--t1 DIR --t2 DIR --out DIR]`.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from datetime import date, timedelta
from itertools import zip_longest
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets.common import (
    TestSetManifest,
    g3_fields,
    load_t1_cases,
    rows_from_file,
    rows_to_file,
    sha256_file,
    write_manifest,
)

SEED = 20260426
TARGET = 150
QUOTAS: dict[str, int] = {
    "g3_arrest": 12, "g3_sections": 12, "g3_charge_sheet": 8, "g3_fir_number": 8, "g3_first_remand": 6,
    "tl_custody": 12, "tl_first_remand": 6, "tl_fir_date": 4, "concordance": 14,
    "rt_custody": 24, "rt_bns": 12, "rt_s479": 12, "rt_parity": 8, "rt_state": 8, "rt_docs": 4,
}  # fmt: skip
assert sum(QUOTAS.values()) == TARGET
# fallback IPC -> BNS table (single-target sections that agree with data/interim/concordance_edges.jsonl)
IPC_TO_BNS: dict[str, str] = {
    "420": "318(4)", "302": "103", "379": "303", "376": "64", "406": "316(2)", "498A": "85", "304B": "80", "307": "109", "323": "115(2)",
    "324": "118(1)", "34": "3(5)", "120B": "61(2)", "354": "74", "363": "137(2)", "411": "317(2)", "366": "87", "452": "333", "353": "132",
    "380": "305", "409": "316(5)", "304": "105", "300": "101", "299": "100", "471": "340",
}  # fmt: skip
OFFENCES = ["cheating", "murder", "NDPS", "dowry death", "cheque dishonour", "rape", "theft", "criminal breach of trust", "kidnapping", "forgery"]
COURTS = ["Sessions Court", "Magistrate", "High Court"]


def _dmy(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def _both(iso: str) -> str:
    return f"{iso} ({_dmy(iso)})"


def _iso(value: Any) -> str | None:
    return value if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-" else None


def _norm(fields: dict[str, Any]) -> dict[str, Any]:
    """Comparable values out of either G3 shape."""
    cs = fields.get("charge_sheet")
    filed = cs.get("filed") if isinstance(cs, dict) else fields.get("charge_sheet_filed")
    fir = fields.get("fir") if isinstance(fields.get("fir"), dict) else {}
    sections = fields.get("sections")
    return {
        "arrest_date": _iso(fields.get("arrest_date")), "first_remand": _iso(fields.get("first_remand")),
        "charge_sheet_filed": filed if isinstance(filed, bool) else None,
        "sections": [str(s) for s in sections] if isinstance(sections, list) and sections else None,
        "fir_number": fir.get("number"), "fir_date": _iso(fir.get("date")),
    }


def _concordance(path: Path) -> tuple[dict[str, str], str]:
    """IPC section -> BNS section for the fixed list, from the concordance file when it holds them, and the source name."""
    if path.exists():
        edges: dict[str, list[str]] = {}
        for row in rows_from_file(path):
            old, new = str(row.get("old_ref", "")), str(row.get("new_ref", ""))
            if old.startswith("IPC ") and new.startswith("BNS "):
                edges.setdefault(old[4:], []).append(new[4:])
        table = {k: v[0] for k, v in edges.items() if len(v) == 1 and k in IPC_TO_BNS}
        if len(table) >= 10:
            return {k: table[k] for k in IPC_TO_BNS if k in table}, f"{path} ({len(table)} of {len(IPC_TO_BNS)} sections found with one target)"
    return dict(IPC_TO_BNS), "built-in table (concordance file not found or too small)"


def build_t6(t1_dir: str, t2_dir: str, out_dir: str) -> TestSetManifest:
    """Template questions with answers from G3, the timeline and the concordance.

    Args:
        t1_dir: see behaviour
        t2_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    from vakeel_sahayak.config import load_config

    rng = random.Random(SEED)
    t1_pool: list[dict[str, Any]] = []
    for c in sorted(load_t1_cases(t1_dir), key=lambda c: c["case_id"]):
        t1_pool.append({"source": "T1", "case_id": c["case_id"], "bundle_id": None, "f": _norm(g3_fields(c)), "date": c.get("date")})
    t2_path = Path(t2_dir) / "truth.jsonl"
    t2_rows = rows_from_file(t2_path) if t2_path.exists() else []
    by_case: dict[str, list[dict[str, Any]]] = {}
    for t in t2_rows:
        by_case.setdefault(t["case_id"], []).append(t)
    t2_pool: list[dict[str, Any]] = []
    for case_id in sorted(by_case):  # one bundle per case (a case is rendered in several kinds with the same values)
        t = rng.choice(sorted(by_case[case_id], key=lambda r: r["bundle_id"]))
        t2_pool.append({"source": "T2", "case_id": case_id, "bundle_id": t["bundle_id"], "f": _norm(t.get("fields") or {}), "date": None})
    rng.shuffle(t1_pool)
    rng.shuffle(t2_pool)
    pool = [p for pair in zip_longest(t1_pool, t2_pool) for p in pair if p is not None]  # alternate the two sets
    concordance, conc_source = _concordance(Path(load_config().paths.interim_dir) / "concordance_edges.jsonl")
    sections = ["420"] + sorted(k for k in concordance if k != "420")  # IPC 420 first: the plan's own example

    def custody(p: dict[str, Any]) -> tuple[str, str] | None:
        arrest = p["f"]["arrest_date"]
        if not arrest:
            return None
        a = date.fromisoformat(arrest)
        as_of = date.fromisoformat(p["date"]) if p["source"] == "T1" and p["date"] else a + timedelta(days=30 + (abs(hash_int(p["case_id"])) % 360))
        days = (as_of - a).days
        return (as_of.isoformat(), f"{days} days") if 0 <= days <= 3000 else None

    cands: dict[str, list[dict[str, Any]]] = {k: [] for k in QUOTAS}

    def add(kind: str, p: dict[str, Any], question: str, answer: str | None, source: str | None, tools: list[str], qkind: str, route: list[str]) -> None:
        cands[kind].append({"source": p["source"], "case_id": p["case_id"], "bundle_id": p["bundle_id"], "question": question,
                            "expected_answer": answer, "answer_source": source, "expected_tools": tools, "kind": qkind, "route": route})

    for i, p in enumerate(pool):
        f = p["f"]
        if f["arrest_date"]:
            add("g3_arrest", p, "On what date was the accused in this case arrested?", _both(f["arrest_date"]), "G3", ["get_fact"], "fact", ["case.dossier"])
        if f["sections"]:
            add("g3_sections", p, "Under which sections is the accused charged in this case?", "; ".join(f["sections"]), "G3", ["get_fact"], "fact", ["case.dossier"])
        if f["charge_sheet_filed"] is not None:
            add("g3_charge_sheet", p, "Has a charge sheet been filed in this case?", "Yes" if f["charge_sheet_filed"] else "No", "G3", ["get_fact"], "fact", ["case.dossier"])
        if f["fir_number"]:
            add("g3_fir_number", p, "What is the FIR number in this case?", str(f["fir_number"]), "G3", ["get_fact"], "fact", ["case.dossier"])
        if f["first_remand"]:
            add("g3_first_remand", p, "On what date was the accused first remanded to custody?", _both(f["first_remand"]), "G3", ["get_fact"], "fact", ["case.dossier"])
            add("tl_first_remand", p, "Which date does the timeline give for the first remand order?", _both(f["first_remand"]), "timeline", ["get_timeline"], "fact", ["case.timeline"])
        if f["fir_date"]:
            add("tl_fir_date", p, "Which date does the timeline give for the FIR?", _both(f["fir_date"]), "timeline", ["get_timeline"], "fact", ["case.timeline"])
        cu = custody(p)
        if cu:
            as_of, ans = cu
            add("tl_custody", p, f"How long, in days, had the accused been held since arrest as on {_dmy(as_of)}?", ans, "timeline", ["get_timeline", "date_calc"], "fact",
                ["case.timeline", "date_calc"])
            add("rt_custody", p, f"How many days in custody as on {_dmy(as_of)}?", ans, "timeline", ["get_timeline", "date_calc"], "routing", ["case.timeline", "date_calc"])
        ipc = sections[i % len(sections)]
        add("concordance", p, f"What is the BNS section for IPC {ipc} under the concordance?", f"BNS {concordance[ipc]}", "concordance", ["map_section"], "fact", ["law.concordance"])
        add("rt_bns", p, f"What is the BNS equivalent of IPC {sections[(i * 7 + 3) % len(sections)]}?", f"BNS {concordance[sections[(i * 7 + 3) % len(sections)]]}",
            "concordance", ["map_section"], "routing", ["law.concordance"])
        add("rt_s479", p, "Is my client eligible under s.479?", None, None, ["rights_check"], "routing", ["rights_radar"])
        add("rt_parity", p, f"Any Supreme Court case on parity in a {OFFENCES[i % len(OFFENCES)]} case?", None, None, ["search_reasoning", "citations"], "routing",
            ["caselaw.reasoning", "caselaw.citations"])
        add("rt_state", p, f"How does the State oppose bail in {OFFENCES[(i * 3 + 1) % len(OFFENCES)]} cases?", None, None, ["search_objections", "get_statute"], "routing",
            ["advocacy.objections", "law.statutes"])
        add("rt_docs", p, f"What did the {COURTS[i % len(COURTS)]} say about antecedents in this case?", None, None, ["search_case_docs"], "routing", ["case.docs"])

    for kind in QUOTAS:  # each template draws its own mix: T1 and T2 candidates alternate, each in its own seeded order
        by_set = {src: [q for q in cands[kind] if q["source"] == src] for src in ("T1", "T2")}
        for lst in by_set.values():
            rng.shuffle(lst)
        cands[kind] = [q for pair in zip_longest(by_set["T1"], by_set["T2"]) for q in pair if q is not None]
    chosen: list[tuple[str, dict[str, Any]]] = []
    used: set[tuple[str, str]] = set()
    short: dict[str, int] = {}
    for kind, quota in QUOTAS.items():
        taken = 0
        for q in cands[kind]:
            key = (q["case_id"], q["question"])
            if key in used or taken >= quota:
                continue
            used.add(key)
            chosen.append((kind, q))
            taken += 1
        if taken < quota:
            short[kind] = quota - taken
    # top up (one question per template in turn) so the size stays about 150 when a template runs short
    spare = {k: [q for q in cands[k] if (q["case_id"], q["question"]) not in used] for k in QUOTAS}
    cycle = ["g3_arrest", "g3_sections", "g3_charge_sheet", "tl_custody", "rt_custody", "rt_s479", "rt_parity", "rt_state", "rt_docs", "concordance", "rt_bns"]
    while len(chosen) < TARGET and any(spare[k] for k in cycle):
        for kind in cycle:
            while spare[kind] and (spare[kind][0]["case_id"], spare[kind][0]["question"]) in used:
                spare[kind].pop(0)
            if spare[kind] and len(chosen) < TARGET:
                q = spare[kind].pop(0)
                used.add((q["case_id"], q["question"]))
                chosen.append((kind, q))
    order = list(QUOTAS)
    chosen.sort(key=lambda kq: (order.index(kq[0]), kq[1]["case_id"], kq[1]["question"]))
    rows = [{"qid": f"t6-{n:03d}", "template": kind, **q} for n, (kind, q) in enumerate(chosen)]
    out = Path(out_dir)
    rows_to_file(out / "questions.jsonl", rows)
    details = {
        "seed": SEED, "per_template": dict(Counter(r["template"] for r in rows)), "per_kind": dict(Counter(r["kind"] for r in rows)),
        "per_answer_source": dict(Counter(str(r["answer_source"]) for r in rows)), "per_source_set": dict(Counter(r["source"] for r in rows)),
        "distinct_cases": len({r["case_id"] for r in rows}), "concordance_source": conc_source, "t2_truth_rows": len(t2_rows),
        "templates_short_of_quota": short, "source_cases_sha256": sha256_file(Path(t1_dir) / "cases.jsonl"), "blind_slice_used": False,
        "not_built": ([] if t2_rows else ["T2 questions: no truth.jsonl in the T2 directory"]) + [f"{k}: {n} short of its quota" for k, n in short.items()],
    }
    manifest = TestSetManifest(set_id="T6", size=len(rows), answers_from="G3 values, the timeline and the IPC-to-BNS concordance, by construction",
                               used_for=["tool calling (T6 chat routing)"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def hash_int(text: str) -> int:
    """A stable integer from text (Python's `hash` is salted per process)."""
    import hashlib

    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    base = Path(load_config().paths.testsets_dir)
    ap = argparse.ArgumentParser(description="Build T6 (chat questions)")
    ap.add_argument("--t1", default=str(base / "t1"))
    ap.add_argument("--t2", default=str(base / "t2"))
    ap.add_argument("--out", default=str(base / "t6"))
    args = ap.parse_args(argv)
    m = build_t6(args.t1, args.t2, args.out)
    print(json.dumps({"size": m.size, **{k: m.details[k] for k in ("per_template", "per_source_set", "distinct_cases", "concordance_source", "not_built")}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
