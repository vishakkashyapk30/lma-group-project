"""Voice intake: dictation, read-back confirmation, deletion of audio (plan §4.5)."""

from __future__ import annotations


def transcribe_dictation(audio_path: str) -> str:
    """Transcribe on the laptop.

    Args:
        audio_path: see behaviour

    Returns:
        Transcript.
    """
    raise NotImplementedError


def readback(transcript: str) -> list[str]:
    """Dates, sections and numbers heard, for counsel to confirm (dictated facts are USER_STATED).

    Args:
        transcript: see behaviour

    Returns:
        Items to confirm.
    """
    raise NotImplementedError


def delete_audio(audio_path: str, keep: bool = False) -> None:
    """Delete audio after transcription unless counsel keeps it.

    Args:
        audio_path: see behaviour
        keep: see behaviour
    """
    raise NotImplementedError
