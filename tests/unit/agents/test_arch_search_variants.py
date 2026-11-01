"""Architecture search of 2026-11-01: X1 to X6 and H1 (`docs/handoff/arch-search-results.md`, `docs/literature-to-code-map.md` "Architecture search").

Every switch is opt-in and the default is byte-identical (the Vakeel / Abhiyojak golden digests in `tests/unit/agents/vakeel/test_variants_golden.py`,
re-asserted here for the explicit-default spelling). Each switch is tested for what it says it does.
"""

from __future__ import annotations

import json

import pytest

from tests.unit.agents._helpers import build_agent, make_ground, make_state
from tests.unit.agents.vakeel import _variants_helpers as vh
from tests.unit.agents.vakeel._scripts import SUPPORTED_G1, UNSUPPORTED_G1, ground_llm, model_ground, pack, reword_llm
from vakeel_sahayak.agents.sutradhar.factor_pick import custody_days_wide, pick_stances, signals_from_dossier, signals_merged
from vakeel_sahayak.agents.vakeel.agent import ABSENCE, VakeelAgent
from vakeel_sahayak.agents.vakeel.claims import split_claim
from vakeel_sahayak.agents.vakeel.facts import FACTS_TEXT_FIELD, span_share, text_fact
from vakeel_sahayak.agents.vakeel.work import SentenceCheck
from vakeel_sahayak.eval.runners.systems import canonical_system, system_switches
from vakeel_sahayak.orchestration.switches import H1_PARTS, IMPLEMENTED_VARIANTS, Switches, assert_variant_implemented
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance

PARITY, CUSTODY = Factor.PARITY_WITH_CO_ACCUSED, Factor.CUSTODY_PERIOD
FACTS = "The applicant has been in judicial custody since 04.01.2024. Co-accused with an identical role were granted bail by this Court."
X_FIELDS = {"X1": ("signal_source", "merge"), "X2": ("argument_policy", "fact_law_split"), "X3": ("sparring_scope", "all_factors"),
            "X4": ("abstention", "strict"), "X5": ("draft_source", "facts_text"), "X6": ("critic_material", "union_free")}


# ---- selection and defaults -----------------------------------------------------------------------------------------
def test_defaults_are_the_full_system():
    s = Switches()
    assert s.variant() == "full"
    assert (s.signal_source, s.argument_policy, s.sparring_scope, s.abstention, s.draft_source, s.critic_material) == ("dossier", "single", "per_ground", "flag", "dossier", "contract")
    assert not s.drafts_from_facts_text


@pytest.mark.parametrize("ident", sorted(X_FIELDS))
def test_each_candidate_sets_exactly_its_field_and_is_registered(ident):
    name, value = X_FIELDS[ident]
    s = Switches.for_variant(ident)
    assert s.model_dump(exclude_defaults=True) == {name: value}
    assert s.variant() == ident
    assert ident in IMPLEMENTED_VARIANTS
    assert_variant_implemented(ident)
    assert system_switches(ident) == s and canonical_system(ident.lower()) == ident


def test_h1_is_the_combination_and_each_leave_one_out_drops_one_part():
    h1 = Switches.for_variant("H1")
    assert h1.model_dump(exclude_defaults=True) == dict(X_FIELDS[k] for k in H1_PARTS)
    assert h1.variant() == "H1" and "H1" in IMPLEMENTED_VARIANTS
    for k in H1_PARTS:
        loo = Switches.for_variant(f"H1m{k[1:]}")
        assert X_FIELDS[k][0] not in loo.model_dump(exclude_defaults=True)
        assert len(loo.model_dump(exclude_defaults=True)) == len(H1_PARTS) - 1
        assert loo.variant() == f"H1m{k[1:]}" and f"H1m{k[1:]}" in IMPLEMENTED_VARIANTS


@pytest.mark.parametrize("bad", [
    {"draft_source": "facts_text", "no_dossier": True}, {"signal_source": "merge", "no_dossier": True},
    {"sparring_scope": "all_factors", "no_sparring": True}, {"critic_material": "union_free", "critic_mode": "sampling"},
    {"abstention": "strict", "no_check_repair": True}, {"abstention": "strict", "repair_mode": "self_critique"},
])
def test_incompatible_combinations_are_refused(bad):
    with pytest.raises(ValueError):
        Switches(**bad)


def test_the_default_run_is_byte_identical_to_the_golden_digests():
    golden = json.loads(vh.GOLDEN.read_text(encoding="utf-8"))
    explicit = Switches(signal_source="dossier", argument_policy="single", sparring_scope="per_ground", abstention="flag", draft_source="dossier", critic_material="contract")
    assert vh.digests(vh.canonical_run(vh.build(switches=explicit))) == golden


# ---- X1: signal merge -----------------------------------------------------------------------------------------------
def test_x1_reads_custody_from_the_facts_when_the_dossier_has_none(dossier, expected_rights_report):
    assert custody_days_wide("The applicant is in detention since 26.12.2023.", "2024-02-16") == 52
    assert custody_days_wide("Nothing about custody here.", "2024-02-16") is None
    empty = signals_from_dossier(None, None)
    sig = signals_merged(None, "The applicant has been in custody since 04.01.2024 and the charge sheet has been filed.", "2024-02-16", None)
    assert empty.custody_days is None and sig.custody_days == 43 and sig.charge_sheet_filed is True
    assert "custody_days" in sig.merged and sig.source == "merge"
    stances = {f: s for f, s, _ in pick_stances(sig)}
    assert stances[Factor.CHARGE_SHEET_FILED] == FactorStance.FAVOURABLE
    assert {f: s for f, s, _ in pick_stances(empty)}[Factor.CHARGE_SHEET_FILED] == FactorStance.NOT_APPLICABLE


def test_x1_never_overrides_a_dossier_value_and_changes_nothing_without_text(dossier, expected_rights_report):
    base = signals_from_dossier(dossier, expected_rights_report)
    same = signals_merged(dossier, None, "2025-02-03", expected_rights_report)
    assert same == base and same.merged == [] and same.source == "dossier"
    merged = signals_merged(dossier, "In custody since 01.01.2020.", "2025-02-03", expected_rights_report)
    assert merged.custody_days == base.custody_days  # the dossier states it (or both are None): the text never replaces a stated value
    if base.custody_days is not None:
        assert "custody_days" not in merged.merged


# ---- X2: fact / law split -------------------------------------------------------------------------------------------
def test_span_share_is_one_for_a_verbatim_span_and_low_for_new_words():
    assert span_share("The applicant has been in judicial custody since 04.01.2024", FACTS) == 1.0
    assert span_share("The applicant is a respected businessman with deep roots", FACTS) < 0.5
    assert span_share("", FACTS) == 1.0


def test_x2_flags_a_case_fact_that_is_not_a_span_and_a_mixed_sentence():
    agent, _, _ = build_agent(VakeelAgent, switches=Switches(argument_policy="fact_law_split"))
    agent._facts = text_fact(FACTS)
    ok, bad, mixed = (split_claim(t)[0] for t in (
        "The applicant has been in judicial custody since 04.01.2024 [F:facts_text].",
        "The applicant is a respected businessman with deep family roots [F:facts_text].",
        "The applicant has been in judicial custody since 04.01.2024 [F:facts_text] [A:DLHC-2022-1187#14].",
    ))
    for sentence, problems in ((ok, []), (bad, ["not_extractive"]), (mixed, ["mixed"])):
        sc = SentenceCheck(sentence.text)
        agent._split_problems(sentence, sc)
        assert sc.problems == problems


def test_x2_offers_the_facts_text_beside_the_dossier_and_the_default_does_not(paragraphs, dossier, expected_rights_report):
    state = make_state(dossier, expected_rights_report, facts_text=FACTS)
    p = pack(PARITY, paragraphs, [("DLHC-2022-1187", 14)])
    for switches, expect in ((Switches(), False), (Switches(argument_policy="fact_law_split"), True)):
        agent, _, _ = build_agent(VakeelAgent, switches=switches, llm=ground_llm(model_ground("G1", PARITY.value, SUPPORTED_G1, [("DLHC-2022-1187", 14)])))
        agent._prime(state)
        assert (FACTS_TEXT_FIELD in agent._evidence_for(p).facts) is expect
    assert "word for word" in agent._ins("vakeel.draft_ground", factor="parity", stance="favourable")


# ---- X5: drafting from the raw facts --------------------------------------------------------------------------------
def test_x5_drafts_from_the_facts_text_and_the_default_from_the_dossier(paragraphs, dossier, expected_rights_report):
    state = make_state(dossier, expected_rights_report, facts_text=FACTS)
    p = pack(PARITY, paragraphs, [("DLHC-2022-1187", 14)])
    default, _, _ = build_agent(VakeelAgent, llm=ground_llm(model_ground("G1", PARITY.value, SUPPORTED_G1, [("DLHC-2022-1187", 14)])))
    default._prime(state)
    assert FACTS_TEXT_FIELD not in default._evidence_for(p).facts and "co_accused_bail" in default._evidence_for(p).facts
    x5, _, _ = build_agent(VakeelAgent, switches=Switches(draft_source="facts_text"), llm=ground_llm(model_ground("G1", PARITY.value, SUPPORTED_G1, [("DLHC-2022-1187", 14)])))
    x5._prime(state)
    assert set(x5._evidence_for(p).facts) == {FACTS_TEXT_FIELD}
    assert x5._dossier is not None  # the dossier stays for the gates and the open issues
    no_text, _, _ = build_agent(VakeelAgent, switches=Switches(draft_source="facts_text"))
    no_text._prime(make_state(dossier, expected_rights_report))
    assert "co_accused_bail" in no_text._evidence_for(p).facts  # no facts text: the dossier facts stand


# ---- X4: strict abstention ------------------------------------------------------------------------------------------
def test_absence_template_matches_silence_and_not_a_principle():
    for text in ("The record does not state any antecedents.", "No facts about the antecedents are on record.", "Antecedents are not established.", "The dossier is silent on the arrest date."):
        assert ABSENCE.search(text), text
    for text in ("The Court held that parity requires the same relief.", "Co-accused with an identical role has been enlarged on bail."):
        assert not ABSENCE.search(text), text


def unsupported_ground(gid="G1"):
    return make_ground(gid, PARITY, UNSUPPORTED_G1, [("DLHC-2022-1187", 14)], check=ClaimCheck.NEEDS_REVIEW)


def supported_ground(gid="G2"):
    return make_ground(gid, Factor.CHARGE_SHEET_FILED, SUPPORTED_G1, [("DLHC-2022-1187", 14)], check=ClaimCheck.SUPPORTED)


def test_x4_default_keeps_a_failing_ground_and_strict_hands_it_to_counsel(dossier, expected_rights_report):
    flag, _, _ = build_agent(VakeelAgent, llm=reword_llm(UNSUPPORTED_G1))
    kept = flag.repair_or_flag([unsupported_ground(), supported_ground()])
    assert [g.id for g in kept] == ["G1", "G2"] and kept[0].check == ClaimCheck.NEEDS_REVIEW
    strict, _, _ = build_agent(VakeelAgent, switches=Switches(abstention="strict"), llm=reword_llm(UNSUPPORTED_G1))
    state = make_state(dossier, expected_rights_report)
    strict._prime(state)
    out = strict.repair_or_flag([unsupported_ground(), supported_ground()])
    assert [g.id for g in out] == ["G2"] and out[0].check == ClaimCheck.SUPPORTED
    brief = strict.assemble_brief(state, out)
    issues = [i.item for i in brief.open_issues]
    assert any("G1" in i and "left out of the argument" in i for i in issues)  # nothing dropped silently
    assert any("No supported argument could be drafted for" in i for i in issues)


def test_x4_removes_only_the_failing_sentence_of_a_mixed_ground():
    two = f"{SUPPORTED_G1}. {UNSUPPORTED_G1}"
    strict, _, _ = build_agent(VakeelAgent, switches=Switches(abstention="strict"), llm=reword_llm(UNSUPPORTED_G1))
    out = strict.repair_or_flag([make_ground("G1", PARITY, two.replace("]. ", "] . ", 1), [("DLHC-2022-1187", 14)], check=ClaimCheck.NEEDS_REVIEW)])
    assert len(out) == 1 and "05.12.2024" not in out[0].argument and "parity requires the same relief" in out[0].argument
    assert out[0].check in (ClaimCheck.SUPPORTED, ClaimCheck.REPAIRED)


def test_x4_leaves_a_clean_ground_untouched():
    strict, _, _ = build_agent(VakeelAgent, switches=Switches(abstention="strict"), llm=reword_llm(SUPPORTED_G1))
    ground = supported_ground()
    out = strict.repair_or_flag([ground])
    assert out[0].argument == ground.argument and out[0].check == ClaimCheck.SUPPORTED


# ---- X3 and X6: Abhiyojak -------------------------------------------------------------------------------------------
def test_x3_adds_a_round_for_factors_without_a_ground_and_default_adds_none():
    base = vh.build()
    vh.run_both(base)
    assert not vh.events_of(base, "round_1_extra")
    env = vh.build(switches=Switches(sparring_scope="all_factors"))
    out = vh.run_both(env)
    extra = vh.events_of(env, "round_1_extra")
    assert len(extra) == 1
    covered = {g.factor.value for g in out.state.brief.grounds}
    raised = [o for o in out.record.objections if o.against == "general" and o.factor not in {"gravity_and_punishment", "flight_risk", "witness_tampering", "antecedents", "statutory_bar"}]
    assert all(o.factor not in covered and o.grounds for o in raised)  # a factor the defence argued is never in the extra round; every objection points at material
    assert len(raised) <= 4


def test_split_metric_classifies_by_markers_and_leaves_m6_alone():
    from vakeel_sahayak.eval.scoring.split_metric import case_row, classify

    assert classify("The applicant has been in custody since 04.01.2024 [F:facts_text].") == "case_fact"
    assert classify("The Court held that parity requires the same relief [A:DLHC-2022-1187#14].") == "legal"
    assert classify("The Court held it on a fact [F:custody_days] [A:DLHC-2022-1187#14].") == "legal"
    assert classify("The record does not state any antecedents [F:antecedents].") == "absence"
    assert classify("Warning: DLHC-2022-1187 has been overruled [A:DLHC-2022-1187#14].") == "note"
    assert classify("Bail is the rule.") == "other"
    brief = {"grounds": [{"argument": "The applicant has been in custody since 04.01.2024 [F:facts_text]. The Court held that parity requires the same relief [A:DLHC-2022-1187#14]."}]}
    row = case_row(brief, "The applicant has been in custody since 04.01.2024.", "c1", lambda premise, s: 0.9 if "custody" in s else 0.1, 0.5)
    assert (row["n_case_fact"], row["n_legal"], row["n_case_fact_unsupported"], row["unsupported_case_fact_rate"], row["unsupported_all_rate"]) == (1, 1, 0, 0.0, 0.5)


def test_x6_adds_a_free_search_and_default_runs_none():
    base = vh.build()
    vh.run_both(base)
    assert not vh.events_of(base, "retrieve_free")
    env = vh.build(switches=Switches(critic_material="union_free"))
    vh.run_both(env)
    assert vh.events_of(env, "retrieve_free")
    assert env.abhiyojak._free_query  # keyed by the dossier facts, not by the ground text
