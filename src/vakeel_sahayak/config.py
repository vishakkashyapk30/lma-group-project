"""Configuration loading: YAML files in configs/ merged into one typed object (plan §3, §6.2)."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# configs/ sits two levels above this package when running from a source checkout (src/vakeel_sahayak/config.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]


class PathsConfig(BaseModel):
    """Filesystem layout (configs/paths.yaml)."""

    data_dir: str = "data"
    raw_dir: str = "data/raw"
    interim_dir: str = "data/interim"
    stores_dir: str = "data/stores"
    testsets_dir: str = "data/testsets"
    cases_dir: str = "data/cases"  # laptop only; raw client files never leave
    models_dir: str = "models"
    ada_scratch: str | None = None
    ada_results: str = "results"


class BudgetConfig(BaseModel):
    """Budgets (configs/budgets.yaml; plan §6.2)."""

    tokens_per_case: int = 150000
    store_calls_per_factor: int = 8
    tokens_per_factor: int = 12000
    drafting_tokens_per_factor: int = 16000  # Vakeel and Abhiyojak calls of a factor (retrieval keeps tokens_per_factor)
    questions_per_round: int = 3  # shared by Munshi and Peshkar (plan §4.3)
    repair_rounds: int = 2
    sparring_rounds: int = 2
    objections_per_ground: int = 2
    show_spend: bool = True
    log_budget_hits: bool = True


class EnvSettings(BaseModel):
    """Values read from the process environment or .env (see .env.example). Secrets are never logged."""

    vllm_base_url: str | None = None
    vllm_model: str | None = None
    local_llm_device: str | None = None
    mistral_api_key: str | None = Field(default=None, repr=False)
    hf_token: str | None = Field(default=None, repr=False)
    ada_user: str | None = None


class AppConfig(BaseModel):
    """Root configuration object assembled from configs/*.yaml."""

    paths: PathsConfig = Field(default_factory=PathsConfig)
    budgets: BudgetConfig = Field(default_factory=BudgetConfig)
    models: dict[str, Any] = Field(default_factory=dict)
    stores: dict[str, Any] = Field(default_factory=dict)
    thresholds: dict[str, Any] = Field(default_factory=dict)
    tools: dict[str, list[str]] = Field(default_factory=dict)  # agent -> allowed tool names
    rights_rules: dict[str, Any] = Field(default_factory=dict)
    bail_sections: list[dict[str, Any]] = Field(default_factory=list)
    splits: dict[str, Any] = Field(default_factory=dict)
    env: EnvSettings = Field(default_factory=EnvSettings)
    config_dir: str = "configs"


def parse_dotenv(path: str | Path) -> dict[str, str]:
    """Parse a minimal .env file (KEY=VALUE lines, '#' comments, optional quotes).

    Args:
        path: file to read; a missing file gives an empty dict

    Returns:
        Mapping of variable names to values.
    """
    p = Path(path)
    if not p.is_file():
        return {}
    out: dict[str, str] = {}
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.removeprefix("export ").strip()] = value
    return out


def _environment(config_dir: Path) -> dict[str, str]:
    """Merge .env files (repo root, then cwd) under the real process environment, which wins."""
    merged: dict[str, str] = {}
    for candidate in (config_dir.parent / ".env", Path.cwd() / ".env"):
        merged.update(parse_dotenv(candidate))
    merged.update({k: v for k, v in os.environ.items() if k.startswith(("VS_", "ADA_", "HF_", "MISTRAL_"))})
    return merged


_YAML_CACHE: dict[tuple[str, int, int], Any] = {}


def _read_yaml(config_dir: Path, name: str, default: Any) -> Any:
    """Read configs/<name>.yaml, returning `default` when the file is absent or empty."""
    path = config_dir / f"{name}.yaml"
    if not path.is_file():
        return default
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _YAML_CACHE:  # parsing is slow in pure Python and load_config runs on every model-role lookup; a changed file is re-read
        try:
            _YAML_CACHE[key] = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise ValueError(f"invalid YAML in {path}: {exc}") from exc
    data = copy.deepcopy(_YAML_CACHE[key])  # callers may edit what they get
    return default if data is None else data


def _build_paths(raw: dict[str, Any], env: dict[str, str]) -> PathsConfig:
    """Map configs/paths.yaml onto PathsConfig; VS_DATA_DIR rebases every path that lives under data/."""
    ada = raw.get("ada") or {}
    values = {
        "data_dir": raw.get("data"),
        "raw_dir": raw.get("raw"),
        "interim_dir": raw.get("interim"),
        "stores_dir": raw.get("stores"),
        "testsets_dir": raw.get("testsets"),
        "cases_dir": raw.get("cases"),
        "models_dir": raw.get("models"),
        "ada_scratch": ada.get("scratch"),
        "ada_results": ada.get("results"),
    }
    values = {k: os.path.expandvars(v) if isinstance(v, str) else v for k, v in values.items() if v is not None}
    override = env.get("VS_DATA_DIR")
    if override:
        base = values.get("data_dir", "data")
        for key, val in list(values.items()):
            if key.endswith("_dir") and key not in ("models_dir",):
                rel = os.path.relpath(val, base) if val != base else "."
                values[key] = override if rel == "." else str(Path(override) / rel)
    return PathsConfig(**values)


def _build_budgets(raw: dict[str, Any], env: dict[str, str]) -> BudgetConfig:
    """Map configs/budgets.yaml onto BudgetConfig, with VS_TOKENS_PER_CASE / VS_STORE_CALLS_PER_FACTOR overrides."""
    factor = raw.get("factor") or {}
    sparring = raw.get("sparring") or {}
    ui = raw.get("ui") or {}
    values: dict[str, Any] = {
        "tokens_per_case": (raw.get("case") or {}).get("tokens"),
        "store_calls_per_factor": factor.get("store_calls"),
        "tokens_per_factor": factor.get("tokens"),
        "drafting_tokens_per_factor": (raw.get("drafting") or {}).get("tokens"),
        "questions_per_round": raw.get("questions_per_round"),
        "repair_rounds": raw.get("repair_rounds"),
        "sparring_rounds": sparring.get("rounds"),
        "objections_per_ground": sparring.get("objections_per_ground"),
        "show_spend": ui.get("show_spend"),
        "log_budget_hits": ui.get("log_budget_hits"),
    }
    if "VS_TOKENS_PER_CASE" in env:
        values["tokens_per_case"] = int(env["VS_TOKENS_PER_CASE"])
    if "VS_STORE_CALLS_PER_FACTOR" in env:
        values["store_calls_per_factor"] = int(env["VS_STORE_CALLS_PER_FACTOR"])
    return BudgetConfig(**{k: v for k, v in values.items() if v is not None})


def _build_env(env: dict[str, str]) -> EnvSettings:
    """Pick the documented variables out of the merged environment (empty strings count as unset)."""

    def get(name: str) -> str | None:
        return env.get(name) or None

    return EnvSettings(
        vllm_base_url=get("VS_VLLM_BASE_URL"),
        vllm_model=get("VS_VLLM_MODEL"),
        local_llm_device=get("VS_LOCAL_LLM_DEVICE"),
        mistral_api_key=get("MISTRAL_API_KEY"),
        hf_token=get("HF_TOKEN"),
        ada_user=get("ADA_USER"),
    )


def resolve_config_dir(config_dir: str | None = None) -> Path:
    """Find the configs directory: argument, then $VS_CONFIG_DIR (or .env), then ./configs, then the repo's configs/."""
    if config_dir:
        return Path(config_dir)
    env_dir = os.environ.get("VS_CONFIG_DIR") or parse_dotenv(Path.cwd() / ".env").get("VS_CONFIG_DIR")
    if env_dir:
        return Path(env_dir)
    for candidate in (Path.cwd() / "configs", _REPO_ROOT / "configs"):
        if candidate.is_dir():
            return candidate
    return Path.cwd() / "configs"


def load_config(config_dir: str | None = None) -> AppConfig:
    """Load and merge configs/*.yaml into an AppConfig (plan §3).

    Environment variables (and a .env file) override the YAML where a variable is documented in .env.example.
    The process environment wins over .env.

    Args:
        config_dir: directory with the YAML files; defaults to ./configs or $VS_CONFIG_DIR

    Returns:
        The merged configuration.

    Raises:
        FileNotFoundError: if the directory is missing or holds no YAML files.
        ValueError: if a YAML file is invalid.
    """
    cdir = resolve_config_dir(config_dir)
    if not cdir.is_dir():
        raise FileNotFoundError(f"config directory not found: {cdir}")
    if not any(cdir.glob("*.yaml")):
        raise FileNotFoundError(f"no *.yaml config files in {cdir}")
    env = _environment(cdir)
    bail = _read_yaml(cdir, "bail_sections", {})
    return AppConfig(
        paths=_build_paths(_read_yaml(cdir, "paths", {}), env),
        budgets=_build_budgets(_read_yaml(cdir, "budgets", {}), env),
        models=_read_yaml(cdir, "models", {}),
        stores=_read_yaml(cdir, "stores", {}),
        thresholds=_read_yaml(cdir, "thresholds", {}),
        tools=_read_yaml(cdir, "tools", {}),
        rights_rules=_read_yaml(cdir, "rights_rules", {}),
        bail_sections=list(bail.get("rows", [])) if isinstance(bail, dict) else [],
        splits=_read_yaml(cdir, "splits", {}),
        env=_build_env(env),
        config_dir=str(cdir),
    )
