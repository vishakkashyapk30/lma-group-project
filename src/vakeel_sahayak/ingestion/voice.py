"""Voice intake: dictation, read-back confirmation, deletion of audio (plan §4.5).

Counsel dictates in Hindi, English or a mix. The audio is transcribed on the laptop, Munshi reads back the dates,
sections and numbers it heard for counsel to confirm, dictated facts are filed as USER_STATED, and the audio is
deleted after transcription unless counsel keeps it.
"""

from __future__ import annotations

import re
from pathlib import Path

from vakeel_sahayak.ingestion.hindi import normalise_for_extraction
from vakeel_sahayak.models.base import AsrClient
from vakeel_sahayak.pipelines.order_facts import DATE_RE
from vakeel_sahayak.pipelines.section_extract import extract_sections
from vakeel_sahayak.pipelines.text_utils import normalise_date

_FIR_NO = re.compile(r"\bF\.?I\.?R\.?\s*(?:no\.?|number|क्रमांक)?\s*[:#-]?\s*(\d{1,6})\s*(?:/|of)\s*(\d{2,4})", re.IGNORECASE)
_ONES = "first second third fourth fifth sixth seventh eighth ninth".split()
_ORDINALS = {
    **{w: i for i, w in enumerate(_ONES, 1)},
    **dict(zip("tenth eleventh twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth".split(), range(10, 20), strict=True)),
    "twentieth": 20,
    "thirtieth": 30,
    **{f"twenty[ -]{w}": 20 + i for i, w in enumerate(_ONES, 1)},
    "thirty[ -]first": 31,
}
_MONTHS = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
_SPOKEN_DAY = re.compile(
    rf"\b(?:the\s+)?({'|'.join(sorted(_ORDINALS, key=len, reverse=True))})\s+(?:of\s+)?(?=(?:{_MONTHS})[a-z]*\b)", re.IGNORECASE
)
_DURATION = re.compile(r"\b(\d{1,3})\s*(days?|months?|years?|दिन|महीने|माह|वर्ष|साल)\b", re.IGNORECASE)
_AGE = re.compile(r"\b(?:aged?|उम्र|आयु)\s*(?:about\s*)?(\d{1,3})\b", re.IGNORECASE)


def transcribe_dictation(audio_path: str, lang_hint: str | None = None, asr: AsrClient | None = None) -> str:
    """Transcribe on the laptop.

    Args:
        audio_path: see behaviour
        lang_hint: 'hi', 'en' or None for mixed dictation
        asr: speech client (default: the configured one, `models.factory.get_asr`)

    Returns:
        Transcript.

    Raises:
        ModelUnavailable: no speech-recognition model is installed.
        FileNotFoundError: the audio file does not exist.
    """
    if not Path(audio_path).is_file():
        raise FileNotFoundError(f"audio file not found: {audio_path}")
    if asr is None:
        from vakeel_sahayak.models.factory import get_asr

        asr = get_asr()
    return asr.transcribe(audio_path, lang_hint).strip()


def spoken_days_to_digits(text: str) -> str:
    """'twentieth August 2024' becomes '20 August 2024' (speech recognition often writes the day as an ordinal word)."""

    def repl(m: re.Match[str]) -> str:
        key = re.sub(r"[ -]+", " ", m.group(1).lower())
        for pattern, day in _ORDINALS.items():
            if re.fullmatch(pattern, key):
                return f"{day} "
        return m.group(0)

    return _SPOKEN_DAY.sub(repl, text)


def readback(transcript: str) -> list[str]:
    """Dates, sections and numbers heard, for counsel to confirm (dictated facts are USER_STATED).

    Args:
        transcript: see behaviour

    Returns:
        Items to confirm, such as 'date: 2024-08-20 (heard as "20 August 2024")', 'section: BNS 318(4)',
        'FIR number: 112/2024', 'duration: 45 days', 'age: 34'.
    """
    text = spoken_days_to_digits(normalise_for_extraction(transcript))
    items: list[str] = []
    for m in DATE_RE.finditer(text):
        iso = normalise_date(m.group(0).replace(",", ", ").strip())
        if iso:
            items.append(f'date: {iso} (heard as "{m.group(0)}")')
    items += [f"section: {ref}" for ref in extract_sections(text)]
    items += ["FIR number: " + f"{m.group(1)}/{m.group(2)}" for m in _FIR_NO.finditer(text)]
    items += [f"duration: {m.group(1)} {m.group(2).lower()}" for m in _DURATION.finditer(text)]
    items += [f"age: {m.group(1)}" for m in _AGE.finditer(text)]
    return list(dict.fromkeys(items))


def readback_question(items: list[str]) -> str:
    """One question that reads the items back to counsel and asks for confirmation."""
    return "I heard: " + "; ".join(items) + ". Is that correct?"


def delete_audio(audio_path: str, keep: bool = False) -> None:
    """Delete audio after transcription unless counsel keeps it.

    Args:
        audio_path: see behaviour
        keep: see behaviour
    """
    if keep:
        return
    Path(audio_path).unlink(missing_ok=True)
