"""configs/*.yaml agree with the plan (plan §2, §4.2, §5.1, §7.3, §12, §17, Appendix C). Read directly with yaml;
config.load_config is tested separately. These pass against the skeleton today."""

from __future__ import annotations

import datetime as dt
import re

import pytest
import yaml

from vakeel_sahayak.schemas.enums import AgentName, StoreName

ALL_YAMLS = [
    "bail_sections.yaml", "budgets.yaml", "models.yaml", "paths.yaml", "rights_rules.yaml", "splits.yaml",
    "stores.yaml", "thresholds.yaml", "tools.yaml",
]


def _as_date(value) -> dt.date:
    return value if isinstance(value, dt.date) else dt.date.fromisoformat(str(value))


def family(model_id: str) -> str:
    """Model family from a hub id ('Qwen/Qwen3-14B-AWQ' -> 'qwen', 'meta-llama/Llama-3.1-8B-Instruct' -> 'llama')."""
    name = model_id.split("/")[-1].lower()
    return re.split(r"[-_.0-9]", name, maxsplit=1)[0]


# ----------------------------------------------------------------------------------------------------------------
# every file parses
# ----------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("name", ALL_YAMLS)
def test_top_level_yaml_parses_to_a_mapping(load_yaml, name):
    """Each top-level config YAML parses to a non-empty mapping."""
    data = load_yaml(name)
    assert isinstance(data, dict) and data


def test_every_yaml_under_configs_parses(configs_dir):
    """Every YAML anywhere under configs/ (including eval/ and finetune/) parses with safe_load."""
    files = sorted(configs_dir.rglob("*.yaml"))
    assert len(files) >= 13  # 9 top-level + eval/ (2) + finetune/ (2)
    for path in files:
        assert yaml.safe_load(path.read_text(encoding="utf-8")) is not None, path


def test_no_config_names_a_paid_api_provider(configs_dir):
    """Open-weight models only at run time, no paid APIs (plan ground rules): no OpenAI/Anthropic/Gemini in configs."""
    text = "\n".join(p.read_text(encoding="utf-8").lower() for p in configs_dir.rglob("*.yaml"))
    for banned in ("openai/gpt", "gpt-4", "claude", "gemini", "api_key"):
        assert banned not in text, banned


# ----------------------------------------------------------------------------------------------------------------
# stores.yaml (plan §5.1)
# ----------------------------------------------------------------------------------------------------------------
def test_stores_yaml_has_ten_stores_on_four_shelves(load_yaml):
    """stores.yaml lists the ten stores on the four shelves with the 2/3/2/3 split of plan §5.1."""
    cfg = load_yaml("stores.yaml")
    shelves = {k: cfg[k] for k in ("law", "caselaw", "advocacy", "case")}
    assert {k: sorted(v) for k, v in shelves.items()} == {
        "law": ["concordance", "statutes"],
        "caselaw": ["citations", "reasoning", "similar"],
        "advocacy": ["arguments", "objections"],
        "case": ["docs", "facts", "timeline"],
    }
    dotted = {f"{shelf}.{store}" for shelf, stores in shelves.items() for store in stores}
    assert dotted == {s.value for s in StoreName}


@pytest.mark.parametrize(
    ("store", "index"),
    [
        ("law.statutes", "exact+bm25"),
        ("law.concordance", "graph"),
        ("caselaw.reasoning", "hybrid(bm25+bge-m3)"),
        ("caselaw.citations", "graph+authority"),
        ("caselaw.similar", "vectors+signature"),
        ("advocacy.arguments", "hybrid"),
        ("advocacy.objections", "hybrid"),
        ("case.docs", "hybrid"),
        ("case.timeline", "exact"),
        ("case.facts", "exact"),
    ],
)
def test_store_index_kind_matches_plan_table(load_yaml, store, index):
    """Each store's index kind is the one in the plan §5.1 table."""
    shelf, name = store.split(".")
    assert load_yaml("stores.yaml")[shelf][name]["index"] == index


@pytest.mark.parametrize(
    ("store", "key", "size"),
    [
        ("law.statutes", "est_rows", 1000),
        ("law.concordance", "est_edges", 600),
        ("caselaw.reasoning", "est_rows", "100-300K"),
        ("caselaw.citations", "est_edges", "100-300K"),
        ("caselaw.similar", "est_rows", "50-100K"),
        ("advocacy.arguments", "est_rows", 100000),
        ("advocacy.objections", "est_rows", 80000),
    ],
)
def test_store_size_estimates_match_plan_table(load_yaml, store, key, size):
    """Size estimates equal the plan §5.1 'Size (est.)' column."""
    shelf, name = store.split(".")
    assert load_yaml("stores.yaml")[shelf][name][key] == size


def test_reasoning_chunk_limit_is_400_tokens(load_yaml):
    """Reasoning chunks are at most 400 tokens (plan §5.2)."""
    assert load_yaml("stores.yaml")["caselaw"]["reasoning"]["chunk_max_tokens"] == 400


def test_argument_bank_is_marked_never_cited_as_authority(load_yaml):
    """advocacy.arguments carries never_cited_as_authority (plan §5.1)."""
    assert load_yaml("stores.yaml")["advocacy"]["arguments"]["never_cited_as_authority"] is True


def test_case_stores_are_per_case_paths(load_yaml):
    """Case-shelf paths are templated by case_id (private, per case) and shared stores are not."""
    cfg = load_yaml("stores.yaml")
    for name, spec in cfg["case"].items():
        assert "{case_id}" in spec["path"], name
    for shelf in ("law", "caselaw", "advocacy"):
        for name, spec in cfg[shelf].items():
            assert "{case_id}" not in spec["path"], f"{shelf}.{name}"
    assert "{case_id}" in cfg["event_log"]["path"] and "{case_id}" in cfg["checkpointer"]["path"]


def test_leakage_rules_in_stores_yaml(load_yaml):
    """Test orders and same-FIR orders are excluded and queries filter to before the case's order (plan §2)."""
    leak = load_yaml("stores.yaml")["leakage"]
    assert set(leak["exclude"]) == {"test_orders", "same_fir_as_test"}
    assert leak["query_filter"] == "before_case_order_date"


# ----------------------------------------------------------------------------------------------------------------
# models.yaml (plan §12, §17)
# ----------------------------------------------------------------------------------------------------------------
LLM_ROLES = {
    # role: (model id, where)
    "agents_14b": ("Qwen/Qwen3-14B-AWQ", "ada"),
    "munshi_4b": ("Qwen/Qwen3-4B", "laptop"),
    "extractor_4b": ("Qwen/Qwen3-4B", "laptop"),
    "fallback_8b": ("Qwen/Qwen3-8B", "laptop"),
    "teacher": ("Qwen/Qwen3-32B-AWQ", "ada"),
    "eval_labeler": ("meta-llama/Llama-3.1-8B-Instruct", "laptop"),
}


@pytest.mark.parametrize(("role", "expected"), LLM_ROLES.items())
def test_llm_roles_have_plan_models_and_locations(load_yaml, role, expected):
    """Every LLM role of plan §12 maps to its model and runs where the plan puts it (agents on Ada, local ones on the laptop)."""
    spec = load_yaml("models.yaml")["llm"][role]
    assert (spec["model"], spec["where"]) == expected


def test_llm_roles_are_exactly_the_plan_roles(load_yaml):
    """No LLM role beyond the six of plan §12 (agents, Munshi, extractor, demo fallback, teacher, labeler)."""
    assert set(load_yaml("models.yaml")["llm"]) == set(LLM_ROLES)


def test_extractor_is_the_adapter_on_the_munshi_weights(load_yaml):
    """The extractor is Qwen3-4B plus a QLoRA adapter; Munshi is the same weights with the adapter off (plan §12)."""
    llm = load_yaml("models.yaml")["llm"]
    assert llm["extractor_4b"]["model"] == llm["munshi_4b"]["model"]
    assert llm["extractor_4b"]["adapter"]
    assert llm["munshi_4b"]["adapter"] is None
    assert llm["extractor_4b"]["quant"] == llm["munshi_4b"]["quant"] == "int4"


def test_agents_14b_serves_the_four_ada_agents(load_yaml):
    """Sutradhar, Vakeel, Abhiyojak and Pairokar use Qwen3-14B on vLLM; Munshi and Peshkar use the local 4B (plan §3.2)."""
    llm = load_yaml("models.yaml")["llm"]
    assert llm["agents_14b"]["runtime"] == "vllm"
    assert sorted(llm["agents_14b"]["used_by"]) == ["abhiyojak", "pairokar", "sutradhar", "vakeel"]
    assert llm["munshi_4b"]["used_by"] == ["munshi"]
    assert llm["extractor_4b"]["used_by"] == ["peshkar"]


def test_teacher_and_labeler_are_different_families(load_yaml):
    """Teacher is Qwen and the labeler is Llama: different families so Qwen output is never both teacher and judge (plan §17, §15.1)."""
    llm = load_yaml("models.yaml")["llm"]
    assert family(llm["teacher"]["model"]) == "qwen"
    assert family(llm["eval_labeler"]["model"]) == "llama"
    assert family(llm["teacher"]["model"]) != family(llm["eval_labeler"]["model"])


def test_labeler_is_never_used_by_the_system(load_yaml):
    """eval_labeler is flagged system_use false and appears in no agent's used_by list."""
    llm = load_yaml("models.yaml")["llm"]
    assert llm["eval_labeler"]["system_use"] is False
    for role, spec in llm.items():
        assert "eval_labeler" not in spec.get("used_by", []), role
    assert "labeler" not in {u for spec in llm.values() for u in spec.get("used_by", [])}


def test_teacher_uses_public_orders_only_and_has_an_api_alternative(load_yaml):
    """The teacher sees public orders only; the alternative is a Mistral API model (plan §12, §17)."""
    teacher = load_yaml("models.yaml")["llm"]["teacher"]
    assert teacher["public_orders_only"] is True
    assert teacher["api_alternative"].startswith("mistral")


def test_vision_models_match_plan(load_yaml):
    """Vision: Qwen3-VL-4B on the laptop, Qwen3-VL-8B on Ada for evaluation, Qwen2.5-VL-7B as alternative (plan §12)."""
    v = load_yaml("models.yaml")["vision"]
    assert v["default"]["model"] == "Qwen/Qwen3-VL-4B-Instruct" and v["default"]["where"] == "laptop"
    assert v["ada_eval"]["model"] == "Qwen/Qwen3-VL-8B-Instruct" and v["ada_eval"]["where"] == "ada"
    assert v["alternative"]["model"] == "Qwen/Qwen2.5-VL-7B-Instruct"


def test_non_llm_components_match_plan(load_yaml):
    """OCR, layout, translation, ASR, embeddings, NLI and privacy components of plan §12."""
    m = load_yaml("models.yaml")
    assert m["ocr"]["primary"].startswith("surya") and m["ocr"]["fallback"].startswith("tesseract")
    assert m["ocr"]["layout"] == "docling"
    assert "indictrans2" in m["translation"]["model"].lower() and m["translation"]["direction"] == "hi-en"
    assert set(m["asr"]["candidates"]) == {"openai/whisper-large-v3-turbo", "ai4bharat/indic-conformer"}
    assert m["embeddings"]["model"] == "BAAI/bge-m3" and m["embeddings"]["where"] == "laptop"
    assert "deberta-v3" in m["nli"]["system"] and m["nli"]["evaluation_only"] == "MiniCheck"
    assert m["privacy"] == {"pii": "presidio", "legal_ner": "InLegalNER"}


def test_test_construction_models_are_separate(load_yaml):
    """NLLB (en->hi) and Indic Parler-TTS are listed under test_construction_only, not under the system's roles (plan §12)."""
    cfg = load_yaml("models.yaml")
    assert "nllb" in cfg["test_construction_only"]["translation_en_hi"].lower()
    assert "parler" in cfg["test_construction_only"]["tts"].lower()
    assert "test_construction_only" not in cfg["llm"]


# ----------------------------------------------------------------------------------------------------------------
# tools.yaml (agents only; tool-level consistency lives in tests/unit/tools)
# ----------------------------------------------------------------------------------------------------------------
def test_tools_yaml_agents_are_exactly_the_six(load_yaml):
    """tools.yaml has one list per agent and exactly the six agents of plan §3.2."""
    assert set(load_yaml("tools.yaml")) == {a.value.lower() for a in AgentName}
    assert len(load_yaml("tools.yaml")) == 6


def test_tools_yaml_lists_are_nonempty_and_unique(load_yaml):
    """Every agent has at least one tool and no tool is listed twice for the same agent."""
    for agent, tools in load_yaml("tools.yaml").items():
        assert tools, agent
        assert len(tools) == len(set(tools)), agent


# ----------------------------------------------------------------------------------------------------------------
# thresholds.yaml, budgets.yaml, paths.yaml
# ----------------------------------------------------------------------------------------------------------------
def test_text_layer_word_share_is_85_percent(load_yaml):
    """A page has a good text layer when >=85% of its words are in word lists (plan §4.2 step 1)."""
    assert load_yaml("thresholds.yaml")["ingestion"]["text_layer_word_share"] == 0.85


def test_tunable_thresholds_are_declared_and_open(load_yaml):
    """Thresholds tuned on dev exist as keys and are null until tuned (plan §2, §4.2)."""
    t = load_yaml("thresholds.yaml")
    for key in ("text_coverage_min", "ocr_conf_min", "dict_word_share_min", "script_consistency_min",
                "chars_per_area_min", "vision_escalation_conf", "doc_type_conf_min", "boundary_sensitivity"):
        assert key in t["ingestion"], key
    for key in ("fact_support_min", "authority_support_min", "span_check_min"):
        assert key in t["nli"], key
    assert set(t["retrieval"]["authority_weights"]) == {"court_level", "bench_size", "citations", "recency"}


def test_retrieval_and_safety_thresholds(load_yaml):
    """k=10 reasoning hits (plan §6.3 example) and at most 3 questions per round (plan §4.3)."""
    t = load_yaml("thresholds.yaml")
    assert t["retrieval"]["top_k_reasoning"] == 10
    assert t["safety"]["max_questions_per_round"] == 3


def test_budgets_yaml_matches_plan(load_yaml):
    """Budgets: 150K tokens/case, 8 store calls and 12K tokens per factor, 3 questions, 2 repair rounds, 2 sparring rounds, 2 objections (plan §4.3, §6.2, §8.1, §9)."""
    b = load_yaml("budgets.yaml")
    assert b["case"]["tokens"] == 150000
    assert b["factor"] == {"store_calls": 8, "tokens": 12000}
    assert b["questions_per_round"] == 3
    assert b["repair_rounds"] == 2
    assert b["sparring"] == {"rounds": 2, "objections_per_ground": 2}
    assert b["ui"]["log_budget_hits"] is True and b["ui"]["show_spend"] is True


def test_safety_question_limit_agrees_with_budget_question_limit(load_yaml):
    """thresholds.safety.max_questions_per_round and budgets.questions_per_round are the same number."""
    assert load_yaml("thresholds.yaml")["safety"]["max_questions_per_round"] == load_yaml("budgets.yaml")[
        "questions_per_round"]


def test_paths_keep_client_files_on_the_laptop(load_yaml):
    """Case files live under data/cases and are marked laptop-only; model weights are loaded from node scratch on Ada (plan §3.1, §17)."""
    p = load_yaml("paths.yaml")
    assert p["cases"].startswith("data/cases")
    assert "/scratch/" in p["ada"]["scratch"]
    raw = open(__import__("pathlib").Path(__file__).resolve().parents[3] / "configs" / "paths.yaml").read()
    assert "NEVER leave the laptop" in raw


# ----------------------------------------------------------------------------------------------------------------
# splits.yaml (plan §2)
# ----------------------------------------------------------------------------------------------------------------
def test_splits_dates_match_plan(load_yaml):
    """Train before 2024; dev is 50 orders from early 2024; test is 200 orders from mid-2024 to 2025 with >=60 BNS-era (plan §2)."""
    s = load_yaml("splits.yaml")
    assert _as_date(s["train"]["before"]) == dt.date(2024, 1, 1)
    assert _as_date(s["dev"]["from"]) == dt.date(2024, 1, 1)
    assert _as_date(s["dev"]["to"]) <= dt.date(2024, 6, 30)  # "early 2024"
    assert s["dev"]["n"] == 50
    assert _as_date(s["test"]["from"]) >= dt.date(2024, 5, 1)  # "mid-2024"
    assert _as_date(s["test"]["to"]) == dt.date(2025, 12, 31)
    assert s["test"]["n"] == 200
    assert s["test"]["min_bns_era"] == 60


def test_splits_do_not_overlap(load_yaml):
    """train < dev < test in time, so date splits prevent leakage (plan §2)."""
    s = load_yaml("splits.yaml")
    assert _as_date(s["train"]["before"]) <= _as_date(s["dev"]["from"])
    assert _as_date(s["dev"]["to"]) <= _as_date(s["test"]["from"])


def test_bns_era_starts_on_1_july_2024_and_falls_inside_the_test_window(load_yaml):
    """BNS-era means offence on or after 1 July 2024 (plan §2); test window contains that date."""
    s = load_yaml("splits.yaml")
    era = _as_date(s["bns_era_offence_on_or_after"])
    assert era == dt.date(2024, 7, 1)
    assert _as_date(s["test"]["from"]) <= era <= _as_date(s["test"]["to"])
    assert s["test"]["min_bns_era"] <= s["test"]["n"]


def test_contamination_cutoff_is_qwen3_release(load_yaml):
    """Results are reported separately for test orders dated after Qwen3's April 2025 release (plan §15.9)."""
    assert _as_date(load_yaml("splits.yaml")["qwen3_release_for_contamination_report"]) == dt.date(2025, 4, 1)


# ----------------------------------------------------------------------------------------------------------------
# rights_rules.yaml (plan §7.3, Appendix C)
# ----------------------------------------------------------------------------------------------------------------
PLAN_STATUSES = {
    "default_bail": ["ELIGIBLE", "NOT_YET", "WINDOW_CLOSED", "CHECK"],
    "undertrial_limit": ["ELIGIBLE", "NOT_YET", "NOT_APPLICABLE", "CHECK"],
    "notice_of_appearance": ["FLAG", "OK", "UNKNOWN"],
    "grounds_of_arrest": ["FLAG", "OK", "UNKNOWN", "CHECK"],
    "production_24h": ["FLAG", "OK", "CHECK"],
    "antil_category": ["A", "B", "C", "D", "CHECK"],
    "statutory_bar": ["BAR_APPLIES", "NOT_APPLICABLE"],
}


def test_rights_rules_yaml_has_the_seven_checks_in_plan_order(load_yaml):
    """Seven checks, in the order of the plan §7.3 table."""
    assert list(load_yaml("rights_rules.yaml")) == list(PLAN_STATUSES)


@pytest.mark.parametrize(("check", "statuses"), PLAN_STATUSES.items())
def test_rights_rules_statuses_match_plan_table(load_yaml, check, statuses):
    """Each check's status list equals the 'Possible outputs' column of plan §7.3."""
    assert load_yaml("rights_rules.yaml")[check]["statuses"] == statuses


@pytest.mark.parametrize("check", PLAN_STATUSES)
def test_rights_rules_have_rule_text_sources_and_last_verified_slot(load_yaml, check):
    """Each rule carries rule text, at least one source and a 'last_verified' slot (null until the week-0 check, plan §7.3)."""
    spec = load_yaml("rights_rules.yaml")[check]
    assert spec["rule"].strip() and spec["sources"]
    assert "last_verified" in spec


def test_rights_rules_statuses_are_valid_rights_status_values(load_yaml):
    """Every status named in rights_rules.yaml is a RightsStatus member."""
    from vakeel_sahayak.schemas.enums import RightsStatus

    valid = {s.value for s in RightsStatus}
    for check, spec in load_yaml("rights_rules.yaml").items():
        assert set(spec["statuses"]) <= valid, check


def _rule_classes():
    from vakeel_sahayak.rights.rules.antil_category import AntilCategoryRule
    from vakeel_sahayak.rights.rules.default_bail import DefaultBailRule
    from vakeel_sahayak.rights.rules.grounds_of_arrest import GroundsOfArrestRule
    from vakeel_sahayak.rights.rules.notice_of_appearance import NoticeOfAppearanceRule
    from vakeel_sahayak.rights.rules.production_24h import Production24hRule
    from vakeel_sahayak.rights.rules.statutory_bar import StatutoryBarRule
    from vakeel_sahayak.rights.rules.undertrial_limit import UndertrialLimitRule

    return [DefaultBailRule, UndertrialLimitRule, NoticeOfAppearanceRule, GroundsOfArrestRule, Production24hRule,
            AntilCategoryRule, StatutoryBarRule]


def test_there_is_one_rule_class_per_check():
    """Seven Rule classes, rule_ids covering the seven RightsCheckName values exactly once."""
    from vakeel_sahayak.schemas.enums import RightsCheckName

    ids = [c.rule_id for c in _rule_classes()]
    assert sorted(i.value for i in ids) == sorted(n.value for n in RightsCheckName)
    assert len(set(ids)) == 7


@pytest.mark.parametrize("rule_cls", _rule_classes(), ids=lambda c: c.__name__)
def test_rule_class_attributes_agree_with_yaml(load_yaml, rule_cls):
    """rule_id, allowed_statuses and sources of the Rule class equal rights_rules.yaml (modulo source-list wording of the same citations)."""
    spec = load_yaml("rights_rules.yaml")[rule_cls.rule_id.value]
    assert [s.value for s in rule_cls.allowed_statuses] == spec["statuses"]
    assert rule_cls.rule_text.strip()
    assert len(rule_cls.sources) == len(spec["sources"])
    # first token of each source (statute number or case name stem) is the same citation in both places
    for cls_src, yaml_src in zip(rule_cls.sources, spec["sources"], strict=True):
        assert cls_src.split(" (")[0].split(" v. ")[0] == yaml_src.split(" (")[0].split(" v. ")[0], (cls_src, yaml_src)


@pytest.mark.parametrize("rule_cls", _rule_classes(), ids=lambda c: c.__name__)
def test_rule_last_verified_is_unset_until_week_0(load_yaml, rule_cls):
    """last_verified is None in both the class and the YAML until the week-0 check against the bare act sets it (plan §7.3)."""
    assert rule_cls.last_verified is None
    assert load_yaml("rights_rules.yaml")[rule_cls.rule_id.value]["last_verified"] is None


@pytest.mark.parametrize(
    ("check", "needle"),
    [
        ("default_bail", "BNSS s.187(3)"),
        ("undertrial_limit", "BNSS s.479"),
        ("notice_of_appearance", "BNSS s.35(3)"),
        ("grounds_of_arrest", "BNSS s.47"),
        ("production_24h", "BNSS s.58"),
        ("antil_category", "Satender Kumar Antil"),
        ("statutory_bar", "NDPS s.37"),
    ],
)
def test_rule_sources_cite_the_appendix_c_provision(load_yaml, check, needle):
    """Each rule's sources name the Appendix C provision or judgment."""
    assert any(needle in s for s in load_yaml("rights_rules.yaml")[check]["sources"])


def test_statutory_bar_sources_name_all_three_acts(load_yaml):
    """Statutory bar cites NDPS s.37, UAPA s.43D(5) and PMLA s.45 (Appendix C)."""
    sources = load_yaml("rights_rules.yaml")["statutory_bar"]["sources"]
    assert sources == ["NDPS s.37", "UAPA s.43D(5)", "PMLA s.45"]


def test_default_bail_rule_text_states_60_90_and_day_one_counting(load_yaml):
    """Default-bail rule text states 90 and 60 days, first remand as day 1, and CHECK for 'may extend to ten years' (Appendix C)."""
    text = load_yaml("rights_rules.yaml")["default_bail"]["rule"]
    assert "90 days" in text and "60 days" in text and "day 1 = first remand" in text and "CHECK" in text


# ----------------------------------------------------------------------------------------------------------------
# bail_sections.yaml (plan §2)
# ----------------------------------------------------------------------------------------------------------------
def test_bail_sections_has_ten_rows(load_yaml):
    """The CrPC to BNSS table has ten rows (plan §2)."""
    assert len(load_yaml("bail_sections.yaml")["rows"]) == 10


@pytest.mark.parametrize(
    ("crpc", "bnss"),
    [("436", "478"), ("436A", "479"), ("437", "480"), ("438", "482"), ("439", "483")],
)
def test_named_crpc_to_bnss_pairs(load_yaml, crpc, bnss):
    """CrPC 436/436A/437/438/439 map to BNSS 478/479/480/482/483 (plan §2)."""
    rows = {str(r["crpc"]): str(r["bnss"]) for r in load_yaml("bail_sections.yaml")["rows"]}
    assert rows[crpc] == bnss


@pytest.mark.parametrize(
    ("crpc", "bnss"),
    [("167(2)", "187(3)"), ("41A", "35(3)"), ("50", "47"), ("57", "58")],
)
def test_rows_backing_the_rights_radar_agree_with_appendix_c(load_yaml, crpc, bnss):
    """The remaining Rights-Radar rows (default bail, notice, grounds, 24h production) match Appendix C's CrPC/BNSS pairs."""
    rows = {str(r["crpc"]): str(r["bnss"]) for r in load_yaml("bail_sections.yaml")["rows"]}
    assert rows[crpc] == bnss


def test_bail_sections_rows_are_unique_and_documented(load_yaml):
    """No duplicate CrPC or BNSS reference and every row has a topic."""
    rows = load_yaml("bail_sections.yaml")["rows"]
    assert len({str(r["crpc"]) for r in rows}) == 10
    assert len({str(r["bnss"]) for r in rows}) == 10
    assert all(r["topic"].strip() for r in rows)
