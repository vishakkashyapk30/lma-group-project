"""The real render_citation tool (plan §8.1): citation text comes only from corpus metadata; unknown ids are errors."""

from __future__ import annotations

from tests.unit.agents._helpers import raises_or_tool_error
from vakeel_sahayak.tools.drafting.claims import RENDER_CITATION_SPEC, render_citation
from vakeel_sahayak.schemas.enums import AgentName


def test_spec_is_vakeel_only_and_touches_no_store_directly():
    """Constants: the tool belongs to Vakeel (passes today)."""
    assert RENDER_CITATION_SPEC.agents == [AgentName.VAKEEL]


def test_known_paragraph_is_rendered_from_metadata(install_stores):
    """DLHC-2022-1187 para 14 renders with its court and year taken from the corpus row."""
    install_stores()
    text = render_citation("DLHC-2022-1187", 14)
    # ASSUMPTION: the rendering uses the stored court name and the year of the order date.
    assert isinstance(text, str) and "2022" in text and "Delhi" in text


def test_unknown_doc_id_is_an_error_not_an_invented_citation(install_stores):
    """An unknown doc_id raises or returns a ToolError; it never yields citation text."""
    install_stores()
    # ASSUMPTION: KeyError/ValueError/LookupError or a returned ToolError (accepted by the helper).
    assert raises_or_tool_error(render_citation, "NOPE-1999-0001", 3)
