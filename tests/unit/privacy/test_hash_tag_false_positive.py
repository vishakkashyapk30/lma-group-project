"""The spotlight delimiter's hash tag is not a phone or ID number; real client numbers are still refused."""

from __future__ import annotations

import pytest

from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_pseudonymised
from vakeel_sahayak.privacy.injection_guard import wrap_untrusted
from vakeel_sahayak.privacy.pseudonymise import _PII, pseudonymise_text
from vakeel_sahayak.schemas.common import SourceRef


def _pii(text: str) -> bool:
    return any(p.search(text) for p, _ in _PII)


@pytest.mark.parametrize("tag", ["cc9937724702", "9937724702ab", "a99377247021", "0f6987654321", "98765432101a"])
def test_hex_tag_is_not_pii_in_pseudonymiser_patterns(tag):
    assert not _pii(f"<<<UNTRUSTED_DOCUMENT_DATA {tag}>>>")
    assert not _pii(f"id {tag} end")


@pytest.mark.parametrize("tag", ["cc9937724702", "9937724702ab", "123456789012", "987654321098"])
def test_boundary_accepts_a_spotlight_block_whose_tag_looks_numeric(tag):
    wrapped = f"<<<UNTRUSTED_DOCUMENT_DATA {tag}>>>\n[doc=x] data\nAccused-1 was arrested.\n<<<END_UNTRUSTED_DOCUMENT_DATA {tag}>>>"
    assert assert_pseudonymised({"case": wrapped}) is None


def test_boundary_accepts_real_wrapped_text_for_many_sources():
    for i in range(300):
        w = wrap_untrusted("Accused-1 was arrested.", SourceRef(doc=f"doc{i}"))
        assert_pseudonymised({"case": w})


@pytest.mark.parametrize(
    "text",
    ["call 9876543210 now", "Mob: +91 98765 43210", "+91-9876543210", "phone9876543210", "Ph.No.9876543210.", "Aadhaar 1234 5678 9012", "UID 123456789012",
     "id: 2345-6789-0123".replace("-", " "), "mobile 9876543210abc".replace("abc", ""), "x9876543210"],
)
def test_real_numbers_are_still_pii(text):
    assert _pii(text)
    with pytest.raises(PrivacyBoundaryError):
        assert_pseudonymised({"facts": text})


def test_a_real_phone_number_next_to_a_spotlight_block_is_still_refused():
    wrapped = "<<<UNTRUSTED_DOCUMENT_DATA cc9937724702>>>\nContact 9876543210\n<<<END_UNTRUSTED_DOCUMENT_DATA cc9937724702>>>"
    with pytest.raises(PrivacyBoundaryError):
        assert_pseudonymised({"case": wrapped})


def test_pseudonymiser_masks_phone_but_leaves_the_tag():
    out, _ = pseudonymise_text("<<<UNTRUSTED_DOCUMENT_DATA cc9937724702>>> call 9876543210", "c1")
    assert "cc9937724702" in out and "9876543210" not in out
