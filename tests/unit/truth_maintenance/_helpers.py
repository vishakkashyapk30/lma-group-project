"""Builders shared by the truth-maintenance tests: briefs with a claim chain, dossier variants, an LLM installer."""

from __future__ import annotations

import sys

from vakeel_sahayak.schemas.bail_brief import Authority, BailBrief, DependsOn, Ground
from vakeel_sahayak.schemas.change_set import ChangeSet, FieldChange
from vakeel_sahayak.schemas.dossier import CaseDossier, ChargeSheetValue
from vakeel_sahayak.schemas.enums import ClaimCheck, ClaimState, Factor, FactorStance

# Literal hashes (independent of `hash_value`) so staleness tests do not depend on the hashing module.
H = {
    "co_accused_bail": "h:a001",
    "sections": "h:a002",
    "charge_sheet": "h:b001",
    "trial_stage": "h:c001",
    "antecedents": "h:d001",
    "custody_days": "h:e001",
}

AUTH = Authority(doc_id="DLHC-2022-1187", para=14)


def ground(gid, factor, argument, facts=None, claims=None, rights=None, events=None, authorities=None) -> Ground:
    """One CURRENT ground with the given dependencies."""
    return Ground(
        id=gid,
        factor=factor,
        stance=FactorStance.FAVOURABLE,
        argument=argument,
        authorities=[AUTH] if authorities else [],
        depends_on=DependsOn(
            facts={f: H[f] for f in (facts or [])},
            claims=list(claims or []),
            rights=list(rights or []),
            events=list(events or []),
            authorities=list(authorities or []),
        ),
        check=ClaimCheck.SUPPORTED,
        state=ClaimState.CURRENT,
    )


def make_brief() -> BailBrief:
    """Five claims. Chain G1 <- G2 <- G3 (G2 cites G1, G3 cites G2); G4 and G5 are unrelated to the chain.

    G1 parity: co_accused_bail, sections            (plan §8.1 example)
    G2 charge sheet filed: charge_sheet, cites G1
    G3 trial delay: trial_stage, cites G2
    G4 antecedents: antecedents
    G5 undertrial period: depends on the rights entry 'undertrial_limit'
    """
    return BailBrief(
        case_id="case-0007",
        grounds=[
            ground(
                "G1",
                Factor.PARITY_WITH_CO_ACCUSED,
                "Co-accused-1, with an identical role, was granted bail on 05.12.2024 [F:co_accused_bail] [A:DLHC-2022-1187#14].",
                facts=["co_accused_bail", "sections"],
                events=["e12"],
                authorities=["DLHC-2022-1187#14"],
            ),
            ground(
                "G2",
                Factor.CHARGE_SHEET_FILED,
                "Investigation is complete: the charge sheet was filed on 02.11.2024 [F:charge_sheet]; see ground G1.",
                facts=["charge_sheet"],
                claims=["G1"],
            ),
            ground(
                "G3",
                Factor.TRIAL_DELAY,
                "Charges are not framed [F:trial_stage]; trial will take long, as argued in ground G2.",
                facts=["trial_stage"],
                claims=["G2"],
            ),
            ground("G4", Factor.ANTECEDENTS, "No antecedents are on record [F:antecedents].", facts=["antecedents"]),
            ground(
                "G5",
                Factor.UNDERTRIAL_PERIOD,
                "The accused has spent 167 days in custody.",
                rights=["undertrial_limit"],
            ),
        ],
    )


def change(*fields: str, rights: list[str] | None = None, events: list[str] | None = None) -> ChangeSet:
    """A hand-built change set touching the named dossier fields (old hash = the literal hash in H)."""
    return ChangeSet(
        case_id="case-0007",
        trigger="new_document",
        fields=[FieldChange(field=f, old_hash=H[f], new_hash=f"{H[f]}-new") for f in fields],
        new_event_ids=list(events or []),
        rights_changed=list(rights or []),
    )


def states(brief: BailBrief) -> dict[str, ClaimState]:
    return {g.id: g.state for g in brief.grounds}


def with_charge_sheet(dossier: CaseDossier, filed: bool, date: str | None) -> CaseDossier:
    """Deep copy of a dossier with the charge-sheet value replaced."""
    out = dossier.model_copy(deep=True)
    out.fields.charge_sheet.value = ChargeSheetValue(filed=filed, date=date)
    return out


def install_llm(monkeypatch, llm, nli=None) -> None:
    """Make every `get_llm(...)` (factory and any module alias) return `llm`; same for `get_nli` when given."""
    import vakeel_sahayak.models.factory as factory

    monkeypatch.setattr(factory, "get_llm", lambda role="agents_14b": llm)
    if nli is not None:
        monkeypatch.setattr(factory, "get_nli", lambda: nli)
    for name, mod in list(sys.modules.items()):
        if not name.startswith("vakeel_sahayak") or mod is None or mod is factory:
            continue
        if hasattr(mod, "get_llm"):
            monkeypatch.setattr(mod, "get_llm", lambda role="agents_14b": llm)
        if nli is not None and hasattr(mod, "get_nli"):
            monkeypatch.setattr(mod, "get_nli", lambda: nli)


def respond_like_a_drafter(counter: list[int]):
    """ScriptedLLM responder: free text, or a JSON object filled from the requested schema (ASSUMPTION: the redraft
    prompt may be constrained to a pydantic schema; unknown properties get neutral values, string ones a marker)."""

    def _responder(prompt: str, schema: dict | None):
        counter[0] += 1
        marker = f"REDRAFTED-{counter[0]} [F:charge_sheet]"
        if not schema:
            return marker
        out: dict = {}
        for key, spec in (schema.get("properties") or {}).items():
            kind = spec.get("type")
            if kind == "string":
                out[key] = (spec.get("enum") or [marker])[0] if spec.get("enum") else marker
            elif kind == "array":
                out[key] = []
            elif kind == "object":
                out[key] = {}
            elif kind in ("integer", "number"):
                out[key] = 0
            elif kind == "boolean":
                out[key] = True
        return out

    return _responder
