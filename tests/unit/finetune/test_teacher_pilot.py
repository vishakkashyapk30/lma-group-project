"""The week-1 teacher pilot and its decision rule (plan §12 'Teacher', §17 'Teacher pilot').

Plan §17: Qwen3-32B-AWQ on Ada vs a Mistral API model on the SAME 50 train orders; measure (1) the share of outputs where every field
passes span_check, (2) tokens per hour, (3) rate-limit stalls. Decision rule: whichever gives MORE VERIFIED PAIRS PER DAY. The API is used only
if (1) its terms allow training use of the outputs, (2) it is free or within a stated budget, (3) versions are pinned and all outputs
are cached; if any condition fails the teacher is Qwen3-32B on Ada. Family rule: the teacher and the evaluation labeler must not be the
same model family.

SKELETON-GAP: the skeleton has `teacher_pilot` (measurement) but no function that applies the decision rule or the family rule. The
tests below fix the intended interface, in `vakeel_sahayak.finetune.teacher_dossiers`:

    verified_pairs_per_day(share_all_pass, tokens_per_hour, tokens_per_order=12_000) -> float
    choose_teacher(metrics: {arm: {metric: value}}, api_conditions: {condition: bool}, tokens_per_order=12_000) -> arm name
    assert_family_rule(teacher_model, labeler_model) -> None        # raises ValueError when both are the same family

Plan §17's own numbers set the default: a teacher order is about 12K tokens ("4K orders x 12K tokens"). They fail until written.
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.finetune._helpers import teacher_dossier, write_jsonl
from vakeel_sahayak.finetune import teacher_dossiers
from vakeel_sahayak.schemas.dossier import CaseDossier

QWEN, MISTRAL = "qwen3-32b-awq-ada", "mistral-api"
ALL_OK = {"terms_allow_training_use": True, "free_or_stated_budget": True, "versions_pinned_and_outputs_cached": True}


def intended(name: str):
    fn = getattr(teacher_dossiers, name, None)
    assert fn is not None, f"SKELETON-GAP: finetune.teacher_dossiers.{name} does not exist yet (plan §17 decision rule)"
    return fn


def arm(share: float, tokens_per_hour: float, stalls: float = 0.0) -> dict[str, float]:
    return {"share_all_fields_pass_span_check": share, "tokens_per_hour": tokens_per_hour, "rate_limit_stalls": stalls}


# ---------------------------------------------------------------- the pilot configuration (passes today)
def test_pilot_config_matches_plan_17(load_yaml):
    cfg = load_yaml("finetune/teacher_pilot.yaml")
    assert cfg["orders"] == 50
    assert cfg["arms"] == [QWEN, MISTRAL]
    assert cfg["metrics"] == ["share_all_fields_pass_span_check", "tokens_per_hour", "rate_limit_stalls"]
    assert cfg["api_conditions"] == ["terms_allow_training_use", "free_or_stated_budget", "versions_pinned_and_outputs_cached"]
    assert "family" in cfg["family_rule"].lower()


def test_pilot_default_is_fifty_orders():
    assert inspect.signature(teacher_dossiers.teacher_pilot).parameters["n"].default == 50


def test_teacher_pilot_registry_entries_agree_with_models_yaml(load_yaml):
    """The Ada arm is the `teacher` role of models.yaml and the API arm is its declared alternative."""
    teacher = load_yaml("models.yaml")["llm"]["teacher"]
    assert teacher["model"] == "Qwen/Qwen3-32B-AWQ" and "mistral" in teacher["api_alternative"]
    assert teacher["public_orders_only"] is True
    assert teacher["where"] == "ada"


def test_teacher_job_hours_in_runs_yaml_vanish_with_the_api(load_yaml):
    """Plan §17: teacher dossiers cost 60 node-hours on Ada and 0 with the API (about 60 node-hours freed)."""
    assert load_yaml("eval/runs.yaml")["jobs"]["teacher_dossiers"] == {"where": "ada", "model": "teacher", "node_hours": 60}


# ---------------------------------------------------------------- measurement: same orders, both arms
class SpyTeacher:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def __call__(self, facts_text: str) -> CaseDossier:  # patched in place of TeacherClient.dossier_from_facts
        self.seen.append(facts_text)
        return CaseDossier.model_validate(teacher_dossier())


def pilot_orders(tmp_path, n: int):
    rows = [{"doc_id": f"o{i:03d}", "facts": f"Facts of order {i}: arrested on 20.08.2024."} for i in range(n)]
    return write_jsonl(tmp_path / "orders.jsonl", rows), rows


def test_both_arms_read_the_same_fifty_orders(tmp_path, monkeypatch):
    """Same 50 orders for both arms (plan §17 'How'): each of 50 facts texts is sent exactly twice, once per arm."""
    spy = SpyTeacher()
    monkeypatch.setattr("vakeel_sahayak.models.teacher.TeacherClient.dossier_from_facts", lambda self, t: spy(t))
    path, _ = pilot_orders(tmp_path, 80)
    teacher_dossiers.teacher_pilot(str(path))
    assert len(spy.seen) == 100 and len(set(spy.seen)) == 50
    assert all(spy.seen.count(t) == 2 for t in set(spy.seen))


def test_pilot_reports_the_three_metrics_for_each_arm(tmp_path, monkeypatch):
    """The returned dict has the share passing span_check, tokens per hour and rate-limit stalls for the Ada arm and the API arm.
    # ASSUMPTION: keys contain the arm name and the metric name (e.g. 'mistral-api/tokens_per_hour')."""
    spy = SpyTeacher()
    monkeypatch.setattr("vakeel_sahayak.models.teacher.TeacherClient.dossier_from_facts", lambda self, t: spy(t))
    path, _ = pilot_orders(tmp_path, 50)
    res = teacher_dossiers.teacher_pilot(str(path), n=50)
    assert all(isinstance(v, float) for v in res.values())
    for a in (QWEN, MISTRAL):
        for metric in ("share_all_fields_pass_span_check", "tokens_per_hour", "rate_limit_stalls"):
            assert any(a in k and metric in k for k in res), (a, metric)


def test_pilot_with_fewer_orders_than_n_uses_all_of_them(tmp_path, monkeypatch):
    spy = SpyTeacher()
    monkeypatch.setattr("vakeel_sahayak.models.teacher.TeacherClient.dossier_from_facts", lambda self, t: spy(t))
    path, _ = pilot_orders(tmp_path, 12)
    teacher_dossiers.teacher_pilot(str(path), n=50)
    assert len(set(spy.seen)) == 12


# ---------------------------------------------------------------- the decision rule (SKELETON-GAP)
@pytest.mark.parametrize(
    ("share", "tph", "expected"),
    [(0.5, 800_000, 800.0), (1.0, 800_000, 1600.0), (0.0, 800_000, 0.0), (0.45, 2_400_000, 2160.0)],
)
def test_verified_pairs_per_day_is_share_times_orders_per_day(share, tph, expected):
    """verified pairs/day = share passing x (tokens per hour / 12K tokens per order) x 24: 800K tokens/h = 66.7 orders/h = 1,600/day."""
    assert intended("verified_pairs_per_day")(share, tph) == pytest.approx(expected)


def test_tokens_per_order_is_a_parameter():
    assert intended("verified_pairs_per_day")(0.5, 800_000, tokens_per_order=6_000) == pytest.approx(1600.0)


def test_the_arm_with_more_verified_pairs_per_day_wins():
    """Mistral: 45% pass at 2.4M tokens/h = 2,160 pairs/day; Qwen: 55% at 0.8M = 880: the API wins when its conditions hold."""
    metrics = {QWEN: arm(0.55, 800_000), MISTRAL: arm(0.45, 2_400_000)}
    assert intended("choose_teacher")(metrics, ALL_OK) == MISTRAL


def test_a_higher_pass_share_does_not_win_if_throughput_is_lower():
    """The rule is pairs per day, not quality alone: Qwen 90% pass but 0.8M tokens/h (1,440/day) loses to Mistral 40% at 3M (2,400/day)."""
    metrics = {QWEN: arm(0.9, 800_000), MISTRAL: arm(0.4, 3_000_000)}
    assert intended("choose_teacher")(metrics, ALL_OK) == MISTRAL


def test_qwen_wins_when_it_produces_more_pairs_per_day():
    metrics = {QWEN: arm(0.6, 800_000), MISTRAL: arm(0.4, 1_000_000)}  # 960 vs 800 pairs/day
    assert intended("choose_teacher")(metrics, ALL_OK) == QWEN


def test_rate_limit_stalls_do_not_enter_the_rule_directly():
    """Stalls are measured and reported, but they already lower tokens per hour: with equal pairs per day, stalls change nothing."""
    a = {QWEN: arm(0.6, 800_000), MISTRAL: arm(0.4, 1_000_000, stalls=0)}
    b = {QWEN: arm(0.6, 800_000), MISTRAL: arm(0.4, 1_000_000, stalls=40)}
    assert intended("choose_teacher")(a, ALL_OK) == intended("choose_teacher")(b, ALL_OK)


def test_a_tie_goes_to_the_open_model_on_ada():
    """# ASSUMPTION: equal pairs per day -> the Ada teacher (no external dependency, no terms to check)."""
    metrics = {QWEN: arm(0.5, 800_000), MISTRAL: arm(0.5, 800_000)}
    assert intended("choose_teacher")(metrics, ALL_OK) == QWEN


# ---------------------------------------------------------------- the three conditions for using the API
API_WINS = {QWEN: arm(0.3, 800_000), MISTRAL: arm(0.6, 3_000_000)}


@pytest.mark.parametrize("failed", sorted(ALL_OK))
def test_api_is_refused_when_any_single_condition_fails(failed):
    """Plan §17: terms must allow training use, it must be free or within budget, versions pinned and outputs cached. One failure -> Qwen."""
    conditions = {**ALL_OK, failed: False}
    assert intended("choose_teacher")(API_WINS, conditions) == QWEN


def test_api_is_refused_when_all_conditions_fail():
    assert intended("choose_teacher")(API_WINS, {k: False for k in ALL_OK}) == QWEN


def test_api_is_chosen_only_if_it_wins_and_every_condition_holds():
    assert intended("choose_teacher")(API_WINS, ALL_OK) == MISTRAL


def test_an_unrecorded_condition_counts_as_failed():
    """# ASSUMPTION: a condition nobody checked (missing key) is not a pass."""
    partial = {"terms_allow_training_use": True, "free_or_stated_budget": True}
    assert intended("choose_teacher")(API_WINS, partial) == QWEN


def test_no_api_measurements_means_qwen():
    """If the API arm was not piloted there is nothing to compare: Qwen3-32B on Ada."""
    assert intended("choose_teacher")({QWEN: arm(0.5, 800_000)}, ALL_OK) == QWEN


# ---------------------------------------------------------------- the family rule (SKELETON-GAP)
LLAMA = "meta-llama/Llama-3.1-8B-Instruct"


@pytest.mark.parametrize("teacher", ["Qwen/Qwen3-32B-AWQ", "mistral-small", "mistral-medium-latest"])
def test_teacher_in_a_different_family_from_the_llama_labeler_is_accepted(teacher):
    intended("assert_family_rule")(teacher, LLAMA)


@pytest.mark.parametrize(
    ("teacher", "labeler"),
    [
        ("meta-llama/Llama-3.1-70B-Instruct", LLAMA),  # same family, different size
        ("Qwen/Qwen3-32B-AWQ", "Qwen/Qwen3-14B"),  # a Qwen labeler would be Qwen grading Qwen
        ("mistral-small", "mistralai/Mistral-7B-Instruct"),
    ],
)
def test_teacher_and_labeler_of_the_same_family_are_rejected(teacher, labeler):
    """Plan §17 family rule: the same model family may not be both the teacher and the evaluation labeler."""
    with pytest.raises(ValueError):
        intended("assert_family_rule")(teacher, labeler)


def test_both_pilot_arms_pass_the_family_rule_against_the_default_labeler(load_yaml):
    """Whichever arm wins, the default labeler (Llama-3.1-8B) is a different family from Qwen and from Mistral."""
    labeler = load_yaml("models.yaml")["llm"]["eval_labeler"]["model"]
    check = intended("assert_family_rule")
    check(load_yaml("models.yaml")["llm"]["teacher"]["model"], labeler)
    check(load_yaml("models.yaml")["llm"]["teacher"]["api_alternative"], labeler)


def test_a_non_qwen_api_labeler_is_acceptable_only_with_a_non_mistral_teacher():
    """Plan §17: the labeler may be Llama on Ada or a non-Qwen API model; if the labeler were a Mistral API model, a Mistral teacher is out."""
    check = intended("assert_family_rule")
    check("Qwen/Qwen3-32B-AWQ", "mistral-small")
    with pytest.raises(ValueError):
        check("mistral-medium-latest", "mistral-small")

