"""M17 removal arm (eval/runners/m17_removal.py): the pack without the paragraph, the target choice, the record block and the score it feeds (offline, fakes for the agents)."""

from __future__ import annotations

import json
from types import SimpleNamespace

from vakeel_sahayak.eval.metrics import citations as ci
from vakeel_sahayak.eval.runners import m17_removal as m17
from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, Ground
from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, SlotResult


def pack(factor=Factor.CUSTODY_PERIOD):
    return EvidencePack(factor=factor, stance=FactorStance.FAVOURABLE, slots=[
        SlotResult(slot="authority", status=SlotStatus.FILLED, items=[{"doc_id": "D1", "para": 4, "text": "x"}, {"doc_id": "D2", "para": 9, "text": "y"}]),
        SlotResult(slot="good_law", status=SlotStatus.FILLED, items=[{"doc_id": "D1", "para": 4, "text": "x"}]),
        SlotResult(slot="statute", status=SlotStatus.FILLED, items=[])])


def test_remove_paragraph_drops_items_and_empties_become_missing():
    new = m17.remove_paragraph([pack(), pack(Factor.ANTECEDENTS)], Factor.CUSTODY_PERIOD, "D1", 4)
    assert len(new) == 1  # only the factor's own pack is redrafted
    by = {s.slot: s for s in new[0].slots}
    assert [i["doc_id"] for i in by["authority"].items] == ["D2"] and by["authority"].status == SlotStatus.FILLED
    assert by["good_law"].items == [] and by["good_law"].status == SlotStatus.MISSING
    assert by["statute"].status == SlotStatus.FILLED  # a slot that was empty before is untouched
    assert m17.remove_paragraph([pack()], Factor.ANTECEDENTS, "D1", 4) == []


def ground(i, factor, cites):
    return Ground(id=f"G{i}", factor=factor, stance=FactorStance.FAVOURABLE, argument=f"Claim {i} [A:D{i}#4].", authorities=[Authority(doc_id=d, para=4) for d in cites])


def test_targets_are_the_first_authority_of_cited_grounds_up_to_the_cap():
    brief = BailBrief(case_id="c", grounds=[ground(1, Factor.CUSTODY_PERIOD, ["D1", "D5"]), ground(2, Factor.ANTECEDENTS, []), ground(3, Factor.FLIGHT_RISK, ["D3"]), ground(4, Factor.TRIAL_DELAY, ["D4"])])
    t = m17.cited_targets(brief, 2)
    assert [(g.id, a.doc_id) for g, a in t] == [("G1", "D1"), ("G3", "D3")]


def test_run_case_writes_the_removal_block(monkeypatch):
    brief = BailBrief(case_id="c", grounds=[ground(1, Factor.CUSTODY_PERIOD, ["D1"])])
    captured_holder = {}

    def fake_run_agents(case, ctx, sutradhar=None, **kw):
        factory_agent = SimpleNamespace(delegate=lambda s, p: s)
        captured_holder["agent"] = factory_agent
        # the real factory wraps `delegate`; here we record what it would have captured
        m17_state = SimpleNamespace(model_copy=lambda update: SimpleNamespace(**update))
        captured_holder["cap"] = (m17_state, [pack()])
        return {"_brief_obj": brief, "brief": brief.model_dump(mode="json")}

    monkeypatch.setattr("vakeel_sahayak.eval.runners.driver.run_agents", fake_run_agents)
    monkeypatch.setattr(m17, "make_sutradhar", lambda captured: captured.update(state=captured_holder.get("cap", (None,))[0] or SimpleNamespace(model_copy=lambda update: SimpleNamespace(**update)), packs=[pack()]) or None)
    seen = {}

    def fake_redraft(ctx, state, packs, g, a):
        seen["doc"] = (a.doc_id, a.para)
        return "Claim 1 rewritten without the paragraph."

    monkeypatch.setattr(m17, "redraft_without", fake_redraft)
    rec = m17.run_case({"case_id": "c"}, SimpleNamespace(), max_claims=3)
    assert seen["doc"] == ("D1", 4)
    block = rec["removal"]
    assert block["n_cited_grounds"] == 1 and block["claims"][0]["original"].startswith("Claim 1") and block["claims"][0]["redraft"].startswith("Claim 1 rewritten")
    assert ci.removal_change(block)["rate"] == 1.0  # the redraft differs: the claim depended on the paragraph
    json.dumps(block)  # the record is JSON-serialisable
