"""Shared test-set utilities and the nine-set registry (plan §15.2): manifest format, Faker names, sizes, independence from the system.

The registry tests read module docstrings and signatures and pass on the skeleton; `write_manifest` and `faker_names` fail until written.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import json
import re
from pathlib import Path

import pytest

from vakeel_sahayak.testsets.common import TestSetManifest, faker_names, write_manifest

PKG = Path(inspect.getfile(importlib.import_module("vakeel_sahayak.testsets"))).parent

BUILDERS = {
    "T1": ("t1_court_grounded", "build_t1", ["parts_path", "gold_dir", "out_dir"], "200"),
    "T2": ("t2_messy_bundles", "build_t2", ["t1_dir", "hldc_dir", "escr_dir", "out_dir"], "4,800"),
    "T3": ("t3_change_sets", "build_t3", ["t1_dir", "out_dir"], "240"),
    "T4": ("t4_rights_scenarios", "build_t4", ["spec_path", "out_dir"], "500"),
    "T5": ("t5_batch", "build_t5", ["t1_dir", "t4_dir", "out_dir"], "300"),
    "T6": ("t6_chat_questions", "build_t6", ["t1_dir", "t2_dir", "out_dir"], "150"),
    "T7": ("t7_safety", "build_t7", ["t1_dir", "out_dir"], "60"),
    "T8": ("t8_speech", "build_t8", ["kathbath_dir", "t1_dir", "out_dir"], "300"),
    "T9": ("t9_citation_formats", "build_t9", ["metadata_path", "out_dir"], "2,000"),
}


@pytest.mark.parametrize("set_id", sorted(BUILDERS))
def test_builder_exists_with_the_planned_inputs_and_returns_a_manifest(set_id):
    """T1-T9 each have one `build_tN(...)` returning a TestSetManifest, and the module docstring states the plan's size."""
    module, fn_name, params, size = BUILDERS[set_id]
    mod = importlib.import_module(f"vakeel_sahayak.testsets.{module}")
    fn = getattr(mod, fn_name)
    assert list(inspect.signature(fn).parameters) == params
    assert inspect.signature(fn).return_annotation in (TestSetManifest, "TestSetManifest")
    assert size in (mod.__doc__ or ""), f"{module}: docstring should state the size {size}"


def test_exactly_nine_test_set_modules():
    """Skeleton naming convention: modules t1_* ... t9_*, one per set."""
    found = sorted(re.match(r"t(\d)_", p.name).group(1) for p in PKG.glob("t[0-9]_*.py"))
    assert found == [str(i) for i in range(1, 10)]


@pytest.mark.parametrize("path", sorted(PKG.glob("*.py")), ids=lambda p: p.name)
def test_construction_never_imports_the_system_under_test(path):
    """No manual annotation and no circular truth: answers come from construction, so test-set code imports neither the Rights Radar
    (T4's answers come from specs written by someone who does not write the Radar), nor agents, nor the system's LLM clients."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
    forbidden = ("vakeel_sahayak.rights", "vakeel_sahayak.agents", "vakeel_sahayak.models.local_llm", "vakeel_sahayak.models.vllm_client",
                 "vakeel_sahayak.orchestration")
    assert not [n for n in names if n.startswith(forbidden)], names


def test_manifest_fields():
    """set_id (T1..T9), size, answers_from, used_for list, path."""
    m = TestSetManifest(set_id="T3", size=240, answers_from="construction", used_for=["F2"], path="data/testsets/t3")
    assert (m.set_id, m.size, m.used_for) == ("T3", 240, ["F2"])
    assert TestSetManifest(set_id="T1", size=200, answers_from="G1-G7", path="p").used_for == []


def test_write_manifest_round_trips(tmp_path):
    """manifest.json is written next to the data and parses back to the same manifest."""
    m = TestSetManifest(set_id="T5", size=300, answers_from="construction (deadlines)", used_for=["F4"], path=str(tmp_path))
    write_manifest(m, str(tmp_path))
    assert TestSetManifest.model_validate(json.loads((tmp_path / "manifest.json").read_text())) == m


def test_write_manifest_creates_the_output_directory(tmp_path):
    """# ASSUMPTION: a missing directory is created rather than being an error."""
    m = TestSetManifest(set_id="T9", size=2000, answers_from="document id", path="x")
    write_manifest(m, str(tmp_path / "new" / "t9"))
    assert (tmp_path / "new" / "t9" / "manifest.json").exists()


# ---------------------------------------------------------------- Faker names (T2 companions, T7 leak tests)
def test_faker_names_are_deterministic_per_seed():
    pytest.importorskip("faker")
    assert faker_names(7, 25) == faker_names(7, 25)
    assert faker_names(7, 25) != faker_names(8, 25)


def test_faker_names_returns_n_distinct_non_empty_names():
    pytest.importorskip("faker")
    names = faker_names(1, 40)
    assert len(names) == 40 and len(set(names)) == 40 and all(n.strip() for n in names)


def test_faker_names_prefix_stability():
    """Asking for more names with the same seed extends the same sequence: T2 and T7 can grow without renaming earlier cases.
    # ASSUMPTION."""
    pytest.importorskip("faker")
    assert faker_names(3, 30)[:10] == faker_names(3, 10)


def test_faker_names_zero_is_empty():
    pytest.importorskip("faker")
    assert faker_names(0, 0) == []
