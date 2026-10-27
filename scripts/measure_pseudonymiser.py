"""Measure the outbound pseudonymisation on the public T1 orders (a proxy: no hand labels, nothing invented).

For every order of data/testsets/t1/{dev,cases}.jsonl (read only) it builds the text a hosted model would receive, the same way as
`eval.runners.driver.file_facts` plus the hosted client: caption names learned, the intake's `pseudonymise_text`, then (new code only)
`privacy.quasi.WireCodec`. The "before" side is the pseudonymiser and boundary of an earlier commit (`--baseline-ref`, read with `git show`).

What is counted, with checks that are independent of the detectors under test wherever possible:
* surviving identifiers per category: values found in the RAW order by separate regexes (the FIR and police-station regexes of
  `pipelines.leakage`, simple label regexes for the rest, the name proxy of docs/handoff/pilot-hosted-model.md) and the order's own
  structured fields (the gold G3 event dates and their spans as written), each counted as surviving when the same string is still in the sent text;
* false masking on legal content: section references, act names and court phrases of the raw order that are no longer in the sent text;
* boundary refusals: the old default check, the new wire check on the old output, the new wire check on the new output;
* the round trip: `decode(encode(text)) == text`, and every shifted date moved by exactly the case's shift.

Usage: .venv/bin/python scripts/measure_pseudonymiser.py --baseline-ref 87905b6 [--out PATH]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import types
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from vakeel_sahayak.eval.runners.driver import learn_caption_names  # noqa: E402
from vakeel_sahayak.pipelines.leakage import _FIR_NO, _POLICE_STATION  # noqa: E402
from vakeel_sahayak.privacy import boundary as new_boundary  # noqa: E402
from vakeel_sahayak.privacy import quasi  # noqa: E402
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap, pseudonymise_text  # noqa: E402

_CAPTION_WORDS = set("aged age years resident petitioner respondent applicant accused state late shri smt district police station village the of and for".split())


def load_old(ref: str) -> tuple[types.ModuleType, types.ModuleType]:
    """The pseudonymise and boundary modules as they were at `ref`."""
    def src(path: str) -> str:
        return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=REPO, check=True, capture_output=True, text=True).stdout

    old_p = types.ModuleType("old_pseudonymise")
    sys.modules["old_pseudonymise"] = old_p
    exec(compile(src("src/vakeel_sahayak/privacy/pseudonymise.py"), "old_pseudonymise", "exec"), old_p.__dict__)  # noqa: S102
    b_src = src("src/vakeel_sahayak/privacy/boundary.py").replace("from vakeel_sahayak.privacy.pseudonymise import", "from old_pseudonymise import")
    old_b = types.ModuleType("old_boundary")
    sys.modules["old_boundary"] = old_b
    exec(compile(b_src, "old_boundary", "exec"), old_b.__dict__)  # noqa: S102
    return old_p, old_b


# ------------------------------------------------------------------------------------------------ independent checks on the raw order
_CHECKS: dict[str, re.Pattern[str]] = {
    "fir_number": _FIR_NO,
    "case_or_crime_number": re.compile(r"(?i)\b(?:crime|case|cr\.?\s*m\.?\s*p\.?|b\.?\s?a\.?|bail\s+appl(?:ication)?\.?|crl\.?\s*m\.?\s*[cp]\.?|m\.?\s*cr\.?\s*c\.?|crl\.?\s*a\.?)\s*no\.?\s*\d+\s*(?:/|of)\s*\d{4}"),
    "village_or_locality": re.compile(r"\b(?i:village|vill\.?|mohalla|gram|tola|basti|colony)\b[\s.:,-]*(?!(?i:no|in|and|of|to|were|residing)\b)[A-Z][A-Za-z]+"),
    "address_after_r/o": re.compile(r"\bR/[oO]\b[\s.:,-]*(?!(?i:village|vill|mohalla|at present))[A-Z][A-Za-z]+"),
    "house_number": re.compile(r"(?i)\b(?:h\.?\s?no|house\s+no|flat\s+no|plot\s+no|d\.\s?no|door\s+no|khasra\s+no|ward\s+no)\.?\s*[:.-]?\s*[\w/-]*\d"),
    "pin_code": re.compile(r"(?i)\bpin(?:\s*code)?\s*[:.\-–]?\s*[1-9]\d{2}\s?\d{3}\b|(?<=[A-Za-z])-\s?[1-9]\d{5}\b"),
    "vehicle_number": re.compile(r"\b[A-Z]{2}[ -]?\d{1,2}[ -]?[A-Z]{1,3}[ -]?\d{4}\b"),
    "account_ifsc_upi": re.compile(r"(?i)\b(?:a/c|account)\s*(?:no|number)?\.?\s*[:.-]?\s*\d{9,18}\b|\b[A-Z]{4}0[A-Z0-9]{6}\b|\b[\w.-]+@(?:ok\w+|ybl|paytm|upi|ibl|axl)\b"),
    "id_numbers": re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b|\b[A-Z]{5}\d{4}[A-Z]\b|\b[A-Z]{3}\d{7}\b|(?i:passport|driving\s+licen[cs]e|voter)\s*(?:id\s*)?(?:no|number)\.?\s*[:.-]?\s*[A-Z0-9]{6,}"),
    "email_or_phone": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+|(?<!\d)[6-9]\d{9}(?!\d)"),
    "age": re.compile(r"(?i)\baged?\W{0,3}(?:about\W{0,3})?\d{1,3}"),
    "date_of_birth": re.compile(r"(?i)\b(?:d\.?\s?o\.?\s?b\.?|date\s+of\s+birth)\W{0,4}\d"),
    "numeric_date": re.compile(r"(?<![\d./-])\d{1,2}[./-]\d{1,2}[./-](?:19|20)\d{2}(?![\d/-])"),
}
_LEGAL: dict[str, re.Pattern[str]] = {
    "section_reference": re.compile(r"(?i)\b(?:sections?|secs?\.?|u/s\.?|under\s+section)\s*\d+[A-Z]?(?:\s*\(\s*\w+\s*\))*(?:\s*(?:/|,|and|&)\s*\d+[A-Z]?(?:\s*\(\s*\w+\s*\))*)*"),
    "act_name": re.compile(r"\b(?:IPC|BNSS?|Cr\.?\s?P\.?\s?C\.?|NDPS|PMLA|UAPA|Indian\s+Penal\s+Code|Bharatiya\s+Nyaya\s+Sanhita|Bharatiya\s+Nagarik\s+Suraksha\s+Sanhita|Code\s+of\s+Criminal\s+Procedure|Arms\s+Act|Excise\s+Act|Prevention\s+of\s+Corruption\s+Act|Information\s+Technology\s+Act|Gangsters?\s+Act|Dowry\s+Prohibition\s+Act)\b"),
    "court_phrase": re.compile(r"(?i)\b(?:high\s+court(?:\s+of\s+(?:judicature\s+(?:at|for)\s+)?[A-Za-z]+)?|supreme\s+court(?:\s+of\s+india)?|sessions\s+court|court\s+of\s+(?:the\s+)?(?:sessions|special)\s+judge)"),
}


def _police_names(raw: str) -> list[str]:
    out = []
    for m in _POLICE_STATION.finditer(raw):
        name = " ".join(m.group(1).split())
        if name and not re.match(r"(?i)(?:case|no|crime|under|the|concerned|district)\b", name):
            out.append(m.group(0))
    return out


def _name_proxy(raw: str) -> set[str]:
    """Party-name tokens by the proxy of pilot-hosted-model.md: words before W/o S/o D/o and after the markers, minus caption words."""
    toks: set[str] = set()
    for m in re.finditer(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s*,?\s*(?:S/o|W/o|D/o|S/O|W/O|D/O)\b", raw):
        toks.update(t for t in m.group(1).split() if len(t) >= 4 and t.lower() not in _CAPTION_WORDS)
    for m in re.finditer(r"(?:S/o|W/o|D/o|S/O|W/O|D/O)\.?\s*(?:Late\s+|LATE\s+|Shri\s+|SHRI\s+|Sri\s+)?([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,2})", raw):
        toks.update(t for t in m.group(1).split() if len(t) >= 4 and t.lower() not in _CAPTION_WORDS)
    return toks


def _gold_dates(row: dict) -> list[str]:
    """Dates as written in the order, from its own structured gold (G3 event spans)."""
    spans = ((row.get("gold") or {}).get("G3") or {}).get("llm_spans") or {}
    return [quasi.DATE_RE.search(v).group(0) for k, v in spans.items() if k.startswith("event=") and isinstance(v, str) and quasi.DATE_RE.search(v)]


def _left(toks: set[str], text: str) -> int:
    """How many proxy name tokens are still whole words of `text`."""
    return sum(1 for t in toks if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", text))


def _surviving(strings: list[str], sent: str, made: set[str] | frozenset[str] = frozenset()) -> int:
    """How many of `strings` are still in `sent` (multiset); a string the date shift itself produced (`made`) is a coincidence, not a survivor."""
    counts = Counter(strings)
    return sum(min(n, sent.count(s)) for s, n in counts.items() if s not in made)


def measure(rows: list[dict], old_p: types.ModuleType, old_b: types.ModuleType) -> dict:
    report: dict = {"orders": len(rows), "identifiers": {}, "legal": {}, "boundary": {}, "round_trip": {}}
    ident = {k: Counter() for k in [*_CHECKS, "police_station", "party_name_tokens", "gold_dates_as_written"]}
    legal = {k: Counter() for k in _LEGAL}
    refusals = Counter()
    reasons = Counter()
    trip_bad, shift_bad, shifted_dates = 0, 0, 0
    refused_ids: list[str] = []
    for row in rows:
        raw = str(row.get("facts_text") or row.get("facts") or "")
        cid = row["case_id"]
        old_map = old_p.PseudonymMap()
        learn_caption_names(raw, old_map)
        old_p.pseudonymise_text(raw, cid, old_map)
        old_out, _ = old_p.pseudonymise_text(raw, cid, old_map)
        new_map = PseudonymMap()
        new_map.ensure_date_shift(cid)
        learn_caption_names(raw, new_map)
        pseudonymise_text(raw, cid, new_map)
        local, _ = pseudonymise_text(raw, cid, new_map)
        codec = quasi.WireCodec(new_map, new_map.date_shift_days)
        sent = codec.encode_text(local)
        trip_bad += codec.decode_text(sent) != local
        for shifted, orig in codec.dates.items():
            a, b = quasi.DATE_RE.fullmatch(shifted), quasi.DATE_RE.fullmatch(orig)
            if a and b:
                shifted_dates += 1
                pa, pb = quasi._parts(a), quasi._parts(b)  # noqa: SLF001
                if dt.date(pa[3], pa[2], pa[1]) - dt.date(pb[3], pb[2], pb[1]) != dt.timedelta(days=new_map.date_shift_days):
                    shift_bad += 1
        made = set(codec.dates)
        for name, pat in _CHECKS.items():
            found = [m.group(0) for m in pat.finditer(raw)]
            ident[name].update(raw=len(found), before=_surviving(found, old_out), after=_surviving(found, sent, made if name == "numeric_date" else frozenset()))
        ps = _police_names(raw)
        ident["police_station"].update(raw=len(ps), before=_surviving(ps, old_out), after=_surviving(ps, sent))
        toks = _name_proxy(raw)
        ident["party_name_tokens"].update(raw=len(toks), before=_left(toks, old_out), after=_left(toks, sent))
        gd = [d for d in _gold_dates(row) if d in raw]  # the T1 facts text is an excerpt: only gold dates that it contains
        ident["gold_dates_as_written"].update(raw=len(gd), before=_surviving(gd, old_out), after=_surviving(gd, sent, made))
        for name, pat in _LEGAL.items():
            found = [m.group(0) for m in pat.finditer(raw)]
            legal[name].update(raw=len(found), before=_surviving(found, old_out), after=_surviving(found, sent))
        try:
            old_b.assert_pseudonymised({"facts": old_out}, mapping=old_map)
        except ValueError:
            refusals["old_default_check_on_old_output"] += 1
        try:
            new_boundary.assert_pseudonymised({"facts": old_out}, mapping=old_map, wire=True)
        except ValueError:
            refusals["new_wire_check_on_old_output"] += 1
        try:
            new_boundary.assert_pseudonymised({"facts": sent}, mapping=new_map, wire=True)
        except ValueError as exc:
            refusals["new_wire_check_on_new_output"] += 1
            refused_ids.append(cid)
            for r in re.findall(r"facts: ([^;]+)", str(exc)):
                reasons[r.strip()] += 1
    report["identifiers"] = {k: dict(v) for k, v in ident.items()}
    report["legal"] = {k: {**dict(v), "false_masking_rate_before": round(1 - v["before"] / v["raw"], 4) if v["raw"] else None,
                           "false_masking_rate_after": round(1 - v["after"] / v["raw"], 4) if v["raw"] else None} for k, v in legal.items()}
    report["boundary"] = {**dict(refusals), "new_refusal_reasons": dict(reasons), "new_refused_ids": refused_ids}
    report["round_trip"] = {"decode_mismatch_orders": trip_bad, "shifted_dates": shifted_dates, "shift_not_exact": shift_bad}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--baseline-ref", required=True, help="commit whose pseudonymiser and boundary are the 'before' side")
    ap.add_argument("--t1", default=str(REPO / "data" / "testsets" / "t1"))
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    rows = [json.loads(line) for name in ("dev", "cases") for line in (Path(args.t1) / f"{name}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    old_p, old_b = load_old(args.baseline_ref)
    report = measure(rows, old_p, old_b)
    text = json.dumps(report, indent=1)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
