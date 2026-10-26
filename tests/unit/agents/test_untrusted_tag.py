"""The spotlight delimiter tag is a hash prefix; a tag with ten digits in a row looked like a phone number to the privacy boundary and blocked an
innocent open-issue text (S10 isolation-off run on the real-store dev case). `BaseAgent.untrusted` re-derives such a tag; every other text is wrapped exactly as before."""

from __future__ import annotations

import re

from tests.unit.agents._helpers import build_agent
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.privacy.boundary import _find_problems
from vakeel_sahayak.privacy.injection_guard import wrap_untrusted
from vakeel_sahayak.schemas.common import SourceRef

PHONE_LIKE_TAG_TEXT = "open issue 462"  # sha256 tag b8519730609c: ten digits in a row
OPEN = SourceRef(doc="open issue")


def test_a_phone_like_tag_is_re_derived_and_passes_the_boundary():
    raw = wrap_untrusted(PHONE_LIKE_TAG_TEXT, OPEN)
    assert any("email, phone or ID number" in p for p in _find_problems({"c": {"x": raw}}, None, None))  # the unfixed wrapper trips the boundary
    agent, _, _ = build_agent(VakeelAgent)
    wrapped = agent.untrusted(PHONE_LIKE_TAG_TEXT, OPEN)
    assert PHONE_LIKE_TAG_TEXT in wrapped and "UNTRUSTED_DOCUMENT_DATA" in wrapped
    assert not [p for p in _find_problems({"c": {"x": wrapped}}, None, None) if "email, phone or ID number" in p]


def test_an_ordinary_text_is_wrapped_exactly_as_before():
    agent, _, _ = build_agent(VakeelAgent)
    text = "Antecedents unknown: confirm with counsel whether any other case is pending."
    assert not re.search(r"[6-9]\d{9}|\d{12}", re.search(r"DATA (\w+)>>>", wrap_untrusted(text, OPEN)).group(1))
    assert agent.untrusted(text, OPEN) == wrap_untrusted(text, OPEN)
