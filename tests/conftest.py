"""Shared pytest configuration and fixtures (spec-driven suite for plan.md v5).

Layers: tests/unit (mirrors src/vakeel_sahayak), tests/integration (modules wired together with fakes),
tests/system (plan §13.6 user flows and the T7 safety suite). Everything runs on a laptop: no GPU, no network,
no real client data. Tests needing real models carry `@pytest.mark.gpu` / `@pytest.mark.models` and are skipped by
default (see `addopts` in pyproject.toml).
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest
import yaml

try:  # hypothesis is optional at import time so a missing install gives a clear skip, not a collection error
    from hypothesis import HealthCheck, settings

    settings.register_profile("ci", max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    settings.register_profile("dev", max_examples=50, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    settings.load_profile("dev")
except ImportError:  # pragma: no cover
    pass

from tests.fakes.data import (  # noqa: E402
    PLANTED_NAMES,
    PLANTED_NAMES_HI,
    CaseWorld,
    build_world,
    load_case_meta,
    load_concordance,
    load_dossier,
    load_events,
    load_orders,
    load_paragraphs,
    load_rights_report,
    load_statutes,
    load_timeline,
)
from tests.fakes.models import ScriptedLLM  # noqa: E402
from tests.fakes.toolbox import FakeToolbox  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------------------------------------------------
# Automatic layer markers
# --------------------------------------------------------------------------------------------------------------------
def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        parts = Path(str(item.fspath)).parts
        for layer in ("unit", "integration", "system"):
            if layer in parts:
                item.add_marker(getattr(pytest.mark, layer))
                break


# --------------------------------------------------------------------------------------------------------------------
# Paths and configs
# --------------------------------------------------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """Give every test its own data dir, so case event logs and alias maps never leak between tests or into data/."""
    from vakeel_sahayak.tools.runtime import set_runtime

    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path_factory.mktemp("vsdata")))
    monkeypatch.setenv("VS_HEAVY_CLIENTS", "offline")  # vision, OCR, ASR and translation stay on the stand-ins when torch and transformers are installed
    monkeypatch.setenv("VS_NLI", "offline")  # unit tests use the lexical checker even where torch and the DeBERTa weights are installed
    monkeypatch.delenv("VS_ALLOW_PAID", raising=False)  # paid providers locked by default (models/paid_lock.py); tests that exercise them use `paid_unlocked`
    for var in ("GEMINI_API_KEY", "GEMINI_API_KEYS"):  # no real Gemini key ever reaches a test (nothing may call the network)
        monkeypatch.delenv(var, raising=False)
    set_runtime(None)
    yield
    set_runtime(None)


@pytest.fixture()
def paid_unlocked(monkeypatch):
    """Unlock OpenAI and Sarvam for a test that exercises their (mocked) transports; the default is locked (owner decision 2026-10-28)."""
    monkeypatch.setenv("VS_ALLOW_PAID", "openai,sarvam")
    yield


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def configs_dir() -> Path:
    return REPO_ROOT / "configs"


@pytest.fixture(scope="session")
def load_yaml(configs_dir: Path):
    """`load_yaml('tools.yaml')` -> parsed dict from configs/ (read directly, independent of `config.load_config`)."""

    def _load(name: str) -> dict:
        return yaml.safe_load((configs_dir / name).read_text(encoding="utf-8"))

    return _load


@pytest.fixture(scope="session")
def contracts_dir() -> Path:
    return REPO_ROOT / "src" / "vakeel_sahayak" / "contracts" / "factors"


# --------------------------------------------------------------------------------------------------------------------
# case-0007 (plan §7.1, §7.3): the worked example, built by construction
# --------------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def case_meta() -> dict:
    return load_case_meta()


@pytest.fixture()
def dossier():
    return load_dossier()


@pytest.fixture()
def timeline():
    return load_timeline()


@pytest.fixture()
def expected_rights_report():
    """The RightsReport exactly as printed in plan §7.3."""
    return load_rights_report()


@pytest.fixture()
def sample_events():
    return load_events()


@pytest.fixture()
def statutes():
    return load_statutes()


@pytest.fixture()
def concordance_edges():
    return load_concordance()


@pytest.fixture()
def paragraphs():
    return load_paragraphs()


@pytest.fixture()
def orders():
    return load_orders()


@pytest.fixture()
def rule_inputs_0007(case_meta):
    """Rights Radar inputs for case-0007 as of 2025-02-03 (antecedents unknown, no times on record)."""
    from vakeel_sahayak.rights.inputs import RuleInputs

    d = case_meta["dates"]
    return RuleInputs(
        as_of=case_meta["as_of"],
        first_remand=d["first_remand"],
        charge_sheet_date=d["charge_sheet"],
        charge_sheet_filed=True,
        arrest_date=d["arrest_date"],
        production_date=d["first_remand"],
        max_punishment=case_meta["section"]["max_punishment"],
        sections=["BNS 318(4)"],
        custody_days=case_meta["expected"]["custody_days"],
        antecedents_known=False,
    )


@pytest.fixture()
def make_rule_inputs(rule_inputs_0007):
    """Factory: `make_rule_inputs(max_punishment='life', charge_sheet_date=None)` -> RuleInputs derived from case-0007."""
    from vakeel_sahayak.rights.inputs import RuleInputs

    def _make(**overrides) -> RuleInputs:
        data = copy.deepcopy(rule_inputs_0007.model_dump())
        data.update(overrides)
        return RuleInputs(**data)

    return _make


# --------------------------------------------------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def world() -> CaseWorld:
    """In-memory stores for case-0007 (test-split and same-FIR orders already excluded)."""
    return build_world()


@pytest.fixture()
def toolbox(world: CaseWorld) -> FakeToolbox:
    return FakeToolbox(world)


@pytest.fixture()
def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM()


@pytest.fixture()
def make_ctx(tmp_path):
    """Factory for an `AgentContext` wired to fakes: `make_ctx(llm=..., toolbox=..., sqlite=False)`."""
    from tests.fakes.context import make_context

    def _make(sqlite: bool = False, **kw):
        return make_context(sqlite_dir=tmp_path if sqlite else None, **kw)

    return _make


@pytest.fixture()
def install_stores(monkeypatch, world):
    """`install_stores()` makes `open_store(...)` return the in-memory stores of `world` for the test."""
    from tests.fakes.stores import install_fake_stores

    def _install(stores=None):
        install_fake_stores(monkeypatch, stores or world.stores)

    return _install


@pytest.fixture(scope="session")
def planted_names() -> list[str]:
    """Synthetic names planted in documents to test pseudonymisation and leaks (plan §15.2 T7). Not real people."""
    return list(PLANTED_NAMES) + list(PLANTED_NAMES_HI)


# --------------------------------------------------------------------------------------------------------------------
# Synthetic PDFs: written by tests/fixtures/pdfgen.py with no PDF library; reading them needs PyMuPDF
# --------------------------------------------------------------------------------------------------------------------
@pytest.fixture()
def pdfs(tmp_path):
    """Namespace with `text`, `legacy`, `scanned`, `mixed`, `corrupt`, `locked` builders writing into tmp_path."""
    from tests.fixtures import pdfgen

    class _Pdfs:
        text = staticmethod(lambda name, pages: pdfgen.make_text_pdf(tmp_path / name, pages))
        legacy = staticmethod(lambda name, pages=None: pdfgen.make_legacy_font_pdf(tmp_path / name, pages))
        scanned = staticmethod(lambda name, n=1: pdfgen.make_image_pdf(tmp_path / name, n))
        mixed = staticmethod(lambda name, spec: pdfgen.make_mixed_pdf(tmp_path / name, spec))
        corrupt = staticmethod(lambda name: pdfgen.make_corrupt_pdf(tmp_path / name))
        locked = staticmethod(lambda name, pw="u": pdfgen.make_locked_pdf(tmp_path / name, pw))
        gen = pdfgen

    return _Pdfs


@pytest.fixture()
def require_pymupdf():
    """Skip (with a clear reason) when PyMuPDF is not installed; the light test venv does not ship it."""
    if importlib.util.find_spec("fitz") is None:
        pytest.skip("PyMuPDF (fitz) is not installed: PDF reading tests need it (pip install pymupdf)")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "needs_langgraph: skipped unless langgraph is installed")
