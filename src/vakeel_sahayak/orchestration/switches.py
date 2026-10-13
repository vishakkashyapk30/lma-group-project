"""Ablation and variant switches (plan §15.4 A1-A10, §15.5 P5-P6, §19 fixed-router fallback). Defaults are the full system."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Switches(BaseModel):
    """Booleans toggled by eval runs."""

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
