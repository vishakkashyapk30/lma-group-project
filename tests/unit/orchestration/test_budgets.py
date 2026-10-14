"""orchestration/budgets.BudgetTracker: per-case and per-factor budgets (plan §6.2, §6.4, configs/budgets.yaml).

Defaults: 150K tokens per case, 8 store calls and 12K tokens per factor. The UI shows spend and every budget hit is
logged (the hit itself is the `exhausted` flag; how the hit is recorded is not specified, so only the flag is tested).
"""

from __future__ import annotations

import inspect

from hypothesis import given, strategies as st

from vakeel_sahayak.config import BudgetConfig
from vakeel_sahayak.orchestration.budgets import BudgetTracker
from vakeel_sahayak.schemas.case import BudgetState
from vakeel_sahayak.schemas.retrieval_plan import BudgetLeft

F = "trial_delay"
G = "parity_with_co_accused"


# ---------------------------------------------------------------------------------------------------------------------
# defaults (pass today)
# ---------------------------------------------------------------------------------------------------------------------
def test_constructor_defaults_match_plan_and_budgets_yaml(load_yaml):
    """BudgetTracker defaults are 150000 / 8 / 12000, equal to configs/budgets.yaml and BudgetConfig."""
    params = inspect.signature(BudgetTracker.__init__).parameters
    got = (
        params["tokens_per_case"].default,
        params["store_calls_per_factor"].default,
        params["tokens_per_factor"].default,
    )
    assert got == (150000, 8, 12000)
    y = load_yaml("budgets.yaml")
    assert (y["case"]["tokens"], y["factor"]["store_calls"], y["factor"]["tokens"]) == got
    c = BudgetConfig()
    assert (c.tokens_per_case, c.store_calls_per_factor, c.tokens_per_factor) == got


def test_budget_state_default_cap_is_150000():
    """BudgetState.tokens_cap defaults to the 150K case budget."""
    assert BudgetState().tokens_cap == 150000


# ---------------------------------------------------------------------------------------------------------------------
# behaviour
# ---------------------------------------------------------------------------------------------------------------------
def test_fresh_tracker_has_full_factor_budget():
    """Before any spend a factor has 8 store calls and 12000 tokens left (plan §6.3 example starts from the cap)."""
    t = BudgetTracker()
    assert t.left(F) == BudgetLeft(store_calls=8, tokens=12000)
    assert t.exhausted(F) is False
    assert t.exhausted() is False


def test_charge_then_left_reduces_exactly():
    """Charging 2 store calls and 3000 tokens leaves 6 and 9000, as in the plan §6.3 RetrievalPlan example."""
    t = BudgetTracker()
    t.charge(F, tokens=3000, store_calls=2)
    assert t.left(F) == BudgetLeft(store_calls=6, tokens=9000)
    t.charge(F, tokens=500, store_calls=1)
    assert t.left(F) == BudgetLeft(store_calls=5, tokens=8500)


def test_case_level_left_counts_tokens_of_all_factors():
    """Factor tokens also count against the 150K case budget; factor=None charges are case-only."""
    t = BudgetTracker()
    t.charge(F, tokens=3000)
    t.charge(G, tokens=2000)
    t.charge(None, tokens=500)
    assert t.left().tokens == 150000 - 5500
    assert t.left(F).tokens == 12000 - 3000  # a case-only charge does not reduce a factor


def test_exhausted_at_exactly_eight_store_calls_not_seven():
    """The per-factor store-call budget is spent at 8 calls, not at 7 (plan §6.2, 8 store calls per factor)."""
    t = BudgetTracker()
    for _ in range(7):
        t.charge(F, store_calls=1)
    assert t.exhausted(F) is False
    t.charge(F, store_calls=1)
    assert t.left(F).store_calls == 0
    assert t.exhausted(F) is True


def test_exhausted_at_exactly_twelve_thousand_factor_tokens():
    """The per-factor token budget is spent at 12000 tokens, not at 11999."""
    t = BudgetTracker()
    t.charge(F, tokens=11999)
    assert t.exhausted(F) is False
    t.charge(F, tokens=1)
    assert t.exhausted(F) is True
    assert t.left(F).tokens == 0


def test_exhausted_case_at_exactly_150000_tokens():
    """exhausted() for the case is False at 149999 tokens and True at 150000."""
    t = BudgetTracker()
    for factor in (F, G, None):
        t.charge(factor, tokens=49999 if factor is None else 50000)
    assert t.exhausted() is False  # 149999
    t.charge(None, tokens=1)
    assert t.exhausted() is True


def test_exhausted_stays_true_and_repeat_calls_are_stable():
    """Once a budget is hit, exhausted() keeps returning True (repeated calls do not reset or toggle it)."""
    t = BudgetTracker()
    t.charge(F, store_calls=8)
    assert [t.exhausted(F) for _ in range(3)] == [True, True, True]
    t.charge(G, store_calls=1)  # other spend does not clear it
    assert t.exhausted(F) is True
    t.charge(None, tokens=150000)
    assert [t.exhausted() for _ in range(3)] == [True, True, True]


def test_factors_are_independent():
    """Spending factor F's whole store-call budget leaves factor G's untouched and not exhausted."""
    t = BudgetTracker()
    t.charge(F, tokens=12000, store_calls=8)
    assert t.exhausted(F) is True
    assert t.exhausted(G) is False
    assert t.left(G) == BudgetLeft(store_calls=8, tokens=12000)


def test_case_exhaustion_exhausts_every_factor():
    """ASSUMPTION: when the case budget is spent, every factor reports exhausted (the docstring: 'factor or case')."""
    t = BudgetTracker()
    t.charge(None, tokens=150000)
    assert t.exhausted() is True
    assert t.exhausted(F) is True
    assert t.exhausted("never_charged_factor") is True


def test_left_never_goes_negative_after_overspend():
    """Overspending clamps what is left at zero."""
    t = BudgetTracker()
    t.charge(F, tokens=20000, store_calls=10)
    assert t.left(F) == BudgetLeft(store_calls=0, tokens=0)


def test_custom_caps_are_honoured():
    """Constructor arguments override the defaults for all three limits."""
    t = BudgetTracker(tokens_per_case=100, store_calls_per_factor=2, tokens_per_factor=50)
    assert t.left(F) == BudgetLeft(store_calls=2, tokens=50)
    t.charge(F, store_calls=2)
    assert t.exhausted(F) is True
    assert t.snapshot().tokens_cap == 100
    t.charge(G, tokens=100)
    assert t.exhausted() is True


def test_snapshot_reports_spend_and_cap():
    """snapshot() is a BudgetState with tokens_cap 150000, total tokens spent and store calls per factor."""
    t = BudgetTracker()
    t.charge(F, tokens=3000, store_calls=2)
    t.charge(G, tokens=1000, store_calls=1)
    t.charge(F, store_calls=1)
    snap = t.snapshot()
    assert isinstance(snap, BudgetState)
    assert snap.tokens_cap == 150000
    assert snap.tokens_spent == 4000
    assert snap.store_calls == {F: 3, G: 1}


def test_snapshot_of_fresh_tracker():
    """Nothing spent: zero tokens and no store calls, cap 150000."""
    snap = BudgetTracker().snapshot()
    assert (snap.tokens_spent, snap.tokens_cap, snap.store_calls) == (0, 150000, {})


@given(
    ops=st.lists(
        st.tuples(st.sampled_from([F, G, None]), st.integers(0, 5000), st.integers(0, 2)), min_size=0, max_size=30
    )
)
def test_property_left_and_exhausted_match_plain_sums(ops):
    """Property: left() is cap minus summed spend (floored at 0) and exhausted() is 'any cap reached'."""
    t = BudgetTracker()
    for factor, tokens, calls in ops:
        t.charge(factor, tokens=tokens, store_calls=calls if factor else 0)
    case_tokens = sum(o[1] for o in ops)
    for factor in (F, G):
        tok = sum(o[1] for o in ops if o[0] == factor)
        calls = sum(o[2] for o in ops if o[0] == factor)
        assert t.left(factor) == BudgetLeft(store_calls=max(0, 8 - calls), tokens=max(0, 12000 - tok))
        assert t.exhausted(factor) == (calls >= 8 or tok >= 12000 or case_tokens >= 150000)
    assert t.left().tokens == max(0, 150000 - case_tokens)
    assert t.exhausted() == (case_tokens >= 150000)
