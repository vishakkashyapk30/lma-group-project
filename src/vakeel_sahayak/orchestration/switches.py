"""Ablation and variant switches (plan §15.4 A1-A10, §15.3 B0-B4, §15.5 P5-P6, §19 fixed-router fallback). Defaults are the full system.

One typed object carries every variant, so an ablation is a flag the agents read, never a code fork. Build the switches
of a named variant with `Switches.for_variant('A9')` (or `'B4'`, `'A10'` with `knockout_store=...`, `'A5'` with
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
| B0-B4 | `baseline` | the eval baselines (B3 also sets `b3_chunking`); 'full' is the full system |
| P5, P6 | `munshi_no_gap_check`, `munshi_no_bundle_split` | Munshi |
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

# A3: the legal-rule tools the LLM must do without ("maps sections, counts days and judges rights itself").
RULE_TOOLS: tuple[str, ...] = ("map_section", "transfer_check", "date_calc", "rights_check")
EXTRACTOR_ROLES: dict[str, str] = {"finetuned_4b": "extractor_4b", "base_4b": "munshi_4b", "prompted_32b": "teacher"}
Baseline = Literal["full", "B0", "B1", "B2", "B3", "B4"]
ChunkingVariant = Literal["fixed_512", "fixed_512_overlap", "recursive", "semantic", "page"]

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
BASELINES: dict[str, dict[str, Any]] = {
    "B0": {"baseline": "B0"},
    "B1": {"baseline": "B1"},
    "B2": {"baseline": "B2"},
    "B3": {"baseline": "B3"},
    "B4": {"baseline": "B4"},
}
INGESTION: dict[str, dict[str, Any]] = {"P5": {"munshi_no_gap_check": True}, "P6": {"munshi_no_bundle_split": True}}
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
    "B0": "single pass: raw facts and the checklist to a brief in one call",
    "B1": "single RAG store: one vector index, top-10 with the facts as the query, one drafting call",
    "B2": "whole-document embeddings: top-3 orders passed in full",
    "B3": "naive chunking: B1 with fixed/overlap/recursive/semantic/page chunks",
    "B4": "every store, no orchestrator: reciprocal-rank fusion; drafting, checks and sparring as Full",
    "P5": "Munshi fixed cascade: no gap check, no re-reading, no questions",
    "P6": "Munshi without bundle splitting and document labelling",
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
    baseline: Baseline = "full"  # B0-B4 (plan §15.3); 'full' is the system
    b3_chunking: ChunkingVariant | None = None  # B3's chunking variant (the best on dev goes into generation)

    # ------------------------------------------------------------------ what the agents ask

    @property
    def check_and_repair(self) -> bool:
        """Vakeel checks and repairs claims (off in A2, A9 and the one-call baselines B0-B3)."""
        return not self.no_check_repair and self.baseline in ("full", "B4")

    @property
    def sparring(self) -> bool:
        """Abhiyojak spars (off in A8, A9 and B0-B3)."""
        return not self.no_sparring and self.baseline in ("full", "B4")

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
    def uses_orchestrator(self) -> bool:
        """Sutradhar orchestrates retrieval at all (only the full system and the ablations; B0-B4 do not)."""
        return self.baseline == "full"

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
        """The switches of a named variant.

        Args:
            variant: 'full', 'A1'..'A10', 'B0'..'B4', 'P5' or 'P6'
            extra: further fields (A10 needs `knockout_store`, A5 an `extractor`, B3 may set `b3_chunking`)

        Returns:
            Switches.

        Raises:
            ValueError: unknown variant, or A10 without a store.
        """
        name = variant.strip().upper() if variant.strip().lower() != "full" else "full"
        table = {"full": {}, **ABLATIONS, **BASELINES, **INGESTION}
        if name not in table:
            raise ValueError(f"unknown variant {variant!r}: use 'full', A1-A10, B0-B4, P5 or P6")
        if name == "A10" and not extra.get("knockout_store"):
            raise ValueError("A10 needs knockout_store='<store name>'")
        if name == "A5" and extra.get("extractor", "finetuned_4b") == "finetuned_4b":
            raise ValueError("A5 needs extractor='base_4b' or 'prompted_32b' (the fine-tuned 4B is the full system)")
        return cls(**{**table[name], **extra})

    def variant(self) -> str:
        """The name of the variant these switches implement ('full', 'A1'..'A10', 'B0'..'B4', 'P5', 'P6', or 'custom')."""
        if self.baseline != "full":
            return self.baseline
        fields = self.model_dump(exclude_defaults=True)
        if not fields:
            return "full"
        if set(fields) == {"knockout_store"}:
            return "A10"
        if set(fields) == {"extractor"}:
            return "A5"
        for name, values in {**ABLATIONS, **INGESTION}.items():
            if values and fields == values:
                return name
        return "custom"

    def describe(self) -> str:
        """One line for run logs and the UI."""
        name = self.variant()
        return VARIANT_DESCRIPTIONS.get(name, "custom switch set: " + ", ".join(f"{k}={v}" for k, v in self.model_dump(exclude_defaults=True).items()))
