"""Authority stance (`Switches.authority_stance='outcome'`; Sweep 4, `docs/literature-to-code-map.md`).

A paragraph from an order that refused bail states the State's point. With the switch, Vakeel offers supporting authorities first,
leaves adverse ones out when others exist, offers them marked adverse when nothing else exists (or when the factor is adverse), and a
ground that cites one carries a Warning note. Default (`off`) is byte-identical: `test_variants_golden.py`.
"""

from __future__ import annotations

from tests.fakes.data import build_world, load_paragraphs
from tests.unit.agents._helpers import build_agent, make_state
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, ground_llm, model_ground, pack
from vakeel_sahayak.agents.vakeel import stance as st
from vakeel_sahayak.agents.vakeel.agent import VakeelAgent
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.enums import Factor

PARITY = Factor.PARITY_WITH_CO_ACCUSED
ON = Switches(authority_stance="outcome")


def with_outcomes(p, outcomes: dict[tuple[str, int], str | None]):
    for slot in p.slots:
        for item in slot.items:
            item["outcome"] = outcomes.get((item["doc_id"], item["para"]))
    return p


def agent_for(sw):
    agent, _ctx, _tb = build_agent(VakeelAgent, switches=sw, llm=ground_llm(model_ground("G1", "parity_with_co_accused", SUPPORTED_G1, [("DLHC-2022-1187", 14)])))
    return agent


def test_default_is_off_and_stance_reads_outcome():
    assert Switches().authority_stance == "off"
    assert st.stance_of({"outcome": "granted"}) == st.SUPPORTS
    assert st.stance_of({"outcome": "rejected"}) == st.ADVERSE
    assert st.stance_of({"outcome": "withdrawn"}) == st.UNKNOWN
    assert st.stance_of({}) == st.UNKNOWN


def test_arrange_prefers_support_and_drops_adverse_when_others_exist():
    c = [{"doc_id": "A", "para": 1, "outcome": "rejected"}, {"doc_id": "B", "para": 1, "outcome": None}, {"doc_id": "C", "para": 1, "outcome": "granted"}]
    kept, dropped = st.arrange(c, "favourable")
    assert [x["doc_id"] for x in kept] == ["C", "B"] and dropped == ["A#1"]
    assert kept[0]["decision"].startswith("supports")


def test_arrange_offers_adverse_marked_when_only_adverse_or_factor_adverse():
    only = [{"doc_id": "A", "para": 1, "outcome": "rejected"}]
    kept, dropped = st.arrange(only, "favourable")
    assert [x["doc_id"] for x in kept] == ["A"] and not dropped and "adverse" in kept[0]["decision"]
    mixed = [{"doc_id": "A", "para": 1, "outcome": "rejected"}, {"doc_id": "C", "para": 1, "outcome": "granted"}]
    kept, dropped = st.arrange(mixed, "adverse")
    assert [x["doc_id"] for x in kept] == ["C", "A"] and not dropped


def test_agent_offers_supporting_authority_only_and_default_keeps_all():
    paras = load_paragraphs()
    cited = [("DLHC-2022-1187", 14), ("DLHC-2021-0420", 11)]
    outcomes = {("DLHC-2022-1187", 14): "rejected", ("DLHC-2021-0420", 11): "granted"}
    p = with_outcomes(pack(PARITY, paras, cited), outcomes)
    on = agent_for(ON)
    off = agent_for(Switches())
    on._set_packs([p])
    off._set_packs([p])
    assert [a["doc_id"] for a in on._candidates(p)[0]] == ["DLHC-2021-0420"]
    assert [a["doc_id"] for a in off._candidates(p)[0]] == ["DLHC-2022-1187", "DLHC-2021-0420"]
    assert "decision" not in off._candidates(p)[0][0]


def test_ground_citing_only_adverse_authority_carries_warning_note():
    paras = load_paragraphs()
    p = with_outcomes(pack(PARITY, paras, [("DLHC-2022-1187", 14)]), {("DLHC-2022-1187", 14): "rejected"})
    agent = agent_for(ON)
    grounds = agent.draft_grounds(_state(), [p])
    text = " ".join(g.argument for g in grounds)
    assert "adverse authority to distinguish" in text
    assert any(g.authorities for g in grounds)


def test_default_run_has_no_adverse_note():
    paras = load_paragraphs()
    p = with_outcomes(pack(PARITY, paras, [("DLHC-2022-1187", 14)]), {("DLHC-2022-1187", 14): "rejected"})
    agent = agent_for(Switches())
    grounds = agent.draft_grounds(_state(), [p])
    assert "adverse authority" not in " ".join(g.argument for g in grounds)


def _state():
    w = build_world()
    return make_state(w.dossier, w.rights)
