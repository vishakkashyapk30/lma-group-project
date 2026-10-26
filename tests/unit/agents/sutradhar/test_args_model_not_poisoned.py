"""Regression: the tool-argument model is built from the real tool function, never from a patched `get_tool`.

A harness that swaps `get_tool` for `*args/**kwargs` wrappers (tests/fakes/toolbox.py) used to leave an empty cached
model behind, so Sutradhar's chat `date_calc` and `map_section` calls failed with 'Extra inputs are not permitted'.
"""

from __future__ import annotations

from vakeel_sahayak.tools import registry


def test_args_model_ignores_a_patched_get_tool(monkeypatch):
    registry._args_model.cache_clear()
    monkeypatch.setattr(registry, "get_tool", lambda name: (lambda *a, **k: None))
    try:
        assert set(registry._args_model("date_calc").model_fields) == {"start", "end", "rule"}
        assert registry.validate_args("map_section", {"code": "IPC", "section": "420", "offence_date": "2024-08-20"})
    finally:
        registry._args_model.cache_clear()


def test_as_of_falls_back_to_the_rights_report_when_the_dossier_has_none():
    from vakeel_sahayak.agents.sutradhar.factor_pick import signals_from_dossier
    from vakeel_sahayak.schemas.dossier import CaseDossier
    from vakeel_sahayak.schemas.rights_report import RightsReport

    dossier = CaseDossier(case_id="c", as_of=None)
    rights = RightsReport(case_id="c", as_of="2025-02-03", checks=[])
    assert signals_from_dossier(dossier, rights).as_of == "2025-02-03"
    assert signals_from_dossier(CaseDossier(case_id="c", as_of="2025-01-01"), rights).as_of == "2025-01-01"
