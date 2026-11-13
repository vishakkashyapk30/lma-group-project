#!/usr/bin/env python3
"""Seed a complete, explicitly synthetic supplement for the local product demo.

This is a UI/demo fixture only. Every generated page is watermarked in text as
synthetic and not a court record. It must never be used as evidence, uploaded
to a real case, committed to git, or used in an evaluation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf
from seed_public_demo import CASE_ID, SOURCE_NAME, seed

from vakeel_sahayak.api.routers.upload import _run_intake
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event

_NOTICE = "SYNTHETIC DEMONSTRATION INPUT — NOT A COURT RECORD OR LEGAL EVIDENCE"

_DOCUMENTS = {
    "05_synthetic_charge_sheet_cover.pdf": """CHARGE SHEET COVER — DEMONSTRATION ONLY

FIR No. 486/2024, PS-2. Sections: NDPS 8(C), NDPS 21(C), NDPS 29.
The charge sheet was filed on 20.02.2025. Investigation is complete and the matter is listed for cognizance.
""",
    "06_synthetic_previous_bail_order.pdf": """BAIL ORDER — DEMONSTRATION ONLY

FIR No. 486/2024, PS-2. The earlier regular bail application was rejected on 15.01.2025 by the Sessions Court.
""",
    "07_synthetic_co_accused_bail_order.pdf": """BAIL ORDER — DEMONSTRATION ONLY

FIR No. 486/2024, PS-2. Co-accused Demo Co-accused-1, described as having a comparable role, was granted bail on 12.03.2025 subject to conditions.
""",
    "08_synthetic_order_sheet.pdf": """ORDER SHEET — DEMONSTRATION ONLY

FIR No. 486/2024, PS-2. The charge sheet has been filed. Charges have been framed and trial has commenced.
Next date of hearing: 16.12.2026.
""",
    "09_synthetic_counsel_affidavit.pdf": """AFFIDAVIT — DEMONSTRATION ONLY

I state for this synthetic product demonstration that no other criminal case is pending against the accused and there are no criminal antecedents.
The accused is a resident of Lucknow, is employed, and supports dependent family members.
""",
}


def _write_pdf(path: Path, body: str) -> None:
    """Write a legible local PDF with a prominent synthetic-data notice."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = f"{_NOTICE}\n\n{body}\n\n{_NOTICE}"
    spare = page.insert_textbox(pymupdf.Rect(48, 48, 547, 794), text, fontsize=11, fontname="helv", lineheight=1.45)
    if spare < 0:
        raise RuntimeError(f"synthetic demo text did not fit: {path.name}")
    doc.save(path)
    doc.close()


def main() -> None:
    case_dir, log = seed(title="Synthetic complete demo — not a court record", run_intake=False)
    supplement = case_dir / "synthetic-demo-inputs"
    supplement.mkdir()
    paths = []
    for name, body in _DOCUMENTS.items():
        path = supplement / name
        _write_pdf(path, body)
        paths.append(path)
    log.append(Event(
        event_id="", ts="", case_id=CASE_ID, kind=EventKind.USER_ACTION, actor=COUNSEL,
        inputs={
            "action": "upload",
            "files": [path.name for path in paths],
            "file_hashes": [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths],
            "source": "synthetic_demo_only",
        },
    ))
    # Ingest all nine files together. The workspace deliberately displays one
    # current intake report, so a supplement-only intake would hide the T2
    # source bundle from its Documents panel.
    questions = _run_intake(log, CASE_ID, [str(case_dir / SOURCE_NAME), *(str(path) for path in paths)])
    print(f"added {len(paths)} synthetic demo documents; intake questions: {len(questions)}")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
