"""Foundation smoke test: fixtures, fakes and the pytest configuration themselves load (plan §7.1 case-0007)."""

from vakeel_sahayak.schemas import CaseDossier


def test_case_0007_fixture_matches_plan_example(case_meta, dossier, timeline):
    assert isinstance(dossier, CaseDossier)
    assert case_meta["expected"]["custody_days"] == 167
    assert dossier.fields.custody_days.value == 167
    assert [e.date for e in timeline] == sorted(e.date for e in timeline)
    assert len(timeline) == 7


def test_world_excludes_test_orders_and_same_fir(world):
    from vakeel_sahayak.schemas.enums import StoreName

    ids = {r.doc_id for r in world.stores[StoreName.CASELAW_REASONING].rows}
    assert "TESTORD-2024-0001" not in ids
    assert "DLHC-2022-1187" in ids
