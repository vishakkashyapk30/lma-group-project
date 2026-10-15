"""config.load_config behaviour (plan §3, §6.2): merges configs/*.yaml into AppConfig and honours $VS_CONFIG_DIR.

These tests fail with NotImplementedError until load_config is implemented."""

from __future__ import annotations

import shutil

import pytest
import yaml

from vakeel_sahayak.config import AppConfig, load_config
from vakeel_sahayak.schemas.enums import AgentName


@pytest.fixture()
def cfg_copy(tmp_path, configs_dir):
    """A private copy of configs/ that tests may edit."""
    dest = tmp_path / "cfg"
    shutil.copytree(configs_dir, dest)
    return dest


def test_load_config_returns_app_config_with_plan_budgets(configs_dir):
    """load_config(dir) returns an AppConfig with 150,000 tokens per case and 8 store calls per factor (plan §6.2)."""
    cfg = load_config(str(configs_dir))
    assert isinstance(cfg, AppConfig)
    assert cfg.budgets.tokens_per_case == 150000
    assert cfg.budgets.store_calls_per_factor == 8
    assert cfg.budgets.tokens_per_factor == 12000
    assert cfg.budgets.questions_per_round == 3
    assert cfg.budgets.repair_rounds == 2
    assert cfg.budgets.sparring_rounds == 2
    assert cfg.budgets.objections_per_ground == 2


def test_load_config_merges_models_stores_thresholds_tools(configs_dir):
    """The merged object carries the models, stores, thresholds and per-agent tool lists from their YAMLs."""
    cfg = load_config(str(configs_dir))
    assert cfg.models["llm"]["agents_14b"]["model"] == "Qwen/Qwen3-14B-AWQ"
    assert cfg.stores["caselaw"]["reasoning"]["chunk_max_tokens"] == 400
    assert cfg.thresholds["ingestion"]["text_layer_word_share"] == 0.85
    assert set(cfg.tools) == {a.value.lower() for a in AgentName}
    assert "export" in cfg.tools["vakeel"] and "export" not in cfg.tools["munshi"]


def test_load_config_paths_section(configs_dir, monkeypatch):
    """Paths come from paths.yaml: stores under data/stores, client cases under data/cases."""
    monkeypatch.delenv("VS_DATA_DIR", raising=False)  # conftest isolates every test's data dir; this test checks the defaults
    cfg = load_config(str(configs_dir))
    assert cfg.paths.stores_dir == "data/stores"
    assert cfg.paths.cases_dir == "data/cases"


def test_load_config_honours_vs_config_dir(monkeypatch, cfg_copy):
    """With no argument, $VS_CONFIG_DIR selects the directory (an edited budget shows up)."""
    path = cfg_copy / "budgets.yaml"
    data = yaml.safe_load(path.read_text())
    data["case"]["tokens"] = 4321
    path.write_text(yaml.safe_dump(data))
    monkeypatch.setenv("VS_CONFIG_DIR", str(cfg_copy))
    assert load_config().budgets.tokens_per_case == 4321


def test_explicit_argument_beats_environment(monkeypatch, cfg_copy, configs_dir):
    """An explicit config_dir wins over $VS_CONFIG_DIR."""
    path = cfg_copy / "budgets.yaml"
    data = yaml.safe_load(path.read_text())
    data["case"]["tokens"] = 4321
    path.write_text(yaml.safe_dump(data))
    monkeypatch.setenv("VS_CONFIG_DIR", str(cfg_copy))
    assert load_config(str(configs_dir)).budgets.tokens_per_case == 150000  # ASSUMPTION: argument has priority


def test_default_directory_is_repo_configs(monkeypatch, repo_root):
    """With neither argument nor environment, ./configs is used (run from the repo root)."""
    monkeypatch.delenv("VS_CONFIG_DIR", raising=False)
    monkeypatch.chdir(repo_root)
    assert load_config().budgets.tokens_per_case == 150000


def test_missing_directory_raises(tmp_path):
    """A directory with no config files is an error, not an empty default config."""
    with pytest.raises((FileNotFoundError, ValueError)):  # ASSUMPTION: either is acceptable
        load_config(str(tmp_path / "nope"))


def test_load_config_is_repeatable(configs_dir):
    """Two loads give equal configs (no hidden state)."""
    assert load_config(str(configs_dir)) == load_config(str(configs_dir))
