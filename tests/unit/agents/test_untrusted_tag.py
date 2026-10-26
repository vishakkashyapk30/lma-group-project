"""The spotlight delimiter tag is a hash prefix; a tag with ten digits in a row looked like a phone number to the privacy boundary and blocked an
innocent open-issue text (S10 isolation-off run on the real-store dev case). the privacy boundary now ignores such a tag, and `BaseAgent.untrusted` wraps every text unchanged."""

from __future__ import annotations

import re

from tests.unit.agents._helpers import build_agent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.privacy.boundary import _find_problems
from vakeel_sahayak.privacy.injection_guard import wrap_untrusted
from vakeel_sahayak.schemas.common import SourceRef

PHONE_LIKE_TAG_TEXT = "open issue 462"  # sha256 tag b8519730609c: ten digits in a row
OPEN = SourceRef(doc="open issue")


def test_a_phone_like_tag_passes_the_boundary_without_any_re_derivation():
    # RECONCILED: the root cause is fixed in privacy/ (hex-token guard in the phone and ID patterns, spotlight delimiter skipped by the boundary), so the
    # wrapper no longer re-derives the tag; the same text must pass the boundary as wrapped by `wrap_untrusted`.
    raw = wrap_untrusted(PHONE_LIKE_TAG_TEXT, OPEN)
    assert "b8519730609c" in raw
    assert not [p for p in _find_problems({"c": {"x": raw}}, None, None) if "email, phone or ID number" in p]
    agent, _, _ = build_agent(VakeelAgent)
    wrapped = agent.untrusted(PHONE_LIKE_TAG_TEXT, OPEN)
    assert wrapped == raw and PHONE_LIKE_TAG_TEXT in wrapped
    assert not [p for p in _find_problems({"c": {"x": wrapped}}, None, None) if "email, phone or ID number" in p]


def test_an_ordinary_text_is_wrapped_exactly_as_before():
    agent, _, _ = build_agent(VakeelAgent)
    text = "Antecedents unknown: confirm with counsel whether any other case is pending."
    assert not re.search(r"[6-9]\d{9}|\d{12}", re.search(r"DATA (\w+)>>>", wrap_untrusted(text, OPEN)).group(1))
    assert agent.untrusted(text, OPEN) == wrap_untrusted(text, OPEN)
