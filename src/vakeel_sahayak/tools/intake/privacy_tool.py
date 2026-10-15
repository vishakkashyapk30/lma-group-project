"""Tools in intake.privacy_tool (plan §16). Each function has a matching <NAME>_SPEC."""

from __future__ import annotations

from vakeel_sahayak.schemas.enums import AgentName
from vakeel_sahayak.tools.base import ToolSpec


def pseudonymise(text: str, case_id: str) -> str:
    """Pseudonymise text after OCR and before it leaves the laptop. (plan §16)

    Args:
        text: see behaviour
        case_id: see behaviour

    Returns:
        Pseudonymised text.
    """
    from vakeel_sahayak.privacy.pseudonymise import load_map, pseudonymise_text, save_map

    mapping = load_map(case_id)
    out, _ = pseudonymise_text(text, case_id, mapping)  # learns new names into `mapping` in place
    save_map(case_id, mapping)  # the alias map stays on the laptop
    return out


PSEUDONYMISE_SPEC = ToolSpec(
    name="pseudonymise",
    description="Pseudonymise text after OCR and before it leaves the laptop.",
    agents=[AgentName.MUNSHI],
    stores=[],
    plan_ref="§16",
)
