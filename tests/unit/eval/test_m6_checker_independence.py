"""The M6 checker is never silently the system's own claim checker (design review 2026-10-27 item 1; evaluation-plan 2.4), the registered
families follow plan 5.3 with the claims' own metrics (C11 on A1, C13 on S8) and C1 as an intersection-union claim, and the sweep's claim tags
follow plan 1.2."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from vakeel_sahayak.eval.metrics import unsupported_fact as uf
from vakeel_sahayak.eval.scoring import engine
from vakeel_sahayak.models import factory
from vakeel_sahayak.models.base import NliClient

ROOT = Path(__file__).resolve().parents[3]


class _RealLikeNli(NliClient):
    """Stands for the system's DeBERTa checker: not offline."""

    name = "deberta-v3-nli"
    is_offline = False

    def entails(self, premise: str, hypothesis: str) -> float:
        return 0.9


@pytest.fixture
def system_nli(monkeypatch):
    factory.set_client("nli", _RealLikeNli())
    monkeypatch.setattr(uf, "_minicheck_scorer", lambda: None)
    yield
    factory.set_client("nli", None)


def test_offline_mode_uses_the_labelled_stand_in(monkeypatch):
    monkeypatch.delenv("VS_MODELS", raising=False)
    monkeypatch.delenv(uf.CHECKER_ENV, raising=False)
    assert uf.checker_backend() == "offline-lexical-nli"


def test_system_checker_is_refused_without_opt_in(monkeypatch, system_nli):
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.delenv(uf.ALLOW_SYSTEM_ENV, raising=False)
    with pytest.raises(uf.SystemCheckerRefused, match="system's own claim checker"):
        uf.checker_backend()


def test_system_checker_opt_in_is_named(monkeypatch, system_nli):
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.setenv(uf.ALLOW_SYSTEM_ENV, "1")
    assert uf.checker_backend() == "deberta-v3-nli (system checker)"


def test_minicheck_wins_in_auto_mode(monkeypatch, system_nli):
    monkeypatch.setenv("VS_MODELS", "auto")
    monkeypatch.setattr(uf, "_minicheck_scorer", lambda: (lambda premise, sentence: 0.1))
    name, score, cut = uf._scorer()
    assert name == uf.MINICHECK_NAME and score("p", "h") < cut


def test_explicit_minicheck_never_falls_back(monkeypatch):
    monkeypatch.setenv(uf.CHECKER_ENV, "minicheck")
    monkeypatch.setattr(uf, "_minicheck_scorer", lambda: None)
    with pytest.raises(uf.SystemCheckerRefused, match="cannot load"):
        uf.checker_backend()


def test_unknown_checker_choice_is_an_error(monkeypatch):
    monkeypatch.setenv(uf.CHECKER_ENV, "judge")
    with pytest.raises(ValueError, match=uf.CHECKER_ENV):
        uf.checker_backend()


def test_minicheck_path_is_the_local_roberta_copy(tmp_path, monkeypatch):
    (tmp_path / "lytang--MiniCheck-RoBERTa-Large").mkdir()
    (tmp_path / "lytang--MiniCheck-RoBERTa-Large" / "config.json").write_text("{}")
    monkeypatch.setenv("VS_MODELS_DIR", str(tmp_path))
    seen = []
    monkeypatch.setattr(uf, "_roberta_scorer", lambda path: seen.append(path) or (lambda p, h: 1.0))
    assert uf._minicheck_scorer() is not None and seen == [str(tmp_path / "lytang--MiniCheck-RoBERTa-Large")]


# ---------------------------------------------------------------------------------------------------------------- families (plan 5.3, 1.2)
def _row(comp, metric, p, diff=0.2, hib=True):
    return {"reference": "full", "comparator": comp, "metric": metric, "n": 30, "status": "ok", "higher_is_better": hib, "diff": diff, "lo": 0.0, "hi": 0.4, "p": p}


def test_claims_with_their_own_metric_are_registered():
    assert ("unsupported_fact_rate", "s8") in engine.family_tests(engine.FAMILIES["F-sparring"])  # C13 (plan 5.3 puts S8 in F-sparring)
    assert ("unsupported_fact_rate", "a1") in engine.family_tests(engine.FAMILIES["F-ablate-recall"])  # C11 is scored on M6 (plan 1.2)
    fams = engine.holm_families([_row("s8", "unsupported_fact_rate", 0.001, diff=-0.1, hib=False)])
    assert fams["F-sparring"]["m_registered"] == 6 and fams["F-ablate-recall"]["m_registered"] == 6
    s8 = next(t for t in fams["F-sparring"]["tests"] if t["comparator"] == "s8")
    assert s8["reject"] is True and s8["sign_favours_reference"] is True
    assert all(len(f["tests"]) == f["m_registered"] for f in fams.values())


def test_c1_is_an_intersection_union_claim():
    comps = engine.FAMILIES["F-RQ1-recall"]["comparators"]
    # every comparator significant at alpha (0.03 > alpha/6, so Holm would reject none of them): the IUT supports C1
    fams = engine.holm_families([_row(c, "factor_recall", 0.03) for c in comps])
    assert fams["F-RQ1-recall"]["iut"]["verdict"] == "supported"
    assert not any(t["reject"] for t in fams["F-RQ1-recall"]["tests"])
    # one comparator not run: incomplete, never supported
    fams = engine.holm_families([_row(c, "factor_recall", 0.001) for c in comps[1:]])
    assert fams["F-RQ1-recall"]["iut"]["verdict"] == "incomplete"
    # one comparator against the reference: not supported
    fams = engine.holm_families([_row(c, "factor_recall", 0.001, diff=(-0.2 if c == "b4" else 0.2)) for c in comps])
    assert fams["F-RQ1-recall"]["iut"]["verdict"] == "not supported"
    assert "iut" not in fams["F-RQ1-halluc"]


# ---------------------------------------------------------------------------------------------------------------- sweep claim tags (plan 1.2)
def test_sweep_claim_tags_follow_plan_1_2():
    arms = yaml.safe_load((ROOT / "configs/eval/sweep_dev.yaml").read_text())["arms"]
    tags: dict[str, set[str]] = {}
    for arm in arms:
        tags.setdefault(str(arm["id"]), set()).update(arm.get("claims") or [])
    assert "C11" in tags["A1"] and "C12" not in tags["A1"]
    assert "C12" in tags["A3"] and "C11" not in tags["A3"]
    assert "C4" in tags["b4"] and "C10" not in tags["b4"]
    for b in ("b1", "b2", "b3"):
        assert "C4" not in tags[b] and {"C1", "C2"} <= tags[b]
    assert "C3" in tags["b6"] and "C1" not in tags["b6"]
    assert tags["A10:*"] >= {"C14"} and "C5" not in tags["A10:*"]
    assert tags["A8"] == {"C28"} and "C7" not in tags["A9"]
    for s in ("S4", "S5", "S12"):
        assert "C9" not in tags[s]


# ---------------------------------------------------------------------------------------------------------------- the real checkpoint
@pytest.mark.models
@pytest.mark.slow
def test_real_minicheck_roberta_separates_supported_from_unsupported():
    from vakeel_sahayak.models.nli import local_checkpoint

    path = local_checkpoint(uf.MINICHECK_ID)
    if path is None:
        pytest.skip("MiniCheck-RoBERTa-Large not under models/hf (make models)")
    pytest.importorskip("torch")
    score = uf._roberta_scorer(path)
    premise = "The applicant was arrested on 12.03.2024 by Hili police. He has been in custody for 90 days and the charge sheet has been filed."
    assert score(premise, "The charge sheet has been filed.") > 0.5
    assert score(premise, "The applicant was arrested in 2019 by the CBI.") < 0.5
