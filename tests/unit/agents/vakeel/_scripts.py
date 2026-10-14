"""Scripts and fixtures for Vakeel tests (plan §8.1).

ASSUMPTION (one place to adjust): Vakeel asks the model for ONE JSON object per ground, shaped like the `Ground` schema
without rendered citations (id, factor, stance, argument, authorities=[{doc_id, para}]), requested with the schema title
'Ground' and answered in pack order. A reword during repair uses the same schema and answers with the new argument.
"""

from __future__ import annotations

import re
from typing import Any

from tests.fakes.models import ScriptedLLM, Seq
from tests.unit.agents._helpers import para_dict
from vakeel_sahayak.schemas.enums import Factor, FactorStance, SlotStatus
from vakeel_sahayak.schemas.retrieval_plan import EvidencePack, SlotResult

# Arguments the fake NLI (tests/fakes/models.py FakeNli) judges against the cited paragraph text.
SUPPORTED_G1 = (
    "Co-accused with an identical role has been enlarged on bail; parity requires the same relief "
    "[F:co_accused_bail] [A:DLHC-2022-1187#14]"
)
SUPPORTED_G2 = "Once the charge sheet is filed custodial interrogation is no longer required [F:charge_sheet] [A:SC-2014-0463#21]"
UNSUPPORTED_G1 = "The accused was granted default bail on 05.12.2024 [F:co_accused_bail] [A:DLHC-2022-1187#14]"  # date not in source


def model_ground(gid: str, factor: str, argument: str, authorities: list[tuple[str, int]], **extra: Any) -> dict[str, Any]:
    """What the model returns: ids only, no rendered citation (plan §8.1: 'the model writes only IDs')."""
    return {
        "id": gid,
        "factor": factor,
        "stance": "favourable",
        "argument": argument,
        "authorities": [{"doc_id": d, "para": p, **extra} for d, p in authorities],
    }


def ground_llm(*grounds: dict[str, Any]) -> ScriptedLLM:
    seq = Seq(*grounds)
    return ScriptedLLM(by_schema={"Ground": seq}, by_prompt=[(re.compile(""), seq)], strict=False, default="")


def reword_llm(replies: list[str] | str) -> ScriptedLLM:
    """A model whose repair rewrites return the given argument text(s) as Ground-shaped JSON (last one repeats)."""
    texts = [replies] if isinstance(replies, str) else list(replies)
    seq = Seq(*[model_ground("G1", "parity_with_co_accused", t, [("DLHC-2022-1187", 14)]) for t in texts])
    return ScriptedLLM(by_schema={"Ground": seq}, by_prompt=[(re.compile(""), seq)], strict=False, default="")


def pack(factor: Factor, paragraphs, cited: list[tuple[str, int]], stance=FactorStance.FAVOURABLE) -> EvidencePack:
    """An EvidencePack whose authority slot holds the given retrieved paragraphs (all built from the fixture)."""
    items = [para_dict(paragraphs, d, p) for d, p in cited]
    return EvidencePack(
        factor=factor,
        stance=stance,
        reason="test",
        slots=[SlotResult(slot="authority", status=SlotStatus.FILLED, items=items)],
    )
