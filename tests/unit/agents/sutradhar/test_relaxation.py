"""Sutradhar filter relaxation (plan §6.2 step 2.4): factor, then section family, then court; the date is never relaxed
(leakage rule, plan §2)."""

from __future__ import annotations

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vakeel_sahayak.agents.sutradhar.relaxation import RELAXATION_ORDER, relax

ARGS = {
    "factor": "parity_with_co_accused",
    "section_family": ["BNS 318(4)", "IPC 420"],
    "court": "Delhi HC",
    "before": "2025-02-03",
    "k": 10,
}


def _absent(args: dict, key: str) -> bool:
    # ASSUMPTION: a dropped filter is either removed from the dict or set to None.
    return args.get(key) is None


def test_relaxation_order_constant():
    """The order is fixed by the plan: factor, then section family, then court."""
    assert RELAXATION_ORDER == ["factor", "section_family", "court"]


def test_step0_drops_only_the_factor_filter():
    """Step 0 removes the factor filter and leaves every other argument intact."""
    out = relax(ARGS, 0)
    assert _absent(out, "factor")
    assert out["section_family"] == ARGS["section_family"]
    assert out["court"] == "Delhi HC"
    assert out["before"] == "2025-02-03"
    assert out["k"] == 10


def test_step1_also_widens_or_drops_section_family():
    """Step 1 additionally widens (superset) or drops the section family; court is still kept."""
    out = relax(ARGS, 1)
    assert _absent(out, "factor")
    family = out.get("section_family")
    # ASSUMPTION: 'widened' = the offence group (a strict superset of the two-entry family) or dropped altogether.
    assert family is None or set(ARGS["section_family"]) < set(family)
    assert out["court"] == "Delhi HC"
    assert out["before"] == "2025-02-03"


def test_step2_also_drops_court():
    """Step 2 additionally drops the court filter."""
    out = relax(ARGS, 2)
    assert _absent(out, "factor")
    family = out.get("section_family")
    assert family is None or set(ARGS["section_family"]) < set(family)
    assert _absent(out, "court")
    assert out["before"] == "2025-02-03"
    assert out["k"] == 10


@pytest.mark.parametrize("step", [3, 4, 10])
def test_relaxing_beyond_the_last_step_is_stable(step):
    """Past the last step nothing more can be relaxed: no error, same result as the last step."""
    # ASSUMPTION: relaxation is cumulative and saturates at step 2.
    assert relax(ARGS, step) == relax(ARGS, 2)


@pytest.mark.parametrize("step", range(0, 6))
def test_before_date_is_never_relaxed_and_input_not_mutated(step):
    """The 'before' date survives every step and the caller's dict is left untouched."""
    original = copy.deepcopy(ARGS)
    out = relax(ARGS, step)
    assert out["before"] == "2025-02-03"
    assert ARGS == original
    assert out is not ARGS


_FAMILIES = st.lists(st.sampled_from(["IPC 420", "BNS 318(4)", "IPC 406", "BNS 316(2)"]), min_size=1, max_size=4, unique=True)


@given(
    factor=st.sampled_from(["parity_with_co_accused", "charge_sheet_filed", "custody_period"]),
    family=_FAMILIES,
    court=st.sampled_from(["Delhi HC", "Bombay HC", "Supreme Court"]),
    before=st.dates().map(lambda d: d.isoformat()),
    k=st.integers(1, 20),
    step=st.integers(0, 5),
)
def test_relaxation_properties(factor, family, court, before, k, step):
    """For any args and step: date and k preserved, factor gone, court gone from step 2, input not mutated."""
    args = {"factor": factor, "section_family": family, "court": court, "before": before, "k": k}
    snapshot = copy.deepcopy(args)
    out = relax(args, step)
    assert args == snapshot
    assert out["before"] == before
    assert out["k"] == k
    assert _absent(out, "factor")
    assert (_absent(out, "court")) == (step >= 2)
    out_family = out.get("section_family")
    if step == 0:
        assert out_family == family
    else:
        assert out_family is None or set(family) <= set(out_family)
