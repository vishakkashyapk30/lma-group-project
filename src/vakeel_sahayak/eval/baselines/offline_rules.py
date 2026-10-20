"""Offline stand-in rules for the baselines' drafting call (no model): one ground per checklist factor whose cue words occur in the facts.

Used only when the model backend is the offline stand-in (`VS_MODELS=offline`); it lets B0-B3 run end to end without a model, and says so in
the run metadata (`offline: true` in the models stamp). It is not evidence about any model.
"""

from __future__ import annotations

import re
from typing import Any

CUES: dict[str, tuple[str, ...]] = {
    "gravity_and_punishment": ("section", "punishable", "offence"),
    "custody_period": ("arrest", "custody", "remand"),
    "charge_sheet_filed": ("charge sheet", "chargesheet", "investigation"),
    "trial_delay": ("trial", "delay", "charges not framed"),
    "parity_with_co_accused": ("co-accused", "co accused", "other accused"),
    "antecedents": ("antecedent", "previous", "criminal history"),
    "flight_risk": ("resident", "abscond", "flight"),
    "witness_tampering": ("witness", "tamper"),
    "weak_prima_facie": ("false", "no material", "no role"),
    "health_age_family": ("ill", "aged", "elderly", "family"),
    "statutory_bar": ("ndps", "uapa", "pmla", "section 37"),
    "undertrial_period": ("undertrial", "months", "years in custody"),
}


def grounds_from_facts(facts: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ground dicts (BailBrief `Ground` shape) for the factors whose cues the facts contain; the sentence with the cue is the argument."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", facts) if s.strip()]
    out: list[dict[str, Any]] = []
    for factor, cues in CUES.items():
        hit = next((s for s in sentences if any(c in s.lower() for c in cues)), None)
        if hit:
            auth = []
            for row in evidence:
                if row.get("doc_id") and isinstance(row.get("para"), int):
                    auth.append({"doc_id": row["doc_id"], "para": row["para"]})
                    break
            out.append({"id": f"G{len(out) + 1}", "factor": factor, "stance": "favourable", "argument": hit, "authorities": auth})
    return out
