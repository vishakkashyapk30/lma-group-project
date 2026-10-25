"""Constructed companion documents on public layouts (IIF-1 FIR, remand order, custody certificate) filled with the case's G3 values and Faker names (plan §2 source 6, §15.2 T2).

Every value in a document comes from the record (`fir.number`, `fir.police_station`, `fir.date`, `offence_date`, `sections`, `arrest_date`,
`first_remand`, `custody_days`, `as_of`), so each field has a known answer by construction; the names and places are synthetic (Faker, seeded from
the record, so the same record always gives the same text). The Hindi versions (`lang="hi"`) are templated from a bilingual glossary: the labels and
the sentences are Hindi, the numbers, dates and section strings stay as they are, and the names come from Faker's Hindi locale. No translation model is
used; a Sarvam-Translate path (only under `public_scope()` with a key set) is not wired because nothing here needs it.

Layouts follow the public forms: the FIR is the Integrated Investigation Form-1 (First Information Report under section 173 BNSS) with its numbered
fields; the remand order and the custody certificate follow the ordinary court and jail formats.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Any

from vakeel_sahayak.testsets.common import faker_names

PLACES_EN = ["Kotwali", "Civil Lines", "Sadar Bazar", "Model Town", "Railway Colony", "Gandhi Nagar", "Station Road", "Market Area"]
PLACES_HI = ["कोतवाली", "सिविल लाइन्स", "सदर बाज़ार", "मॉडल टाउन", "रेलवे कॉलोनी", "गांधी नगर", "स्टेशन रोड", "बाज़ार क्षेत्र"]
DISTRICTS_EN = ["Pune", "Lucknow", "Patna", "Jaipur", "Bhopal", "Nagpur", "Indore", "Raipur"]
DISTRICTS_HI = ["पुणे", "लखनऊ", "पटना", "जयपुर", "भोपाल", "नागपुर", "इंदौर", "रायपुर"]


def _seed(record: dict[str, Any], salt: str) -> int:
    blob = json.dumps(record, sort_keys=True, default=str, ensure_ascii=False) + salt
    return int(hashlib.sha256(blob.encode()).hexdigest()[:8], 16)


def _dmy(iso: Any) -> str:
    if not isinstance(iso, str) or len(iso) != 10:
        return "not recorded"
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return "not recorded"
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def _sections(record: dict[str, Any]) -> str:
    sections = record.get("sections") or []
    return ", ".join(str(s) for s in sections) if sections else "not recorded"


def _fir(record: dict[str, Any]) -> dict[str, Any]:
    return record.get("fir") if isinstance(record.get("fir"), dict) else {}


def _pick(options: list[str], record: dict[str, Any], salt: str) -> str:
    return options[_seed(record, salt) % len(options)]


def _as_of(record: dict[str, Any]) -> str | None:
    if isinstance(record.get("as_of"), str):
        return record["as_of"]
    arrest, days = record.get("arrest_date"), record.get("custody_days")
    if isinstance(arrest, str) and isinstance(days, int):
        return (date.fromisoformat(arrest) + timedelta(days=days)).isoformat()
    return None


def _locale(lang: str) -> str:
    return "hi_IN" if lang == "hi" else "en_IN"


def make_fir(g3_record: dict[str, Any], lang: str = "hi") -> str:
    """FIR text on the IIF-1 layout (English, or Hindi from the templated glossary).

    Args:
        g3_record: see behaviour
        lang: "en" or "hi"

    Returns:
        Text.
    """
    r = g3_record
    fir = _fir(r)
    informant, accused, officer = faker_names(_seed(r, "fir"), 3, _locale(lang))
    hi = lang == "hi"
    station = fir.get("police_station") or "not recorded"
    place = _pick(PLACES_HI if hi else PLACES_EN, r, "place")
    district = _pick(DISTRICTS_HI if hi else DISTRICTS_EN, r, "district")
    lines = (
        [
            "प्रथम सूचना रिपोर्ट (भारतीय नागरिक सुरक्षा संहिता की धारा 173 के अंतर्गत)",
            "एकीकृत जांच प्रपत्र-1 (IIF-1)",
            f"1. जिला: {district}    थाना: {station}    प्रथम सूचना रिपोर्ट सं. {fir.get('number', 'दर्ज नहीं')}    दिनांक: {_dmy(fir.get('date'))}",
            f"2. अधिनियम और धाराएं: {_sections(r)}",
            f"3. अपराध की तिथि: {_dmy(r.get('offence_date'))}",
            f"4. थाने में सूचना प्राप्ति की तिथि: {_dmy(fir.get('date'))}",
            "5. सूचना का प्रकार: लिखित",
            f"6. घटना स्थल: {place}, जिला {district}",
            f"7. सूचनाकर्ता का नाम: {informant}",
            f"8. आरोपी का नाम: {accused}",
            f"9. आरोपी की गिरफ्तारी की तिथि: {_dmy(r.get('arrest_date'))}",
            "10. संक्षिप्त तथ्य: सूचनाकर्ता की शिकायत पर मामला दर्ज किया गया और जांच शुरू की गई।",
            f"जांच अधिकारी: {officer}",
        ]
        if hi
        else [
            "FIRST INFORMATION REPORT (under Section 173 BNSS)",
            "Integrated Investigation Form-1 (IIF-1)",
            f"1. District: {district}    P.S.: {station}    FIR No. {fir.get('number', 'not recorded')}    Date: {_dmy(fir.get('date'))}",
            f"2. Acts and Sections: {_sections(r)}",
            f"3. Date of occurrence of offence: {_dmy(r.get('offence_date'))}",
            f"4. Date on which information was received at the P.S.: {_dmy(fir.get('date'))}",
            "5. Type of information: written",
            f"6. Place of occurrence: {place}, District {district}",
            f"7. Name of the complainant/informant: {informant}",
            f"8. Name of the accused: {accused}",
            f"9. Date of arrest of the accused: {_dmy(r.get('arrest_date'))}",
            "10. Brief facts: the case was registered on the written complaint of the informant and investigation was taken up.",
            f"Investigating officer: {officer}",
        ]
    )
    return "\n".join(lines) + "\n"


def make_remand_order(g3_record: dict[str, Any], lang: str = "en") -> str:
    """Remand order text (English, or Hindi from the templated glossary).

    Args:
        g3_record: see behaviour
        lang: "en" or "hi"

    Returns:
        Text.
    """
    r = g3_record
    fir = _fir(r)
    magistrate, accused = faker_names(_seed(r, "remand"), 2, _locale(lang))
    first = r.get("first_remand")
    until = _dmy((date.fromisoformat(first) + timedelta(days=14)).isoformat()) if isinstance(first, str) and len(first) == 10 else "not recorded"
    if lang == "hi":
        return "\n".join(
            [
                "न्यायिक मजिस्ट्रेट के न्यायालय में",
                f"रिमांड आदेश दिनांक {_dmy(first)}",
                f"प्रथम सूचना रिपोर्ट सं. {fir.get('number', 'दर्ज नहीं')}, थाना {fir.get('police_station', 'दर्ज नहीं')}, धाराएं {_sections(r)}।",
                f"आरोपी {accused} को दिनांक {_dmy(r.get('arrest_date'))} को गिरफ्तार किया गया और दिनांक {_dmy(first)} को न्यायालय में पेश किया गया।",
                f"आरोपी को दिनांक {until} तक न्यायिक अभिरक्षा में रिमांड पर भेजा जाता है। यह प्रथम रिमांड आदेश है।",
                f"मजिस्ट्रेट: {magistrate}",
            ]
        ) + "\n"
    return "\n".join(
        [
            "IN THE COURT OF THE JUDICIAL MAGISTRATE",
            f"Remand order dated {_dmy(first)}",
            f"FIR No. {fir.get('number', 'not recorded')}, P.S. {fir.get('police_station', 'not recorded')}, Sections {_sections(r)}.",
            f"The accused {accused} was arrested on {_dmy(r.get('arrest_date'))} and produced before this Court on {_dmy(first)}.",
            f"The accused is remanded to judicial custody until {until}. This is the first remand order, dated {_dmy(first)}.",
            f"Magistrate: {magistrate}",
        ]
    ) + "\n"


def make_custody_certificate(g3_record: dict[str, Any], lang: str = "en") -> str:
    """Custody certificate text (English, or Hindi from the templated glossary).

    Args:
        g3_record: see behaviour
        lang: "en" or "hi"

    Returns:
        Text.
    """
    r = g3_record
    fir = _fir(r)
    superintendent, accused = faker_names(_seed(r, "custody"), 2, _locale(lang))
    as_of, days = _as_of(r), r.get("custody_days")
    if lang == "hi":
        lines = [
            "अभिरक्षा प्रमाण पत्र",
            f"जिला कारागार के अधीक्षक द्वारा दिनांक {_dmy(as_of)} को जारी।",
            f"प्रमाणित किया जाता है कि {accused} प्रथम सूचना रिपोर्ट सं. {fir.get('number', 'दर्ज नहीं')} में दिनांक {_dmy(r.get('arrest_date'))} से अभिरक्षा में है।",
        ]
        if isinstance(days, int):
            lines.append(f"दिनांक {_dmy(as_of)} तक अभिरक्षा की अवधि {days} दिन है।")
        lines.append(f"अधीक्षक: {superintendent}")
        return "\n".join(lines) + "\n"
    lines = [
        "CUSTODY CERTIFICATE",
        f"Issued by the Superintendent, District Jail, on {_dmy(as_of)}.",
        f"It is certified that {accused} has been in custody in FIR No. {fir.get('number', 'not recorded')} since {_dmy(r.get('arrest_date'))}.",
    ]
    if isinstance(days, int):
        lines.append(f"The period of custody as on {_dmy(as_of)} is {days} days.")
    lines.append(f"Superintendent: {superintendent}")
    return "\n".join(lines) + "\n"


def make_hindi_order(g3_record: dict[str, Any], court: str | None = None) -> str:
    """A short Hindi order summary templated from the record (the Hindi stand-in for a T1 order, which is English; no translation is used).

    Args:
        g3_record: see behaviour
        court: the court's name from T1, written as it is

    Returns:
        Text.
    """
    r = g3_record
    fir = _fir(r)
    accused, counsel = faker_names(_seed(r, "order-hi"), 2, "hi_IN")
    return "\n".join(
        [
            f"माननीय न्यायालय{(' - ' + court) if court else ''}",
            "जमानत आवेदन पर आदेश",
            f"प्रथम सूचना रिपोर्ट सं. {fir.get('number', 'दर्ज नहीं')}, थाना {fir.get('police_station', 'दर्ज नहीं')}, धाराएं {_sections(r)}।",
            f"आवेदक {accused} को दिनांक {_dmy(r.get('arrest_date'))} को गिरफ्तार किया गया। आवेदक की ओर से अधिवक्ता {counsel} उपस्थित हुए।",
            "आवेदक ने नियमित जमानत की प्रार्थना की है। अभियोजन पक्ष को सुना गया और अभिलेख का अवलोकन किया गया।",
        ]
    ) + "\n"
