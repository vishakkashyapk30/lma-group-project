"""Tools in intake.language (plan §4.5). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from pathlib import Path

from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.ingestion.source import AUDIO_SUFFIXES
from vakeel_sahayak.ingestion.voice import transcribe_dictation
from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolError, ToolSpec
from vakeel_sahayak.tools.intake._common import check_file, guarded
from vakeel_sahayak.tools.store_call import invalid
from vakeel_sahayak.tools.types import TranscriptResult


def translate(text: str, src: str = "hi", tgt: str = "en") -> str | ToolError:
    """IndicTrans2 translation; keep both texts. (plan §4.5)

    Args:
        text: see behaviour
        src: 'hi'
        tgt: 'en'

    Returns:
        Translation. The caller keeps the original (an offline run uses a marked word-level glossary, not IndicTrans2).
    """
    if not isinstance(text, str) or not text.strip():
        return invalid("translate", "text must not be empty")
    if (src, tgt) != ("hi", "en"):
        return invalid("translate", f"only hi to en is supported, got {src!r} to {tgt!r}")
    from vakeel_sahayak.ingestion.hindi import translate_keeping_original

    return guarded("translate", lambda: translate_keeping_original(text).english)


def transcribe(audio_path: str, lang_hint: str | None = None) -> TranscriptResult | ToolError:
    """Speech recognition on the laptop (Whisper or IndicConformer). (plan §4.5)

    Args:
        audio_path: see behaviour
        lang_hint: 'hi', 'en', 'mixed' or None

    Returns:
        TranscriptResult. The audio file is left in place: Munshi deletes it after transcription unless counsel keeps it.
    """
    if err := check_file("transcribe", audio_path):
        return err
    if Path(audio_path).suffix.lower() not in AUDIO_SUFFIXES:
        return invalid("transcribe", f"not an audio file: use one of {sorted(AUDIO_SUFFIXES)}")
    if lang_hint not in (None, "hi", "en", "mixed"):
        return invalid("transcribe", f"lang_hint must be 'hi', 'en', 'mixed' or null, got {lang_hint!r}")

    def run() -> TranscriptResult:
        text = transcribe_dictation(audio_path, None if lang_hint == "mixed" else lang_hint)
        return TranscriptResult(text=text, lang=lang_of(text) if text.strip() else lang_hint)

    return guarded("transcribe", run)


TRANSLATE_SPEC = ToolSpec(
    name="translate",
    description="IndicTrans2 translation; keep both texts.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.5",
)

TRANSCRIBE_SPEC = ToolSpec(
    name="transcribe",
    description="Speech recognition on the laptop (Whisper or IndicConformer).",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§4.5",
)
