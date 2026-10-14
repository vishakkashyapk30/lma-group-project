"""Seed a per-case SQLite event log for GateGuard tests.

ASSUMPTION: `GateGuard()` has no constructor arguments, so it finds the case record through `EventLog()` whose default
location derives from `$VS_DATA_DIR` (configs/paths.yaml, .env.example); the tests point that at tmp_path and also chdir
there, then seed the log through the same default. Payload shapes: tests/unit/record/_helpers.py.
"""

from __future__ import annotations


from tests.unit.record._helpers import dossier_events, gate_approved, gate_opened, view_write
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.bail_brief import BailBrief, Ground
from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.enums import ClaimCheck, Factor, FactorStance, FieldStatus, GateId, SparringVerdict
from vakeel_sahayak.schemas.sparring import Objection, SparringRecord

G1 = GateId.GATE_1_DOSSIER.value
G2 = GateId.GATE_2_EXPORT.value


def point_default_log_at(tmp_path, monkeypatch) -> None:
    """Make the default EventLog location land inside tmp_path."""
    monkeypatch.setenv("VS_DATA_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def ground(gid: str, check: ClaimCheck, factor: Factor = Factor.CUSTODY_PERIOD) -> Ground:
    return Ground(id=gid, factor=factor, stance=FactorStance.FAVOURABLE, argument=f"argument {gid}", check=check)


def objection(oid: str, verdict: SparringVerdict, against: str = "G1") -> Objection:
    return Objection(id=oid, against=against, factor="custody_period", objection=f"objection {oid}", verdict=verdict)


def resolved_dossier(dossier):
    """The case-0007 dossier with antecedents answered by counsel (nothing UNSUPPORTED left)."""
    fields = dossier.fields.model_copy(
        update={"antecedents": TrackedField[list[str]](value=[], source=None, status=FieldStatus.USER_STATED)}
    )
    return dossier.model_copy(update={"fields": fields})


def seed_dossier(log: EventLog, case_id: str, dossier) -> None:
    for e in dossier_events(case_id, dossier):
        log.append(e)
    log.append(gate_opened(case_id, G1))


def seed_brief_and_sparring(log: EventLog, case_id: str, grounds: list[Ground], objections: list[Objection]) -> None:
    log.append(view_write(case_id, "brief", BailBrief(case_id=case_id, grounds=grounds)))
    log.append(view_write(case_id, "sparring", SparringRecord(case_id=case_id, rounds=2, objections=objections), "ABHIYOJAK"))
    log.append(gate_opened(case_id, G2))


def approve(log: EventLog, case_id: str, gate: str, acknowledged: list[str] | None = None, dossier_hash: str | None = None):
    log.append(gate_approved(case_id, gate, acknowledged, dossier_hash))
