"""Ablation and variant switches (plan §15.4 A1-A10, §15.5 P5-P6, §19 fixed-router fallback). Defaults are the full system.

One typed object carries every variant, so an ablation is a flag the agents read, never a code fork. Build the switches
of a named variant with `Switches.for_variant('A9')` (or `'A10'` with `knockout_store=...`, `'A5'` with
`extractor=...`); `Switches().variant()` names the variant a switch set implements.

| Id | Switch | Who reads it |
|---|---|---|
| A1 | `no_dossier` | Sutradhar and Vakeel read the raw facts instead of the dossier |
| A2 | `no_check_repair` | Vakeel skips check-and-repair (sparring stays on) |
| A3 | `no_tools` | `map_section`, `transfer_check`, `date_calc`, `rights_check` refused in `call_tool`; the LLM judges itself |
| A4 | `plain_retrieval` | Sutradhar drops section family, part and factor filters and the transfer flag |
| A5 | `extractor` | Peshkar's model role (`extractor_role()`): fine-tuned 4B, base 4B, or prompted 32B |
| A6 | `fixed_router` | contracts in a fixed order with fixed queries; no planning or sufficiency check (also the loop fallback) |
| A7 | `free_planner` | the LLM plans with no evidence contracts (`fixed_router` wins if both are set) |
| A8 | `no_sparring` | Abhiyojak is skipped (check-and-repair stays on) |
| A9 | `no_sparring` + `no_check_repair` | completes the 2x2 with Full, A2, A8 |
| A10 | `knockout_store` | that store is refused in `call_tool`; retrieval and slot fill only, no drafting |
| P5, P6 | `munshi_no_gap_check`, `munshi_no_bundle_split` | Munshi |

Literature-derived architecture variants (`docs/evaluation-plan.md` section 3.3, `docs/literature-to-code-map.md`); every default is the
current behaviour, so the full system is unchanged:

| Id | Switch | Who reads it |
|---|---|---|
| S1 | `retrieval_policy='self_critique'` | Sutradhar: a prompted critic judges the retrieved paragraphs (relevant / supported) and picks the corrective re-retrieval; replaces `assess_slot` for corpus slots |
| S2 | `retrieval_policy='adaptive'` | Sutradhar: per-factor retrieval depth (none / single-step / multi-step) from rule features; caps rounds and store calls |
| S4 | `weak_signal='skew'` | slot assessment: Gini / top-gap of the hybrid scores of a corpus search flag a flat list as weak (FILLED -> WEAK) and cue a filter relaxation |
| S5 (A16) | `graph_expansion=True` | `search_reasoning(expand_graph=True)` for authority slots: personalised PageRank over the citation graph from the plain hits (HippoRAG 2 style), re-ranked by text plus walk score |
| S3 (A11b) | `stopping='rules_llm'` or `'llm'` | Sutradhar's re-plan: a prompted sufficiency rater second-guesses (or replaces) the rule-based stop |

EV-01 (evaluation plan 3.3 and 3.4): the switches below were DEFINED here first (fields, validation, names) and their behaviour was built by
the variant tasks; today every id of the table is implemented. `Switches.implemented_variants()` lists the ids that do something and `assert_variant_implemented(name)`
makes the evaluation runners fail loudly on an id that is declared but not built. Every default is the current behaviour, so `Switches().variant() == 'full'`.

| Id (aliases) | Switch | Who reads it |
|---|---|---|
| S6 (A12) | `store_prior='order'` | learned store prior orders calls inside a contract |
| B5 (S6b) | `store_prior='only'` | learned store router replaces contracts |
| S7 (A11a) | `munshi_gap_policy='hierarchy'` | Munshi gap re-reading ranked by document structure (default 'sequential') |
| S8 (A2b) | `repair_mode='self_critique'` | Vakeel repairs from its own re-read, no outside verifier ('none' is A2 / `no_check_repair`) |
| S9 (A8b) | `critic_mode='sampling'` | k-sample critic at equal tokens ('none' is A8 / `no_sparring`) |
| S10 (A8c) | `abhiyojak_isolation=False` | Abhiyojak sees Vakeel's notes |
| S11 (A8d), S11b, S11c | `critic_mode='three_role'`; `draft_mode='debate'`; `draft_mode='vote'` | three-role review; two-instance debate; three-sample vote |
| S12, S12b | `topology='sequential'`; `'single_agent'` | orchestration graph |
| S13 | any grid of the switches above | the workflow-search driver (no single arm) |
| S14 (A14), S14b, S14c | `plan_cache=True`; `urgency_policy='fifo'`; `'urgency_least_work'` (also `'shortest_first'`, a baseline with no variant id) | batch cache and scheduler |
| S14d | `prefix_layout=True` | prompt layout (`models/prompting.render_prompt(prefix_friendly=)`); not named in the plan, added with sweep 3 |
| S15 (A13), S15b | `output_format='reasoning_first'`; `'free_then_parse'` ('answer_only' is the current behaviour) | Vakeel's schemas (S15); `orchestration/structured_output.output_format` (S15b: no decoding constraint, free text then parse) |
| S16, S16b | `chunking='proposition'`; `'late'` ('structure' is the current chunker) | chunking variants (retrieval-only runner) |
| S17 (A15), S17b, S17c, S17d | `no_typed_handoff`; `no_spotlighting`; `no_guard`; all three | injection defences |
| P7 | `munshi_image_only=True` | ingestion: page images straight to the vision model |

Two opt-in switches added after the evaluation plan (ids S18 and P8 are given here; docs/literature-to-code-map.md, Sweep 4): `authority_stance='outcome'` (S18) (Vakeel prefers authorities from orders that granted
bail and marks the ones that refused it as adverse authority to distinguish; Wachsmuth et al., ACL 2018) and `munshi_keep_weak_text=True` (P8: a text layer with
60-84% dictionary words is kept as a low-confidence read, flagged to counsel, instead of dropping to ask-counsel).

Id numbering: this module and `docs/evaluation-plan.md` use the plan's S-ids. The literature review numbers the same ideas differently
(its S2 = plan S5 graph retrieval, its R1 = plan S3 stopping, its R2 = plan S4 skew signal); `docs/literature-to-code-map.md` names both.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

# A3: the legal-rule tools the LLM must do without ("maps sections, counts days and judges rights itself").
RULE_TOOLS: tuple[str, ...] = ("map_section", "transfer_check", "date_calc", "rights_check")
EXTRACTOR_ROLES: dict[str, str] = {"finetuned_4b": "extractor_4b", "base_4b": "munshi_4b", "prompted_32b": "teacher"}

ABLATIONS: dict[str, dict[str, Any]] = {
    "A1": {"no_dossier": True},
    "A2": {"no_check_repair": True},
    "A3": {"no_tools": True},
    "A4": {"plain_retrieval": True},
    "A5": {},  # pass extractor='base_4b' or 'prompted_32b'
    "A6": {"fixed_router": True},
    "A7": {"free_planner": True},
    "A8": {"no_sparring": True},
    "A9": {"no_sparring": True, "no_check_repair": True},
    "A10": {},  # pass knockout_store='<store>'
}
# Architecture variants of evaluation plan 3.3. S3 has two arms: "S3" (rules, then an LLM rater) and "S3b" (the LLM rater alone).
# Papers: S3 = Sufficient Context (Joren et al., ICLR 2025), AutoSearch (Findings of ACL 2026), Stop-RAG (NeurIPS 2025 workshop).
# S-numbering: the evaluation plan's. The literature review uses other ids for the same ideas (its S2 = plan S5, R1 = S3, R2 = S4).
# EV-01 declared every S-id of the plan as a switch set; all of them are built now (see IMPLEMENTED_VARIANTS, which `assert_variant_implemented` reads).
ARCHITECTURE: dict[str, dict[str, Any]] = {
    "S1": {"retrieval_policy": "self_critique"},
    "S2": {"retrieval_policy": "adaptive"},
    "S3": {"stopping": "rules_llm"},
    "S3b": {"stopping": "llm"},
    "S4": {"weak_signal": "skew"},
    "S5": {"graph_expansion": True},
    "S6": {"store_prior": "order"},
    "S7": {"munshi_gap_policy": "hierarchy"},
    "S8": {"repair_mode": "self_critique"},
    "S9": {"critic_mode": "sampling"},
    "S10": {"abhiyojak_isolation": False},
    "S11": {"critic_mode": "three_role"},
    "S11b": {"draft_mode": "debate"},
    "S11c": {"draft_mode": "vote"},
    "S12": {"topology": "sequential"},
    "S12b": {"topology": "single_agent"},
    "S13": {},  # a searched grid of the other switches: pass the grid point as fields
    "S14": {"plan_cache": True},
    "S14b": {"urgency_policy": "fifo"},
    "S14c": {"urgency_policy": "urgency_least_work"},
    "S14d": {"prefix_layout": True},
    "S15": {"output_format": "reasoning_first"},
    "S15b": {"output_format": "free_then_parse"},
    "S16": {"chunking": "proposition"},
    "S16b": {"chunking": "late"},
    "S17": {"no_typed_handoff": True},
    "S17b": {"no_spotlighting": True},
    "S17c": {"no_guard": True},
    "S17d": {"no_typed_handoff": True, "no_spotlighting": True, "no_guard": True},
    "S18": {"authority_stance": "outcome"},  # sweep 4: not in the evaluation plan; id added here
}
# The evaluation plan's ablation and baseline ids for the variants above (the canonical name is the S-id).
VARIANT_ALIASES: dict[str, str] = {
    "A11B": "S3", "A11A": "S7", "A12": "S6", "S6B": "B5", "A16": "S5", "A2B": "S8", "A8B": "S9", "A8C": "S10", "A8D": "S11",
    "A13": "S15", "A14": "S14", "A15": "S17",
}
INGESTION: dict[str, dict[str, Any]] = {
    "P5": {"munshi_no_gap_check": True}, "P6": {"munshi_no_bundle_split": True}, "P7": {"munshi_image_only": True},
    "P8": {"munshi_keep_weak_text": True},  # sweep 4: not in the evaluation plan; id added here
}
BASELINE_SWITCHES: dict[str, dict[str, Any]] = {"B5": {"store_prior": "only"}}  # learned store router, no contracts
# Ids whose behaviour exists today: full, A1-A10, S1-S18 including S3b, S11b, S11c, S12b, S14b-S14d, S15b, S16b, S17b-S17d, B5 and P5-P8 (S13 as the search harness, S14b, S14c, S16, S16b as studies and
# scheduler/chunking switches read outside the per-case pipeline: `eval/runners/systems.SCOPES` says which). No id of the variant table is declared but unbuilt today; an id added to the
# table and left out of this set is refused by `assert_variant_implemented` until its behaviour exists.
IMPLEMENTED_VARIANTS: frozenset[str] = frozenset({"full", *ABLATIONS, "S1", "S2", "S3", "S3b", "S4", "S5", "S6", "B5", "S12", "S12b", "S13", "S16", "S16b", "S8", "S9", "S10", "S11", "S11b", "S11c", "S7", "S14", "S14b", "S14c", "S14d", "S15", "S15b", "S17", "S17b", "S17c", "S17d", "S18", "P5", "P6", "P7", "P8"})
VARIANT_DESCRIPTIONS: dict[str, str] = {
    "full": "Munshi -> Peshkar -> Sutradhar, with Vakeel, Abhiyojak and all checks",
    "A1": "no dossier: Sutradhar and Vakeel read the raw facts",
    "A2": "no check-and-repair (sparring on)",
    "A3": "no tools: the LLM maps sections, counts days and judges rights itself",
    "A4": "plain retrieval: no section family, no part or factor filters, no transfer flag",
    "A5": "extractor variant: fine-tuned 4B vs base 4B vs prompted 32B",
    "A6": "fixed router: contracts in a fixed order with fixed queries; no planning or sufficiency check",
    "A7": "free planner: the LLM plans with no evidence contracts",
    "A8": "no sparring (check-and-repair on)",
    "A9": "neither sparring nor check-and-repair",
    "A10": "store knock-out: one store removed; retrieval and slot-fill only",
    "S3": "sufficiency stopping: rules first, then an LLM rater may veto the stop (Sufficient Context)",
    "S3b": "sufficiency stopping: the LLM rater alone decides when to stop",
    "S1": "retrieval critique (Self-RAG / CRAG style): a prompted critic judges the paragraphs and picks the corrective re-retrieval",
    "S2": "adaptive retrieval depth per factor (none, single-step, iterative) from rule features",
    "S4": "score-skew weak-evidence signal (Gini and top-gap of the fused scores)",
    "S5": "citation-graph expansion of the retrieved paragraphs (HippoRAG 2 style personalised PageRank)",
    "S6": "learned store prior orders the calls inside a contract",
    "S7": "Munshi hierarchy-ranked gap re-reading (IntrAgent style)",
    "S8": "Vakeel self-critique repair: no outside verifier",
    "S9": "sampling-only critic at equal tokens instead of Abhiyojak",
    "S10": "Abhiyojak without context isolation",
    "S11": "three-role review (grader, critic, defender) instead of Abhiyojak",
    "S11b": "two-instance Vakeel debate for two rounds",
    "S11c": "three-sample Vakeel vote",
    "S12": "sequential factors in one growing context",
    "S12b": "single agent: Vakeel does its own retrieval and drafting",
    "S13": "automatically searched workflow (a grid point of the other switches)",
    "S14": "plan-template cache for batch runs",
    "S14b": "batch scheduling first come first served",
    "S14c": "batch scheduling urgency first with a least-work-done tie-break",
    "S14d": "prefix-friendly prompt layout (shared text first, per-case text last) so serving-layer prefix caches hit across cases",
    "S15": "reasoning field before the constrained answer fields",
    "S15b": "free text then parse",
    "S16": "proposition-unit chunking",
    "S16b": "late chunking",
    "S17": "injection defence off: no typed hand-off",
    "S17b": "injection defence off: no spotlighting",
    "S17c": "injection defence off: no guard",
    "S17d": "all three injection defences off",
    "S18": "authority stance: Vakeel prefers authorities from orders that granted bail and marks refusals as adverse authority to distinguish",
    "B5": "learned store router alone: no evidence contracts",
    "P5": "Munshi fixed cascade: no gap check, no re-reading, no questions",
    "P6": "Munshi without bundle splitting and document labelling",
    "P7": "image-only ingestion: page images go straight to the vision model, no OCR text",
    "P8": "Munshi keeps a 60-84% dictionary-word text layer as a low-confidence read instead of asking counsel",
}


class Switches(BaseModel):
    """Booleans toggled by eval runs."""

    model_config = ConfigDict(extra="forbid")

    no_dossier: bool = False  # A1
    no_check_repair: bool = False  # A2
    no_tools: bool = False  # A3
    plain_retrieval: bool = False  # A4: no section family, no part/factor filters, no transfer flag
    fixed_router: bool = False  # A6 (also the default fallback if the orchestrator loops)
    free_planner: bool = False  # A7: no evidence contracts
    no_sparring: bool = False  # A8
    munshi_no_gap_check: bool = False  # P5
    munshi_no_bundle_split: bool = False  # P6
    knockout_store: str | None = None  # A10
    extractor: Literal["finetuned_4b", "base_4b", "prompted_32b"] = "finetuned_4b"  # A5
    # S3 (A11b), Sufficient Context (Joren et al., ICLR 2025) / AutoSearch / Stop-RAG: who decides that a factor has enough evidence
    stopping: Literal["rules", "rules_llm", "llm"] = "rules"
    # EV-01 (evaluation plan 3.4): fields only; behaviour comes with the variant implementations. Defaults are the current behaviour.
    retrieval_policy: Literal["contract", "self_critique", "adaptive"] = "contract"  # S1, S2
    weak_signal: Literal["rules", "skew"] = "rules"  # S4
    graph_expansion: bool = False  # S5 (A16)
    store_prior: Literal["off", "order", "only"] = "off"  # S6 (A12), B5
    munshi_gap_policy: Literal["hierarchy", "sequential"] = "sequential"  # S7 (A11a); 'sequential' is today's re-read order
    repair_mode: Literal["grounded", "self_critique", "none"] = "grounded"  # S8 (A2b); 'none' is no_check_repair
    critic_mode: Literal["abhiyojak", "sampling", "three_role", "none"] = "abhiyojak"  # S9, S11 (A8b, A8d); 'none' is no_sparring
    abhiyojak_isolation: bool = True  # S10 (A8c)
    draft_mode: Literal["single", "debate", "vote"] = "single"  # S11
    topology: Literal["orchestrated", "sequential", "single_agent"] = "orchestrated"  # S12
    plan_cache: bool = False  # S14 (A14)
    urgency_policy: Literal["fifo", "urgency", "urgency_least_work", "shortest_first"] = "urgency"  # S14; 'urgency' is the current scheduler; 'shortest_first' is a baseline with no named variant id
    prefix_layout: bool = False  # S14d: prompts put the shared text first (corpus, then case; keys in a fixed order)
    output_format: Literal["reasoning_first", "answer_only", "free_then_parse"] = "answer_only"  # S15 (A13); today's schemas are answer-only
    no_typed_handoff: bool = False  # S17 (A15) defence flags
    no_spotlighting: bool = False
    no_guard: bool = False
    munshi_image_only: bool = False  # P7
    # S18 (not in the evaluation plan): Vakeel offers supporting authorities first and marks authorities from orders that refused bail as
    # adverse authority to distinguish (Wachsmuth et al., ACL 2018, counter-argument retrieval; agents/vakeel/stance.py). 'off' is today's behaviour.
    authority_stance: Literal["off", "outcome"] = "off"
    munshi_keep_weak_text: bool = False  # P8 (not in the evaluation plan): Munshi keeps a 67-84% dictionary-word text layer as a low-confidence read (agents/munshi, ingestion/pipeline.py)
    chunking: Literal["structure", "proposition", "late", "fixed", "recursive", "semantic", "page"] = "structure"  # S16 (not named in plan 3.4: the chunker of the retrieval-only runner)

    @model_validator(mode="after")
    def _variants_need_the_planner(self) -> Switches:
        """A6 has no sufficiency check and A7 no contracts, so the planner variants have nothing to change there."""
        if self.stopping != "rules" and (self.fixed_router or self.free_planner):
            raise ValueError("stopping variants (S3) modify Sutradhar's planned loop: they cannot combine with fixed_router (A6) or free_planner (A7)")
        if self.retrieval_policy != "contract" and (self.fixed_router or self.free_planner):
            raise ValueError("retrieval_policy variants (S1, S2) replace the contract-driven plan: they cannot combine with fixed_router (A6) or free_planner (A7)")
        if self.weak_signal != "rules" and self.fixed_router:
            raise ValueError("weak_signal='skew' (S4) feeds the sufficiency check: it cannot combine with fixed_router (A6), which has none")
        if self.store_prior != "off" and self.fixed_router:
            raise ValueError("store_prior (S6, B5) orders or picks stores: it cannot combine with fixed_router (A6), whose order is fixed")
        if self.store_prior == "order" and self.free_planner:
            raise ValueError("store_prior='order' (S6) orders calls inside a contract: it cannot combine with free_planner (A7), which has no contracts")
        if self.store_prior == "only":
            planner = [n for n, on in {"stopping": self.stopping != "rules", "retrieval_policy": self.retrieval_policy != "contract",
                                       "weak_signal": self.weak_signal != "rules", "graph_expansion": self.graph_expansion, "plan_cache": self.plan_cache}.items() if on]
            if planner:  # free_planner (A7) is a legal partner: B5 has no contracts either
                raise ValueError("store_prior='only' (B5) replaces the contracts: it cannot combine with the contract-loop variants " + ", ".join(planner))
        if self.topology == "sequential" and (self.fixed_router or self.free_planner):
            raise ValueError("topology='sequential' (S12) runs Sutradhar's planned loop one factor at a time: it cannot combine with fixed_router (A6) or free_planner (A7)")
        if self.topology == "single_agent":
            planner_switches = [
                name for name, active in {
                    "fixed_router": self.fixed_router, "free_planner": self.free_planner, "stopping": self.stopping != "rules",
                    "retrieval_policy": self.retrieval_policy != "contract", "weak_signal": self.weak_signal != "rules",
                    "store_prior": self.store_prior != "off",
                }.items() if active
            ]
            if planner_switches:
                raise ValueError(f"topology='single_agent' (S12b) merges Sutradhar away: it cannot combine with {', '.join(planner_switches)}")
        if self.munshi_gap_policy == "hierarchy" and self.munshi_no_gap_check:
            raise ValueError("munshi_gap_policy='hierarchy' (S7) is a gap-handling policy: it cannot combine with munshi_no_gap_check (P5)")
        # A2 / A8 are the existing 'none' arms of repair_mode / critic_mode: keep the two spellings consistent
        if self.repair_mode == "self_critique" and self.no_check_repair:
            raise ValueError("repair_mode='self_critique' (S8) repairs: it cannot combine with no_check_repair (A2); use repair_mode='none' or no_check_repair alone")
        if self.repair_mode == "none":
            self.no_check_repair = True
        if self.critic_mode in {"sampling", "three_role"} and self.no_sparring:
            raise ValueError(f"critic_mode={self.critic_mode!r} (S9, S11) is a critic: it cannot combine with no_sparring (A8); use critic_mode='none' or no_sparring alone")
        if self.critic_mode == "none":
            self.no_sparring = True
        if not self.abhiyojak_isolation and self.critic_mode in {"sampling", "three_role"}:
            raise ValueError(f"abhiyojak_isolation=False (S10) changes what Abhiyojak reads: it cannot combine with critic_mode={self.critic_mode!r}, which replaces Abhiyojak")
        if not self.abhiyojak_isolation and self.no_sparring:
            raise ValueError("abhiyojak_isolation=False (S10) widens what Abhiyojak sees: it cannot combine with no_sparring (A8) or critic_mode='none'")
        return self

    # ------------------------------------------------------------------ what the agents ask

    @property
    def check_and_repair(self) -> bool:
        """Vakeel checks and repairs claims (off in A2 and A9)."""
        return not self.no_check_repair

    @property
    def sparring(self) -> bool:
        """Abhiyojak spars (off in A8 and A9)."""
        return not self.no_sparring

    @property
    def uses_dossier(self) -> bool:
        """Sutradhar and Vakeel read the approved dossier (not in A1)."""
        return not self.no_dossier

    @property
    def uses_rule_tools(self) -> bool:
        """The legal-rule tools are available (not in A3)."""
        return not self.no_tools

    @property
    def uses_contracts(self) -> bool:
        """Sutradhar works from evidence contracts (not in A7; the fixed router always uses them)."""
        return self.fixed_router or not self.free_planner

    @property
    def uses_planner(self) -> bool:
        """Sutradhar plans, assesses and re-plans (not in A6)."""
        return not self.fixed_router

    @property
    def retrieval_filters(self) -> bool:
        """Section family, part and factor filters and the transfer flag are used (not in A4)."""
        return not self.plain_retrieval

    @property
    def drafting(self) -> bool:
        """A brief is drafted (A10 measures retrieval and slot fill only)."""
        return self.knockout_store is None

    def tool_allowed(self, tool: str) -> bool:
        """False for a legal-rule tool under A3."""
        return not (self.no_tools and tool in RULE_TOOLS)

    def store_allowed(self, store: Any) -> bool:
        """False for the store knocked out in A10."""
        return self.knockout_store is None or str(getattr(store, "value", store)) != self.knockout_store

    def extractor_role(self) -> str:
        """Peshkar's model role for A5: 'extractor_4b' (fine-tuned), 'munshi_4b' (base 4B) or 'teacher' (prompted 32B)."""
        return EXTRACTOR_ROLES[self.extractor]

    # ------------------------------------------------------------------ naming

    @classmethod
    def for_variant(cls, variant: str, **extra: Any) -> Switches:
        """The switches of a named variant (built even when its behaviour is not implemented: see `assert_variant_implemented`).

        Args:
            variant: 'full', 'A1'..'A10', the S-ids of evaluation plan 3.3 ('S1'..'S17' and their 'b'/'c'/'d' arms), 'B5', 'P5'..'P7',
                or a plan alias (A11a, A11b, A12, A13, A14, A15, A16, A2b, A8b, A8c, A8d, S6b); case-insensitive
            extra: further fields (A10 needs `knockout_store`, A5 an `extractor`, S13 the searched grid point)

        Returns:
            Switches.

        Raises:
            ValueError: unknown variant, A10 without a store, A5 without a non-default extractor, S13 without a grid point,
                or an invalid combination of fields.
        """
        table = _variant_table()
        canonical = {key.upper(): key for key in table}
        wanted = variant.strip().upper()
        name = canonical.get(VARIANT_ALIASES.get(wanted, wanted), variant)
        if name not in table:
            raise ValueError(f"unknown variant {variant!r}: use 'full', A1-A16 (A2b, A8b-A8d, A11a, A11b), S1-S17, B5, P5, P6 or P7")
        if name == "A10" and not extra.get("knockout_store"):
            raise ValueError("A10 needs knockout_store='<store name>'")
        if name == "A5" and extra.get("extractor", "finetuned_4b") == "finetuned_4b":
            raise ValueError("A5 needs extractor='base_4b' or 'prompted_32b' (the fine-tuned 4B is the full system)")
        if name == "S13" and not extra:
            raise ValueError("S13 is a searched grid of the other switches: pass the grid point as fields, e.g. for_variant('S13', stopping='llm')")
        return cls(**{**table[name], **extra})

    def variant(self) -> str:
        """The name of the variant these switches implement ('full', 'A1'..'A10', S-ids, 'B5', 'P5'..'P7', or 'custom')."""
        fields = self.model_dump(exclude_defaults=True)
        if self.no_check_repair and fields.get("repair_mode") == "none":
            del fields["repair_mode"]  # the same arm as no_check_repair alone
        if self.no_sparring and fields.get("critic_mode") == "none":
            del fields["critic_mode"]
        if not fields:
            return "full"
        if set(fields) == {"knockout_store"}:
            return "A10"
        if set(fields) == {"extractor"}:
            return "A5"
        for name, values in _variant_table().items():
            if values and fields == values:
                return name
        return "custom"

    @staticmethod
    def implemented_variants() -> frozenset[str]:
        """Variant ids whose behaviour exists today: every id of the variant table ('full', A1-A10, S1-S18, B5, P5-P8). An id declared in the table and absent here is not built."""
        return IMPLEMENTED_VARIANTS

    def describe(self) -> str:
        """One line for run logs and the UI."""
        name = self.variant()
        return VARIANT_DESCRIPTIONS.get(name, "custom switch set: " + ", ".join(f"{k}={v}" for k, v in self.model_dump(exclude_defaults=True).items()))


def _variant_table() -> dict[str, dict[str, Any]]:
    """Every named variant: the switch values that define it ('full' is empty)."""
    return {"full": {}, **ABLATIONS, **INGESTION, **ARCHITECTURE, **BASELINE_SWITCHES}


def canonical_variant(name: str) -> str:
    """The canonical id of a variant name or plan alias ('a12' -> 'S6', 'A11b' -> 'S3').

    Raises:
        ValueError: unknown variant.
    """
    canonical = {key.upper(): key for key in _variant_table()}
    wanted = name.strip().upper()
    wanted = VARIANT_ALIASES.get(wanted, wanted)
    if wanted not in canonical:
        raise ValueError(f"unknown variant {name!r}")
    return canonical[wanted]


def assert_variant_implemented(name: str) -> None:
    """Fail loudly when an evaluation run selects a variant whose behaviour is not built yet.

    Args:
        name: a variant id or plan alias (case-insensitive).

    Raises:
        NotImplementedError: the variant is defined as a switch set but no agent reads it yet (names the variant and its switches).
        ValueError: unknown variant.
    """
    canonical = canonical_variant(name)
    if canonical not in IMPLEMENTED_VARIANTS:
        raise NotImplementedError(
            f"variant {name!r} ({canonical}: {VARIANT_DESCRIPTIONS.get(canonical, 'searched workflow')}) is not implemented yet: "
            f"its switches {_variant_table()[canonical] or '(grid point)'} exist but no agent reads them; "
            f"implemented today: {', '.join(sorted(IMPLEMENTED_VARIANTS))}"
        )
