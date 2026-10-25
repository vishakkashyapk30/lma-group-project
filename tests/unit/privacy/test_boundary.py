"""Outbound boundary (plan §16, skeleton §2 'Privacy and safety').

Only pseudonymised text may be sent to Ada: a payload carrying page images, audio or un-pseudonymised text is rejected.
ASSUMPTION: a rejection raises AssertionError, ValueError or PermissionError (never a bare RuntimeError).
"""

from __future__ import annotations

import pytest

from tests.fakes.data import PLANTED_NAMES, PLANTED_NAMES_HI
from tests.unit.privacy._helpers import EN_TEXT, PNG_BYTES, WAV_BYTES, rejects
from vakeel_sahayak.privacy.boundary import assert_pseudonymised
from vakeel_sahayak.privacy.pseudonymise import pseudonymise_text

PSEUDONYMISED = (
    "The accused Accused-1 was arrested on 20.08.2024. Co-accused-1 was granted bail on 05.12.2024. "
    "Complainant-1 deposed before the Magistrate."
)


def test_pseudonymised_text_payload_passes():
    """Plan §16: a payload of pseudonymised text is allowed (returns None, raises nothing)."""
    assert assert_pseudonymised({"case_id": "case-0007", "prompt": PSEUDONYMISED, "factor": "parity_with_co_accused"}) is None


def test_output_of_pseudonymise_text_passes_the_boundary():
    """Plan §16: the real pipeline output clears the boundary."""
    out, _ = pseudonymise_text(EN_TEXT, "case-0007")
    assert_pseudonymised({"prompt": out})


def test_nested_pseudonymised_payload_passes():
    """Plan §16: nested messages of pseudonymised text pass."""
    assert_pseudonymised({"messages": [{"role": "user", "content": PSEUDONYMISED}], "meta": {"n": 1}})


@pytest.mark.parametrize("name", PLANTED_NAMES + PLANTED_NAMES_HI)
def test_payload_with_a_planted_name_is_rejected(name):
    """Plan §16/T7: a planted real name in outbound text is rejected."""
    with rejects():
        assert_pseudonymised({"prompt": f"The accused {name} was arrested on 20.08.2024."})


def test_planted_name_in_a_nested_field_is_rejected():
    """Plan §16/T7: the check looks inside nested payloads."""
    with rejects():
        assert_pseudonymised({"messages": [{"role": "user", "content": "Surety is Anil Pratap Singh."}]})


def test_page_image_bytes_are_rejected():
    """Plan §16: raw page-image bytes never leave the laptop."""
    with rejects():
        assert_pseudonymised({"page_image": PNG_BYTES, "prompt": PSEUDONYMISED})


def test_page_image_bytes_nested_in_a_list_are_rejected():
    """Plan §16: images hidden in nested structures are still caught."""
    with rejects():
        assert_pseudonymised({"pages": [{"n": 1, "data": PNG_BYTES}]})


def test_audio_bytes_are_rejected():
    """Plan §16: raw audio bytes never leave the laptop."""
    with rejects():
        assert_pseudonymised({"audio": WAV_BYTES})


@pytest.mark.parametrize("path", ["/home/counsel/cases/case-0007/hearing.wav", "voice_note.mp3", "intake/statement.m4a"])
def test_audio_file_path_is_rejected(path):
    """Plan §16: an audio file path (as key value) in the payload is rejected."""
    with rejects():
        assert_pseudonymised({"audio_path": path})


def test_payload_passes_once_the_image_is_removed():
    """Plan §16: dropping the image from the same payload makes it pass (the image was the only violation)."""
    payload = {"page_image": PNG_BYTES, "prompt": PSEUDONYMISED}
    with rejects():
        assert_pseudonymised(payload)
    del payload["page_image"]
    assert_pseudonymised(payload)


def test_corpus_document_ids_are_not_mistaken_for_id_numbers():
    """A court-order id such as JHHC010343052023 holds 12 digits but is an identifier (in an id field or in running text); 12 bare digits are still refused."""
    import pytest

    from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_pseudonymised

    assert_pseudonymised({"tool": "get_orders", "args": {"doc_ids": ["JHHC010343052023", "DLHC-2022-1187"]}})
    assert_pseudonymised({"text": "See HPHC010225332022 para 6."})
    for payload in ({"args": {"note": "010343052023"}}, {"args": {"doc_ids": ["010343052023"]}}, {"text": "Aadhaar 1234 5678 9012"}):
        with pytest.raises(PrivacyBoundaryError):
            assert_pseudonymised(payload)
