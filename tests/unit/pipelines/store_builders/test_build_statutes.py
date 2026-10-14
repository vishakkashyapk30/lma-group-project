"""Builder of `law.statutes` (plan §5.1): one row per section of the IPC, BNS, CrPC and BNSS plus NDPS s.37, UAPA s.43D(5) and
PMLA s.45, with text, maximum punishment, bailable and cognisable; exact lookup plus BM25 over the text.

Statutes are not orders, so the leakage exclusion set has no effect on them."""

from __future__ import annotations

import pytest

from tests.fakes.data import load_statutes
from vakeel_sahayak.pipelines.store_builders.build_statutes import build_statutes
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.stores.law_statutes import StatuteStore


@pytest.fixture()
def built(interim, tmp_path):
    out = tmp_path / "statutes"
    n = build_statutes(str(interim), str(out))
    store = StatuteStore()
    store.open(str(out))
    yield n, store
    store.close()


def test_store_identity():
    assert StatuteStore.name == StoreName.LAW_STATUTES


def test_every_input_row_is_stored(built):
    n, store = built
    assert n == store.count() == len(load_statutes()) == 13


def test_exact_lookup_of_the_case_0007_section(built):
    """BNS 318(4): 7 years, non-bailable, cognisable (plan §7.1 example `sections`)."""
    _, store = built
    row = store.get("BNS", "318(4)")
    assert row.max_punishment == "7 years"
    assert row.bailable is False and row.cognisable is True
    assert "Cheating" in row.text


def test_ipc_420_has_the_same_maximum_punishment(built):
    _, store = built
    assert store.get("IPC", "420").max_punishment == "7 years"


@pytest.mark.parametrize(("code", "section"), [("NDPS", "37"), ("UAPA", "43D(5)"), ("PMLA", "45")])
def test_special_act_bail_bars_are_included(built, code, section):
    """Plan §5.1: NDPS s.37, UAPA s.43D(5) and PMLA s.45 sit beside the four codes (the statutory-bar factor needs them)."""
    _, store = built
    assert store.get(code, section).text


@pytest.mark.parametrize(("code", "section"), [("CrPC", "439"), ("BNSS", "483"), ("CrPC", "436A"), ("BNSS", "479")])
def test_bail_provisions_of_both_procedure_codes_are_included(built, code, section):
    _, store = built
    assert store.get(code, section).text


def test_unknown_section_raises(built):
    """An unknown section is an error, never a guess."""
    _, store = built
    with pytest.raises((KeyError, LookupError, ValueError)):
        store.get("IPC", "99999")


def test_bm25_finds_the_cheating_sections(built):
    """'Which section covers cheating' is answered by BM25 over the text: BNS 318(4) and IPC 420 lead."""
    _, store = built
    top = {(r.code, r.section) for r in store.search("cheating dishonestly inducing delivery", k=3)}
    assert {("BNS", "318(4)"), ("IPC", "420")} <= top


def test_code_filter_restricts_the_search(built):
    _, store = built
    rows = store.search("cheating", code="BNS", k=10)
    assert rows and all(r.code == "BNS" for r in rows)


def test_exclusion_set_does_not_remove_statutes(interim, tmp_path):
    """Passing the leakage set changes nothing: statutes carry no doc ids."""
    n = build_statutes(str(interim), str(tmp_path / "s"), exclude_doc_ids={"TESTORD-2024-0001"})
    assert n == 13
