"""A text-only evaluation case is pseudonymised like the production intake before any agent sees it: real names never reach a model client."""

from __future__ import annotations

from tests.integration._helpers import full_pipeline_llm
from vakeel_sahayak.eval.runners.driver import build_context, file_facts, learn_caption_names, run_agents
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_pseudonymised
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap, load_map

ORDER = (
    "IN THE HIGH COURT OF JHARKHAND AT RANCHI\n\nBA No. 9258 of 2023\n\n"
    "Chando Mahto @ Chando Yadav                    ...    Petitioner\n\nVersus\n\nThe State of Jharkhand\n\n"
    "For the Petitioner : Mr. Shahid Yunus, Advocate\n\nOrder dated 16.02.2024. The petitioner was arrested on 20.08.2023 under "
    "Section 318(4) BNS. Complainant Ramesh Verma alleges cheating. Charge sheet filed 02.11.2023."
)
NAMES = ["Chando Mahto", "Chando Yadav", "Shahid Yunus", "Ramesh Verma"]


def test_the_caption_rule_learns_parties_the_intake_rules_miss():
    mapping = PseudonymMap()
    assert {"Chando Mahto", "Chando Yadav"} <= set(learn_caption_names(ORDER, mapping))


def test_file_facts_returns_only_pseudonymised_text_and_saves_the_map(toolbox):
    case = {"case_id": "case-0007", "facts": ORDER, "before": toolbox.world.case_date}
    ctx = build_context(case, tools=toolbox.tools, llm=full_pipeline_llm())
    clean = file_facts(ctx, case, shelve=False)
    assert not any(n.lower() in clean.lower() for n in NAMES)
    assert "02.11.2023" in clean  # dates and sections survive
    mapping = load_map("case-0007", ctx.cases_dir)
    assert set(NAMES) <= set(mapping.known_names())
    assert_pseudonymised({"text": clean}, mapping=mapping)  # the boundary passes the cleaned text
    try:
        assert_pseudonymised({"text": ORDER}, mapping=mapping)
    except PrivacyBoundaryError:
        pass
    else:  # pragma: no cover
        raise AssertionError("the boundary must still refuse the raw text")


def test_named_facts_reach_the_model_client_only_in_pseudonymised_form(toolbox):
    llm = full_pipeline_llm()
    case = {"case_id": "case-0007", "facts": ORDER, "before": toolbox.world.case_date}
    ctx = build_context(case, tools=toolbox.tools, llm=llm)
    res = run_agents(case, ctx)
    assert llm.calls, "the model client was never called"
    sent = "\n".join(llm.prompts).lower()
    assert not any(n.lower() in sent for n in NAMES)
    assert not [e for e in res["errors"] if "privacy" in e.lower()]
    refusals = [e for e in ctx.log.read("case-0007") if "privacy_boundary" in str(e.outputs)]
    assert not refusals


def test_capitalised_relations_and_counsel_of_a_court_caption_are_learned():
    text = ("BINOD KUMAR SINGH S/O SARJU SINGH R/O VILLAGE- JALWAIYA\n...  Appellant/s\n"
            "Appearance: For the Appellant/s: Mr.Rama Kant Singh, Adv. For the State: Mr. S.K. Srivastava, APP\nHON'BLE MR. JUSTICE ANJANI KUMAR SHARAN\n")
    mapping = PseudonymMap()
    learned = learn_caption_names(text, mapping)
    assert {"BINOD KUMAR SINGH", "SARJU SINGH", "Rama Kant Singh", "S.K. Srivastava"} <= set(learned)
    cleaned = mapping.apply(text)
    assert "SARJU" not in cleaned.upper() and "RAMA KANT" not in cleaned.upper()
