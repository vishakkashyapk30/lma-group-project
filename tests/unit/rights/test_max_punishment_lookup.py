"""The maximum punishment the Rights Radar reads for BNS 109 and NDPS 21(a) (demo cases 03 and 05, 15 Nov 2026).

Causes fixed: (1) a charge such as `BNS 3(5)` (common intention) has no punishment of its own, and `most_severe` returned None when any one
section lacked one, so BNS 109 (death) was dropped; (2) the statute lookup matched exactly, so `NDPS 21(a)` found no row. NDPS sections that
grade by quantity keep the maximum empty until the charged clause is named (the store holds only the heaviest term).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from vakeel_sahayak.agents.peshkar.agent import PeshkarAgent
from vakeel_sahayak.pipelines import first_schedule as fs
from vakeel_sahayak.rights.engine import RightsEngine
from vakeel_sahayak.schemas.dossier import CaseDossier, ChargeSheetValue, SectionValue
from vakeel_sahayak.schemas.enums import FieldStatus
from vakeel_sahayak.schemas.store_rows import StatuteRow
from vakeel_sahayak.stores.law_statutes import StatuteStore
from vakeel_sahayak.tools.base import ToolError

NDPS_21 = """21. Punishment for contravention in relation to manufactured drugs and preparations.— Whoever ... shall be punishable,—
(a) where the contravention involves small quantity, with rigorous imprisonment for a term which may extend to one year, or with fine which may extend to ten thousand rupees, or with both;
(b) where the contravention involves quantity, lesser than commercial quantity but greater than small quantity, with rigorous imprisonment for a term which may extend to ten years, and with fine which may extend to one lakh rupees;
(c) where the contravention involves commercial quantity, with rigorous imprisonment for a term which shall not be less than ten years but which may extend to twenty years, and shall also be liable to fine which shall not be less than one lakh rupees but which may extend to two lakh rupees:
Provided that the court may, for reasons to be recorded in the judgment, impose a fine exceeding two lakh rupees."""


def _agent(rows: dict[tuple[str, str], SimpleNamespace]) -> PeshkarAgent:
    """A Peshkar whose `get_statute` answers like the store: the exact row, else the bare section's row."""
    agent = object.__new__(PeshkarAgent)

    def tool(name, **kw):
        assert name == "get_statute"
        row = rows.get((kw["code"], kw["section"])) or rows.get((kw["code"], kw["section"].split("(")[0]))
        return row if row else ToolError(tool=name, kind="not_found", message="no such section", retryable=False)

    agent._tool = tool  # type: ignore[method-assign]
    return agent


def _map(agent, code, section):
    return agent._map_section({"as_written": f"{code} {section}", "code": code, "section": section}, None, {})


def _inputs(*sections: dict):
    dossier = CaseDossier(case_id="c-test")
    dossier.fields.sections.value = [SectionValue(**s) for s in sections]
    dossier.fields.sections.status = FieldStatus.VERIFIED
    return RightsEngine().build_inputs(dossier, [], "2026-01-01")


def _sec(code, section, punishment=None):
    return {"as_written": f"{code} {section}", "code": code, "section": section, "max_punishment": punishment}


# ---- the official table and the statute store
@pytest.mark.parametrize(
    ("code", "section", "want"),
    [("BNS", "109", "death"), ("BNS", "109(1)", "10 years"), ("BNS", "109(2)", "death"), ("IPC", "302", "death")],
)
def test_first_schedule_maximum_for_sections_and_clauses(code, section, want):
    # BNS 109 has sub-rows (10 years, life, death): the section level is the heaviest, a clause picks its own sub-row
    assert fs.classify(code, section)[1] == want


def test_ipc_307_is_unchanged():
    assert fs.classify("IPC", "307") == (False, "death")  # the heaviest sub-row, as before


def test_store_get_strips_the_clause_when_there_is_no_row_for_it():
    store = StatuteStore()
    store.open()
    rows = [StatuteRow(code="NDPS", section=s, text="x") for s in ("21", "22")] + [StatuteRow(code="BNS", section=s, text="x") for s in ("318", "318(4)")]
    store._rows = rows  # the offline seed has no NDPS 21 or 22
    try:
        assert store.get("NDPS", "22(c)").section == "22"
        assert store.get("NDPS", "21(a)").section == "21"
        assert store.get("BNS", "318(4)").section == "318(4)"  # a row that exists for the clause is still preferred
        with pytest.raises(LookupError):
            store.get("NDPS", "9999(a)")
        with pytest.raises(LookupError):  # an IPC/BNS clause never takes the bare row (BNS 3 is definitions)
            store.get("BNS", "318(9)")
    finally:
        store.close()


# ---- Peshkar: the dossier value
def test_bns_109_dossier_maximum_is_death_with_or_without_a_clause():
    agent = _agent({("BNS", "109"): SimpleNamespace(bailable=None, max_punishment=None, text="")})
    assert _map(agent, "BNS", "109")["max_punishment"] == "death"
    assert _map(agent, "BNS", "109(1)")["max_punishment"] == "10 years"  # the sub-row of the clause, not the heaviest


def test_ndps_21a_dossier_maximum_comes_from_the_clause_text():
    agent = _agent({("NDPS", "21"): SimpleNamespace(bailable=None, max_punishment="20 years", text=NDPS_21)})
    assert _map(agent, "NDPS", "21(a)")["max_punishment"] == "1 year"
    assert _map(agent, "NDPS", "21(b)")["max_punishment"] == "10 years"
    assert _map(agent, "NDPS", "21(c)")["max_punishment"] == "20 years"


@pytest.mark.parametrize("section", ["21", "21(d)"])
def test_ndps_without_a_quantity_clause_leaves_the_maximum_empty(section):
    agent = _agent({("NDPS", "21"): SimpleNamespace(bailable=None, max_punishment="20 years", text=NDPS_21)})
    assert "max_punishment" not in _map(agent, "NDPS", section)


def test_ndps_section_that_does_not_grade_by_quantity_keeps_its_maximum():
    agent = _agent({("NDPS", "27"): SimpleNamespace(bailable=None, max_punishment="1 year", text="27. Punishment for consumption")})
    assert _map(agent, "NDPS", "27")["max_punishment"] == "1 year"


# ---- Rights Radar inputs
def test_a_common_intention_charge_does_not_hide_the_maximum_of_bns_109():
    inputs = _inputs(_sec("BNS", "109", "death"), _sec("BNS", "3(5)"))
    assert inputs.max_punishment == "death"
    assert inputs.sections == ["BNS 109", "BNS 3(5)"]


def test_unlawful_assembly_membership_does_not_hide_the_maximum():
    assert _inputs(_sec("BNS", "103(1)", "death"), _sec("BNS", "190")).max_punishment == "death"
    assert _inputs(_sec("IPC", "302", "life"), _sec("IPC", "149")).max_punishment == "life"


def test_a_section_whose_maximum_is_unknown_still_leaves_it_unknown():
    assert _inputs(_sec("BNS", "109", "death"), _sec("BNS", "61(2)")).max_punishment is None  # conspiracy: "same as for abetment"


def test_ipc_inputs_are_unchanged():
    assert _inputs(_sec("IPC", "420", "7 years"), _sec("IPC", "34")).max_punishment == "7 years"
    assert _inputs(_sec("IPC", "420", "7 years"), _sec("IPC", "406", "3 years")).max_punishment == "7 years"


# ---- the rules
def _run(*sections: dict, first_remand="2025-03-01", cs="2025-04-20"):
    dossier = CaseDossier(case_id="c-test")
    dossier.fields.sections.value = [SectionValue(**s) for s in sections]
    dossier.fields.sections.status = FieldStatus.VERIFIED
    dossier.fields.first_remand.value = first_remand
    dossier.fields.first_remand.status = FieldStatus.VERIFIED
    dossier.fields.arrest_date.value = first_remand
    dossier.fields.arrest_date.status = FieldStatus.VERIFIED
    dossier.fields.charge_sheet.value = ChargeSheetValue(filed=True, date=cs)
    dossier.fields.charge_sheet.status = FieldStatus.VERIFIED
    return RightsEngine().run(dossier, [], "2026-01-01")


@pytest.mark.parametrize("section", ["22", "21"])
def test_plain_ndps_section_stays_check_and_says_why(section):
    report = _run(_sec("NDPS", section))  # the dossier leaves the maximum empty for a section graded by quantity
    for name in ("default_bail", "undertrial_limit"):
        res = report.get(name)
        assert res.status.value == "CHECK"
        assert "set by the clause and the quantity" in res.detail and f"NDPS s.{section}" in res.detail


def test_ndps_21a_with_its_maximum_runs_the_rules_with_the_60_day_limit():
    report = _run(_sec("NDPS", "21(a)", "1 year"))
    res = report.get("default_bail")
    assert "60-day limit (maximum 1 year)" in res.detail and "not on record" not in res.detail and res.status.value != "CHECK"


def test_a_non_ndps_missing_maximum_message_is_unchanged():
    res = _run(_sec("BNS", "999")).get("default_bail")
    assert res.detail == "Maximum punishment is not on record, so the 60 or 90 day limit is unknown."


def test_bns_109_with_3_5_runs_default_bail_from_the_death_maximum():
    res = _run(_sec("BNS", "109", "death"), _sec("BNS", "3(5)"), cs="2025-05-20").get("default_bail")
    assert "90-day limit (maximum death)" in res.detail and res.status.value != "CHECK"


def test_clause_maximum_function():
    assert fs.ndps_clause_maximum("21(a)", NDPS_21) == "1 year"
    assert fs.ndps_clause_maximum("21", NDPS_21) is None
    assert fs.ndps_clause_maximum("21(a)", "") is None
    assert fs.ndps_is_quantity_dependent(NDPS_21) and not fs.ndps_is_quantity_dependent("27. consumption")
