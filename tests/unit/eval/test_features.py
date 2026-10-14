"""Feature evaluations F1-F8 (plan §15.6): each module has `run(out_dir, shard, n_shards)` (system and comparison arms, resumable) and
`score(run_dir) -> dict[str, float]`. The module docstring states the feature, test set, gold, comparison and metrics.

| ID | Feature | Test set / gold | Metrics |
| F1 | Abhiyojak sparring | T1, G4 | objection-factor recall and precision vs G4; unsupported-fact rate in replies; share of UNANSWERED flagged |
| F2 | incremental redrafting | T3 | stale-claim rate; unchanged-claim stability; tokens and wall time; no edits on no-op controls |
| F3 | Rights Radar | T4; G7 on T1 | accuracy per rule; false-ELIGIBLE rate; CHECK rate; agreement with G7 |
| F4 | Pairokar batch desk | T5 | missed-deadline rate; pairwise ranking accuracy; cases per node-hour; cache hit rate; output equality |
| F5 | court-ready application | T1, G3 dates | section compliance; List of Dates precision/recall vs G3; dates without source; annexure index |
| F6 | hearing-prep card | T1, G5, G6 | recall/precision of court-discussed factors; recall of imposed condition types |
| F7 | citations, good-law | T9; T1 runs | resolution accuracy by format; coverage; treatment kappa; rate of citing overruled precedents |
| F8 | Hindi and voice | T2 (K5, K6); T8 | Hindi CER; field-accuracy gap Hindi vs English; WER; date/section/number error before and after read-back |

# ASSUMPTION (the plan names the metrics, not the file layout): `score(run_dir)` reads ONE arm's directory, one JSON file per case
# (`run_dir/<case_id>.json`), with the payload keys written in each test; results are means over cases ('macro'), and the metric keys are
# the snake_case names used below. Numbers are small enough to check by hand.
"""

from __future__ import annotations

import importlib
import inspect
import json

import pytest

FEATURES = {
    "f1": ("f1_sparring", ["T1", "G4"], ["recall", "precision", "unsupported", "UNANSWERED"]),
    "f2": ("f2_incremental_redraft", ["T3"], ["stale-claim", "stability", "tokens", "no-op"]),
    "f3": ("f3_rights_radar", ["T4", "G7"], ["accuracy per rule", "false-ELIGIBLE", "CHECK rate"]),
    "f4": ("f4_batch_desk", ["T5"], ["missed-deadline", "pairwise ranking", "node-hour", "cache hit", "output equality"]),
    "f5": ("f5_application", ["T1", "G3"], ["section compliance", "List of Dates", "without source", "annexure"]),
    "f6": ("f6_hearing_card", ["T1", "G5", "G6"], ["G5", "G6", "recall"]),
    "f7": ("f7_citations", ["T9"], ["resolution accuracy", "coverage", "overruled"]),
    "f8": ("f8_hindi_voice", ["T2", "T8", "K5", "K6"], ["CER", "WER", "read-back"]),
}


def mod(fid: str):
    return importlib.import_module(f"vakeel_sahayak.eval.features.{FEATURES[fid][0]}")


def write_arm(tmp_path, rows: dict[str, dict]) -> str:
    d = tmp_path / "arm"
    d.mkdir(exist_ok=True)
    for case_id, payload in rows.items():
        (d / f"{case_id}.json").write_text(json.dumps({"case_id": case_id, **payload}, ensure_ascii=False), encoding="utf-8")
    return str(d)


# ---------------------------------------------------------------- structure (passes today)
def test_there_are_exactly_eight_features():
    import pkgutil

    import vakeel_sahayak.eval.features as pkg

    assert sorted(m.name[:2] for m in pkgutil.iter_modules(pkg.__path__)) == [f"f{i}" for i in range(1, 9)]


@pytest.mark.parametrize("fid", sorted(FEATURES))
def test_entry_points_are_run_and_score(fid):
    m = mod(fid)
    assert list(inspect.signature(m.run).parameters) == ["out_dir", "shard", "n_shards"]
    assert list(inspect.signature(m.score).parameters) == ["run_dir"]
    assert inspect.signature(m.run).parameters["n_shards"].default == 1


@pytest.mark.parametrize("fid", sorted(FEATURES))
def test_docstring_declares_test_set_gold_and_metrics(fid):
    """The module docstring carries the plan §15.6 row: test set, gold and the metrics it reports."""
    doc = mod(fid).__doc__ or ""
    assert f"Feature evaluation {fid.upper()}" in doc
    for needle in FEATURES[fid][1] + FEATURES[fid][2]:
        assert needle.lower() in doc.lower(), (fid, needle)


def test_f1_is_the_sparring_arm_of_the_two_by_two():
    """F1 compares against the 2x2 (A2, A8, A9) of plan §15.4."""
    assert "A2, A8, A9" in mod("f1").__doc__


def test_f7_compares_against_a_regex_only_resolver_and_b0_to_b4():
    assert "regex-only" in mod("f7").__doc__ and "B0-B4" in mod("f7").__doc__


def test_f8_compares_whisper_and_indicconformer_and_no_readback():
    doc = mod("f8").__doc__
    assert "Whisper vs IndicConformer" in doc and "no read-back" in doc


def test_features_run_inside_the_resumable_shard_convention(load_yaml):
    """F1-F6 jobs in runs.yaml are Ada interactive shard jobs (plan §17): f1_f5_f6, f2_change_sets, f3_baselines, f4_nocache."""
    jobs = load_yaml("eval/runs.yaml")["jobs"]
    for name in ("f1_f5_f6", "f2_change_sets", "f3_baselines", "f4_nocache"):
        assert jobs[name]["where"] == "ada"
    assert jobs["f2_change_sets"]["updates"] == 180 and jobs["f2_change_sets"]["noop_controls"] == 60
    assert jobs["f3_baselines"]["scenarios"] == 1000  # 2 comparison arms x 500 T4 scenarios


# ---------------------------------------------------------------- score on constructed run directories
def test_f1_objection_recall_precision_and_unanswered_flagging(tmp_path):
    """Predicted {parity, antecedents, flight_risk} vs G4 {parity, antecedents, witness_tampering, gravity}: recall 2/4, precision 2/3;
    1 of 10 reply sentences unsupported; both UNANSWERED objections flagged."""
    d = write_arm(tmp_path, {"c1": {
        "predicted_factors": ["parity_with_co_accused", "antecedents", "flight_risk"],
        "gold_g4": ["parity_with_co_accused", "antecedents", "witness_tampering", "gravity_and_punishment"],
        "reply_sentences": 10, "unsupported_reply_sentences": 1, "unanswered": ["O2", "O3"], "flagged_unanswered": ["O2", "O3"]}})
    res = mod("f1").score(d)
    assert res["objection_recall"] == pytest.approx(0.5) and res["objection_precision"] == pytest.approx(2 / 3)
    assert res["unsupported_reply_rate"] == pytest.approx(0.1)
    assert res["unanswered_flagged_share"] == pytest.approx(1.0)


def test_f1_unflagged_unanswered_objections_lower_the_share(tmp_path):
    d = write_arm(tmp_path, {"c1": {"predicted_factors": [], "gold_g4": ["antecedents"], "reply_sentences": 4, "unsupported_reply_sentences": 0,
                                     "unanswered": ["O2", "O3"], "flagged_unanswered": ["O2"]}})
    assert mod("f1").score(d)["unanswered_flagged_share"] == pytest.approx(0.5)


def test_f2_stale_claims_stability_and_noop_edits(tmp_path):
    """One change case: 1 of 10 claims still states an old value; the 8 unchanged claims are word for word. One no-op control left untouched."""
    d = write_arm(tmp_path, {
        "u1": {"noop": False, "claims_total": 10, "claims_stale": 1, "unchanged_total": 8, "unchanged_identical": 8, "tokens": 5000, "wall_s": 40.0, "edited": True},
        "u2": {"noop": True, "claims_total": 10, "claims_stale": 0, "unchanged_total": 10, "unchanged_identical": 10, "tokens": 0, "wall_s": 1.0, "edited": False},
    })
    res = mod("f2").score(d)
    assert res["stale_claim_rate"] == pytest.approx(0.1)
    assert res["unchanged_claim_stability"] == pytest.approx(1.0)
    assert res["noop_edit_rate"] == pytest.approx(0.0)
    assert res["tokens"] == pytest.approx(5000.0)  # tokens on real changes (no-ops cost nothing and are scored separately)


def test_f2_an_edit_on_a_noop_control_is_counted(tmp_path):
    d = write_arm(tmp_path, {"u1": {"noop": True, "claims_total": 4, "claims_stale": 0, "unchanged_total": 4, "unchanged_identical": 3,
                                    "tokens": 900, "wall_s": 5.0, "edited": True}})
    res = mod("f2").score(d)
    assert res["noop_edit_rate"] == pytest.approx(1.0)


def test_f3_accuracy_per_rule_false_eligible_and_check_rate(tmp_path):
    """Four T4 scenarios: default_bail 1 of 2 right (one false ELIGIBLE), undertrial_limit 2 of 2 right (one CHECK)."""
    d = write_arm(tmp_path, {
        "s1": {"rule": "default_bail", "predicted": "ELIGIBLE", "designed": "NOT_YET"},
        "s2": {"rule": "default_bail", "predicted": "NOT_YET", "designed": "NOT_YET"},
        "s3": {"rule": "undertrial_limit", "predicted": "CHECK", "designed": "CHECK"},
        "s4": {"rule": "undertrial_limit", "predicted": "ELIGIBLE", "designed": "ELIGIBLE"}})
    res = mod("f3").score(d)
    assert res["accuracy/default_bail"] == pytest.approx(0.5) and res["accuracy/undertrial_limit"] == pytest.approx(1.0)
    assert res["false_eligible_rate"] == pytest.approx(0.25)
    assert res["check_rate"] == pytest.approx(0.25)


def test_f4_missed_deadlines_ranking_cache_hits_and_throughput(tmp_path):
    """Planted cases ranked 1 and 3, unplanted 2 and 4: 3 of the 4 (planted, unplanted) pairs are ordered correctly; one planted
    deadline missed; 2 of 4 cache hits; 4 cases in 2 node-hours."""
    rows = {
        "p1": {"planted": True, "rank": 1, "missed_deadline": False, "cache_hit": True, "output_equal_single": True, "seconds": 1800},
        "p2": {"planted": True, "rank": 3, "missed_deadline": True, "cache_hit": False, "output_equal_single": True, "seconds": 1800},
        "u1": {"planted": False, "rank": 2, "missed_deadline": False, "cache_hit": True, "output_equal_single": True, "seconds": 1800},
        "u2": {"planted": False, "rank": 4, "missed_deadline": False, "cache_hit": False, "output_equal_single": False, "seconds": 1800}}
    res = mod("f4").score(write_arm(tmp_path, rows))
    assert res["pairwise_ranking_accuracy"] == pytest.approx(0.75)
    assert res["missed_deadline_rate"] == pytest.approx(0.5)
    assert res["cache_hit_rate"] == pytest.approx(0.5)
    assert res["cases_per_node_hour"] == pytest.approx(2.0)
    assert res["output_equality_rate"] == pytest.approx(0.75)


def test_f5_section_compliance_list_of_dates_and_annexure(tmp_path):
    """10 of 11 required sections; List of Dates {a,b,c} vs G3 {a,b,d,e}: precision 2/3, recall 1/2; 1 of 5 dates unsourced; annexure matches."""
    d = write_arm(tmp_path, {"c1": {"required_sections_present": 10, "required_sections_total": 11, "lod_dates": ["a", "b", "c"],
                                    "gold_dates": ["a", "b", "d", "e"], "dates_without_source": 1, "dates_total": 5, "annexure_matches_uploads": True}})
    res = mod("f5").score(d)
    assert res["section_compliance"] == pytest.approx(10 / 11)
    assert res["lod_precision"] == pytest.approx(2 / 3) and res["lod_recall"] == pytest.approx(0.5)
    assert res["dates_without_source_rate"] == pytest.approx(0.2)
    assert res["annexure_match_rate"] == pytest.approx(1.0)


def test_f6_court_discussed_factors_and_imposed_conditions(tmp_path):
    """Card factors {parity, custody} vs G5 {parity, trial_delay}: recall and precision 1/2; conditions {passport, reporting} vs G6 {passport}: recall 1."""
    d = write_arm(tmp_path, {"c1": {"predicted_factors": ["parity_with_co_accused", "custody_period"], "gold_g5": ["parity_with_co_accused", "trial_delay"],
                                    "predicted_conditions": ["passport", "reporting"], "gold_g6": ["passport"]}})
    res = mod("f6").score(d)
    assert res["factor_recall"] == pytest.approx(0.5) and res["factor_precision"] == pytest.approx(0.5)
    assert res["condition_recall"] == pytest.approx(1.0)


def test_f7_resolution_by_format_coverage_false_resolutions_and_overruled_citations(tmp_path):
    """T9 strings: SCC 2 of 3 right, neutral 2 of 2; 4 of 5 true citations resolved at all; 1 of 2 distractors wrongly resolved; and
    1 of 4 briefs cites an overruled precedent without a warning."""
    rows = {
        "s1": {"format": "scc", "doc_id": "A", "predicted_doc_id": "A", "distractor": False},
        "s2": {"format": "scc", "doc_id": "B", "predicted_doc_id": "B", "distractor": False},
        "s3": {"format": "scc", "doc_id": "C", "predicted_doc_id": None, "distractor": False},
        "s4": {"format": "neutral", "doc_id": "D", "predicted_doc_id": "D", "distractor": False},
        "s5": {"format": "neutral", "doc_id": "E", "predicted_doc_id": "E", "distractor": False},
        "d1": {"format": "scc", "doc_id": None, "predicted_doc_id": "A", "distractor": True},
        "d2": {"format": "air", "doc_id": None, "predicted_doc_id": None, "distractor": True},
        "b1": {"brief": True, "cited_overruled_without_warning": True}, "b2": {"brief": True, "cited_overruled_without_warning": False},
        "b3": {"brief": True, "cited_overruled_without_warning": False}, "b4": {"brief": True, "cited_overruled_without_warning": False}}
    res = mod("f7").score(write_arm(tmp_path, rows))
    assert res["resolution_accuracy/scc"] == pytest.approx(2 / 3) and res["resolution_accuracy/neutral"] == pytest.approx(1.0)
    assert res["coverage"] == pytest.approx(0.8)
    assert res["false_resolution_rate"] == pytest.approx(0.5)
    assert res["overruled_cited_rate"] == pytest.approx(0.25)


def test_f8_cer_wer_language_gap_and_readback_errors(tmp_path):
    """Hindi CER 1/3 (one wrong character of three), WER 1/3; field accuracy 0.8 Hindi vs 0.9 English -> gap 0.1; entity errors drop from
    3 of 10 to 1 of 10 after the read-back."""
    rows = {
        "h1": {"lang": "hi", "hyp": "abc", "ref": "abd", "field_accuracy": 0.8, "words_hyp": "a b c", "words_ref": "a x c",
               "entity_errors_before": 3, "entity_errors_after": 1, "entities_total": 10},
        "e1": {"lang": "en", "hyp": "abd", "ref": "abd", "field_accuracy": 0.9, "words_hyp": "a x c", "words_ref": "a x c",
               "entity_errors_before": 0, "entity_errors_after": 0, "entities_total": 0}}
    res = mod("f8").score(write_arm(tmp_path, rows))
    assert res["hindi_cer"] == pytest.approx(1 / 3)
    assert res["wer"] == pytest.approx(1 / 6)  # mean over the two utterances: (1/3 + 0) / 2
    assert res["field_accuracy_gap"] == pytest.approx(0.1)
    assert res["entity_error_rate_before_readback"] == pytest.approx(0.3)
    assert res["entity_error_rate_after_readback"] == pytest.approx(0.1)


@pytest.mark.parametrize("fid", sorted(FEATURES))
def test_score_of_an_empty_run_dir_is_an_error_not_a_made_up_number(tmp_path, fid):
    """No saved cases means nothing to score: ValueError (ASSUMPTION), never zeros that look like results."""
    (tmp_path / "empty").mkdir()
    with pytest.raises(ValueError):
        mod(fid).score(str(tmp_path / "empty"))
