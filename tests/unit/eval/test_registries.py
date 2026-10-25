"""Baseline, ablation and ingestion-pipeline registries (plan §15.3-15.5) and the run registry (§17, configs/eval/runs.yaml).

The registries are the modules under vakeel_sahayak.eval.{baselines,ablations,ingestion}, discovered by naming convention
(skeleton.md: `b0_*` ... `b4_*`, `a1_*` ... `a10_*`, `p1_*` ... `p6_*`). Structure tests pass today; `make_switches()` /
`run_case()` behaviour tests fail until implemented.
"""

import importlib
import inspect
import pkgutil
import re

import pytest

from vakeel_sahayak.orchestration.switches import Switches


def module_names(package: str) -> dict[str, str]:
    """Map short id ('b0', 'a10', 'p6') -> module name for every module in the package."""
    pkg = importlib.import_module(package)
    found = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        m = re.match(r"([bap]\d+)_", info.name)
        if m:
            found[m.group(1)] = f"{package}.{info.name}"
    return found


BASELINES = module_names("vakeel_sahayak.eval.baselines")
ABLATIONS = module_names("vakeel_sahayak.eval.ablations")
PIPELINES = module_names("vakeel_sahayak.eval.ingestion")


# ------------------------------------------------------------------ registries are complete
def test_baselines_b0_to_b4_and_full_system():
    """Plan §15.3: B0-B4 plus the Full system module (and B6, the no-model expert-rule baseline of docs/evaluation-plan.md 3.1)."""
    assert sorted(BASELINES) == ["b0", "b1", "b2", "b3", "b4", "b6"]  # RECONCILED: B6 (expert-rule, no model) is a baseline of evaluation-plan 3.1
    importlib.import_module("vakeel_sahayak.eval.baselines.full_system")


def test_ablations_a1_to_a10():
    """Plan §15.4: ten ablations A1-A10."""
    assert sorted(ABLATIONS, key=lambda s: int(s[1:])) == [f"a{i}" for i in range(1, 11)]


def test_ingestion_pipelines_p1_to_p6_and_munshi():
    """Plan §15.5: P1-P6 plus the full Munshi pipeline."""
    assert sorted(PIPELINES) == [f"p{i}" for i in range(1, 7)]
    importlib.import_module("vakeel_sahayak.eval.ingestion.munshi_full")


@pytest.mark.parametrize("module", sorted(BASELINES.values()))
def test_baseline_entry_point_signature(module):
    """Every baseline exposes run_case(case, ctx) -> BailBrief."""
    fn = importlib.import_module(module).run_case
    assert list(inspect.signature(fn).parameters) == ["case", "ctx"]


@pytest.mark.parametrize("module", sorted(PIPELINES.values()) + ["vakeel_sahayak.eval.ingestion.munshi_full"])
def test_pipeline_entry_point_signature(module):
    """Every ingestion pipeline exposes ingest_bundle(pdf_path, ctx=None) -> IngestionReport."""
    fn = importlib.import_module(module).ingest_bundle
    assert list(inspect.signature(fn).parameters) == ["pdf_path", "ctx"]


@pytest.mark.parametrize("module", sorted(ABLATIONS.values()))
def test_ablation_entry_points_and_declared_switch(module):
    """Each ablation has make_switches() and a resumable run(cases_path, out_dir, shard, n_shards), and its docstring names
    switches that exist on `Switches`."""
    mod = importlib.import_module(module)
    assert list(inspect.signature(mod.run).parameters) == ["cases_path", "out_dir", "shard", "n_shards"]
    assert inspect.signature(mod.make_switches).return_annotation in (Switches, "Switches")
    for name in re.findall(r"Switch: (\w+)", mod.__doc__ or ""):
        assert name in Switches.model_fields, f"{module} declares unknown switch {name}"
    assert "Switch" in (mod.__doc__ or "")


def test_every_switch_belongs_to_some_ablation_or_variant():
    """Each field of Switches is documented by an ablation (A1-A10) or an ingestion variant (P5/P6) or the A6 fallback."""
    documented = set()
    for module in ABLATIONS.values():
        documented |= set(re.findall(r"(\w+)(?:=|\s+in\s+\{)", (importlib.import_module(module).__doc__ or "").split("Switch:")[-1]))
    documented |= {"munshi_no_gap_check", "munshi_no_bundle_split"}  # P5 / P6 live in the Switches class comments
    # RECONCILED: the S-variants of evaluation plan 3.3 are documented in switches.py and docs/literature-to-code-map.md, not by ablation modules
    # RECONCILED: EV-01 adds fields per evaluation-plan §3.4 (named variants in ARCHITECTURE / INGESTION / BASELINE_SWITCHES)
    ev01 = {
        "retrieval_policy", "weak_signal", "graph_expansion", "store_prior", "munshi_gap_policy", "repair_mode", "critic_mode",
        "abhiyojak_isolation", "draft_mode", "topology", "plan_cache", "urgency_policy", "output_format", "no_typed_handoff",
        "no_spotlighting", "no_guard", "munshi_image_only", "chunking",
        "authority_stance", "munshi_keep_weak_text",  # RECONCILED: sweep 4 (S18, P8)
        "prefix_layout",  # RECONCILED: sweep 3 added S14d (prefix-friendly prompt layout)
    }
    assert set(Switches.model_fields) <= documented | {"extractor", "knockout_store", "stopping"} | ev01


# ------------------------------------------------------------------ run registry and hypotheses config
def test_run_registry_matches_plan(load_yaml):
    """configs/eval/runs.yaml: shard 5 h; RQ1 systems Full/B0/B1/B4 x3 runs and B2/B3 x1; ablations A1-A4, A6-A9 on 100 cases;
    A10 as a separate retrieval-level job; statistics block of plan §15.9; one sbatch-able job only (QLoRA)."""
    runs = load_yaml("eval/runs.yaml")
    assert runs["shard_hours"] == 5
    jobs = runs["jobs"]
    assert jobs["rq1_full"]["systems"] == ["full", "b0", "b1", "b4"] and jobs["rq1_full"]["runs"] == 3
    assert jobs["rq1_full"]["cases"] == 200 and jobs["rq1_full"]["testset"] == "T1"
    assert jobs["rq1_b2_b3"]["systems"] == ["b2", "b3"] and jobs["rq1_b2_b3"]["runs"] == 1
    assert jobs["ablations"]["ids"] == ["A1", "A2", "A3", "A4", "A6", "A7", "A8", "A9"] and jobs["ablations"]["cases"] == 100
    assert "a10_knockouts" in jobs and "a5_extractors" in jobs
    assert jobs["a5_extractors"]["variants"] == ["finetuned_4b", "base_4b", "prompted_32b"]
    assert [name for name, j in jobs.items() if j.get("where") == "ada-batch"] == ["qlora"]
    stats = runs["statistics"]
    assert stats["bootstrap_ci"] == 0.95 and stats["test"] == "wilcoxon_signed_rank" and stats["correction"] == "holm_bonferroni"
    assert stats["repeats"] == {"full": 3, "b0": 3, "b1": 3, "b4": 3, "others": 1}


def test_ada_job_node_hours_match_plan_totals(load_yaml):
    """Plan §17 per-job node-hours: teacher 60, RQ1 82, ablations 50, A5 6, RQ2 vision 3, RQ2 full 7.5, F2 18, F1/F5/F6 6.5,
    F3 10, F4 5, T6 2, T7 9 (sum with 20 dev hours = ~279)."""
    jobs = load_yaml("eval/runs.yaml")["jobs"]
    expected = {"teacher_dossiers": 60, "rq1_full": 82, "ablations": 50, "a5_extractors": 6, "rq2_vision": 3, "rq2_full": 7.5,
                "f2_change_sets": 18, "f1_f5_f6": 6.5, "f3_baselines": 10, "f4_nocache": 5, "t6_tool_calling": 2, "t7_safety": 9}
    for name, hours in expected.items():
        assert jobs[name]["node_hours"] == hours, name
    assert sum(expected.values()) + 20 == pytest.approx(278.0, abs=1.5)  # plan total ~279 including 20 dev hours


def test_hypotheses_registry(load_yaml):
    """Plan §14.2: H1a, H1b, H1c, H2 are registered."""
    hyp = load_yaml("eval/hypotheses.yaml")
    assert {"H1a", "H1b", "H1c", "H2"} <= set(hyp)


def test_failure_classes_are_the_eleven_of_plan_15_9():
    """Plan §15.9 failure analysis lists exactly eleven automatic error types."""
    from vakeel_sahayak.eval.failure_analysis import ErrorType

    assert {e.name for e in ErrorType} == {
        "WRONG_ROUTE_OR_OCR", "WRONG_SPLIT_OR_TYPE", "WRONG_SECTION_OR_DATE", "UNSUPPORTED_FACT", "MISSED_FACTOR",
        "MISGROUNDED_AUTHORITY", "WRONG_TRANSFER", "OVERRULED_CITED", "STALE_AFTER_UPDATE", "MISSED_OBJECTION",
        "WRONG_RIGHTS_FLAG",
    }


# ------------------------------------------------------------------ ablation switches (fail until implemented)
ABLATION_SWITCH = {
    "a1": {"no_dossier": True},
    "a2": {"no_check_repair": True},
    "a3": {"no_tools": True},
    "a4": {"plain_retrieval": True},
    "a6": {"fixed_router": True},
    "a7": {"free_planner": True},
    "a8": {"no_sparring": True},
    "a9": {"no_sparring": True, "no_check_repair": True},
}


@pytest.mark.parametrize("ablation", sorted(ABLATION_SWITCH))
def test_make_switches_sets_exactly_the_documented_flags(ablation):
    """Each ablation flips only its documented flag(s) and leaves every other switch at the full-system default."""
    switches = importlib.import_module(ABLATIONS[ablation]).make_switches()
    default = Switches().model_dump()
    changed = {k: v for k, v in switches.model_dump().items() if v != default[k]}
    assert changed == ABLATION_SWITCH[ablation]


def test_a5_covers_the_three_extractors():
    """A5 is parametrised by extractor in {finetuned_4b, base_4b, prompted_32b}."""
    mod = importlib.import_module(ABLATIONS["a5"])
    assert mod.make_switches().extractor in {"finetuned_4b", "base_4b", "prompted_32b"}


def test_a10_knocks_out_one_store():
    """A10 removes one store at a time via knockout_store."""
    from vakeel_sahayak.schemas.enums import StoreName

    sw = importlib.import_module(ABLATIONS["a10"]).make_switches()
    assert sw.knockout_store in {s.value for s in StoreName}


def test_two_by_two_sparring_verifier_design():
    """The 2x2 of §9/§15.4: Full (neither flag), A2 (no check-repair), A8 (no sparring), A9 (neither check nor sparring)
    are four distinct settings."""
    combos = set()
    combos.add((False, False))  # Full
    for ab in ("a2", "a8", "a9"):
        sw = importlib.import_module(ABLATIONS[ab]).make_switches()
        combos.add((sw.no_check_repair, sw.no_sparring))
    assert combos == {(False, False), (True, False), (False, True), (True, True)}


# ------------------------------------------------------------------ baselines on the fakes (fail until implemented)
def _case(world):
    return {"case_id": "case-0007", "facts": "The accused was arrested on 20.08.2024 for cheating under Section 318(4) BNS. "
            "Charge sheet filed 02.11.2024. Co-accused-1 granted bail 05.12.2024.", "before": world.case_date}


def test_b0_is_one_llm_call_no_retrieval_no_agents(make_ctx, toolbox):
    """B0 single pass: exactly one LLM call and no tool or store call (plan §15.3)."""
    from tests.fakes.models import ScriptedLLM
    from vakeel_sahayak.eval.baselines import b0_single_pass

    llm = ScriptedLLM(strict=False, default='{"grounds": []}')
    ctx = make_ctx(llm=llm, toolbox=toolbox)
    b0_single_pass.run_case(_case(toolbox.world), ctx)
    assert len(llm.calls) == 1
    assert toolbox.calls == [] and toolbox.store_calls() == 0


def test_b4_queries_every_shared_store_without_a_planner(make_ctx, toolbox):
    """B4: every store is queried with the facts and factor names, results fused by RRF; no RetrievalPlan call (no orchestrator)."""
    from tests.fakes.models import ScriptedLLM
    from vakeel_sahayak.eval.baselines import b4_all_stores

    llm = ScriptedLLM(strict=False, default='{"grounds": []}')
    ctx = make_ctx(llm=llm, toolbox=toolbox)
    b4_all_stores.run_case(_case(toolbox.world), ctx)
    assert not llm.calls_for("RetrievalPlan")
    queried = {c.name for c in toolbox.calls}
    assert {"search_reasoning", "search_objections", "search_arguments", "similar_orders", "search_statutes"} <= queried
    for call in toolbox.calls:
        if "before" in call.kwargs:
            assert call.kwargs["before"] == "2025-02-03"
