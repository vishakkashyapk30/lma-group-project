"""`check_claim` and `render_citation` (plan §8.1, §5.3, §5.1).

check_claim(claim, refs): authority support (NLI of the cited paragraph against the claim), the good-law flag, and 'no citation that was not
retrieved'. Refs are written `A:<doc_id>#<para>` (authority) and `F:<field>` (fact). Rules under test:

* an OVERRULED authority BLOCKS the claim: `supported` is False even when the paragraph supports the sentence; DISTINGUISHED is shown
  but does not block;
* a reference that does not exist is reported in `unretrieved_citations` and blocks the claim;
* authorities are REASONING paragraphs only: a reference to a defense or prosecution submission is not a valid authority;
* `render_citation` renders text from corpus metadata only: the model writes only ids, so no model call is needed or allowed.

The NLI client is the overlap-based FakeNli (a changed date or number flips a claim to unsupported).
# SKELETON-GAP: `check_claim(claim, refs)` has no case id, so the fact-support check against the dossier quote (`F:` refs) and the transfer flag
# (which compares the paragraph's IPC section with the case's BNS section) cannot be exercised on the tool alone; both are tested through the
# Vakeel agent in tests/unit/agents/vakeel/test_checking.py.
"""

from __future__ import annotations

import pytest

from tests.fakes.models import FakeNli, ScriptedLLM
from tests.unit.tools_case._helpers import assert_tool_error, install_recording_stores, stores_touched
from tests.unit.truth_maintenance._helpers import install_llm
from vakeel_sahayak.schemas.enums import AgentName, GoodLawStatus, StoreName, Treatment
from vakeel_sahayak.schemas.store_rows import CitationEdge
from vakeel_sahayak.tools.drafting.claims import CHECK_CLAIM_SPEC, RENDER_CITATION_SPEC, check_claim, render_citation
from vakeel_sahayak.tools.types import ClaimCheckResult

PARITY_CLAIM = "Co-accused with an identical role has been enlarged on bail; parity requires the same relief"  # = DLHC-2022-1187#14
OVERRULED_CLAIM = "The role attributed to the petitioner distinguishes him from the co-accused"  # = DLHC-2023-0911#12 (overruled)
DISTINGUISHED_CLAIM = "Delay in trial; Article 21"  # = BOMHC-2024-0355#8


@pytest.fixture()
def rig(world, monkeypatch):
    install_llm(monkeypatch, ScriptedLLM(strict=False, default=""), FakeNli())
    return install_recording_stores(monkeypatch, world)


# ---------------------------------------------------------------- check_claim
def test_a_supported_claim_with_a_good_authority_passes(rig):
    res = check_claim(PARITY_CLAIM, ["A:DLHC-2022-1187#14"])
    assert isinstance(res, ClaimCheckResult) and res.supported is True
    assert res.authority_support is not None and res.authority_support >= 0.5
    assert res.good_law == GoodLawStatus.OK and res.unretrieved_citations == []


def test_a_claim_the_paragraph_does_not_support_fails(rig):
    """A changed date makes the sentence unsupported by the cited paragraph (fake NLI), so the claim is not SUPPORTED."""
    res = check_claim("Co-accused was granted bail on 05.12.2024 after an identical role was found", ["A:DLHC-2022-1187#14"])
    assert res.supported is False


def test_an_overruled_authority_blocks_the_claim_even_if_the_paragraph_supports_it(rig):
    """Plan §5.3: an overruled precedent 'cannot be cited without a warning': the sentence matches DLHC-2023-0911#12 word for word, but
    that order is overruled by SC-2020-0100, so supported is False and the flag is OVERRULED."""
    res = check_claim(OVERRULED_CLAIM, ["A:DLHC-2023-0911#12"])
    assert res.authority_support is not None and res.authority_support >= 0.5
    assert res.good_law == GoodLawStatus.OVERRULED and res.supported is False


def test_a_distinguished_authority_is_shown_but_does_not_block(world, rig):
    world.stores[StoreName.CASELAW_CITATIONS].edges.append(
        CitationEdge(citing_doc_id="DLHC-2024-0777", cited_doc_id="BOMHC-2024-0355", treatment=Treatment.DISTINGUISHED))
    res = check_claim(DISTINGUISHED_CLAIM, ["A:BOMHC-2024-0355#8"])
    assert res.good_law == GoodLawStatus.DISTINGUISHED and res.supported is True


def test_one_overruled_reference_among_good_ones_still_blocks(rig):
    """The most severe flag over all the claim's authorities wins."""
    res = check_claim(OVERRULED_CLAIM + ". " + PARITY_CLAIM, ["A:DLHC-2022-1187#14", "A:DLHC-2023-0911#12"])
    assert res.good_law == GoodLawStatus.OVERRULED and res.supported is False


@pytest.mark.parametrize("ref", ["A:NOPE-1999-0001#3", "A:DLHC-2022-1187#999"])
def test_a_citation_that_was_not_retrieved_is_reported_and_blocks(rig, ref):
    """'No citation that wasn't retrieved': an id or paragraph that does not exist comes back in unretrieved_citations. # ASSUMPTION: the
    reference string is reported as given."""
    res = check_claim(PARITY_CLAIM, [ref])
    assert res.unretrieved_citations == [ref] and res.supported is False


@pytest.mark.parametrize("ref", ["A:DLHC-2022-1187#9", "A:DLHC-2023-0911#6"])
def test_defense_and_prosecution_paragraphs_are_not_valid_authorities(rig, ref):
    """Argument and objection banks are for coverage and phrasing, never authority (plan §5.1): DLHC-2022-1187#9 (defense) and
    DLHC-2023-0911#6 (prosecution) exist in the corpus but are not reasoning, so citing them as `A:` fails the check.
    # ASSUMPTION: they are reported as unretrieved authorities."""
    res = check_claim("Co-accused was granted bail", [ref])
    assert res.supported is False and ref in res.unretrieved_citations


def test_check_claim_never_touches_the_advocacy_stores(world, rig):
    check_claim(PARITY_CLAIM, ["A:DLHC-2022-1187#14"])
    assert stores_touched(world) <= {StoreName.CASELAW_REASONING, StoreName.CASELAW_CITATIONS, StoreName.LAW_CONCORDANCE}


@pytest.mark.parametrize("args", [("", ["A:DLHC-2022-1187#14"]), ("   ", None), (PARITY_CLAIM, ["A:no-hash"]), (PARITY_CLAIM, ["X:DLHC-2022-1187#14"]),
                                  (PARITY_CLAIM, ["A:DLHC-2022-1187#abc"])])
def test_check_claim_rejects_empty_claims_and_malformed_references(rig, args):
    assert_tool_error(lambda: check_claim(*args))


def test_check_claim_is_vakeel_only_and_has_no_gate():
    assert CHECK_CLAIM_SPEC.agents == [AgentName.VAKEEL] and CHECK_CLAIM_SPEC.gated is False


# ---------------------------------------------------------------- render_citation
def forbid_llm(monkeypatch):
    """Any model call fails: render_citation must be pure corpus metadata."""
    import vakeel_sahayak.models.factory as factory

    def boom(*a, **k):
        raise AssertionError("render_citation must not call a model")

    monkeypatch.setattr(factory, "get_llm", boom)


def test_render_citation_from_metadata_alone(world, monkeypatch):
    """court, year and paragraph come from the corpus row: DLHC-2022-1187#14 is a Delhi HC order of 2022-06-03."""
    forbid_llm(monkeypatch)
    opened = install_recording_stores(monkeypatch, world)
    text = render_citation("DLHC-2022-1187", 14)
    assert "Delhi" in text and "2022" in text and "14" in text and "DLHC-2022-1187" in text
    assert {n for n, _ in opened} <= {StoreName.CASELAW_REASONING, StoreName.CASELAW_CITATIONS}


def test_render_citation_of_a_supreme_court_judgment(world, install_stores):
    install_stores()
    text = render_citation("SC-2014-0463", 21)
    assert "Supreme Court" in text and "2014" in text and "21" in text


def test_render_citation_without_a_paragraph_cites_the_document(world, install_stores):
    """para=None -> a document-level citation: no paragraph number is invented."""
    install_stores()
    text = render_citation("DLHC-2022-1187")
    assert "DLHC-2022-1187" in text and "para" not in text.lower()


def test_render_citation_is_deterministic_and_never_contains_paragraph_text(world, install_stores):
    install_stores()
    a, b = render_citation("DLHC-2021-0420", 11), render_citation("DLHC-2021-0420", 11)
    assert a == b and "Prolonged custody" not in a


def test_different_documents_give_different_citations(world, install_stores):
    install_stores()
    assert render_citation("DLHC-2022-1187", 14) != render_citation("DLHC-2021-0420", 11)


@pytest.mark.parametrize(("doc_id", "para"), [("NOPE-1999-0001", 3), ("DLHC-2022-1187", 999), ("", 1), ("DLHC-2022-1187", 0), ("DLHC-2022-1187", -1)])
def test_unknown_or_invalid_ids_are_errors_never_an_invented_citation(world, install_stores, doc_id, para):
    install_stores()
    assert_tool_error(lambda: render_citation(doc_id, para))


def test_render_citation_spec_is_vakeel_only():
    assert RENDER_CITATION_SPEC.agents == [AgentName.VAKEEL] and RENDER_CITATION_SPEC.gated is False
