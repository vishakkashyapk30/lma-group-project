"""Null-agent audit of the metrics (evaluation plan §5.7; literature review E3).

A metric that rewards doing nothing is broken. Five degenerate agents are scored on one toy case and each must land
near the floor on the metric it tries to game. The copy-the-facts agent shows why faithfulness is never reported
alone: it is perfectly faithful and argues nothing. The unsupported-fact checker is whatever `unsupported_fact_rate`
resolves to (the offline lexical NLI when no model is installed).
"""

import random
import statistics

import pytest

from vakeel_sahayak.eval.metrics.factor_scores import factor_recall_precision
from vakeel_sahayak.eval.metrics.retrieval import mean_reciprocal_rank, ndcg_at_k, recall_at_k
from vakeel_sahayak.eval.metrics.safety import export_violations
from vakeel_sahayak.eval.metrics.unsupported_fact import unsupported_fact_rate
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
from vakeel_sahayak.schemas.enums import EventKind, Factor, FactorStance
from vakeel_sahayak.schemas.events import Event

F = Factor
FACTS = (
    "The applicant was arrested on 12.03.2024 in FIR No. 112/2024 under Section 379 IPC. "
    "The charge sheet was filed on 20.06.2024. He has been in custody for 140 days."
)
GOLD = [F.CUSTODY_PERIOD, F.CHARGE_SHEET_FILED]
ANSWERABLE = [F.CUSTODY_PERIOD, F.CHARGE_SHEET_FILED, F.GRAVITY_AND_PUNISHMENT, F.ANTECEDENTS, F.TRIAL_DELAY, F.UNDERTRIAL_PERIOD]
GOLD_DOCS = ["SC-2022-77", "SC-2014-12", "HC-2023-501"]


def _brief(grounds):
    return BailBrief(case_id="case-0001", grounds=[
        Ground(id=f"G{i}", factor=f, stance=FactorStance.FAVOURABLE, argument=a) for i, (f, a) in enumerate(grounds, start=1)
    ])


def _f1(recall, precision):
    return 2 * recall * precision / (recall + precision) if recall + precision else 0.0


def _factor_scores(brief):
    return factor_recall_precision([g.factor for g in brief.grounds], GOLD, ANSWERABLE)


def test_empty_brief_has_zero_recall():
    assert _factor_scores(_brief([]))[0] == 0.0


@pytest.mark.xfail(strict=True, reason="unsupported_fact_rate returns 0.0 for a brief with no sentences; plan 5.7 says report 'no claims', not 0")
def test_empty_brief_is_no_claims_not_a_perfect_unsupported_rate():
    assert unsupported_fact_rate(_brief([]), FACTS) is None


def test_copy_the_facts():
    """Fully faithful, but argues no answerable factor and cites nothing."""
    brief = _brief([(F.HEALTH_AGE_FAMILY, FACTS)])
    assert unsupported_fact_rate(brief, FACTS) == 0.0
    assert _factor_scores(brief)[0] == 0.0
    retrieved = [a.doc_id for g in brief.grounds for a in g.authorities]
    assert recall_at_k(retrieved, GOLD_DOCS) == mean_reciprocal_rank(retrieved, GOLD_DOCS) == ndcg_at_k(retrieved, GOLD_DOCS) == 0.0


@pytest.mark.parametrize("template", [
    "{name}.",  # copy-the-checklist: the twelve factor names
    "The applicant deserves bail because of {name}.",  # argue-all-twelve: a template ground per factor
])
def test_arguing_every_factor_buys_recall_not_precision(template):
    """Recall 1.0 by construction (why claim C3 exists); precision and F1 fall to the gold share of answerable factors."""
    brief = _brief([(f, template.format(name=f.value.replace("_", " "))) for f in F])
    recall, precision = _factor_scores(brief)
    assert recall == 1.0
    assert precision == pytest.approx(len(GOLD) / len(ANSWERABLE))
    assert _f1(recall, precision) < 0.6


def test_argue_all_twelve_states_unsupported_grounds():
    brief = _brief([(f, f"The applicant deserves bail because of {f.value.replace('_', ' ')}.") for f in F])
    assert unsupported_fact_rate(brief, FACTS) > 0.8


def test_random_citations_score_near_chance():
    """Real doc ids drawn at random: recall@10 near 10/N, MRR and nDCG near 0."""
    pool = GOLD_DOCS + [f"HC-2020-{i:04d}" for i in range(497)]
    rng = random.Random(0)
    runs = [rng.sample(pool, 10) for _ in range(300)]
    assert statistics.mean(recall_at_k(r, GOLD_DOCS) for r in runs) < 0.05
    assert statistics.mean(mean_reciprocal_rank(r, GOLD_DOCS) for r in runs) < 0.05
    assert statistics.mean(ndcg_at_k(r, GOLD_DOCS) for r in runs) < 0.05


def test_export_without_approval_fires_the_safety_metric():
    """The safety metric can fire: an export with no Gate 2 approval counts."""
    ev = Event(event_id="e1", case_id="case-0001", ts="2025-02-03T10:00:01Z", kind=EventKind.TOOL_CALL, actor="VAKEEL", tool="export", inputs={})
    assert export_violations([ev]) >= 1
