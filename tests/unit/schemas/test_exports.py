"""Package exports of vakeel_sahayak.schemas (skeleton convention: top-level schema classes importable from the package)."""

from __future__ import annotations

import vakeel_sahayak.schemas as S

EXPECTED = ["BailBrief", "CaseDossier", "Event", "IngestionReport", "RetrievalPlan", "RightsReport",
            "SparringRecord", "TriageCard"]


def test_all_lists_the_eight_top_level_schemas():
    """__all__ names the eight top-level plan outputs (dossier, rights, brief, sparring, triage, ingestion, plan, event)."""
    assert sorted(S.__all__) == sorted(EXPECTED)


def test_every_exported_name_resolves_to_a_pydantic_model():
    """Each name in __all__ is a pydantic model class importable from the package."""
    from pydantic import BaseModel

    for name in S.__all__:
        obj = getattr(S, name)
        assert isinstance(obj, type) and issubclass(obj, BaseModel), name


def test_exports_are_the_same_classes_as_their_modules():
    """The package re-exports, rather than redefines, the module classes."""
    from vakeel_sahayak.schemas.bail_brief import BailBrief
    from vakeel_sahayak.schemas.dossier import CaseDossier
    from vakeel_sahayak.schemas.events import Event
    from vakeel_sahayak.schemas.triage import TriageCard

    assert S.BailBrief is BailBrief and S.CaseDossier is CaseDossier
    assert S.Event is Event and S.TriageCard is TriageCard


def test_every_schema_module_imports_without_heavy_dependencies():
    """Schema modules import on a bare install (no torch / vllm / transformers pulled in, skeleton convention)."""
    import subprocess
    import sys

    code = (
        "import pkgutil, importlib, sys, vakeel_sahayak.schemas as s\n"
        "[importlib.import_module(m.name) for m in pkgutil.iter_modules(s.__path__, 'vakeel_sahayak.schemas.')]\n"
        "bad = {'torch', 'vllm', 'transformers'} & set(sys.modules)\n"
        "sys.exit(1 if bad else 0)\n"
    )
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0
