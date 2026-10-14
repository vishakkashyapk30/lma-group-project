"""Baselines B0-B4 and Full (plan §15.3): what each one does and, above all, what each one ISOLATES.

All use Qwen3-14B and the same 12-factor checklist, and the same clean facts text.

| ID | System | Isolates |
| B0 | raw facts + checklist -> brief in one call | no retrieval, no agents |
| B1 | one RAG index, top-10 with the facts as query, one drafting call | one store vs many |
| B2 | whole-document embeddings, top-3 orders passed in full | granularity |
| B3 | B1 with a naive chunker (five variants), best on dev | chunking |
| B4 | every store queried with facts and factor names, fused by RRF; drafting, checks and sparring as in Full | many stores vs an agent choosing |
| Full | Munshi -> Peshkar -> Sutradhar, Vakeel, Abhiyojak, all checks | |

The registry facts (entry points, B0 makes one call and no tool call, B4 touches every shared store without a planner) are in
test_registries.py; this file adds the remaining behaviour. Everything runs on the fakes of tests/fakes; the tests fail until the
baselines are implemented. Tool-call arguments are read from `FakeToolbox.calls`.
# SKELETON-GAP: B1's 'single vector index' and B2's 'top-3 orders in full' have no store in the skeleton (similar_orders returns
# metadata rows, not order text). The tests therefore pin what is observable: how many retrieval calls, with which arguments.
"""

from __future__ import annotations

import importlib

import pytest

from tests.fakes.models import ScriptedLLM
from tests.integration._helpers import calls_of, full_pipeline_llm
from vakeel_sahayak.schemas.bail_brief import DRAFT_LABEL, BailBrief
from vakeel_sahayak.schemas.enums import Factor

BASELINES = ["b0_single_pass", "b1_single_rag", "b2_whole_doc", "b3_naive_chunking", "b4_all_stores"]
CHECK_TOOLS = {"check_claim", "good_law_check", "transfer_check", "render_citation"}
RETRIEVAL_TOOLS = {"search_reasoning", "search_arguments", "search_objections", "similar_orders", "search_statutes", "get_statute",
                   "search_case_docs", "citations", "map_section"}
FACTS = ("The accused was arrested on 20.08.2024 for cheating under Section 318(4) BNS. Charge sheet filed 02.11.2024. "
         "Co-accused-1 granted bail 05.12.2024.")


def case(world):
    return {"case_id": "case-0007", "facts": FACTS, "before": world.case_date}


def brief_llm() -> ScriptedLLM:
    return ScriptedLLM(strict=False, default=BailBrief(case_id="case-0007").model_dump_json())


def run(name, make_ctx, toolbox, llm=None):
    mod = importlib.import_module(f"vakeel_sahayak.eval.baselines.{name}")
    llm = llm or brief_llm()
    ctx = make_ctx(llm=llm, toolbox=toolbox)
    return mod.run_case(case(toolbox.world), ctx), llm


def retrieval_calls(toolbox):
    return [c for c in toolbox.calls if c.name in RETRIEVAL_TOOLS]


def spaced(factor: Factor) -> str:
    return factor.value.replace("_", " ")


# ---------------------------------------------------------------- every baseline returns a draft brief
@pytest.mark.parametrize("name", BASELINES)
def test_every_baseline_returns_a_labelled_brief_for_the_case(name, make_ctx, toolbox):
    """The comparison is on BailBrief objects with the fixed draft label (plan §8.1, §16): no baseline may drop it."""
    brief, _ = run(name, make_ctx, toolbox)
    assert isinstance(brief, BailBrief) and brief.case_id == "case-0007" and brief.label == DRAFT_LABEL


@pytest.mark.parametrize("name", BASELINES)
def test_no_baseline_cites_a_document_dated_after_the_case_or_a_test_order(name, make_ctx, toolbox):
    """Leakage rule applies to the baselines too (plan §2): shared-store calls carry the case's `before` date."""
    run(name, make_ctx, toolbox)
    for c in toolbox.calls:
        if c.name in {"search_reasoning", "search_arguments", "search_objections", "similar_orders"}:
            assert c.kwargs.get("before") == toolbox.world.case_date, c


# ---------------------------------------------------------------- B0: no retrieval, no agents
def test_b0_prompt_holds_the_facts_and_the_whole_twelve_factor_checklist(make_ctx, toolbox):
    """Same checklist as every system (plan §15.3 'no gain from just knowing the checklist'): all 12 factors are in the one prompt."""
    _, llm = run("b0_single_pass", make_ctx, toolbox)
    prompt = llm.calls[0].prompt.lower()
    assert FACTS.split(".")[0].lower() in prompt
    assert all(f.value in prompt or spaced(f) in prompt for f in Factor)
    assert len(list(Factor)) == 12


def test_b0_has_no_planner_no_checker_no_sparring_calls(make_ctx, toolbox):
    _, llm = run("b0_single_pass", make_ctx, toolbox)
    assert len(llm.calls) == 1 and llm.calls[0].schema_title in (None, "BailBrief")


# ---------------------------------------------------------------- B1: one index, top-10, one drafting call
def test_b1_retrieves_once_with_the_facts_as_the_query_and_k_ten(make_ctx, toolbox):
    """Plan §15.3: 'top-10 retrieved with the facts as the query' from ONE index (one store, not many)."""
    run("b1_single_rag", make_ctx, toolbox)
    calls = retrieval_calls(toolbox)
    assert len(calls) == 1
    q = calls[0].kwargs
    assert FACTS in (q.get("query") or q.get("facts_text"))
    assert q.get("k", 10) == 10


def test_b1_uses_no_factor_filter_no_section_family_and_no_checks(make_ctx, toolbox):
    """B1 is plain RAG: no factor filter, no section-family expansion, no claim checks, no good-law or transfer flag."""
    run("b1_single_rag", make_ctx, toolbox)
    for c in retrieval_calls(toolbox):
        assert not c.kwargs.get("factor") and not c.kwargs.get("section_family")
    assert not CHECK_TOOLS & {c.name for c in toolbox.calls}


def test_b1_makes_one_drafting_call_and_no_planning_call(make_ctx, toolbox):
    _, llm = run("b1_single_rag", make_ctx, toolbox)
    assert len(llm.calls) == 1 and not llm.calls_for("RetrievalPlan")


def test_b1_puts_the_retrieved_paragraphs_into_the_one_prompt(make_ctx, toolbox):
    """Retrieved text reaches the drafting call (otherwise B1 would equal B0)."""
    _, llm = run("b1_single_rag", make_ctx, toolbox)
    assert "enlarged on bail" in llm.calls[0].prompt or "charge sheet is filed" in llm.calls[0].prompt


# ---------------------------------------------------------------- B2: whole-document vectors, top-3 orders in full
def test_b2_retrieves_whole_orders_not_paragraphs(make_ctx, toolbox):
    """Granularity is what B2 isolates: it asks the whole-order index (similar_orders) for 3 orders and never searches paragraphs."""
    run("b2_whole_doc", make_ctx, toolbox)
    names = [c.name for c in retrieval_calls(toolbox)]
    assert names == ["similar_orders"]
    assert retrieval_calls(toolbox)[0].kwargs.get("k") == 3
    assert not {"search_reasoning", "search_arguments", "get_paragraph"} & set(names)


def test_b2_one_drafting_call_and_no_checks(make_ctx, toolbox):
    _, llm = run("b2_whole_doc", make_ctx, toolbox)
    assert len(llm.calls) == 1 and not CHECK_TOOLS & {c.name for c in toolbox.calls}


def test_b2_whole_document_embedding_is_truncated_at_8k_tokens(load_yaml):
    """models.yaml: one BGE-M3 vector per order, truncated at 8,192 tokens (plan §15.3 'truncated at 8K tokens')."""
    assert load_yaml("models.yaml")["embeddings"]["max_tokens_whole_doc"] == 8192


# ---------------------------------------------------------------- B3: B1 with a naive chunker
def test_b3_is_b1_plus_a_chunker_one_retrieval_one_draft(make_ctx, toolbox):
    """B3 differs from B1 only in how the index was chunked, so its call pattern is B1's: one top-10 retrieval, one drafting call."""
    _, llm = run("b3_naive_chunking", make_ctx, toolbox)
    calls = retrieval_calls(toolbox)
    assert len(calls) == 1 and len(llm.calls) == 1 and calls[0].kwargs.get("k", 10) == 10
    assert not CHECK_TOOLS & {c.name for c in toolbox.calls}


def test_b3_best_variant_is_chosen_on_dev(load_yaml):
    """The five chunkers all run in the retrieval-only analysis; the best on dev goes into generation (plan §15.3).
    # SKELETON-GAP: intended `b3_naive_chunking.select_best_variant(dev_recall: dict[str, float]) -> str`."""
    mod = importlib.import_module("vakeel_sahayak.eval.baselines.b3_naive_chunking")
    fn = getattr(mod, "select_best_variant", None)
    assert fn is not None, "SKELETON-GAP: b3_naive_chunking.select_best_variant"
    dev = {"fixed_512": 0.41, "fixed_512_overlap": 0.44, "recursive": 0.47, "semantic": 0.39, "page": 0.30}
    assert fn(dev) == "recursive"


# ---------------------------------------------------------------- B4: every store, no orchestrator
def test_b4_queries_with_the_facts_and_with_each_factor_name(make_ctx, toolbox):
    """Plan §15.3: 'each store is queried with the facts and factor names'. Across the retrieval calls the facts and all 12 factors occur."""
    run("b4_all_stores", make_ctx, toolbox)
    text = " ".join(str(c.kwargs) for c in retrieval_calls(toolbox)).lower()
    assert FACTS.split(".")[0].lower() in text
    assert all(f.value in text or spaced(f) in text for f in Factor)


def test_b4_drafts_checks_and_spars_like_full(make_ctx, toolbox):
    """'Drafting, checks and sparring are the same as the full system': with a grounded draft, check_claim runs on it and the
    Abhiyojak calls happen; what is missing relative to Full is only the Sutradhar planner."""
    llm = full_pipeline_llm()
    run("b4_all_stores", make_ctx, toolbox, llm)
    assert toolbox.count("check_claim") >= 1
    assert calls_of(llm, "objections", "judge")
    assert not calls_of(llm, "plan", "factors")


def test_b4_fuses_rankings_with_reciprocal_rank_fusion():
    """RRF with k=60: B appears in both lists (1/62 + 1/61), A only first (1/61), C only second (1/62), so the order is B, A, C.
    # SKELETON-GAP: intended `b4_all_stores.reciprocal_rank_fusion(rankings: list[list[str]], k: int = 60) -> list[str]`."""
    mod = importlib.import_module("vakeel_sahayak.eval.baselines.b4_all_stores")
    fn = getattr(mod, "reciprocal_rank_fusion", None)
    assert fn is not None, "SKELETON-GAP: b4_all_stores.reciprocal_rank_fusion"
    assert fn([["A", "B"], ["B", "C"]]) == ["B", "A", "C"]


# ---------------------------------------------------------------- Full: the contrast that B4 isolates
def test_full_plans_with_sutradhar_where_b4_does_not(make_ctx, toolbox):
    """Full = B4's drafting, checks and sparring + Sutradhar's evidence-contract planning: the 14B plans (RetrievalPlan calls)."""
    llm = full_pipeline_llm()
    mod = importlib.import_module("vakeel_sahayak.eval.baselines.full_system")
    ctx = make_ctx(llm=llm, toolbox=toolbox)
    brief = mod.run_case(case(toolbox.world), ctx)
    assert isinstance(brief, BailBrief)
    assert calls_of(llm, "plan") and calls_of(llm, "objections", "judge")
    assert toolbox.count("check_claim") >= 1


def test_the_what_each_baseline_isolates_table_is_in_the_module_docstrings():
    """Each module docstring names its plan §15.3 definition, so a reader of the results knows what the comparison isolates."""
    expect = {
        "b0_single_pass": ("single pass", "no retrieval"),
        "b1_single_rag": ("single rag", "top-10"),
        "b2_whole_doc": ("whole-document", "top-3"),
        "b3_naive_chunking": ("chunking", "20% overlap"),
        "b4_all_stores": ("every store", "reciprocal-rank fusion"),
    }
    for name, needles in expect.items():
        doc = (importlib.import_module(f"vakeel_sahayak.eval.baselines.{name}").__doc__ or "").lower()
        assert all(n in doc for n in needles), (name, needles)

