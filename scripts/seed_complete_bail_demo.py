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
import pymupdf

TITLE = "Demo · complete bail file (synthetic)"
NOTICE = "SYNTHETIC DEMONSTRATION DOCUMENT - NOT A COURT RECORD OR LEGAL EVIDENCE"

DOCUMENTS: dict[str, str] = {
    "01_fir.pdf": """FIRST INFORMATION REPORT (under Section 154 CrPC)
Integrated Investigation Form-1 (IIF-1)
1. District: New Delhi P.S.: PS-12 FIR No. 63/2024 Date: 10.03.2024
2. Acts and Sections: IPC 420, IPC 406.
3. Date of occurrence of offence: 05.03.2024
4. Date on which information was received at the P.S.: 10.03.2024
5. Type of information: written
6. Place of occurrence: Connaught Place, District New Delhi
7. Name of the complainant/informant: Complainant-1
8. Name of the accused: Accused-1 and Co-accused-2
9. Date of arrest of the accused: 12.03.2024
10. Brief facts: Complainant-1 states that on 05.03.2024 Accused-1 took Rs. 6,50,000 as an advance for the supply of
textile machinery and did not deliver it. The case was registered on the written complaint and investigation was taken up.
Investigating officer: IO-1""",
    "02_arrest_memo.pdf": """ARREST MEMO
FIR No. 63/2024, P.S. PS-12.
Sections: IPC 420, IPC 406.
Accused-1 was arrested on 12.03.2024 at 18:30 hrs at his residence in Karol Bagh, New Delhi.
The grounds of arrest were communicated to Accused-1 in writing on 12.03.2024 and a relative was informed the same day.
Arresting officer: IO-1""",
    "03_remand_order.pdf": """IN THE COURT OF THE JUDICIAL MAGISTRATE
Remand order dated 13.03.2024
FIR No. 63/2024, P.S. PS-12.
Sections: IPC 420, IPC 406.
The accused Accused-1 was arrested on 12.03.2024 and produced before this Court on 13.03.2024 at 11:00 hrs.
The accused is remanded to judicial custody until 27.03.2024. This is the first remand order, dated 13.03.2024.""",
    "04_previous_bail_order.pdf": """IN THE COURT OF THE SESSIONS JUDGE, PATIALA HOUSE COURTS, NEW DELHI
Bail Application No. 512/2024, State v. Accused-1, FIR No. 63/2024, P.S. PS-12.
Order dated 10.04.2024.
The investigation is at an initial stage and the money trail is yet to be traced.
The earlier regular bail application of Accused-1 was rejected on 10.04.2024 by the Sessions Court.""",
    "05_charge_sheet.pdf": """FINAL REPORT (CHARGE SHEET) under Section 173 CrPC
FIR No. 63/2024, P.S. PS-12.
Sections: IPC 420, IPC 406.
The charge sheet was filed on 06.05.2024. Investigation is complete.
Rs. 2,00,000 was recovered at the instance of Accused-1. The documents relied on have been seized and are in the custody of
the investigating agency, and the evidence is documentary. 22 prosecution witnesses are cited.
Investigating officer: IO-1""",
    "06_co_accused_bail_order.pdf": """IN THE COURT OF THE SESSIONS JUDGE, PATIALA HOUSE COURTS, NEW DELHI
Bail Application No. 981/2024, State v. Co-accused-2, FIR No. 63/2024, P.S. PS-12.
Order dated 18.07.2024.
Co-accused-2, whose role is comparable to that of Accused-1, was granted bail on 18.07.2024 with one surety.""",
    "07_order_sheet.pdf": """IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE, PATIALA HOUSE COURTS, NEW DELHI
Order sheet, State v. Accused-1 and another, FIR No. 63/2024, P.S. PS-12.
01.06.2024: Cognizance taken on the charge sheet.
15.11.2024: Charges have been framed against both accused. Trial has commenced.
Witnesses examined so far: PW-1 (Complainant-1), PW-2 and PW-3. 3 of the 22 prosecution witnesses have been examined.
No complaint of threat or of tampering with any witness has been made by the prosecution.
Next date of hearing: 16.12.2026.""",
    "08_custody_certificate.pdf": """CUSTODY CERTIFICATE
Issued by the Superintendent, Central Jail, Tihar, on 10.11.2026.
It is certified that Accused-1 has been in custody in FIR No. 63/2024 since 12.03.2024.
The period of custody as on 10.11.2026 is 973 days. His conduct in jail has been satisfactory.
Superintendent: Central Jail""",
    "09_police_verification.pdf": """POLICE VERIFICATION REPORT (antecedents)
FIR No. 63/2024, P.S. PS-12. Subject: Accused-1.
On verification of the records, Accused-1 has no previous involvement in any criminal case.
No other criminal case is pending against Accused-1 and he has no criminal antecedents. He is a first-time offender.
Verified by: IO-1""",
    "10_personal_circumstances.pdf": """AFFIDAVIT OF PERSONAL CIRCUMSTANCES
In FIR No. 63/2024, P.S. PS-12, on behalf of Accused-1.
Accused-1 is 34 years old and has been a resident of Karol Bagh, New Delhi since birth, where he owns his residence.
Accused-1 runs a small registered trading business and is the sole earning member of his family.
He supports his wife, two minor children aged eight and five, and his widowed mother aged 68 who has a heart condition.
Accused-1 is diabetic and is under treatment in jail, as recorded by the jail medical officer.
His brother is willing to stand surety, and Accused-1 does not hold a passport.""",
    "11_vakalatnama.pdf": """VAKALATNAMA
BEFORE THE HIGH COURT OF DELHI AT NEW DELHI
Criminal Miscellaneous (Bail) Application under Section 483 BNSS on behalf of Accused-1.
In FIR No. 63/2024, P.S. PS-12, New Delhi.
Counsel appointed for Accused-1 to apply for regular bail and to appear at every hearing of the application.""",
}


def notice_png() -> bytes:
    """The synthetic-document stamp as an image: visible on the page, absent from its text layer."""
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=16)
    page.insert_text((2, 12), NOTICE, fontsize=10, fontname="hebo", color=(0.65, 0.1, 0.1))
    png = page.get_pixmap(dpi=200).tobytes("png")
    doc.close()
    return png


def write_pdf(path: Path, body: str, stamp: bytes) -> None:
    """One page: the stamp at the top and the foot, the body as text in between."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(pymupdf.Rect(48, 22, 548, 38), stream=stamp)
    page.insert_image(pymupdf.Rect(48, 806, 548, 822), stream=stamp)
    if page.insert_textbox(pymupdf.Rect(48, 56, 547, 790), body, fontsize=10.5, fontname="helv", lineheight=1.4) < 0:
        raise RuntimeError(f"text did not fit on one page: {path.name}")
    doc.save(path)
    doc.close()


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
        for name, body in DOCUMENTS.items():
            write_pdf(Path(tmp) / name, body, stamp)
            paths.append(Path(tmp) / name)
        handles = [open(p, "rb") for p in paths]
        try:
            res = api.post(f"/api/cases/{case_id}/upload", files=[("files", (p.name, h, "application/pdf")) for p, h in zip(paths, handles)])
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
