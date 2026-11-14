#!/usr/bin/env python3
"""A complete, synthetic bail file for the product demo: every question intake would ask is answered by a document.

The case is invented and internally consistent (one FIR, one set of dates, role pseudonyms only: Accused-1, Co-accused-2,
Complainant-1, IO-1). Every page carries a stamp saying it is a synthetic demonstration document, not a court record; the
stamp is an image, so it is visible but is not read as a fact of the case. It is for showing the full flow (intake,
dossier, Rights Radar, Gate 1, draft, sparring, Gate 2, export) without gaps; never upload it to a real case, use it as
evidence or use it in an evaluation.

What the documents establish (so the dossier, the Rights Radar and the grounds have something to work with):
- FIR 63/2024 of 10.03.2024 under IPC 420 and 406 (cheating; maximum seven years), offence on 05.03.2024, so the IPC
  governs and the dossier maps it to BNS 318(4) itself;
- arrest on 12.03.2024 with written grounds, first remand on 13.03.2024;
- charge sheet filed on 06.05.2024 (day 54 of 60: no default bail), cognizance, charges framed and trial commenced, 3 of 22
  prosecution witnesses examined, no complaint of threats;
- an earlier bail application rejected on 10.04.2024, before the charge sheet; Co-accused-2 granted bail on 18.07.2024;
- no antecedents (police verification): a first-time offender past one-third of the maximum (BNSS s.479(1) proviso);
- roots in Delhi, dependants, a medical condition and a surety.

Usage (against a running API, as the web interface does): .venv/bin/python scripts/seed_complete_bail_demo.py [--api URL] [--reset] [--consent sarvam]

`--consent sarvam` records counsel's consent (POST /api/cases/{id}/consent) before the upload, for a backend run with Sarvam on, so that
intake and drafting may send this case's pseudonymised text to Sarvam. Use it only when you, as counsel, consent for this synthetic case.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vakeel_sahayak.demo.cases import BY_SLUG, NOTICE, notice_png, write_pdf  # noqa: E402 - the same file as the evaluator demo's case 01

TITLE = "Demo · complete bail file (synthetic)"
_CASE = BY_SLUG["01-cheating-parity"]
DOCUMENTS: dict[str, str] = {d.name: d.body for d in _CASE.documents}
__all__ = ["DOCUMENTS", "NOTICE", "TITLE", "notice_png"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    ap.add_argument("--reset", action="store_true", help="delete an existing case with this title first (DELETE /api/cases/{id})")
    ap.add_argument("--consent", choices=["sarvam", "openai"], help="record counsel's consent for this hosted provider before the upload")
    args = ap.parse_args(argv)
    with httpx.Client(base_url=args.api, timeout=900) as api, tempfile.TemporaryDirectory() as tmp:
        existing = [c["case_id"] for c in api.get("/api/cases").raise_for_status().json() if c["title"] == TITLE]
        if existing and not args.reset:
            print(f"{TITLE!r} already exists as {', '.join(existing)} (use --reset to recreate it)")
            return 0
        for case_id in existing:
            api.delete(f"/api/cases/{case_id}").raise_for_status()
        case_id = api.post("/api/cases", json={"title": TITLE}).raise_for_status().json()["case_id"]
        if args.consent:
            note = "counsel's consent for the synthetic demonstration case"
            api.post(f"/api/cases/{case_id}/consent", json={"provider": args.consent, "granted": True, "note": note}).raise_for_status()
        stamp = notice_png()
        paths = []
        for doc in _CASE.documents:
            write_pdf(Path(tmp) / doc.name, doc, stamp)
            paths.append(Path(tmp) / doc.name)
        handles = [open(p, "rb") for p in paths]
        try:
            res = api.post(f"/api/cases/{case_id}/upload", files=[("files", (p.name, h, "application/pdf")) for p, h in zip(paths, handles, strict=True)])
        finally:
            for h in handles:
                h.close()
        res.raise_for_status()
        body = res.json()
        print(f"{case_id}: {len(body['accepted'])} documents uploaded; questions from intake: {len(body['questions'])}")
        for q in body["questions"]:
            print(f"  question: {q}")
        print(f"open http://localhost:3000/case/{case_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
