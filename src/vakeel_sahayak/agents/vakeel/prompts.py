"""Prompt templates for Vakeel. Documents are data: wrap document text with privacy.injection_guard.wrap_untrusted (plan §16)."""

from __future__ import annotations

SYSTEM_PROMPT: str = ""  # TODO: write in the agent's own voice and constraints (plan §3.2)
USER_PROMPT_TEMPLATES: dict[str, str] = {}  # TODO: one per decision point
