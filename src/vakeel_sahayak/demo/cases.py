"""Six synthetic, internally consistent bail files for the evaluator demo, with counsel's scripted answers.

Every case is invented. Persons appear only as role pseudonyms (Accused-1, Co-accused-2, Complainant-1, IO-1), police stations as
PS-<n>, and FIR numbers belong to no real case. Every page carries the image stamp "SYNTHETIC DEMONSTRATION DOCUMENT - NOT A COURT
RECORD OR LEGAL EVIDENCE" at its top and foot (an image, so it is visible but is not read as a fact of the case). Dates are chosen so
that the custody arithmetic holds on the recording date (14.11.2026): the custody certificates are dated 10.11.2026.

The six cases vary the offence and the law (IPC before 1 July 2024, BNS after; NDPS small and commercial quantity), the custody
position (default bail open or closed, one-third of the maximum under BNSS s.479, grounds of arrest only oral, arrest without a
notice of appearance), the record (complete, documents missing, a Hindi FIR with a Devanagari text layer, one image-only scanned
page) and the history (co-accused on bail or not, first-time offender or antecedents, an earlier bail application rejected).

`ScriptedAnswer`s are what counsel answers when intake asks (matched to the question by a regular expression); each may also set a
dossier field (PATCH /api/cases/{id}/dossier/{field}, status USER_EDITED) with the value the story fixes. `counsel_edits` are facts
counsel adds to the dossier without being asked. Only `scripts/demo/record_demos.py` uses this module; it needs PyMuPDF and, for the
Hindi FIR, a Devanagari font (Noto, see `testsets.rendering.devanagari_font`).
"""

from __future__ import annotations

import io
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

NOTICE = "SYNTHETIC DEMONSTRATION DOCUMENT - NOT A COURT RECORD OR LEGAL EVIDENCE"
GATE_1_NOTE = "approved by counsel for the recorded evaluator demo"


@dataclass(frozen=True)
class Doc:
    """One single-page PDF of a case: `kind` is 'text' (born-digital English), 'hindi' (Devanagari text layer) or 'scan' (image only)."""

    name: str
    body: str
    kind: str = "text"


@dataclass(frozen=True)
class ScriptedAnswer:
    """Counsel's answer to an intake question whose text matches `pattern` (case-insensitive regex); `field`/`value` also set the dossier field."""

    pattern: str
    answer: str
    field: str | None = None
    value: Any = None


@dataclass(frozen=True)
class DemoCase:
    """One demo case: what the evaluator is told, the documents, and counsel's scripted part."""

    slug: str
    case_id: str
    title: str
    story: str
    variant: dict[str, str]
    documents: list[Doc]
    answers: list[ScriptedAnswer] = field(default_factory=list)
    counsel_edits: list[tuple[str, Any, str]] = field(default_factory=list)  # (field, value, what counsel said)

    def answer_for(self, question: str) -> ScriptedAnswer | None:
        """The first scripted answer whose pattern matches the question, else None."""
        import re

        return next((a for a in self.answers if re.search(a.pattern, question, re.IGNORECASE)), None)


# ---------------------------------------------------------------------------------------------------------------- answers

def _common_answers(*, fir: dict, first_time: bool, pending: str, charge_sheet: tuple[bool, str | None], previous: list[dict], co_accused: list[dict],
                    custody: str, arrest: str, remand: str, offence: str, sections: list[dict], mapping: str = "") -> list[ScriptedAnswer]:
    """Answers to every question template Munshi and Peshkar can ask, filled from one case's facts (so they agree with its papers)."""
    filed, cs_date = charge_sheet
    cs_text = f"Yes. The charge sheet was filed on {_dmy(cs_date)}." if filed and cs_date else "No. As on today no charge sheet has been filed."
    prev_text = ("No earlier bail application has been decided in this case." if not previous else
                 "; ".join(f"The {p['court']} {p['outcome']} bail on {_dmy(p['date'])}" for p in previous) + ". The order is in the file.")
    co_text = ("There is no co-accused who has applied for bail." if not co_accused else
               "; ".join(f"{c['id']} was {c['outcome']} bail" + (f" on {_dmy(c['date'])}" if c.get("date") else "") for c in co_accused) + ".")
    ante_text = "No. No other case is pending against the accused and he has no criminal antecedents." if first_time else pending
    fir_text = f"FIR No. {fir['number']} of P.S. {fir['police_station']}, dated {_dmy(fir['date'])}"
    out = [  # a conflict between readings: counsel names the right one (another number in the papers belongs to another case or event)
        ScriptedAnswer(r"different values for (the )?fir", f"The FIR of this case is {fir_text}; any other FIR number in the papers is a different case.", "fir", fir),
        ScriptedAnswer(r"different values for (the )?(date of )?arrest", f"The arrest was on {_dmy(arrest)}, as the arrest memo says.", "arrest_date", arrest),
        ScriptedAnswer(r"different values for (the )?first.?remand", f"The first remand was on {_dmy(remand)}, as the remand order says.", "first_remand", remand),
        ScriptedAnswer(r"different values for (the )?(date of )?(the )?offence", f"The offence is of {_dmy(offence)}, as the FIR says.", "offence_date", offence),
        ScriptedAnswer(r"different values for (the )?charge.?sheet", cs_text, "charge_sheet", {"filed": filed, "date": cs_date}),
        ScriptedAnswer(r"different values|which one is correct", "The dates and figures in the FIR, the arrest memo and the remand order are the correct ones; "
                       "please use those (the court orders prevail over any secondary note)."),
        ScriptedAnswer(r"could map to more than one section|new code", mapping or "Use the section the papers name; no other mapping is claimed."),
        ScriptedAnswer(r"unreadable|clearer cop", "No clearer copy is available; the page is a photocopy as served. Its contents are confirmed by the other papers in the file."),
        ScriptedAnswer(r"could not be opened", "The file is intact on my side; please read the copy filed."),
        ScriptedAnswer(r"other pending cases|antecedent", ante_text, "antecedents", [] if first_time else [pending]),
        ScriptedAnswer(r"charge.?sheet", cs_text, "charge_sheet", {"filed": filed, "date": cs_date}),
        ScriptedAnswer(r"earlier bail|bail application been decided", prev_text, "previous_bail", previous),
        ScriptedAnswer(r"co-accused", co_text, "co_accused_bail", co_accused),
        ScriptedAnswer(r"custody certificate", custody),
        ScriptedAnswer(r"first remand|first remanded", f"The accused was first remanded on {_dmy(remand)}.", "first_remand", remand),
        ScriptedAnswer(r"arrest", f"The accused was arrested on {_dmy(arrest)}.", "arrest_date", arrest),
        ScriptedAnswer(r"date of the alleged offence|offence", f"The alleged offence is of {_dmy(offence)}.", "offence_date", offence),
        ScriptedAnswer(r"section", "The sections are those named in the FIR: " + ", ".join(s["as_written"] for s in sections) + ".", "sections", sections),
        ScriptedAnswer(r"FIR", "The FIR is in the file (the first document)."),
    ]
    return out


def _dmy(iso: str | None) -> str:
    if not iso:
        return ""
    y, m, d = iso.split("-")
    return f"{d}.{m}.{y}"


def _sec(as_written: str) -> dict:
    code, _, section = as_written.partition(" ")
    return {"as_written": as_written, "code": code, "section": section}


# ---------------------------------------------------------------------------------------------------------------- case 01

_CASE_01 = DemoCase(
    slug="01-cheating-parity",
    case_id="demo-01",
    title="Demo · Cheating under the IPC, co-accused already on bail",
    story=("Accused-1 is charged under IPC 420 and 406 for taking an advance of Rs. 6,50,000 for machinery that was never delivered; the "
           "offence (March 2024) predates the BNS, so the IPC governs. He has been in custody since 12.03.2024, the charge sheet was filed in "
           "time and the trial is under way; his earlier bail application was rejected, while Co-accused-2, with a comparable role, is on bail."),
    variant={"offence": "IPC 420/406 cheating (maximum 7 years), offence before 1 July 2024",
             "custody": "default bail closed (charge sheet on day 55 of 60); past one-third of the maximum as a first-time offender (BNSS s.479)",
             "record": "complete file, eleven born-digital documents",
             "parity": "Co-accused-2 granted bail; first-time offender; earlier bail application rejected"},
    documents=[
        Doc("01_fir.pdf", """FIRST INFORMATION REPORT (under Section 154 CrPC)
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
Investigating officer: IO-1"""),
        Doc("02_arrest_memo.pdf", """ARREST MEMO
FIR No. 63/2024, P.S. PS-12.
Sections: IPC 420, IPC 406.
Accused-1 was arrested on 12.03.2024 at 18:30 hrs at his residence in Karol Bagh, New Delhi.
The grounds of arrest were communicated to Accused-1 in writing on 12.03.2024 and a relative was informed the same day.
Arresting officer: IO-1"""),
        Doc("03_remand_order.pdf", """IN THE COURT OF THE JUDICIAL MAGISTRATE
Remand order dated 13.03.2024
FIR No. 63/2024, P.S. PS-12.
Sections: IPC 420, IPC 406.
The accused Accused-1 was arrested on 12.03.2024 and produced before this Court on 13.03.2024 at 11:00 hrs.
The accused is remanded to judicial custody until 27.03.2024. This is the first remand order, dated 13.03.2024."""),
        Doc("04_previous_bail_order.pdf", """IN THE COURT OF THE SESSIONS JUDGE, PATIALA HOUSE COURTS, NEW DELHI
Bail Application No. 512/2024, State v. Accused-1, FIR No. 63/2024, P.S. PS-12.
Order dated 10.04.2024.
The investigation is at an initial stage and the money trail is yet to be traced.
The earlier regular bail application of Accused-1 was rejected on 10.04.2024 by the Sessions Court."""),
        Doc("05_charge_sheet.pdf", """FINAL REPORT (CHARGE SHEET) under Section 173 CrPC
FIR No. 63/2024, P.S. PS-12.
Sections: IPC 420, IPC 406.
The charge sheet was filed on 06.05.2024. Investigation is complete.
Rs. 2,00,000 was recovered at the instance of Accused-1. The documents relied on have been seized and are in the custody of
the investigating agency, and the evidence is documentary. 22 prosecution witnesses are cited.
Investigating officer: IO-1"""),
        Doc("06_co_accused_bail_order.pdf", """IN THE COURT OF THE SESSIONS JUDGE, PATIALA HOUSE COURTS, NEW DELHI
Bail Application No. 981/2024, State v. Co-accused-2, FIR No. 63/2024, P.S. PS-12.
Order dated 18.07.2024.
Co-accused-2, whose role is comparable to that of Accused-1, was granted bail on 18.07.2024 with one surety."""),
        Doc("07_order_sheet.pdf", """IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE, PATIALA HOUSE COURTS, NEW DELHI
Order sheet, State v. Accused-1 and another, FIR No. 63/2024, P.S. PS-12.
01.06.2024: Cognizance taken on the charge sheet.
15.11.2024: Charges have been framed against both accused. Trial has commenced.
Witnesses examined so far: PW-1 (Complainant-1), PW-2 and PW-3. 3 of the 22 prosecution witnesses have been examined.
No complaint of threat or of tampering with any witness has been made by the prosecution.
Next date of hearing: 16.12.2026."""),
        Doc("08_custody_certificate.pdf", """CUSTODY CERTIFICATE
Issued by the Superintendent, Central Jail, Tihar, on 10.11.2026.
It is certified that Accused-1 has been in custody in FIR No. 63/2024 since 12.03.2024.
The period of custody as on 10.11.2026 is 973 days. His conduct in jail has been satisfactory.
Superintendent: Central Jail"""),
        Doc("09_police_verification.pdf", """POLICE VERIFICATION REPORT (antecedents)
FIR No. 63/2024, P.S. PS-12. Subject: Accused-1.
On verification of the records, Accused-1 has no previous involvement in any criminal case.
No other criminal case is pending against Accused-1 and he has no criminal antecedents. He is a first-time offender.
Verified by: IO-1"""),
        Doc("10_personal_circumstances.pdf", """AFFIDAVIT OF PERSONAL CIRCUMSTANCES
In FIR No. 63/2024, P.S. PS-12, on behalf of Accused-1.
Accused-1 is 34 years old and has been a resident of Karol Bagh, New Delhi since birth, where he owns his residence.
Accused-1 runs a small registered trading business and is the sole earning member of his family.
He supports his wife, two minor children aged eight and five, and his widowed mother aged 68 who has a heart condition.
Accused-1 is diabetic and is under treatment in jail, as recorded by the jail medical officer.
His brother is willing to stand surety, and Accused-1 does not hold a passport."""),
        Doc("11_vakalatnama.pdf", """VAKALATNAMA
BEFORE THE HIGH COURT OF DELHI AT NEW DELHI
Criminal Miscellaneous (Bail) Application under Section 483 BNSS on behalf of Accused-1.
In FIR No. 63/2024, P.S. PS-12, New Delhi.
Counsel appointed for Accused-1 to apply for regular bail and to appear at every hearing of the application."""),
    ],
    answers=_common_answers(
        fir={"number": "63/2024", "police_station": "PS-12", "date": "2024-03-10"},
        first_time=True, pending="", charge_sheet=(True, "2024-05-06"),
        previous=[{"court": "Sessions Court, Patiala House", "date": "2024-04-10", "outcome": "rejected"}],
        co_accused=[{"id": "Co-accused-2", "outcome": "granted", "date": "2024-07-18"}],
        custody="The custody certificate of 10.11.2026 is in the file: in custody since 12.03.2024, 973 days as on that date.",
        arrest="2024-03-12", remand="2024-03-13", offence="2024-03-05", sections=[_sec("IPC 420"), _sec("IPC 406")],
        mapping="The offence is of 05.03.2024, before 1 July 2024, so the IPC applies; IPC 420 corresponds to BNS 318(4) and IPC 406 to BNS 316(2)."),
)

# ---------------------------------------------------------------------------------------------------------------- case 02

_CASE_02 = DemoCase(
    slug="02-bns-theft-default-bail",
    case_id="demo-02",
    title="Demo · Theft under the BNS, no charge sheet after 60 days",
    story=("Accused-1 is charged under BNS 303(2) for a shop theft on 09.08.2026, so the new codes (BNS and BNSS) apply. He was first "
           "remanded on 12.08.2026 and the police have not filed a charge sheet, so the 60-day period for default bail has run out; he has "
           "one other theft case pending and no co-accused."),
    variant={"offence": "BNS 303(2) theft (up to 5 years in the First Schedule), offence after 1 July 2024",
             "custody": "default bail open: no charge sheet after the 60 days of BNSS s.187(3)",
             "record": "complete file, eight born-digital documents",
             "parity": "no co-accused; antecedents (one other case pending); no earlier bail application"},
    documents=[
        Doc("01_fir.pdf", """FIRST INFORMATION REPORT (under Section 173 BNSS)
1. District: South Delhi P.S.: PS-7 FIR No. 214/2026 Date: 10.08.2026
2. Acts and Sections: BNS 303(2).
3. Date of occurrence of offence: 09.08.2026, between 21:00 and 22:00 hrs
4. Date on which information was received at the P.S.: 10.08.2026
5. Type of information: written
6. Place of occurrence: a mobile phone shop, Lajpat Nagar, District South Delhi
7. Name of the complainant/informant: Complainant-1
8. Name of the accused: Accused-1
9. Brief facts: Complainant-1, the owner of the shop, states that on the night of 09.08.2026 the shutter of his shop was
forced open and six mobile phones worth about Rs. 1,10,000 were taken. The CCTV camera of a neighbouring shop shows a person
resembling Accused-1 near the shutter at 21:40 hrs. The case was registered and investigation was taken up.
Investigating officer: IO-1"""),
        Doc("02_arrest_memo.pdf", """ARREST MEMO
FIR No. 214/2026, P.S. PS-7. Sections: BNS 303(2).
Accused-1 was arrested on 11.08.2026 at 17:30 hrs at Govindpuri, New Delhi.
The grounds of arrest were communicated to Accused-1 in writing on 11.08.2026 and his mother was informed the same day.
Two mobile phones were recovered at the instance of Accused-1.
Arresting officer: IO-1"""),
        Doc("03_remand_order.pdf", """IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, SAKET COURTS, NEW DELHI
Remand order dated 12.08.2026
FIR No. 214/2026, P.S. PS-7. Sections: BNS 303(2).
The accused Accused-1 was arrested on 11.08.2026 and produced before this Court on 12.08.2026 at 11:30 hrs.
The accused is remanded to judicial custody until 26.08.2026. This is the first remand order, dated 12.08.2026."""),
        Doc("04_order_sheet.pdf", """IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, SAKET COURTS, NEW DELHI
Order sheet, State v. Accused-1, FIR No. 214/2026, P.S. PS-7.
26.08.2026: Investigation pending. Judicial custody extended until 23.09.2026.
23.09.2026: Investigation pending. Judicial custody extended until 21.10.2026.
21.10.2026: IO-1 states that the charge sheet is under preparation. The charge sheet has not been filed.
Judicial custody extended until 18.11.2026.
Next date of hearing: 18.11.2026."""),
        Doc("05_custody_certificate.pdf", """CUSTODY CERTIFICATE
Issued by the Superintendent, Central Jail, Tihar, on 10.11.2026.
It is certified that Accused-1 has been in custody in FIR No. 214/2026 since 11.08.2026.
The period of custody as on 10.11.2026 is 91 days. No charge sheet has been received by the jail.
His conduct in jail has been satisfactory.
Superintendent: Central Jail"""),
        Doc("06_police_verification.pdf", """POLICE VERIFICATION REPORT (antecedents)
FIR No. 214/2026, P.S. PS-7. Subject: Accused-1.
Accused-1 is involved in one other case: FIR No. 88/2025 under BNS 303(2), P.S. PS-9, in which the trial is pending
and Accused-1 is on bail. No other involvement was found.
Verified by: IO-1"""),
        Doc("07_personal_circumstances.pdf", """AFFIDAVIT OF PERSONAL CIRCUMSTANCES
In FIR No. 214/2026, P.S. PS-7, on behalf of Accused-1.
Accused-1 is 27 years old and lives in a rented room in Govindpuri, New Delhi with his mother and younger sister.
He works as a delivery rider and is the only earning member of the family.
His brother-in-law is willing to stand surety. Accused-1 does not hold a passport."""),
        Doc("08_vakalatnama.pdf", """VAKALATNAMA
IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, SAKET COURTS, NEW DELHI
Application for default bail under Section 187(3) BNSS on behalf of Accused-1.
In FIR No. 214/2026, P.S. PS-7, New Delhi.
Counsel appointed for Accused-1 to apply for bail and to appear at every hearing of the application."""),
    ],
    answers=_common_answers(
        fir={"number": "214/2026", "police_station": "PS-7", "date": "2026-08-10"},
        first_time=False, pending="Yes. FIR No. 88/2025 under BNS 303(2), P.S. PS-9, is pending trial; he is on bail in that case.",
        charge_sheet=(False, None), previous=[], co_accused=[],
        custody="The custody certificate of 10.11.2026 is in the file: in custody since 11.08.2026, 91 days as on that date.",
        arrest="2026-08-11", remand="2026-08-12", offence="2026-08-09", sections=[_sec("BNS 303(2)")]),
)

# ---------------------------------------------------------------------------------------------------------------- case 03

_FIR_HI = """प्रथम सूचना रिपोर्ट (भारतीय नागरिक सुरक्षा संहिता की धारा 173 के अंतर्गत)
1. जिला: लखनऊ थाना: PS-3 एफ.आई.आर. संख्या: 151/2026 दिनांक: 02.07.2026
2. अधिनियम एवं धाराएँ: NDPS 21(a)
3. घटना की तिथि: 02.07.2026, समय लगभग 21:00 बजे
4. थाने पर सूचना प्राप्त होने की तिथि: 02.07.2026
5. घटनास्थल: चारबाग रेलवे स्टेशन के पास, लखनऊ
6. सूचनाकर्ता: IO-1, उप निरीक्षक, थाना PS-3
7. अभियुक्त: Accused-1
8. गिरफ्तारी की तिथि: 02.07.2026
9. संक्षिप्त विवरण: गश्त के दौरान संदेह होने पर अभियुक्त Accused-1 को रोका गया। विधिवत तलाशी लेने पर उसकी पैंट की जेब से 4 ग्राम हेरोइन (स्मैक) बरामद हुई। बरामद मात्रा अल्प मात्रा की श्रेणी में है। अभियुक्त को मौके पर गिरफ्तार किया गया और बरामद माल को सील कर दिया गया। मुकदमा पंजीकृत कर विवेचना प्रारम्भ की गई।
विवेचक: IO-1"""

_CASE_03 = DemoCase(
    slug="03-ndps-small-hindi",
    case_id="demo-03",
    title="Demo · NDPS small quantity, Hindi FIR, grounds of arrest only oral",
    story=("Accused-1, a 22-year-old student, is charged under NDPS 21(a) for 4 grams of heroin, a small quantity, so the s.37 bar does not apply; the FIR is in H"
           "indi. He was arrested on 02.07.2026 and told the grounds of arrest only orally; the charge sheet was filed in time (day 54 of 60). The Rights Radar still shows CHECK for default bail and for the BNSS s.479 undertrial limit, because no maximum punishment was on record for the charged section, so counsel is asked to check both."),
    variant={"offence": "NDPS 21(a) small quantity (maximum 1 year); the s.37 twin conditions do not apply",
             "custody": "charge sheet filed on day 54 of 60, in time; the radar nevertheless shows CHECK for default bail and for BNSS s.479 because no maximum punishment is on record; grounds of arrest given only orally in the scenario (the radar shows UNKNOWN: no record of them in the dossier)",
             "record": "Hindi FIR (Devanagari text layer) with eight English documents",
             "parity": "no co-accused; first-time offender; no earlier bail application"},
    documents=[
        Doc("01_fir_hindi.pdf", _FIR_HI, kind="hindi"),
        Doc("02_arrest_memo.pdf", """ARREST MEMO
FIR No. 151/2026, P.S. PS-3, Lucknow. Sections: NDPS 21(a).
Accused-1 was arrested on 02.07.2026 at 21:40 hrs near Charbagh railway station, Lucknow.
The grounds of arrest were informed to Accused-1 orally at the time of arrest. No written grounds of arrest were served on him.
His mother was informed by telephone on 03.07.2026.
Arresting officer: IO-1"""),
        Doc("03_seizure_memo.pdf", """SEIZURE MEMO (RECOVERY MEMO)
FIR No. 151/2026, P.S. PS-3, Lucknow.
On 02.07.2026 at about 21:15 hrs, on a personal search of Accused-1 conducted after informing him of his right under Section 50 of the NDPS Act, 4 grams of heroin (smack) were recovered from the pocket of his trousers.
The quantity recovered is a small quantity (the notified small quantity for heroin is 5 grams).
The recovered substance was sealed and a sample was drawn for the forensic laboratory.
Seizing officer: IO-1"""),
        Doc("04_remand_order.pdf", """IN THE COURT OF THE CHIEF JUDICIAL MAGISTRATE, LUCKNOW
Remand order dated 03.07.2026
FIR No. 151/2026, P.S. PS-3. Sections: NDPS 21(a).
The accused Accused-1 was arrested on 02.07.2026 and produced before this Court on 03.07.2026 at 14:00 hrs.
The accused is remanded to judicial custody until 17.07.2026. This is the first remand order, dated 03.07.2026."""),
        Doc("05_charge_sheet.pdf", """FINAL REPORT (CHARGE SHEET) under Section 193 BNSS
FIR No. 151/2026, P.S. PS-3, Lucknow. Sections: NDPS 21(a).
The charge sheet was filed on 25.08.2026. Investigation is complete.
The forensic report confirms diacetylmorphine (heroin), net weight 4.0 grams, a small quantity.
6 prosecution witnesses are cited, all of them police officials. No independent witness was joined at the recovery.
Investigating officer: IO-1"""),
        Doc("06_custody_certificate.pdf", """CUSTODY CERTIFICATE
Issued by the Superintendent, District Jail, Lucknow, on 10.11.2026.
It is certified that Accused-1 has been in custody in FIR No. 151/2026 since 02.07.2026.
The period of custody as on 10.11.2026 is 131 days. His conduct in jail has been satisfactory.
Superintendent: District Jail"""),
        Doc("07_police_verification.pdf", """POLICE VERIFICATION REPORT (antecedents)
FIR No. 151/2026, P.S. PS-3, Lucknow. Subject: Accused-1.
On verification of the records, Accused-1 has no previous involvement in any criminal case.
No other criminal case is pending against Accused-1 and he has no criminal antecedents. He is a first-time offender.
Verified by: IO-1"""),
        Doc("08_personal_circumstances.pdf", """AFFIDAVIT OF PERSONAL CIRCUMSTANCES
In FIR No. 151/2026, P.S. PS-3, Lucknow, on behalf of Accused-1.
Accused-1 is 22 years old and a second-year B.Com student at a college in Lucknow, where he has lived since birth.
His father has died and his mother works as a domestic worker; he has a younger brother in school.
His maternal uncle is willing to stand surety. He is represented by legal aid counsel assigned by the District Legal Services Authority."""),
        Doc("09_vakalatnama.pdf", """VAKALATNAMA (LEGAL AID)
IN THE COURT OF THE SPECIAL JUDGE (NDPS ACT), LUCKNOW
Application for regular bail under Section 480 BNSS on behalf of Accused-1.
In FIR No. 151/2026, P.S. PS-3, Lucknow.
Legal aid counsel assigned to Accused-1 to apply for bail and to appear at every hearing of the application."""),
    ],
    answers=_common_answers(
        fir={"number": "151/2026", "police_station": "PS-3", "date": "2026-07-02"},
        first_time=True, pending="", charge_sheet=(True, "2026-08-25"), previous=[], co_accused=[],
        custody="The custody certificate of 10.11.2026 is in the file: in custody since 02.07.2026, 131 days as on that date.",
        arrest="2026-07-02", remand="2026-07-03", offence="2026-07-02", sections=[_sec("NDPS 21(a)")]),
)

# ---------------------------------------------------------------------------------------------------------------- case 04

_CASE_04 = DemoCase(
    slug="04-ndps-commercial-scanned",
    case_id="demo-04",
    title="Demo · NDPS commercial quantity, s.37 bar, one scanned page",
    story=("Accused-1 is charged under NDPS 21(c) and 29 for 1.2 kg of heroin found in the car he was driving, a commercial quantity, so "
           "bail needs the twin conditions of s.37. The charge sheet came within the 180 days of the NDPS Act, his earlier bail "
           "application was rejected, he has one other NDPS case pending and the seizure memo is only a scanned image."),
    variant={"offence": "NDPS 21(c)/29 commercial quantity (maximum 20 years); the s.37 twin conditions apply",
             "custody": "default bail closed (charge sheet on day 167 of the NDPS Act's 180)",
             "record": "ten born-digital documents and one image-only scanned page (the seizure memo)",
             "parity": "Co-accused-2 refused bail; antecedents (one other NDPS case pending); earlier bail application rejected"},
    documents=[
        Doc("01_fir.pdf", """FIRST INFORMATION REPORT (under Section 173 BNSS)
1. District: Amritsar Rural P.S.: PS-5 FIR No. 77/2026 Date: 15.01.2026
2. Acts and Sections: NDPS 21(c), NDPS 29.
3. Date of occurrence of offence: 15.01.2026, about 18:45 hrs
4. Date on which information was received at the P.S.: 15.01.2026
5. Type of information: recorded on the statement of IO-1
6. Place of occurrence: a police check point on the GT Road near a village in District Amritsar Rural
7. Name of the informant: IO-1, Sub-Inspector, P.S. PS-5
8. Name of the accused: Accused-1 (driver) and Co-accused-2 (passenger)
9. Brief facts: A car driven by Accused-1, with Co-accused-2 in the front seat, was stopped at the check point. On search, a bag
under the driver's seat was found to contain 1 kg 200 grams of heroin. Both were arrested on the spot.
Investigating officer: IO-1"""),
        Doc("02_arrest_memo.pdf", """ARREST MEMO
FIR No. 77/2026, P.S. PS-5. Sections: NDPS 21(c), NDPS 29.
Accused-1 was arrested on 15.01.2026 at 19:30 hrs at the check point on the GT Road, District Amritsar Rural.
The grounds of arrest were communicated to Accused-1 in writing on 15.01.2026 and his brother was informed the same day.
Arresting officer: IO-1"""),
        Doc("03_seizure_memo_scanned.pdf", """SEIZURE MEMO (RECOVERY MEMO)
FIR No. 77/2026, P.S. PS-5. Sections: NDPS 21(c), NDPS 29.
Date and time: 15.01.2026, 19:05 hrs. Place: police check point, GT Road.
Before the search Accused-1 and Co-accused-2 were told of their right under Section 50 of the NDPS Act to be searched before a gazetted officer or a magistrate; both declined in writing.
From a bag under the driver's seat of the car, 1 kg 200 grams of heroin was recovered.
Two samples of 5 grams each were drawn and sealed with the seal AB; the remainder was sealed separately.
Seizing officer: IO-1""", kind="scan"),
        Doc("04_remand_order.pdf", """IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, AMRITSAR
Remand order dated 16.01.2026
FIR No. 77/2026, P.S. PS-5. Sections: NDPS 21(c), NDPS 29.
The accused Accused-1 was arrested on 15.01.2026 and produced before this Court on 16.01.2026 at 12:00 hrs.
The accused is remanded to judicial custody until 30.01.2026. This is the first remand order, dated 16.01.2026."""),
        Doc("05_charge_sheet.pdf", """FINAL REPORT (CHARGE SHEET) under Section 193 BNSS
FIR No. 77/2026, P.S. PS-5. Sections: NDPS 21(c), NDPS 29.
The charge sheet was filed on 01.07.2026. Investigation is complete.
The forensic report confirms diacetylmorphine (heroin) in both samples. The recovered quantity is a commercial quantity.
14 prosecution witnesses are cited.
Investigating officer: IO-1"""),
        Doc("06_previous_bail_order.pdf", """IN THE COURT OF THE SPECIAL JUDGE (NDPS ACT), AMRITSAR
Bail Application No. 1104/2026, State v. Accused-1, FIR No. 77/2026, P.S. PS-5.
Order dated 20.08.2026.
The recovery is of a commercial quantity and the twin conditions of Section 37 of the NDPS Act are not satisfied.
The applicant is also involved in another case under the NDPS Act.
The regular bail application of Accused-1 was rejected on 20.08.2026."""),
        Doc("07_order_sheet.pdf", """IN THE COURT OF THE SPECIAL JUDGE (NDPS ACT), AMRITSAR
Order sheet, State v. Accused-1 and another, FIR No. 77/2026, P.S. PS-5.
20.08.2026: The bail applications of Accused-1 and of Co-accused-2 are rejected by separate orders.
10.09.2026: Charges have been framed against both accused. Trial has commenced.
Witnesses examined so far: PW-1 and PW-2. 2 of the 14 prosecution witnesses have been examined.
Next date of hearing: 25.11.2026."""),
        Doc("08_custody_certificate.pdf", """CUSTODY CERTIFICATE
Issued by the Superintendent, Central Jail, Amritsar, on 10.11.2026.
It is certified that Accused-1 has been in custody in FIR No. 77/2026 since 15.01.2026.
The period of custody as on 10.11.2026 is 299 days. His conduct in jail has been satisfactory.
Superintendent: Central Jail"""),
        Doc("09_police_verification.pdf", """POLICE VERIFICATION REPORT (antecedents)
FIR No. 77/2026, P.S. PS-5. Subject: Accused-1.
Accused-1 is involved in one other case: FIR No. 12/2022 under NDPS 21(b), P.S. PS-8, Amritsar, in which the trial is pending
and Accused-1 is on bail. No other involvement was found.
Verified by: IO-1"""),
        Doc("10_personal_circumstances.pdf", """AFFIDAVIT OF PERSONAL CIRCUMSTANCES
In FIR No. 77/2026, P.S. PS-5, on behalf of Accused-1.
Accused-1 is 38 years old, a driver by profession, and lives in his own house in a village of District Amritsar Rural.
He supports his wife and three children aged 14, 11 and 7. His brother is willing to stand surety."""),
        Doc("11_vakalatnama.pdf", """VAKALATNAMA
BEFORE THE HIGH COURT OF PUNJAB AND HARYANA AT CHANDIGARH
Criminal Miscellaneous (Main) bail application under Section 483 BNSS on behalf of Accused-1.
In FIR No. 77/2026, P.S. PS-5, District Amritsar Rural.
Counsel appointed for Accused-1 to apply for regular bail and to appear at every hearing of the application."""),
    ],
    answers=_common_answers(
        fir={"number": "77/2026", "police_station": "PS-5", "date": "2026-01-15"},
        first_time=False, pending="Yes. FIR No. 12/2022 under NDPS 21(b), P.S. PS-8, Amritsar, is pending trial; he is on bail in that case.",
        charge_sheet=(True, "2026-07-01"),
        previous=[{"court": "Special Court (NDPS), Amritsar", "date": "2026-08-20", "outcome": "rejected"}],
        co_accused=[{"id": "Co-accused-2", "outcome": "refused", "date": "2026-08-20"}],
        custody="The custody certificate of 10.11.2026 is in the file: in custody since 15.01.2026, 299 days as on that date.",
        arrest="2026-01-15", remand="2026-01-16", offence="2026-01-15", sections=[_sec("NDPS 21(c)"), _sec("NDPS 29")]),
)

# ---------------------------------------------------------------------------------------------------------------- case 05

_CASE_05 = DemoCase(
    slug="05-bns-attempt-murder-parity",
    case_id="demo-05",
    title="Demo · Attempt to murder under the BNS, co-accused on bail",
    story=("Accused-1 is charged under BNS 109 and 3(5) for a knife wound in a quarrel over parking on 13.03.2025, an attempt to murder. He has been in custody si"
           "nce 16.03.2025; the charge sheet was filed on day 81 of 90, in time. The Rights Radar shows CHECK for default bail and for the BNSS s.479 limit because it had no maximum punishment on record, although the dossier lists the section's maximum as death, so counsel is asked to check. His bail was refused by the Sessions Court, and Co-accused-2, said to have only held the injured, was granted bail by the High Court."),
    variant={"offence": "BNS 109 with 3(5), attempt to murder (life imprisonment where hurt is caused), offence after 1 July 2024",
             "custody": "charge sheet filed on day 81 of 90, in time; the radar nevertheless shows CHECK for default bail and for BNSS s.479 because no maximum punishment is on record (the dossier lists it as death for BNS 109)",
             "record": "complete file, eleven born-digital documents including the medico-legal report",
             "parity": "Co-accused-2 granted bail with a lesser role; first-time offender; earlier bail application rejected"},
    documents=[
        Doc("01_fir.pdf", """FIRST INFORMATION REPORT (under Section 173 BNSS)
1. District: Rohini P.S.: PS-14 FIR No. 302/2025 Date: 14.03.2025
2. Acts and Sections: BNS 109, BNS 3(5).
3. Date of occurrence of offence: 13.03.2025, about 22:30 hrs
4. Date on which information was received at the P.S.: 14.03.2025, 00:15 hrs
5. Type of information: statement of the injured recorded at the hospital
6. Place of occurrence: a residential lane in Sector 7, Rohini, Delhi
7. Name of the complainant/informant: Complainant-1 (the injured)
8. Name of the accused: Accused-1 and Co-accused-2
9. Brief facts: Complainant-1 states that a quarrel arose over the parking of a motorcycle. Co-accused-2 held him by the arms and
Accused-1 struck him once on the left side of his abdomen with a knife. Neighbours took him to the hospital.
Investigating officer: IO-1"""),
        Doc("02_arrest_memo.pdf", """ARREST MEMO
FIR No. 302/2025, P.S. PS-14. Sections: BNS 109, BNS 3(5).
Accused-1 was arrested on 16.03.2025 at 08:00 hrs at his residence in Rohini, Delhi.
The grounds of arrest were communicated to Accused-1 in writing on 16.03.2025 and his father was informed the same day.
Arresting officer: IO-1"""),
        Doc("03_remand_order.pdf", """IN THE COURT OF THE DUTY METROPOLITAN MAGISTRATE, ROHINI COURTS, DELHI
Remand order dated 17.03.2025
FIR No. 302/2025, P.S. PS-14. Sections: BNS 109, BNS 3(5).
The accused Accused-1 was arrested on 16.03.2025 and produced before this Court on 17.03.2025 at 10:30 hrs.
The accused is remanded to judicial custody until 31.03.2025. This is the first remand order, dated 17.03.2025."""),
        Doc("04_medico_legal_report.pdf", """MEDICO-LEGAL REPORT
Patient: Complainant-1. Brought to the casualty on 13.03.2025 at 23:05 hrs.
Injury: one incised wound, 4 cm x 1 cm, on the left flank of the abdomen; no injury to internal organs.
Nature of injury: simple. Weapon: sharp-edged.
The patient was discharged on 19.03.2025 in a stable condition."""),
        Doc("05_charge_sheet.pdf", """FINAL REPORT (CHARGE SHEET) under Section 193 BNSS
FIR No. 302/2025, P.S. PS-14. Sections: BNS 109, BNS 3(5).
The charge sheet was filed on 05.06.2025. Investigation is complete.
The knife was recovered at the instance of Accused-1. 18 prosecution witnesses are cited.
Investigating officer: IO-1"""),
        Doc("06_previous_bail_order.pdf", """IN THE COURT OF THE ADDITIONAL SESSIONS JUDGE, ROHINI COURTS, DELHI
Bail Application No. 640/2025, State v. Accused-1, FIR No. 302/2025, P.S. PS-14.
Order dated 22.07.2025.
A knife blow to the abdomen is attributed to the applicant and the material witnesses are yet to be examined.
The regular bail application of Accused-1 was rejected on 22.07.2025."""),
        Doc("07_co_accused_bail_order.pdf", """IN THE HIGH COURT OF DELHI AT NEW DELHI
Bail Application No. 1932/2025, Co-accused-2 v. State, FIR No. 302/2025, P.S. PS-14.
Order dated 10.03.2026.
Co-accused-2 is alleged to have held the injured; no weapon is attributed to him. The injury is opined to be simple.
Co-accused-2 was granted bail on 10.03.2026 with one surety."""),
        Doc("08_order_sheet.pdf", """IN THE COURT OF THE ADDITIONAL SESSIONS JUDGE, ROHINI COURTS, DELHI
Order sheet, State v. Accused-1 and another, FIR No. 302/2025, P.S. PS-14.
15.10.2025: Charges have been framed against both accused. Trial has commenced.
12.08.2026: The injured, PW-1 (Complainant-1), has been examined and cross-examined.
Witnesses examined so far: 6 of the 18 prosecution witnesses have been examined.
No complaint of threat to any witness has been made. Next date of hearing: 03.12.2026."""),
        Doc("09_custody_certificate.pdf", """CUSTODY CERTIFICATE
Issued by the Superintendent, Central Jail, Tihar, on 10.11.2026.
It is certified that Accused-1 has been in custody in FIR No. 302/2025 since 16.03.2025.
The period of custody as on 10.11.2026 is 604 days. His conduct in jail has been satisfactory.
Superintendent: Central Jail"""),
        Doc("10_police_verification.pdf", """POLICE VERIFICATION REPORT (antecedents)
FIR No. 302/2025, P.S. PS-14. Subject: Accused-1.
On verification of the records, Accused-1 has no previous involvement in any criminal case.
No other criminal case is pending against Accused-1 and he has no criminal antecedents. He is a first-time offender.
Verified by: IO-1"""),
        Doc("11_personal_circumstances.pdf", """AFFIDAVIT OF PERSONAL CIRCUMSTANCES
In FIR No. 302/2025, P.S. PS-14, on behalf of Accused-1.
Accused-1 is 29 years old, an electrician, and has lived in Rohini, Delhi since birth.
He supports his wife, an infant daughter and his parents. His father is willing to stand surety.
Accused-1 does not hold a passport."""),
    ],
    answers=_common_answers(
        fir={"number": "302/2025", "police_station": "PS-14", "date": "2025-03-14"},
        first_time=True, pending="", charge_sheet=(True, "2025-06-05"),
        previous=[{"court": "Sessions Court, Rohini", "date": "2025-07-22", "outcome": "rejected"}],
        co_accused=[{"id": "Co-accused-2", "outcome": "granted", "date": "2026-03-10"}],
        custody="The custody certificate of 10.11.2026 is in the file: in custody since 16.03.2025, 604 days as on that date.",
        arrest="2025-03-16", remand="2025-03-17", offence="2025-03-13", sections=[_sec("BNS 109"), _sec("BNS 3(5)")]),
)

# ---------------------------------------------------------------------------------------------------------------- case 06

_CASE_06 = DemoCase(
    slug="06-bns-breach-of-trust-missing-papers",
    case_id="demo-06",
    title="Demo · Breach of trust under the BNS, arrest without notice, papers missing",
    story=("Accused-1, an accountant, is charged under BNS 316(2) for diverting Rs. 3,80,000 of his employer's collections, an offence "
           "punishable with up to five years. He was arrested on 05.10.2026 without a notice of appearance and without recorded reasons; "
           "counsel has only four papers, so intake asks what is missing and counsel answers from instructions."),
    variant={"offence": "BNS 316(2) criminal breach of trust (maximum 5 years), offence after 1 July 2024",
             "custody": "arrest without a notice of appearance or recorded reasons (BNSS s.35(3), Arnesh Kumar; the radar shows UNKNOWN for the notice rule); default-bail window not yet open (day 40 of 60)",
             "record": "four documents only: charge-sheet status, custody certificate, antecedents and earlier orders are missing, so intake asks",
             "parity": "no co-accused; first-time offender (by counsel's answer); no earlier bail application"},
    documents=[
        Doc("01_fir.pdf", """FIRST INFORMATION REPORT (under Section 173 BNSS)
1. District: Pune City P.S.: PS-11 FIR No. 410/2026 Date: 20.09.2026
2. Acts and Sections: BNS 316(2).
3. Date of occurrence of offence: between 01.06.2026 and 31.08.2026
4. Date on which information was received at the P.S.: 20.09.2026
5. Type of information: written
6. Place of occurrence: the office of a trading firm, Pune City
7. Name of the complainant/informant: Complainant-1, proprietor of the firm
8. Name of the accused: Accused-1, the firm's accountant
9. Brief facts: Complainant-1 states that between June and August 2026 Accused-1, who was entrusted with the cash collections of
the firm, did not deposit collections amounting to Rs. 3,80,000 and made false entries in the cash book.
Investigating officer: IO-1"""),
        Doc("02_arrest_memo.pdf", """ARREST MEMO
FIR No. 410/2026, P.S. PS-11, Pune City. Sections: BNS 316(2).
Accused-1 was arrested on 05.10.2026 at 11:00 hrs at the office of the firm.
Notice of appearance under Section 35(3) BNSS: not issued.
Reasons for arrest: (this column is left blank).
A written note of the grounds of arrest was given to Accused-1 and his wife was informed the same day.
Arresting officer: IO-1"""),
        Doc("03_remand_order.pdf", """IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, PUNE
Remand order dated 06.10.2026
FIR No. 410/2026, P.S. PS-11. Sections: BNS 316(2).
The accused Accused-1 was arrested on 05.10.2026 and produced before this Court on 06.10.2026 at 13:00 hrs.
The accused is remanded to judicial custody until 20.10.2026. This is the first remand order, dated 06.10.2026."""),
        Doc("04_vakalatnama.pdf", """VAKALATNAMA
IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, PUNE
Application for regular bail under Section 480 BNSS on behalf of Accused-1.
In FIR No. 410/2026, P.S. PS-11, Pune City.
Counsel appointed for Accused-1 to apply for bail and to appear at every hearing of the application."""),
    ],
    answers=_common_answers(
        fir={"number": "410/2026", "police_station": "PS-11", "date": "2026-09-20"},
        first_time=True, pending="", charge_sheet=(False, None), previous=[], co_accused=[],
        custody=("The jail has not yet issued the certificate; it was applied for on 10.11.2026. Accused-1 has been in judicial custody "
                 "since his arrest on 05.10.2026 and has not been released."),
        arrest="2026-10-05", remand="2026-10-06", offence="2026-08-31", sections=[_sec("BNS 316(2)")]),
    counsel_edits=[
        ("personal", ["Accused-1 is 41 years old and has lived in Pune for 15 years in a rented flat.",
                      "He supports his wife, two school-going children and his father aged 72.",
                      "His employer holds the cash book and the bank statements; the amount is disputed.",
                      "His wife's brother is willing to stand surety; he does not hold a passport."],
         "Personal circumstances from counsel's instructions: 41, resident of Pune for 15 years, wife, two children and an aged father; "
         "the accounts are with the employer and the amount is disputed; a surety is available."),
    ],
)

CASES: list[DemoCase] = [_CASE_01, _CASE_02, _CASE_03, _CASE_04, _CASE_05, _CASE_06]
BY_SLUG = {c.slug: c for c in CASES}


# ---------------------------------------------------------------------------------------------------------------- PDFs

def notice_png() -> bytes:
    """The synthetic-document stamp as an image: visible on the page, absent from its text layer."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=500, height=16)
    page.insert_text((2, 12), NOTICE, fontsize=10, fontname="hebo", color=(0.65, 0.1, 0.1))
    png = page.get_pixmap(dpi=200).tobytes("png")
    doc.close()
    return png


def _stamp(page: Any, stamp: bytes) -> None:
    import pymupdf

    page.insert_image(pymupdf.Rect(48, 22, 548, 38), stream=stamp)
    page.insert_image(pymupdf.Rect(48, 806, 548, 822), stream=stamp)


def _text_page(body: str, stamp: bytes) -> Any:
    """A document holding one born-digital page: the stamp at the top and the foot, the body as text in between."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    _stamp(page, stamp)
    if page.insert_textbox(pymupdf.Rect(48, 56, 547, 790), body, fontsize=10.5, fontname="helv", lineheight=1.4) < 0:
        raise RuntimeError("text did not fit on one page")
    return doc


def write_pdf(path: Path, doc_spec: Doc, stamp: bytes) -> None:
    """Write one single-page PDF of the given kind ('text', 'hindi' or 'scan'); every kind carries the stamp at top and foot."""
    import pymupdf

    if doc_spec.kind == "text":
        doc = _text_page(doc_spec.body, stamp)
    elif doc_spec.kind == "hindi":
        from vakeel_sahayak.testsets import rendering

        pages = rendering.paginate(doc_spec.body, "hi")
        if len(pages) != 1:
            raise RuntimeError(f"Hindi text did not fit on one page: {path.name}")
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        _stamp(page, stamp)
        rendering._draw_text_page(page, pages[0], "hi")  # Devanagari with an exact Unicode text layer (Noto, shaped by MuPDF)
    elif doc_spec.kind == "scan":
        doc = _scan(doc_spec.body, stamp, seed=sum(map(ord, path.name)))
    else:
        raise ValueError(f"unknown document kind {doc_spec.kind!r}")
    doc.set_metadata({"producer": "vakeel-sahayak evaluator demo (synthetic)", "creator": "", "title": "", "author": "",
                      "creationDate": "", "modDate": ""})
    doc.save(path, deflate=True, garbage=3)
    doc.close()


def _scan(body: str, stamp: bytes, seed: int) -> Any:
    """An image-only page (no text layer): the born-digital page rasterised in grey at 150 dpi, slightly rotated, with speckle, as JPEG."""
    import pymupdf
    from PIL import Image, ImageFilter

    src = _text_page(body, stamp)
    png = src[0].get_pixmap(dpi=150, colorspace=pymupdf.csGRAY, alpha=False).tobytes("png")
    src.close()
    rng = random.Random(seed)
    img = Image.open(io.BytesIO(png)).convert("L")
    img = img.rotate(rng.uniform(-0.8, 0.8), resample=Image.BICUBIC, expand=False, fillcolor=255)
    px = img.load()
    w, h = img.size
    for _ in range(w * h // 400):  # light speckle, as on a photocopy
        x, y = rng.randrange(w), rng.randrange(h)
        px[x, y] = rng.choice((0, 90, 200))
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, stream=buf.getvalue())
    return doc


def write_documents(case: DemoCase, folder: Path) -> list[Path]:
    """Write every document of `case` into `folder` and return the paths in filing order."""
    folder.mkdir(parents=True, exist_ok=True)
    stamp = notice_png()
    paths = []
    for spec in case.documents:
        path = folder / spec.name
        write_pdf(path, spec, stamp)
        paths.append(path)
    return paths
