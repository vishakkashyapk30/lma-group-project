"""Statistics wrappers (plan §15.9): paired bootstrap 95% CI, Wilcoxon signed-rank, Holm-Bonferroni within a family."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vakeel_sahayak.eval.stats.bootstrap import paired_bootstrap_ci
from vakeel_sahayak.eval.stats.holm import holm_bonferroni
from vakeel_sahayak.eval.stats.wilcoxon import wilcoxon_signed_rank


class TestPairedBootstrap:
    """Returns (mean paired difference, lower, upper). # ASSUMPTION: tuple order (mean, ci_low, ci_high)."""

    def test_identical_systems_have_zero_difference(self):
        """a == b -> mean 0 and a degenerate interval at 0."""
        a = [0.2, 0.5, 0.9, 0.4]
        assert paired_bootstrap_ci(a, a, n_boot=200) == (0.0, 0.0, 0.0)

    def test_constant_shift_has_a_degenerate_interval(self):
        """Every pair differs by +0.1 -> mean 0.1 and the interval collapses on 0.1."""
        b = [0.2, 0.5, 0.9, 0.4, 0.7]
        a = [x + 0.1 for x in b]
        mean, lo, hi = paired_bootstrap_ci(a, b, n_boot=300)
        assert mean == pytest.approx(0.1) and lo == pytest.approx(0.1) and hi == pytest.approx(0.1)

    def test_length_mismatch_is_rejected(self):
        """Paired samples must have equal length."""
        with pytest.raises(ValueError):
            paired_bootstrap_ci([1.0, 2.0], [1.0], n_boot=10)

    @settings(max_examples=25, deadline=None)
    @given(st.lists(st.tuples(st.floats(0, 1), st.floats(0, 1)), min_size=2, max_size=15))
    def test_property_interval_contains_the_mean_and_is_ordered(self, pairs):
        """lo <= mean <= hi (up to float noise) and the interval is ordered."""
        a, b = [p[0] for p in pairs], [p[1] for p in pairs]
        mean, lo, hi = paired_bootstrap_ci(a, b, n_boot=200)
        assert lo <= hi
        assert lo - 1e-9 <= mean <= hi + 1e-9

    def test_wider_confidence_gives_wider_interval(self):
        """alpha=0.01 (99%) is at least as wide as alpha=0.20 (80%) on the same data."""
        a = [0.9, 0.2, 0.7, 0.4, 0.8, 0.1, 0.6]
        b = [0.5, 0.3, 0.4, 0.4, 0.6, 0.3, 0.2]
        _, lo1, hi1 = paired_bootstrap_ci(a, b, n_boot=2000, alpha=0.01)
        _, lo2, hi2 = paired_bootstrap_ci(a, b, n_boot=2000, alpha=0.20)
        assert (hi1 - lo1) >= (hi2 - lo2) - 1e-9


class TestWilcoxon:
    def test_all_positive_differences_exact_p(self):
        """Ten distinct positive paired differences: exact two-sided p = 2 / 2**10. # ASSUMPTION: exact test for n <= 50
        (scipy's default), not the normal approximation."""
        a = [float(i) for i in range(1, 11)]
        b = [0.0] * 10
        assert wilcoxon_signed_rank(a, b) == pytest.approx(2 / 1024, rel=1e-6)

    def test_symmetric_in_direction(self):
        """Two-sided: swapping the systems gives the same p-value."""
        a = [0.9, 0.8, 0.7, 0.95, 0.6, 0.85]
        b = [0.5, 0.4, 0.45, 0.5, 0.3, 0.2]
        assert wilcoxon_signed_rank(a, b) == pytest.approx(wilcoxon_signed_rank(b, a))

    def test_no_difference_gives_p_one(self):
        """All differences zero -> p = 1.0 (the wrapper must not raise)."""
        assert wilcoxon_signed_rank([0.5, 0.6, 0.7], [0.5, 0.6, 0.7]) == 1.0

    def test_length_mismatch_is_rejected(self):
        """Paired samples must have equal length."""
        with pytest.raises(ValueError):
            wilcoxon_signed_rank([1.0, 2.0], [1.0])

    @settings(max_examples=30, deadline=None)
    @given(st.lists(st.floats(-1, 1), min_size=6, max_size=20))
    def test_property_p_in_unit_interval(self, diffs):
        """p-values are probabilities."""
        p = wilcoxon_signed_rank([d for d in diffs], [0.0] * len(diffs))
        assert 0.0 <= p <= 1.0


class TestHolmBonferroni:
    def test_textbook_example(self):
        """m=4 at alpha .05: thresholds .0125, .0167, .025, .05 -> D and A rejected, C stops the step-down, B not rejected."""
        p = {"A": 0.01, "B": 0.04, "C": 0.03, "D": 0.005}
        assert holm_bonferroni(p, alpha=0.05) == {"D": True, "A": True, "C": False, "B": False}

    def test_holm_rejects_more_than_plain_bonferroni(self):
        """p .02 and .04 (m=2): Bonferroni (.025) rejects only the first; Holm (.025 then .05) rejects both."""
        assert holm_bonferroni({"a": 0.02, "b": 0.04}, alpha=0.05) == {"a": True, "b": True}

    def test_stops_at_first_failure(self):
        """After the first non-rejection no later hypothesis is rejected, even if its p looks small."""
        res = holm_bonferroni({"x": 0.02, "y": 0.026, "z": 0.04}, alpha=0.05)
        assert not any(res.values())

    def test_single_comparison_is_plain_alpha(self):
        """m=1 -> reject iff p <= alpha."""
        assert holm_bonferroni({"only": 0.04}) == {"only": True}
        assert holm_bonferroni({"only": 0.06}) == {"only": False}

    def test_every_key_is_returned(self):
        """Output covers each comparison exactly once."""
        p = {"H1a-B0": 0.001, "H1a-B1": 0.2, "H1a-B2": 0.04}
        assert set(holm_bonferroni(p)) == set(p)

    @given(st.dictionaries(st.text("abcdef", min_size=1, max_size=3), st.floats(0.0, 1.0), min_size=1, max_size=8))
    def test_property_rejections_are_monotone_in_p_and_dominate_bonferroni(self, p):
        """Rejected p-values are all <= alpha; any p below every rejected-set maximum is rejected; Holm rejects at least
        what Bonferroni (alpha/m) rejects."""
        alpha = 0.05
        res = holm_bonferroni(p, alpha=alpha)
        rejected = [p[k] for k, v in res.items() if v]
        assert all(x <= alpha for x in rejected)
        if rejected:
            assert all(res[k] for k in p if p[k] <= max(rejected))
        m = len(p)
        assert all(res[k] for k in p if p[k] <= alpha / m)
