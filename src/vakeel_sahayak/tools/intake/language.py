"""Tools in intake.language (plan §4.5). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec
from vakeel_sahayak.tools.types import TranscriptResult


def translate(text: str, src: str = "hi", tgt: str = "en") -> str:
    """IndicTrans2 translation; keep both texts. (plan §4.5)

    Args:
        text: see behaviour
        src: see behaviour
        tgt: see behaviour

    Returns:
        Translation.
    """
    raise NotImplementedError


def transcribe(audio_path: str, lang_hint: str | None = None) -> TranscriptResult:
    """Speech recognition on the laptop (Whisper or IndicConformer). (plan §4.5)

    Args:
        audio_path: see behaviour
        lang_hint: see behaviour

    Returns:
        TranscriptResult.
    """
    raise NotImplementedError


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
