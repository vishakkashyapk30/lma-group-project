"""The objections sheet words an objection that got no reply because the sparring budget was spent (NOT_REPLIED_BUDGET) in plain words."""

from __future__ import annotations

from vakeel_sahayak.agents.abhiyojak.agent import NOT_REPLIED_REASON
from vakeel_sahayak.export.objections import _verdict_cell
from vakeel_sahayak.schemas.sparring import Objection, ObjectionGround


def _o(verdict, reason):
    return Objection(id="O1", against="G1", factor="custody_period", objection="x", grounds=[ObjectionGround(fact="fir")], reply=None, verdict=verdict, reason=reason)


def test_budget_state_is_plain_words_without_the_code():
    from vakeel_sahayak.schemas.enums import SparringVerdict

    cell = _verdict_cell(_o(SparringVerdict.UNANSWERED, NOT_REPLIED_REASON))
    assert cell == "No reply was drafted because the sparring budget was spent; counsel answers this one."
    assert "NOT_REPLIED_BUDGET" not in cell
    assert _verdict_cell(_o(SparringVerdict.PARTLY, "covers the role")) == "Partly: covers the role"
    assert _verdict_cell(_o(None, None)) == "Not judged"
