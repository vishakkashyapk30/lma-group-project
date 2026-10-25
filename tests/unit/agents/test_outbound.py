"""Masking of public corpus rows and normalising of citations before they enter an outbound prompt."""

from __future__ import annotations

from vakeel_sahayak.agents.abhiyojak.isolation import _ground_view
from vakeel_sahayak.agents.outbound import mask_public, normalise_citation
from vakeel_sahayak.privacy.boundary import assert_public_text, assert_pseudonymised


def test_account_number_phone_email_masked_and_boundary_passes():
    rows = {"objection_bank": [{"doc_id": "HPHC010225332022", "para": 3, "text": "Paid to account 123456789012, call 9876543210 or a@b.com."}]}
    with_pii = rows["objection_bank"][0]["text"]
    try:
        assert_public_text(rows)
        raise AssertionError("boundary should refuse the raw row")
    except ValueError:
        pass
    masked = mask_public(rows)
    assert_public_text(masked)
    assert "[ID-NUMBER]" in masked["objection_bank"][0]["text"] and "[PHONE]" in masked["objection_bank"][0]["text"] and "[EMAIL]" in masked["objection_bank"][0]["text"]
    assert masked["objection_bank"][0]["doc_id"] == "HPHC010225332022"
    assert rows["objection_bank"][0]["text"] == with_pii  # input not mutated


def test_clean_rows_unchanged():
    rows = {"a": [{"doc_id": "X-1", "text": "Section 439 CrPC, para 12 of the order."}], "n": 3}
    assert mask_public(rows) == rows


def test_citation_with_parties_is_normalised():
    assert normalise_citation("State of Kerala v. Ramesh Kumar, (2022) 10 SCC 51, para 14", "D1", 14) == "(2022) 10 SCC 51, para 14"
    assert normalise_citation("Ram Singh v. State, Crl. M.C. No. 123/2020", "D2", 5) == "Crl. M.C. No. 123/2020, para 5"
    assert normalise_citation("Ram Singh vs State of UP (Allahabad High Court, 03.06.2022), para 4", "ALHC-1", 4) == "Judgment ALHC-1, para 4"
    same = "Order of the Delhi High Court dated 03.06.2022 (DLHC-2022-1187), para 14"
    assert normalise_citation(same, "DLHC-2022-1187", 14) == same
    assert normalise_citation(None) is None


def test_ground_view_citation_passes_name_guard():
    g = {"id": "G1", "factor": "gravity", "argument": "x", "authorities": [{"doc_id": "D1", "para": 14, "citation": "State of Kerala v. Mohan Das Nair, (2022) 10 SCC 51, para 14"}]}
    view = _ground_view(g)
    assert view["authorities"][0]["citation"] == "(2022) 10 SCC 51, para 14"
    assert_pseudonymised({"case": view})
