#!/usr/bin/env python3
"""Record the evaluator demo: drive each synthetic case (`vakeel_sahayak.demo.cases`) through a RUNNING API end to end, then snapshot it.

The calls are the web interface's (frontend/lib/api.ts): create the case, record counsel's consent for the hosted provider (the case is
synthetic), upload the PDFs (intake: Munshi reads, Peshkar builds the dossier, the List of Dates and the Rights Radar), answer intake's
questions with the case's scripted answers (PATCH the dossier field, POST the answer), approve Gate 1 as scripted counsel, read the
Rights Radar, draft (Sutradhar plans, Vakeel drafts, Abhiyojak spars, Vakeel writes the hearing card) and read every tab. Gate 2 is
LEFT OPEN: the evaluator approves it in the tour.

Per case it writes `demo/cases/<slug>/case/` (a copy of `<data>/cases/<case_id>/`), `demo/cases/<slug>/events.jsonl` (the case's rows of
`<data>/record.sqlite`) and `demo/cases/<slug>/tour.json` (captions from this run's numbers), plus the raw API answers in
`<work>/<slug>/raw.json` (not committed; `tour` rebuilds the tours from them).

    record_demos.py run --api http://127.0.0.1:8020 --data-dir <the API's VS_DATA_DIR> [--cases 01-cheating-parity,...] [--reset]
    record_demos.py tour --data-dir <dir>       # rebuild tour.json from <work>/<slug>/raw.json
    record_demos.py check                       # secrets and machine paths grep, and the size of demo/

The API must run with the same VS_DATA_DIR (the snapshot is read from it) and `VS_DEMO_CASES=off`. See docs/handoff/evaluator-demo.md.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from vakeel_sahayak.demo.cases import BY_SLUG, CASES, GATE_1_NOTE, DemoCase, write_documents  # noqa: E402

DEMO = ROOT / "demo"
WORK = Path(tempfile.gettempdir()) / "vs-demo-work"
CONSENT_NOTE = "counsel's consent for the synthetic evaluator-demo case (no real client)"
SKIP_SNAPSHOT = {".lock"}


class RecordError(RuntimeError):
    """The run of one case could not complete; the message says where."""


# ---------------------------------------------------------------------------------------------------------------- driving the API

def _get(api: httpx.Client, path: str, missing_ok: bool = False) -> Any:
    res = api.get(path)
    if missing_ok and res.status_code == 404:
        return None
    if res.status_code >= 400:
        raise RecordError(f"GET {path}: {res.status_code} {res.text[:300]}")
    return res.json()


def _send(api: httpx.Client, method: str, path: str, **kw: Any) -> Any:
    res = api.request(method, path, **kw)
    if res.status_code >= 400:
        raise RecordError(f"{method} {path}: {res.status_code} {res.text[:300]}")
    return res.json() if res.content else None


def drive(api: httpx.Client, case: DemoCase, reset: bool, tmp: Path) -> dict[str, Any]:
    """Run one case end to end through the API; returns every answer the run produced (the raw record of the run)."""
    raw: dict[str, Any] = {"slug": case.slug, "case_id": case.case_id, "timings": {}}
    t0 = time.time()
    raw["health"] = _get(api, "/healthz")
    present = {c["case_id"] for c in _get(api, "/api/cases")}
    if case.case_id in present:
        if not reset:
            raise RecordError(f"{case.case_id} already exists in the API's data directory (use --reset)")
        _send(api, "DELETE", f"/api/cases/{case.case_id}")
    _send(api, "POST", "/api/cases", json={"title": case.title, "case_id": case.case_id})
    backend = (raw["health"].get("llm_backend") or "").lower()
    if backend in ("sarvam", "openai"):
        raw["consent"] = _send(api, "POST", f"/api/cases/{case.case_id}/consent", json={"provider": backend, "granted": True, "note": CONSENT_NOTE})

    # Intake: all papers in one upload, as counsel drops the folder (Munshi, then Peshkar).
    paths = write_documents(case, tmp / case.slug)
    handles = [open(p, "rb") for p in paths]
    try:
        t = time.time()
        raw["upload"] = _send(api, "POST", f"/api/cases/{case.case_id}/upload",
                              files=[("files", (p.name, h, "application/pdf")) for p, h in zip(paths, handles, strict=True)])
        raw["timings"]["intake_s"] = round(time.time() - t, 1)
    finally:
        for h in handles:
            h.close()
    raw["uploaded"] = [{"name": p.name, "kind": d.kind} for p, d in zip(paths, case.documents, strict=True)]
    raw["ingestion"] = _get(api, f"/api/cases/{case.case_id}/ingestion", missing_ok=True)
    if raw["ingestion"] is None:
        raise RecordError("intake produced no ingestion report (see the API log)")
    raw["dossier_before"] = _get(api, f"/api/cases/{case.case_id}/dossier")

    # Counsel answers intake's questions (and adds what the case's instructions say), as in the dossier tab.
    questions = list(dict.fromkeys([*raw["upload"].get("questions", []), *raw["dossier_before"].get("open_questions", [])]))
    raw["answers"] = []
    for q in questions:
        scripted = case.answer_for(q)
        if scripted is None:
            raise RecordError(f"no scripted answer matches the question {q!r}: add a pattern to {case.slug} in vakeel_sahayak/demo/cases.py")
        entry = {"question": q, "answer": scripted.answer, "field": scripted.field}
        if scripted.field is not None:
            _send(api, "PATCH", f"/api/cases/{case.case_id}/dossier/{scripted.field}", json={"value": scripted.value})
        _send(api, "POST", f"/api/cases/{case.case_id}/gates/answers", json={"question": q, "answer": scripted.answer})
        raw["answers"].append(entry)
    raw["edits"] = []
    for field, value, said in case.counsel_edits:
        _send(api, "PATCH", f"/api/cases/{case.case_id}/dossier/{field}", json={"value": value})
        raw["edits"].append({"field": field, "said": said})
    raw["dossier"] = _get(api, f"/api/cases/{case.case_id}/dossier")
    raw["dates"] = _get(api, f"/api/cases/{case.case_id}/dates")

    # Gate 1: counsel acknowledges what the papers do not support and approves.
    gate1 = _get(api, f"/api/cases/{case.case_id}/gates/GATE_1_DOSSIER")
    raw["gate1_before"] = gate1
    raw["gate1"] = _send(api, "POST", f"/api/cases/{case.case_id}/gates/GATE_1_DOSSIER/approve",
                         json={"acknowledged_fields": list(gate1.get("unresolved_unsupported", []))})
    raw["gate1_note"] = GATE_1_NOTE
    raw["rights"] = _get(api, f"/api/cases/{case.case_id}/rights", missing_ok=True)

    # Drafting: Sutradhar, Vakeel, Abhiyojak; then every tab, and the Gate 2 checklist (left open).
    t = time.time()
    raw["draft"] = _send(api, "POST", f"/api/cases/{case.case_id}/draft")
    raw["timings"]["draft_s"] = round(time.time() - t, 1)
    raw["brief"] = _get(api, f"/api/cases/{case.case_id}/brief", missing_ok=True)
    raw["spar"] = _get(api, f"/api/cases/{case.case_id}/spar", missing_ok=True)
    raw["prep"] = _get(api, f"/api/cases/{case.case_id}/prep", missing_ok=True)
    raw["budget"] = _get(api, f"/api/cases/{case.case_id}/budget")
    raw["gate2"] = _get(api, f"/api/cases/{case.case_id}/gates/GATE_2_EXPORT")
    raw["summary"] = _get(api, f"/api/cases/{case.case_id}")
    raw["export_before_gate2"] = api.post(f"/api/cases/{case.case_id}/export", json={"format": "DOCX"}).status_code
    if raw["brief"] is None:
        raise RecordError("drafting produced no brief")
    raw["timings"]["total_s"] = round(time.time() - t0, 1)
    raw["date"] = date.today().isoformat()
    return raw


# ---------------------------------------------------------------------------------------------------------------- record and spend

def case_events(data_dir: Path, case_id: str) -> list[str]:
    """The case's rows of the shared record, as stored (one JSON body per event), in order."""
    con = sqlite3.connect(f"file:{data_dir / 'record.sqlite'}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute("SELECT body FROM events WHERE case_id = ? ORDER BY seq", (case_id,))]
    finally:
        con.close()


def event_stats(bodies: list[str]) -> dict[str, Any]:
    """Counts the tour quotes from the record: tool calls by agent and tool, store reads, hosted-model calls, errors."""
    stats: dict[str, Any] = {"events": len(bodies), "tool_calls": {}, "store_calls": 0, "llm_calls": 0, "hosted_calls": 0, "errors": 0,
                             "fallbacks": 0, "by_agent": {}}
    for body in bodies:
        ev = json.loads(body)
        kind, actor, tool = ev.get("kind"), str(ev.get("actor")), ev.get("tool") or ""
        stats["by_agent"][actor] = stats["by_agent"].get(actor, 0) + 1
        if kind == "TOOL_CALL":
            stats["tool_calls"][tool] = stats["tool_calls"].get(tool, 0) + 1
            if tool.startswith(("search_", "get_", "lookup_", "find_")) or "store" in (ev.get("inputs") or {}):
                stats["store_calls"] += 1
        if kind == "ERROR":
            stats["errors"] += 1
        text = json.dumps(ev.get("outputs") or {})[:4000]
        if actor in ("sarvam", "openai"):
            stats["hosted_calls"] += 1
        if "fallback" in text.lower():
            stats["fallbacks"] += 1
    return stats


def run_window(bodies: list[str]) -> tuple[str, str] | None:
    """First and last event time of the case (UTC, second precision): the window in which the run made its hosted calls."""
    times = sorted(json.loads(b)["ts"][:19] for b in bodies if json.loads(b).get("ts"))
    return (times[0], times[-1] + "~") if times else None


def spend(data_dir: Path, case_id: str, window: tuple[str, str] | None = None) -> dict[str, Any]:
    """Sarvam spend of the case from the run's ledger (`<data>/sarvam/ledger.sqlite`): INR, calls and tokens, and the chat model used.

    Calls the ledger files under the case id count, and so do calls without a case id (translation of a Hindi quote, for example)
    made inside the case's run window: the recorder runs one case at a time, so they belong to it.
    """
    path = data_dir / "sarvam" / "ledger.sqlite"
    out: dict[str, Any] = {"inr": 0.0, "calls": 0, "input_tokens": 0, "output_tokens": 0, "models": []}
    if not path.is_file():
        return out
    lo, hi = window or ("~", "~")
    where = "(case_id = ? OR (case_id IS NULL AND substr(ts, 1, 19) >= ? AND substr(ts, 1, 19) <= ?))"
    args = (case_id, lo, hi)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        counted = "CASE status WHEN 'settled' THEN cost_micro WHEN 'reserved' THEN reserved_micro WHEN 'unknown' THEN reserved_micro ELSE 0 END"
        row = con.execute(f"SELECT COALESCE(SUM({counted}),0), COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
                          f"FROM calls WHERE {where} AND status != 'cache'", args).fetchone()
        out.update(inr=round(row[0] / 1e6, 4), calls=row[1], input_tokens=row[2], output_tokens=row[3])
        out["models"] = [r[0] for r in con.execute(f"SELECT DISTINCT model FROM calls WHERE {where} AND kind = 'chat'", args)]
        out["by_kind"] = {k: {"calls": n, "inr": round(c / 1e6, 4)} for k, n, c in con.execute(
            f"SELECT kind, COUNT(*), COALESCE(SUM({counted}),0) FROM calls WHERE {where} AND status != 'cache' GROUP BY kind", args)}
    finally:
        con.close()
    return out


# ---------------------------------------------------------------------------------------------------------------- snapshot

def snapshot(data_dir: Path, case: DemoCase, bodies: list[str], out: Path) -> Path:
    """Copy `<data>/cases/<case_id>/` into `<out>/cases/<slug>/case/` (SQLite files through the backup API) and write events.jsonl."""
    src = data_dir / "cases" / case.case_id
    folder = out / "cases" / case.slug
    target = folder / "case"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if path.is_dir() or path.name in SKIP_SNAPSHOT or path.name.endswith(("-wal", "-shm", "-journal")):
            continue
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix in (".sqlite", ".db"):
            s, d = sqlite3.connect(f"file:{path}?mode=ro", uri=True), sqlite3.connect(dest)
            try:
                s.backup(d)
            finally:
                s.close()
                d.close()
        else:
            shutil.copy2(path, dest)
    (folder / "events.jsonl").write_text("".join(b + "\n" for b in bodies), encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------------------------------------------- tour

def _n(k: int, word: str, plural: str | None = None) -> str:
    return f"{k} {word if k == 1 else (plural or word + 's')}"


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1] if items else ""


def _value_text(value: Any) -> str:
    if value is None:
        return "not on record"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {v}" for k, v in value.items() if v not in (None, ""))
    if isinstance(value, list):
        if not value:
            return "none"
        return "; ".join(_value_text(v) if not isinstance(v, str) else v for v in value)
    return str(value)


FIELD_LABELS = {"fir": "FIR", "offence_date": "Date of offence", "sections": "Sections", "arrest_date": "Date of arrest",
                "first_remand": "First remand", "custody_days": "Days in custody", "charge_sheet": "Charge sheet",
                "trial_stage": "Trial stage", "previous_bail": "Earlier bail orders", "co_accused_bail": "Co-accused bail",
                "antecedents": "Antecedents", "personal": "Personal circumstances", "parties": "Parties"}
CHECK_LABELS = {"default_bail": "Default bail", "undertrial_limit": "Undertrial limit (BNSS s.479)", "notice_of_appearance": "Notice of appearance",
                "grounds_of_arrest": "Grounds of arrest", "production_24h": "Production within 24 hours", "antil_category": "Antil category",
                "statutory_bar": "Statutory bar"}


def _sections_text(value: Any) -> str:
    if not value:
        return "not on record"
    out = []
    for s in value:
        bit = s.get("as_written") or f"{s.get('code')} {s.get('section')}"
        if s.get("equivalent"):
            bit += f" (= {s['equivalent']})"
        if s.get("max_punishment"):
            bit += f", maximum {s['max_punishment']}"
        out.append(bit)
    return "; ".join(out)


LANGS = {"en": "English", "hi": "Hindi"}
ROUTES = {"text_layer": "text layer", "ocr": "OCR", "vision": "vision model", "translate": "translation"}
DOC_TYPES = {"FIR": "FIR", "ARREST_MEMO": "arrest memo", "REMAND_ORDER": "remand order", "BAIL_ORDER": "bail order",
             "CHARGE_SHEET_COVER": "charge sheet", "ORDER_SHEET": "order sheet", "CUSTODY_CERTIFICATE": "custody certificate",
             "AFFIDAVIT": "affidavit", "MEDICAL": "medical report", "OTHER": "other"}
STATUS_WORDS = {"VERIFIED": "verified from the papers", "COMPUTED": "computed", "UNSUPPORTED": "not supported by the papers",
                "AMBIGUOUS": "ambiguous", "USER_STATED": "stated by counsel", "USER_EDITED": "set by counsel"}


def _route_name(route: list[str]) -> str:
    first = (route or ["?"])[0].split(":")[0].strip()
    return ROUTES.get(first, first.replace("_", " "))


def _clip(text: Any, n: int = 260) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def build_tour(case: DemoCase, raw: dict[str, Any]) -> dict[str, Any]:
    """The tour of one recorded run: nine steps whose captions state what each agent did in THIS run, with its numbers."""
    ing, dossier, rights = raw["ingestion"], raw["dossier"], raw.get("rights") or {"checks": []}
    brief, spar, prep = raw.get("brief") or {}, raw.get("spar") or {}, raw.get("prep") or {}
    cost = raw.get("spend", {})
    docs = ing.get("documents", [])
    routes: dict[str, int] = {}
    for d in docs:
        for pr in d.get("page_routes", []):
            name = _route_name(pr.get("route") or [])
            routes[name] = routes.get(name, 0) + 1
    langs = sorted({LANGS.get(d.get("lang"), d.get("lang")) for d in docs if d.get("lang")})
    types = sorted({DOC_TYPES.get(d.get("type", "OTHER"), str(d.get("type", "other")).replace("_", " ").lower()) for d in docs})
    unreadable = sum(1 for d in docs for pr in d.get("page_routes", []) if pr.get("status") not in (None, "OK"))
    filed = ing.get("filed", {})
    answers = raw.get("answers", [])
    fields = dossier.get("fields", {})
    status_count: dict[str, int] = {}
    for f in fields.values():
        status_count[f.get("status", "UNSUPPORTED")] = status_count.get(f.get("status", "UNSUPPORTED"), 0) + 1
    checks = rights.get("checks", [])
    grounds = brief.get("grounds", [])
    withheld = [w for w in brief.get("withheld", []) if w.get("sentences")]
    withheld_n = sum(len(w["sentences"]) for w in withheld)
    present = {g.get("id") for g in grounds}
    dropped = [w["ground"] for w in withheld if w.get("dropped") or w["ground"] not in present]
    objections = spar.get("objections", [])
    verdicts: dict[str, int] = {}
    for o in objections:
        key = str(o.get("verdict") or "pending").lower()
        verdicts[key] = verdicts.get(key, 0) + 1
    gate2 = raw.get("gate2", {})
    store_calls = raw.get("budget", {}).get("store_calls", {}) or {}
    store_total = sum(store_calls.values())
    factors = sorted(k for k in store_calls if k != "case")
    ack = raw.get("gate1_before", {}).get("unresolved_unsupported", [])
    steps: list[dict[str, Any]] = []

    route_text = _join([f"{k} for {_n(v, 'page')}" for k, v in sorted(routes.items())])
    steps.append({
        "stage": "INTAKE", "tab": "dossier", "title": "Munshi reads the papers", "agent": "MUNSHI", "action": None,
        "caption": (f"Counsel uploaded {_n(len(raw['uploaded']), 'PDF')} at once. Munshi read every page ({route_text or 'no page routes recorded'}), "
                    f"named {_n(len(docs), 'document')} ({_join(types)}) in {_join(langs) or 'English'}, and filed "
                    f"{_n(filed.get('timeline_events', 0), 'dated event')} and {_n(filed.get('sections', 0), 'charged section')}. "
                    + (f"{_n(unreadable, 'page')} could not be read and became a question. " if unreadable else "")
                    + (f"Intake put {_n(len(answers), 'question')} to counsel." if answers else "The papers answered every checklist item, so intake asked nothing.")),
        "filled": [{"label": f["name"], "value": {"text": "born-digital PDF", "hindi": "Hindi FIR with a Devanagari text layer",
                                                   "scan": "scanned page: an image with no text layer"}[f["kind"]]} for f in raw["uploaded"]],
    })
    from_papers = status_count.get("VERIFIED", 0) + status_count.get("COMPUTED", 0)
    from_counsel = status_count.get("USER_EDITED", 0) + status_count.get("USER_STATED", 0)
    key_fields = ("fir", "sections", "arrest_date", "first_remand", "custody_days", "charge_sheet", "previous_bail", "co_accused_bail", "antecedents")
    steps.append({
        "stage": "DOSSIER", "tab": "dossier", "title": "Peshkar builds the dossier", "agent": "PESHKAR", "action": None,
        "caption": (f"Peshkar filled the {_n(len(fields), 'field')} of the dossier: {from_papers} from the papers, each with the quoted sentence and page, "
                    f"{from_counsel} from counsel and {status_count.get('UNSUPPORTED', 0) + status_count.get('AMBIGUOUS', 0)} left open. "
                    + (f"Counsel answered {_n(len(answers), 'question')} from instructions; those fields are marked as counsel's, never as verified. " if answers else "")
                    + f"The List of Dates has {_n(len(raw.get('dates', [])), 'entry', 'entries')}, each tied to its page."),
        "filled": ([{"label": a["question"], "value": a["answer"]} for a in answers]
                   + [{"label": FIELD_LABELS.get(e["field"], e["field"]), "value": e["said"]} for e in raw.get("edits", [])]
                   + [{"label": FIELD_LABELS.get(k, k), "value": f"{_sections_text(fields[k].get('value')) if k == 'sections' else _value_text(fields[k].get('value'))} "
                                                                f"({STATUS_WORDS.get(fields[k].get('status'), str(fields[k].get('status')).lower())})"}
                      for k in key_fields if k in fields]),
    })
    steps.append({
        "stage": "GATE_1", "tab": "dossier", "title": "Gate 1: counsel approves the facts", "agent": None, "action": None,
        "caption": ("Nothing is drafted until counsel approves the dossier, and the code accepts that approval from counsel only. "
                    + (f"Counsel acknowledged {_n(len(ack), 'field')} the papers do not support ({_join([FIELD_LABELS.get(a, a) for a in ack])}) and approved."
                       if ack else "Every field had a source or counsel's answer, so counsel approved without acknowledging any gap.")),
        "filled": [{"label": "Gate 1 note", "value": raw.get("gate1_note", GATE_1_NOTE)}]
                  + [{"label": f"Acknowledged: {FIELD_LABELS.get(a, a)}", "value": "not supported by the papers; acknowledged by counsel"} for a in ack],
    })
    notable = [c for c in checks if c.get("status") not in ("NOT_APPLICABLE", "OK", "UNKNOWN")]
    steps.append({
        "stage": "RIGHTS", "tab": "rights", "title": "Rights Radar", "agent": "PESHKAR", "action": None,
        "caption": (f"At intake Peshkar ran the {_n(len(checks), 'rule')} of the Rights Radar on the dossier as of {rights.get('as_of', raw.get('date'))}: date "
                    f"arithmetic and statute tables, not the language model. "
                    + (_join([f"{CHECK_LABELS.get(c['check'], c['check'])}: {c['status']}" for c in notable]) + ". " if notable else "")
                    + "Each result names its rule and the dates it used; rules not yet re-checked against the bare act are marked unverified."),
        "filled": [{"label": CHECK_LABELS.get(c["check"], c["check"]), "value": f"{c.get('status')}: {c.get('detail', '')}"} for c in checks],
    })
    checks_of_grounds: dict[str, int] = {}
    for g in grounds:
        key = str(g.get("check", "")).lower().replace("_", " ")
        checks_of_grounds[key] = checks_of_grounds.get(key, 0) + 1
    steps.append({
        "stage": "BRIEF", "tab": "brief", "title": "Sutradhar plans, Vakeel drafts", "agent": "VAKEEL", "action": None,
        "caption": (f"Sutradhar planned the brief factor by factor ({_n(len(factors), 'factor')}) and fetched the evidence each needs: {_n(store_total, 'store call')}. "
                    f"Vakeel drafted {_n(len(grounds), 'ground')} ({_join([f'{v} {k}' for k, v in sorted(checks_of_grounds.items())])}). Every sentence was checked "
                    f"against its source; {_n(withheld_n, 'sentence')} the checker could not support {'were' if withheld_n != 1 else 'was'} withheld"
                    + (f", leaving {_n(len(dropped), 'ground')} for counsel to draft" if dropped else "") + "."
                    + (f" {_n(len(brief.get('open_issues', [])), 'open issue')} {'are' if len(brief.get('open_issues', [])) != 1 else 'is'} listed for counsel." if brief.get("open_issues") else "")),
        "filled": [{"label": f"{g.get('id')} · {str(g.get('factor', '')).replace('_', ' ')}", "value": f"{g.get('check')}: {_clip(g.get('argument'))}"} for g in grounds]
                  + [{"label": f"Withheld from {w['ground']}", "value": f"{_n(len(w['sentences']), 'sentence')}; reason: {_clip(w['sentences'][0].get('reason'), 120)}"}
                     for w in withheld],
    })
    steps.append({
        "stage": "SPAR", "tab": "spar", "title": "Abhiyojak argues the other side", "agent": "ABHIYOJAK", "action": None,
        "caption": (f"Abhiyojak, the prosecution sparring partner, raised {_n(len(objections), 'objection')} "
                    f"in {_n(spar.get('rounds', 0), 'round')}, each grounded in a prosecution argument from comparable orders or a fact of the case"
                    + (f"; {_n(len(spar.get('discarded', [])), 'ungrounded objection')} {'were' if len(spar.get('discarded', [])) != 1 else 'was'} discarded" if spar.get("discarded") else "")
                    + (f". After Vakeel's replies: {_join([f'{v} {k}' for k, v in sorted(verdicts.items())])}." if verdicts else ". There was nothing to reply to.")),
        "filled": [{"label": f"{o.get('id')} against {o.get('against')} ({str(o.get('factor', '')).replace('_', ' ')})",
                    "value": f"{o.get('verdict') or 'pending'}: {_clip(o.get('objection'))}"} for o in objections],
    })
    steps.append({
        "stage": "HEARING_PREP", "tab": "prep", "title": "Hearing card", "agent": "VAKEEL", "action": None,
        "caption": (f"Vakeel turned the brief and the sparring into a card for the hearing: {_n(len(prep.get('bench_concerns', [])), 'likely question')} from the bench "
                    f"with answers, {_n(len(prep.get('lead_with', [])), 'ground')} to lead with and {_n(len(prep.get('conditions', [])), 'bail condition')} counsel can offer. "
                    "It predicts nothing and gives no grant rate."),
        "filled": ([{"label": f"Lead with {p.get('ground')} ({str(p.get('factor', '')).replace('_', ' ')})", "value": _clip(p.get("point"))} for p in prep.get("lead_points", [])]
                   + [{"label": f"Bench may raise: {str(c.get('factor', '')).replace('_', ' ')}", "value": _clip(c.get("answer") or c.get("concern"))}
                      for c in prep.get("bench_concerns", [])]
                   + [{"label": "Condition counsel can offer", "value": str(x)} for x in prep.get("conditions", [])]),
    })
    unsupported, review, unanswered = (gate2.get("unresolved_unsupported", []), gate2.get("unresolved_needs_review", []), gate2.get("unresolved_unanswered", []))
    items = len(unsupported) + len(review) + len(unanswered)
    steps.append({
        "stage": "GATE_2", "tab": "brief", "title": "Gate 2: your approval", "agent": None, "action": "approve_gate_2",
        "caption": (f"Export is impossible until counsel approves Gate 2: in this run the export call before approval was refused ({raw.get('export_before_gate2')}). "
                    + (f"The checklist has {_n(items, 'item')} for counsel ({_join([s for s in (_n(len(unsupported), 'unsupported field') if unsupported else '', _n(len(review), 'ground') + ' to review' if review else '', _n(len(unanswered), 'unanswered objection') if unanswered else '') if s])}); "
                       "approving records that counsel has read them. " if items else "The checklist is clear. ")
                    + "Next approves Gate 2 as counsel."),
        "filled": [{"label": f, "value": f"{FIELD_LABELS.get(f, f)}: not supported by the papers; counsel acknowledges"} for f in unsupported]
                  + [{"label": f"NEEDS_REVIEW:{g}", "value": f"ground {g}: counsel has reviewed it"} for g in review]
                  + [{"label": f"UNANSWERED:{o}", "value": f"objection {o}: no supported reply; counsel has read it"} for o in unanswered],
    })
    steps.append({
        "stage": "FILE", "tab": "brief", "title": "File: download the application", "agent": None, "action": None,
        "caption": ("With Gate 2 approved, export writes four Word files: the bail application, the List of Dates, the objections sheet and the "
                    "hearing card. Each is labelled a draft; counsel settles and signs the final text."),
        "filled": [{"label": n, "value": d} for n, d in (("application.docx", "the bail application"), ("list_of_dates.docx", "the List of Dates and Events"),
                                                          ("objections_sheet.docx", "the objections and replies"), ("hearing_card.docx", "the hearing card"))],
    })
    backend = raw.get("health", {}).get("llm_backend") or "offline"
    model = (cost.get("models") or [backend])[0]
    return {
        "slug": case.slug, "case_id": case.case_id, "title": case.title, "story": case.story, "variant": case.variant,
        "recorded": {"date": raw.get("date"), "backend": backend, "model": model, "cost_inr": round(float(cost.get("inr", 0.0)), 2)},
        "steps": steps,
    }


# ---------------------------------------------------------------------------------------------------------------- checks

SECRET_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|hf_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{20,}|SARVAM_API_KEY|OPENAI_API_KEY|GEMINI_API_KEY|api-subscription-key|Bearer\s+[A-Za-z0-9._-]{12,})")


def check(out: Path, extra_paths: list[str]) -> int:
    """Grep demo/ for key-like strings and for this machine's paths; print the size. Non-zero when something is found."""
    needles = [p for p in {str(Path.home()), "/tmp/", *extra_paths} if p]
    bad = 0
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="ignore")
        if SECRET_RE.search(text):
            print(f"KEY-LIKE STRING in {path}")
            bad += 1
        for n in needles:
            if n in text:
                print(f"MACHINE PATH {n!r} in {path}")
                bad += 1
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"{out}: {size / 1e6:.1f} MB in {sum(1 for p in out.rglob('*') if p.is_file())} files")
    return 1 if bad else 0


def scrub_paths(folder: Path, data_dir: Path) -> None:
    """Rewrite the run's absolute data-directory paths in the snapshot's text files to paths relative to the cases folder."""
    roots = sorted({str(data_dir), str(data_dir.resolve())}, key=len, reverse=True)
    for path in folder.rglob("*"):
        if not path.is_file() or path.suffix not in (".json", ".jsonl", ".txt", ".md"):
            continue
        text = path.read_text(encoding="utf-8", errors="strict")
        new = text
        for r in roots:
            new = new.replace(r + "/cases/", "").replace(r, ".")
        if new != text:
            path.write_text(new, encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--api", default="http://127.0.0.1:8020")
    run.add_argument("--data-dir", required=True, type=Path, help="the API's VS_DATA_DIR")
    run.add_argument("--cases", default=",".join(c.slug for c in CASES))
    run.add_argument("--reset", action="store_true", help="delete and re-record a case already in the API's data directory")
    run.add_argument("--out", type=Path, default=DEMO)
    run.add_argument("--work", type=Path, default=WORK)
    tour = sub.add_parser("tour")
    tour.add_argument("--cases", default=",".join(c.slug for c in CASES))
    tour.add_argument("--out", type=Path, default=DEMO)
    tour.add_argument("--work", type=Path, default=WORK)
    tour.add_argument("--data-dir", type=Path, help="recompute each case's spend from this data directory's Sarvam ledger")
    chk = sub.add_parser("check")
    chk.add_argument("--out", type=Path, default=DEMO)
    chk.add_argument("--path", action="append", default=[], help="another machine path that must not appear")
    args = ap.parse_args(argv)

    if args.cmd == "check":
        return check(args.out, args.path)
    slugs = [s.strip() for s in args.cases.split(",") if s.strip()]
    unknown = [s for s in slugs if s not in BY_SLUG]
    if unknown:
        print(f"unknown case(s): {', '.join(unknown)}; known: {', '.join(BY_SLUG)}", file=sys.stderr)
        return 2
    if args.cmd == "tour":
        for slug in slugs:
            raw = json.loads((args.work / slug / "raw.json").read_text(encoding="utf-8"))
            if args.data_dir:
                bodies = (args.out / "cases" / slug / "events.jsonl").read_text(encoding="utf-8").splitlines()
                raw["spend"] = spend(args.data_dir, BY_SLUG[slug].case_id, run_window([b for b in bodies if b.strip()]))
                (args.work / slug / "raw.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
            (args.out / "cases" / slug / "tour.json").write_text(json.dumps(build_tour(BY_SLUG[slug], raw), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"{slug}: tour rebuilt")
        return 0

    failed = 0
    with httpx.Client(base_url=args.api, timeout=httpx.Timeout(3600, connect=10)) as api, tempfile.TemporaryDirectory() as tmp:
        for slug in slugs:
            case = BY_SLUG[slug]
            work = args.work / slug
            work.mkdir(parents=True, exist_ok=True)
            print(f"{slug}: recording as {case.case_id} ...", flush=True)
            try:
                raw = drive(api, case, args.reset, Path(tmp))
            except (RecordError, httpx.HTTPError) as exc:
                failed += 1
                print(f"{slug}: FAILED: {exc}", flush=True)
                continue
            bodies = case_events(args.data_dir, case.case_id)
            raw["stats"] = event_stats(bodies)
            raw["spend"] = spend(args.data_dir, case.case_id, run_window(bodies))
            (work / "raw.json").write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
            folder = snapshot(args.data_dir, case, bodies, args.out)
            scrub_paths(folder, args.data_dir)
            tour_doc = build_tour(case, raw)
            (folder / "tour.json").write_text(json.dumps(tour_doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"{slug}: done in {raw['timings']['total_s']} s; questions {len(raw['answers'])}, grounds {len((raw['brief'] or {}).get('grounds', []))}, "
                  f"objections {len((raw['spar'] or {}).get('objections', []))}, spend INR {raw['spend']['inr']:.2f} "
                  f"({raw['spend']['calls']} hosted calls)", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
