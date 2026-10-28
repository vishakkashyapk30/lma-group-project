"""Model interfaces and import hygiene (plan §12; skeleton conventions 'Models').

Encodes: every model type has an abstract interface with the documented methods; concrete clients subclass the right
interface; nothing heavy (torch, vLLM, transformers) is imported when `vakeel_sahayak.models.*` is imported; the
evaluation labeler and the teacher are not LLMClients and are never imported by the system; agents resolve roles that
exist in configs/models.yaml.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pkgutil
import subprocess
import sys
from pathlib import Path

import pytest

import vakeel_sahayak
from vakeel_sahayak.models import base

SRC = Path(vakeel_sahayak.__file__).resolve().parent

# interface -> abstract method names (plan §12, models/base.py)
INTERFACES = {
    "LLMClient": {"generate", "count_tokens"},
    "VisionClient": {"transcribe_page"},
    "OcrClient": {"ocr"},
    "AsrClient": {"transcribe"},
    "TranslationClient": {"translate"},
    "NliClient": {"entails"},
    "EmbeddingClient": {"embed"},
}

# module -> (class name, interface it implements)
CONCRETE = {
    "vakeel_sahayak.models.vllm_client": ("VllmClient", "LLMClient"),
    "vakeel_sahayak.models.local_llm": ("LocalLLMClient", "LLMClient"),
    "vakeel_sahayak.models.vlm": ("LocalVisionClient", "VisionClient"),
    "vakeel_sahayak.models.ocr": ("SuryaOcrClient", "OcrClient"),
    "vakeel_sahayak.models.asr": ("WhisperAsrClient", "AsrClient"),
    "vakeel_sahayak.models.translation": ("IndicTrans2Client", "TranslationClient"),
    "vakeel_sahayak.models.nli": ("DebertaNliClient", "NliClient"),
    "vakeel_sahayak.models.embeddings": ("Bgem3EmbeddingClient", "EmbeddingClient"),
}

HEAVY = ["torch", "vllm", "transformers", "openai", "peft", "bitsandbytes", "sentence_transformers"]


def _model_modules() -> list[str]:
    pkg = importlib.import_module("vakeel_sahayak.models")
    return [m.name for m in pkgutil.iter_modules(pkg.__path__, "vakeel_sahayak.models.")]


# ---------------------------------------------------------------------------------------------------------------------
# abstract interfaces
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("iface,methods", sorted(INTERFACES.items()))
def test_interface_has_exactly_the_documented_abstract_methods(iface, methods):
    """Each interface in models/base.py declares exactly its documented abstract methods."""
    cls = getattr(base, iface)
    assert inspect.isabstract(cls)
    assert set(cls.__abstractmethods__) == methods


@pytest.mark.parametrize("iface", sorted(INTERFACES))
def test_interface_cannot_be_instantiated(iface):
    """An abstract client cannot be instantiated directly."""
    with pytest.raises(TypeError):
        getattr(base, iface)()


def test_llm_generate_signature_matches_plan():
    """LLMClient.generate takes (prompt, max_tokens=1024, temperature=0.0, json_schema=None) for constrained decoding."""
    params = inspect.signature(base.LLMClient.generate).parameters
    assert list(params) == ["self", "prompt", "max_tokens", "temperature", "json_schema"]
    assert params["max_tokens"].default == 1024
    assert params["temperature"].default == 0.0
    assert params["json_schema"].default is None


def test_every_interface_is_covered_by_this_test_module():
    """All ABCs defined in models/base.py are listed here, so a new model type needs a new test."""
    abcs = {n for n, c in vars(base).items() if inspect.isclass(c) and c.__module__ == base.__name__ and inspect.isabstract(c)}
    assert abcs == set(INTERFACES)


# ---------------------------------------------------------------------------------------------------------------------
# concrete classes
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("module,spec", sorted(CONCRETE.items()))
def test_concrete_client_subclasses_right_interface_and_is_complete(module, spec):
    """Each concrete client subclasses its interface and implements every abstract method (no abstract leftovers)."""
    name, iface = spec
    cls = getattr(importlib.import_module(module), name)
    assert issubclass(cls, getattr(base, iface))
    assert not inspect.isabstract(cls)
    others = [getattr(base, i) for i in INTERFACES if i != iface]
    assert not any(issubclass(cls, o) for o in others), "a client implements exactly one interface"


@pytest.mark.parametrize("module,spec", sorted(CONCRETE.items()))
def test_concrete_client_signatures_match_interface(module, spec):
    """Overriding methods keep the interface's parameter names, so callers can swap clients."""
    name, iface = spec
    cls = getattr(importlib.import_module(module), name)
    for method in INTERFACES[iface]:
        want = list(inspect.signature(getattr(getattr(base, iface), method)).parameters)
        got = list(inspect.signature(getattr(cls, method)).parameters)
        assert got == want, f"{name}.{method}"


def test_every_models_module_defines_a_known_client_or_is_a_known_helper():
    """No unreviewed model module: each models.* module is a listed client, base, factory, labeler or teacher."""
    known = set(CONCRETE) | {
        "vakeel_sahayak.models.base",
        "vakeel_sahayak.models.factory",
        "vakeel_sahayak.models.labeler",
        "vakeel_sahayak.models.teacher",
        # RECONCILED: helpers the plan's clients need but does not name: the deterministic offline stand-ins
        # (VS_MODELS=offline, plan §15.4), the JSON-schema grammar helper (constrained decoding, §12) and the shared prompt layout.
        "vakeel_sahayak.models.offline",
        "vakeel_sahayak.models.offline_llm",
        "vakeel_sahayak.models.json_schema",
        "vakeel_sahayak.models.prompting",
        "vakeel_sahayak.models.prefix",  # RECONCILED: sweep 3 (S14d) prefix-friendly layout helper and shared-prefix meter; not a client
        # RECONCILED: the Sarvam API package (external, off by default); its adapters implement the interfaces above.
        "vakeel_sahayak.models.sarvam",
        # RECONCILED: the OpenAI API package (external, off by default, hard spending cap); its adapter implements LLMClient.
        "vakeel_sahayak.models.openai",
        # RECONCILED: the paid-provider lock (owner decision 2026-10-28); a guard, not a client.
        "vakeel_sahayak.models.paid_lock",
    }
    assert set(_model_modules()) == known


def test_eval_labeler_and_teacher_are_not_llm_clients():
    """EvalLabeler and TeacherClient are evaluation/training only: they must not be usable as an agent LLMClient."""
    from vakeel_sahayak.models.labeler import EvalLabeler
    from vakeel_sahayak.models.teacher import TeacherClient

    assert not issubclass(EvalLabeler, base.LLMClient)
    assert not issubclass(TeacherClient, base.LLMClient)
    for cls in (EvalLabeler, TeacherClient):
        assert not any(issubclass(cls, getattr(base, i)) for i in INTERFACES)


def test_labeler_and_teacher_public_methods():
    """The labeler labels against a closed label set; the teacher returns a CaseDossier from facts text (plan §12)."""
    from vakeel_sahayak.models.labeler import EvalLabeler
    from vakeel_sahayak.models.teacher import TeacherClient
    from vakeel_sahayak.schemas.dossier import CaseDossier

    assert list(inspect.signature(EvalLabeler.label).parameters) == ["self", "text", "label_set"]
    sig = inspect.signature(TeacherClient.dossier_from_facts)
    assert list(sig.parameters) == ["self", "facts_text"]
    assert "CaseDossier" in str(sig.return_annotation) or sig.return_annotation is CaseDossier


# ---------------------------------------------------------------------------------------------------------------------
# no heavy imports at import time (subprocess so earlier tests cannot pollute sys.modules)
# ---------------------------------------------------------------------------------------------------------------------
def test_importing_every_models_module_does_not_import_heavy_libraries():
    """Heavy libraries (torch, vllm, transformers, ...) are imported inside functions only (skeleton 'Layout')."""
    mods = _model_modules() + ["vakeel_sahayak.models"]
    code = (
        "import importlib, sys\n"
        f"for m in {mods!r}:\n"
        "    importlib.import_module(m)\n"
        f"heavy = [h for h in {HEAVY!r} if h in sys.modules]\n"
        "assert not heavy, heavy\n"
    )
    res = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=SRC.parent.parent,
        env={**__import__("os").environ, "PYTHONPATH": str(SRC.parent)},
    )
    assert res.returncode == 0, res.stderr[-2000:]


# ---------------------------------------------------------------------------------------------------------------------
# system code never reaches evaluation-only models or model libraries directly (AST scan)
# ---------------------------------------------------------------------------------------------------------------------
def _imports(path: Path) -> set[str]:
    """All imported dotted names in a file, at any nesting depth (including imports inside functions)."""
    out: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


def _py_files(*packages: str) -> list[Path]:
    files = [p for pkg in packages for p in (SRC / pkg).rglob("*.py")]
    assert files, packages
    return files


SYSTEM_PACKAGES = ["agents", "ingestion", "tools", "rights", "record", "orchestration"]


@pytest.mark.parametrize("package", SYSTEM_PACKAGES)
def test_system_packages_never_import_labeler_or_teacher(package):
    """The Llama labeler and the teacher are evaluation/training only; the system never imports them (plan §12)."""
    bad = []
    for f in _py_files(package):
        for name in _imports(f):
            if name.startswith(("vakeel_sahayak.models.labeler", "vakeel_sahayak.models.teacher")):
                bad.append((f.relative_to(SRC).as_posix(), name))
    assert not bad


@pytest.mark.parametrize("package", SYSTEM_PACKAGES)
def test_system_packages_do_not_import_model_libraries_directly(package):
    """All LLM calls go through models/ clients: no vllm, transformers or openai imports in system code (plan §12)."""
    bad = []
    for f in _py_files(package):
        for name in _imports(f):
            if name.split(".")[0] in {"vllm", "transformers", "openai"}:
                bad.append((f.relative_to(SRC).as_posix(), name))
    assert not bad


def test_labeler_and_teacher_modules_have_no_system_importers_anywhere_but_eval_side():
    """Only eval/, pipelines/gold, finetune and the factory-free model modules may import labeler/teacher."""
    allowed = ("eval/", "pipelines/", "finetune/", "models/")
    offenders = []
    for f in SRC.rglob("*.py"):
        rel = f.relative_to(SRC).as_posix()
        if rel.startswith(allowed):
            continue
        if any(n.startswith(("vakeel_sahayak.models.labeler", "vakeel_sahayak.models.teacher")) for n in _imports(f)):
            offenders.append(rel)
    assert not offenders


def test_factory_does_not_expose_labeler_or_teacher_getter():
    """models/factory resolves system roles only: it has no get_labeler / get_teacher."""
    from vakeel_sahayak.models import factory

    public = {n for n in vars(factory) if n.startswith("get_")}
    # RECONCILED: get_tts (Sarvam Bulbul, test-set construction) and get_langid (Sarvam /text-lid) are not labeler/teacher getters;
    # get_llm_model builds the client of an AGENT role with an explicit model id (the B0L baseline), not a labeler or a teacher.
    assert public == {
        "get_llm",
        "get_llm_model",
        "get_vision",
        "get_ocr",
        "get_asr",
        "get_translator",
        "get_nli",
        "get_embedder",
        "get_tts",
        "get_langid",
    }


# ---------------------------------------------------------------------------------------------------------------------
# configs/models.yaml roles
# ---------------------------------------------------------------------------------------------------------------------
def _agent_classes():
    from vakeel_sahayak.agents.registry import AGENT_CLASSES

    out = {}
    for name, dotted in AGENT_CLASSES.items():
        mod, cls = dotted.rsplit(".", 1)
        out[name] = getattr(importlib.import_module(mod), cls)
    return out


def test_six_agents_declare_a_role_model():
    """Each of the six agents declares ROLE_MODEL (plan §3.2)."""
    classes = _agent_classes()
    assert set(classes) == {"MUNSHI", "PESHKAR", "SUTRADHAR", "VAKEEL", "ABHIYOJAK", "PAIROKAR"}
    for name, cls in classes.items():
        assert isinstance(cls.ROLE_MODEL, str) and cls.ROLE_MODEL, name


@pytest.mark.parametrize(
    "agent,role",
    [
        ("MUNSHI", "munshi_4b"),
        ("PESHKAR", "extractor_4b"),
        ("SUTRADHAR", "agents_14b"),
        ("VAKEEL", "agents_14b"),
        ("ABHIYOJAK", "agents_14b"),
        ("PAIROKAR", "agents_14b"),
    ],
)
def test_agent_role_resolves_in_models_yaml(load_yaml, agent, role):
    """Each agent's ROLE_MODEL is the plan §3.2 role and exists under `llm:` in configs/models.yaml, listing that agent."""
    cls = _agent_classes()[agent]
    assert cls.ROLE_MODEL == role
    llm = load_yaml("models.yaml")["llm"]
    assert role in llm
    assert agent.lower() in llm[role]["used_by"]


def test_model_placement_matches_plan(load_yaml):
    """Munshi/Peshkar roles run locally on the laptop, the 14B agents on Ada via vLLM (plan §3.2, §12)."""
    llm = load_yaml("models.yaml")["llm"]
    assert (llm["agents_14b"]["runtime"], llm["agents_14b"]["where"]) == ("vllm", "ada")
    for role in ("munshi_4b", "extractor_4b"):
        assert (llm[role]["runtime"], llm[role]["where"]) == ("local", "laptop")
    assert llm["extractor_4b"]["adapter"], "Peshkar's extractor is the QLoRA adapter"
    assert llm["munshi_4b"]["adapter"] is None, "Munshi runs the base 4B"


def test_eval_labeler_is_not_a_system_role_and_differs_in_family_from_teacher(load_yaml):
    """The labeler is never an agent role, is flagged system_use false, and is a different family than the teacher."""
    llm = load_yaml("models.yaml")["llm"]
    assert llm["eval_labeler"]["system_use"] is False
    used = {cls.ROLE_MODEL for cls in _agent_classes().values()}
    assert "eval_labeler" not in used and "teacher" not in used
    family = lambda m: m.split("/")[0].lower()  # noqa: E731
    assert family(llm["eval_labeler"]["model"]) != family(llm["teacher"]["model"])
    assert "llama" in llm["eval_labeler"]["model"].lower()
    assert "qwen" in llm["teacher"]["model"].lower()
