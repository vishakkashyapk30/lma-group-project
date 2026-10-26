"""Scoring pipeline: run discovery, slices, refusal of the blind slice, gold-source switching and the sweep, Holm family restriction."""

from __future__ import annotations

import json

import pytest

from tests.unit.eval.scoring_fixtures import gold_row, record, write_run, write_t1
from vakeel_sahayak.eval.scoring import engine
from vakeel_sahayak.eval.scoring.loader import discover_rights, discover_runs, gold_rows, resolve_slice_ids
from vakeel_sahayak.eval.scoring.pipeline import score_command, sweep_delta
from vakeel_sahayak.testsets import blind as blind_mod
from vakeel_sahayak.testsets.blind import BlindSliceError

DEV = ["d1", "d2", "d3", "d4"]
TEST = ["t1", "t2", "t3", "t4"]
BLIND = ["t4"]
OPEN = ["t1", "t2", "t3"]


def make_dev_rows(source: str):
    # agreed: every dev case has G1 {custody_period}; rule-only gold adds charge_sheet_filed to d1 and d2 (so agreed and rule recall differ)
    rule_extra = ["charge_sheet_filed"] if source == "rule" else []
    return [gold_row(c, ["custody_period", *(rule_extra if c in ("d1", "d2") else [])]) for c in DEV]


def make_test_rows(source: str):
    return [gold_row(c, ["custody_period"]) for c in TEST]


@pytest.fixture()
def testsets(tmp_path):
    root = tmp_path / "testsets"
    for src in ("agreed", "rule"):
        write_t1(root, src, make_dev_rows(src), make_test_rows(src), OPEN, BLIND)
    return root


@pytest.fixture()
def runs(tmp_path):
    """full (2 runs) and b0 and b1 on the four dev cases, plus a T4 rights arm."""
    root = tmp_path / "runs"
    full = [record(c, ["custody_period", "charge_sheet_filed"], tokens=1000) for c in DEV]
    write_run(root, "full", 1, full)
    write_run(root, "full", 2, [record(c, ["custody_period"], tokens=1100) for c in DEV])
    write_run(root, "b0", 1, [record(c, ["antecedents"], tokens=100, gates=False) for c in DEV])
    write_run(root, "b1", 1, [record(c, ["custody_period"], tokens=300, gates=False) for c in DEV[:3]])
    rd = root / "f3" / "radar"
    rd.mkdir(parents=True)
    for i in range(4):
        (rd / f"s{i}.json").write_text(json.dumps({"rule": "default_bail", "predicted": "ELIGIBLE" if i else "NOT_YET", "designed": "ELIGIBLE", "arm": "radar"}), encoding="utf-8")
    return root


def test_discover_runs_systems_runs_and_rights(runs):
    found = discover_runs(runs)
    assert [(r.system, r.run, len(r.records)) for r in found] == [("b0", 1, 4), ("b1", 1, 3), ("full", 1, 4), ("full", 2, 4)]
    assert list(discover_rights(runs)) == ["radar"]


def test_duplicate_system_run_is_an_error(runs, tmp_path):
    write_run(runs / "copy", "b0", 1, [record("d1", ["custody_period"])])
    with pytest.raises(ValueError, match="appears twice"):
        discover_runs(runs)


def test_dev_slice_needs_no_lock_and_scores(testsets, runs, tmp_path):
    res = score_command(str(runs), str(tmp_path / "out"), gold_source="agreed", slice_name="dev", testsets_dir=str(testsets))["agreed"]
    assert res["meta"]["n_gold_cases"] == 4 and res["meta"]["slice"] == "dev"
    full = res["systems"]["full"]
    # case-level mean over runs: run1 recall 1.0, run2 recall 1.0 (gold is {custody_period} only) -> mean 1.0 on 4 cases
    assert full["n_cases"] == 4 and full["runs"] == [1, 2]
    assert full["metrics"]["factor_recall"]["mean"] == pytest.approx(1.0)
    assert full["metrics"]["tokens"]["mean"] == pytest.approx(1050.0)
    assert res["systems"]["b0"]["metrics"]["factor_recall"]["mean"] == 0.0
    assert res["systems"]["b1"]["n_cases"] == 3
    assert full["pass"]["k"] == 2 and full["pass"]["pass_hat_k"] == 1.0
    assert (tmp_path / "out" / "score_agreed.json").is_file() and (tmp_path / "out" / "per_case_agreed.csv").is_file()
    assert res["rights"]["arms"]["radar"]["n"] == 4 and res["rights"]["arms"]["radar"]["accuracy"] == pytest.approx(0.75)


def test_open_slice_excludes_blind_and_dev_ids(testsets):
    ids = resolve_slice_ids("open", "agreed", testsets)
    assert ids == set(OPEN) and "t4" not in ids
    assert {r["case_id"] for r in gold_rows("open", ids, "agreed", testsets)} == set(OPEN)


def test_blind_refused_without_flag(testsets, tmp_path):
    with pytest.raises(BlindSliceError, match="explicit flag"):
        resolve_slice_ids("blind", "agreed", testsets, lock=tmp_path / "blind.lock", check_tag=False)
    assert not (tmp_path / "blind.lock").exists()


def test_blind_refused_without_freeze_tag(testsets, tmp_path, monkeypatch):
    monkeypatch.setattr(blind_mod, "freeze_tag_exists", lambda tag=blind_mod.FREEZE_TAG: False)
    with pytest.raises(BlindSliceError, match="git tag"):
        resolve_slice_ids("blind", "agreed", testsets, open_blind=True, lock=tmp_path / "blind.lock", check_tag=True)
    assert not (tmp_path / "blind.lock").exists()


def test_blind_refused_when_lock_exists_and_opens_once(testsets, tmp_path, runs):
    lock = tmp_path / "blind.lock"
    ids = resolve_slice_ids("blind", "agreed", testsets, open_blind=True, lock=lock, check_tag=False)
    assert ids == set(BLIND) and lock.is_file()
    with pytest.raises(BlindSliceError, match="already been opened"):
        resolve_slice_ids("blind", "agreed", testsets, open_blind=True, lock=lock, check_tag=False)
    # through the scoring entry point too
    with pytest.raises(BlindSliceError):
        score_command(str(runs), str(tmp_path / "o"), slice_name="blind", testsets_dir=str(testsets), open_blind=True, lock=lock, check_tag=False)
    assert not (tmp_path / "o" / "score_agreed.json").exists()


def test_blind_ids_never_appear_in_dev_or_open_scoring(testsets, runs, tmp_path):
    # runs of a test-slice system that also saved the blind case: scoring the open slice drops it and counts it as excluded
    write_run(runs, "x", 1, [record(c, ["custody_period"]) for c in ["t1", "t2", "t4"]])
    res = score_command(str(runs), str(tmp_path / "o"), slice_name="open", testsets_dir=str(testsets))["agreed"]
    assert res["systems"]["x"]["n_cases"] == 2 and res["meta"]["excluded_records"]["x"] == 1


def test_bad_run_dir_does_not_burn_the_blind_opening(testsets, tmp_path):
    lock = tmp_path / "blind.lock"
    with pytest.raises(FileNotFoundError):
        score_command(str(tmp_path / "empty"), str(tmp_path / "o"), slice_name="blind", testsets_dir=str(testsets), open_blind=True, lock=lock, check_tag=False)
    empty = tmp_path / "empty2"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        score_command(str(empty), str(tmp_path / "o"), slice_name="blind", testsets_dir=str(testsets), open_blind=True, lock=lock, check_tag=False)
    assert not lock.exists()


def test_gold_source_switching_changes_labels_not_outputs(testsets, runs, tmp_path):
    agreed = score_command(str(runs), str(tmp_path / "a"), gold_source="agreed", testsets_dir=str(testsets))["agreed"]
    rule = score_command(str(runs), str(tmp_path / "r"), gold_source="rule", testsets_dir=str(testsets))["rule"]
    assert agreed["meta"]["gold_source"] == "agreed" and rule["meta"]["gold_source"] == "rule"
    assert agreed["meta"]["gold_sha256"] != rule["meta"]["gold_sha256"]
    # run-side numbers are identical on both golds
    assert agreed["systems"]["full"]["metrics"]["tokens"]["mean"] == rule["systems"]["full"]["metrics"]["tokens"]["mean"]
    # full run 1 argues {custody_period, charge_sheet_filed}; run 2 only {custody_period}. Agreed gold {custody}: recall 1.0 both runs.
    # Rule gold on d1, d2 adds charge_sheet_filed: run 1 recall 1.0, run 2 recall 0.5 -> case mean 0.75 on d1, d2; 1.0 on d3, d4 -> 0.875
    assert agreed["systems"]["full"]["metrics"]["factor_recall"]["mean"] == pytest.approx(1.0)
    assert rule["systems"]["full"]["metrics"]["factor_recall"]["mean"] == pytest.approx(0.875)


def test_sweep_writes_both_golds_and_the_delta(testsets, runs, tmp_path):
    res = score_command(str(runs), str(tmp_path / "s"), gold_source="both", testsets_dir=str(testsets))
    out = tmp_path / "s"
    assert {p.name for p in out.glob("*.json")} == {"score_agreed.json", "score_rule.json", "sweep.json"}
    sweep = json.loads((out / "sweep.json").read_text())
    d = sweep["systems"]["full"]["factor_recall"]
    assert d["delta"] == pytest.approx(0.125) and d["agreed"]["mean"] == pytest.approx(1.0) and d["rule"]["mean"] == pytest.approx(0.875)
    assert res["sweep"]["slice"] == "dev"
    # the same outputs on both golds: the sweep adds no rows to the paired tests (same count of comparisons on each gold)
    assert len(res["agreed"]["paired"]) == len(res["rule"]["paired"])


def paired_row(comp, metric, p, diff=0.2, hib=True):
    return {"reference": "full", "comparator": comp, "metric": metric, "n": 30, "status": "ok", "higher_is_better": hib, "diff": diff, "lo": 0.0, "hi": 0.4, "p": p, "p_source": "wilcoxon"}


def test_holm_uses_registered_family_size_not_the_number_run():
    # F-RQ1-recall registers 6 tests. One test run with p = 0.02: alpha / 6 = 0.0083 -> NOT rejected (alone it would pass 0.05)
    paired = [paired_row("b0", "factor_recall", 0.02)]
    fams = engine.holm_families(paired)
    assert fams["F-RQ1-recall"]["m_registered"] == 6
    assert paired[0]["holm_reject"] is False and paired[0]["family"] == "F-RQ1-recall"
    # with p = 0.005 < 0.05 / 6 it is rejected
    paired = [paired_row("b0", "factor_recall", 0.005)]
    engine.holm_families(paired)
    assert paired[0]["holm_reject"] is True


def test_holm_step_down_inside_a_family_only():
    paired = [paired_row("b0", "factor_recall", 0.001), paired_row("b1", "factor_recall", 0.004), paired_row("b4", "factor_recall", 0.2)]
    engine.holm_families(paired)
    assert [p["holm_reject"] for p in paired] == [True, True, False]  # 0.001 <= .05/6, 0.004 <= .05/5, 0.2 stops the step-down


def test_comparisons_outside_registered_families_are_exploratory_and_uncorrected():
    paired = [paired_row("zz", "factor_recall", 0.0001), paired_row("b0", "tokens", 0.0001, diff=-5, hib=False), paired_row("b0", "factor_recall", 0.0001)]
    fams = engine.holm_families(paired)
    assert paired[0]["family"] is None and paired[0]["holm_reject"] is None  # comparator not in F-RQ1-recall
    assert paired[1]["family"] is None  # tokens is in no family
    assert paired[2]["family"] == "F-RQ1-recall"
    assert all(len(f["tests"]) == f["m_registered"] for f in fams.values())


def test_families_do_not_pool():
    # a different family's p-values never enter F-RQ1-recall's correction
    paired = [paired_row("b0", "factor_recall", 0.005)] + [paired_row(c, "objection_recall", 0.9) for c in ("s9", "s10")]
    engine.holm_families(paired)
    assert paired[0]["holm_reject"] is True and paired[1]["family"] == "F-sparring"


def test_pending_family_when_metric_missing():
    paired = [{"reference": "full", "comparator": "b0", "metric": "unsupported_fact_rate", "n": 0, "status": "pending", "higher_is_better": False}]
    fams = engine.holm_families(paired)
    assert fams["F-RQ1-halluc"]["tests"][0]["status"] == "pending" and paired[0]["holm_reject"] is None


def test_sweep_robustness_flag():
    def side(rej, diff=0.3):
        return {"meta": {"gold_sha256": "x", "n_gold_cases": 5, "slice": "dev"}, "systems": {},
                "families": {"F-RQ1-recall": {"claims": "C1", "tests": [{"comparator": "b0", "metric": "factor_recall", "diff": diff, "p": 0.01, "reject": rej,
                                                                        "sign_favours_reference": diff > 0}]}}}

    assert sweep_delta(side(True), side(True))["family_tests"][0]["robust"] is True
    assert sweep_delta(side(True), side(False))["family_tests"][0]["robust"] is False
    assert sweep_delta(side(True), side(True, diff=-0.3))["family_tests"][0]["robust"] is False


def test_paired_comparisons_on_synthetic_runs(testsets, runs, tmp_path):
    res = score_command(str(runs), str(tmp_path / "o"), testsets_dir=str(testsets))["agreed"]
    row = next(p for p in res["paired"] if p["comparator"] == "b0" and p["metric"] == "factor_recall")
    assert row["n"] == 4 and row["diff"] == pytest.approx(1.0) and row["family"] == "F-RQ1-recall"
    tok = next(p for p in res["paired"] if p["comparator"] == "b1" and p["metric"] == "tokens")
    assert tok["n"] == 3 and tok["family"] is None  # b1 scored on three cases: pairing uses the common cases only
    mc = next(p for p in res["paired"] if p["comparator"] == "b0" and p["metric"].startswith("pass_per_case"))
    assert mc["b10"] == 4 and mc["b01"] == 0 and mc["p"] == pytest.approx(2 / 16)


def test_reference_missing_gives_no_pairs(testsets, runs, tmp_path):
    res = score_command(str(runs), str(tmp_path / "o"), testsets_dir=str(testsets), reference="nope")["agreed"]
    assert res["paired"] == []


# ---------------------------------------------------------------------------------------------------------------- code version of the runs
def _stamp(run_dir, sha, dirty=False, tree="t"):
    mp = run_dir / "MANIFEST.json"
    m = json.loads(mp.read_text(encoding="utf-8"))
    m.update(git_sha=sha, git_dirty=dirty, code_tree_hash=tree)
    mp.write_text(json.dumps(m), encoding="utf-8")


def test_runs_from_different_commits_are_refused_unless_allowed(testsets, tmp_path):
    root = tmp_path / "mixed"
    _stamp(write_run(root, "full", 1, [record(c, ["custody_period"]) for c in DEV]), "aaa111")
    _stamp(write_run(root, "b0", 1, [record(c, ["custody_period"], gates=False) for c in DEV]), "bbb222")
    with pytest.raises(ValueError, match="different code versions"):
        score_command(str(root), str(tmp_path / "o1"), testsets_dir=str(testsets))
    res = score_command(str(root), str(tmp_path / "o2"), testsets_dir=str(testsets), allow_mixed_code=True)["agreed"]
    assert len(res["meta"]["code_versions"]) == 2


def test_same_commit_scores_and_is_recorded(testsets, tmp_path):
    root = tmp_path / "same"
    _stamp(write_run(root, "full", 1, [record(c, ["custody_period"]) for c in DEV]), "aaa111", tree="x")
    _stamp(write_run(root, "b0", 1, [record(c, ["custody_period"], gates=False) for c in DEV]), "aaa111", tree="x")
    res = score_command(str(root), str(tmp_path / "o"), testsets_dir=str(testsets))["agreed"]
    assert list(res["meta"]["code_versions"]) == ["aaa111:x"] and len(res["meta"]["code_versions"]["aaa111:x"]) == 2


def test_same_sha_with_edited_tree_counts_as_different(testsets, tmp_path):
    root = tmp_path / "tree"
    _stamp(write_run(root, "full", 1, [record(c, ["custody_period"]) for c in DEV]), "aaa111", dirty=True, tree="one")
    _stamp(write_run(root, "b0", 1, [record(c, ["custody_period"], gates=False) for c in DEV]), "aaa111", dirty=True, tree="two")
    with pytest.raises(ValueError, match="different code versions"):
        score_command(str(root), str(tmp_path / "o"), testsets_dir=str(testsets))


def test_legacy_manifests_without_git_sha_do_not_block(testsets, runs, tmp_path):
    res = score_command(str(runs), str(tmp_path / "o"), testsets_dir=str(testsets))["agreed"]
    assert list(res["meta"]["code_versions"]) == ["unknown"]
