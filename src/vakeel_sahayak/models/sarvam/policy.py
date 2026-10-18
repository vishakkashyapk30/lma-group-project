"""Privacy policy for the Sarvam API (plan §16). Every Sarvam call site goes through `authorize`.

Sarvam is an EXTERNAL service, and raw client files never leave counsel's machine unless counsel says so. Three things decide:

1. **Mode** (`VS_SARVAM` = off | public | pseudonymised | consented; else yaml `sarvam.enabled` + `sarvam.mode`; default off):
   - `public`: public or constructed data only (test-set construction, gold labels of public orders, teacher data
     from public orders, T8 synthetic speech);
   - `pseudonymised`: also client text, after `privacy.boundary.assert_pseudonymised` passes (`PrivacyBoundaryError` otherwise);
   - `consented`: also raw client pages, audio and un-pseudonymised text, for cases whose counsel recorded a consent event.
2. **Data class** of the call (`DataClass`), declared by the caller through a scope:
   `with sarvam_scope(DataClass.PUBLIC): ...` for public/constructed data, `sarvam_scope(DataClass.CLIENT_TEXT, case_id=...)` for
   pseudonymised client text, and the default (no scope) is `CLIENT_RAW`, the most restricted class.
3. **Consent**: a USER_ACTION event by counsel (`tool='sarvam_consent'`, `inputs.granted`) in the case event log; the latest
   one wins, so counsel can revoke. Every client-data call is then logged as an event with sizes only, never payload content.

A violation raises `SarvamPolicyError` (mode/consent) or `PrivacyBoundaryError` (text that is not pseudonymised). The factory
wrappers catch both and fall back to the local implementation.
"""

from __future__ import annotations

import contextlib
import contextvars
import os
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from vakeel_sahayak.models.sarvam.config import sarvam_config
from vakeel_sahayak.models.sarvam.errors import SarvamPolicyError

CONSENT_TOOL = "sarvam_consent"
AUDIT_ACTOR = "sarvam"


class SarvamMode(str, Enum):
    """How far Sarvam may be used (ordered: each mode includes the ones before it)."""

    OFF = "off"
    PUBLIC = "public"
    PSEUDONYMISED = "pseudonymised"
    CONSENTED = "consented"

    @property
    def rank(self) -> int:
        """Position in the order off < public < pseudonymised < consented."""
        return list(SarvamMode).index(self)


class DataClass(str, Enum):
    """What a call carries."""

    PUBLIC = "public"  # public court orders, statutes, constructed or synthetic data
    CLIENT_TEXT = "client_text"  # client-derived text that has been pseudonymised
    CLIENT_RAW = "client_raw"  # raw client pages, audio or un-pseudonymised text (the default)


_REQUIRED_MODE = {DataClass.PUBLIC: SarvamMode.PUBLIC, DataClass.CLIENT_TEXT: SarvamMode.PSEUDONYMISED, DataClass.CLIENT_RAW: SarvamMode.CONSENTED}


def sarvam_mode() -> SarvamMode:
    """Effective mode: env `VS_SARVAM`, else yaml (`enabled` true gives `mode`), else OFF.

    Raises:
        ValueError: for an unknown VS_SARVAM value.
    """
    raw = os.environ.get("VS_SARVAM")
    if raw is None or not raw.strip():
        cfg = sarvam_config()
        raw = str(cfg["mode"]) if cfg.get("enabled") else "off"
    try:
        return SarvamMode(raw.strip().lower())
    except ValueError:
        raise ValueError(f"VS_SARVAM must be one of {[m.value for m in SarvamMode]}, got {raw!r}") from None


@dataclass(frozen=True)
class SarvamScope:
    """What the current code is doing with Sarvam: the data class, the case (for consent and audit) and the purpose."""

    data: DataClass = DataClass.CLIENT_RAW
    case_id: str | None = None
    event_log: Any = None  # record.event_log.EventLog; opened from the case id when None
    purpose: str = ""
    mapping: Any = None  # the case's PseudonymMap for the boundary check (loaded from the case when None)


_SCOPE: contextvars.ContextVar[SarvamScope | None] = contextvars.ContextVar("sarvam_scope", default=None)


def current_scope() -> SarvamScope:
    """The active scope (the most restricted one, CLIENT_RAW with no case, when none is set)."""
    return _SCOPE.get() or SarvamScope()


@contextlib.contextmanager
def sarvam_scope(
    data: DataClass = DataClass.CLIENT_RAW, *, case_id: str | None = None, event_log: Any = None, purpose: str = "", mapping: Any = None
) -> Iterator[SarvamScope]:
    """Declare what the enclosed Sarvam calls carry. Only the caller knows whether data is public, so only the caller sets this."""
    scope = SarvamScope(data, case_id, event_log, purpose, mapping)
    token = _SCOPE.set(scope)
    try:
        yield scope
    finally:
        _SCOPE.reset(token)


def public_scope(purpose: str = "") -> contextlib.AbstractContextManager[SarvamScope]:
    """`sarvam_scope(DataClass.PUBLIC)` for test-set construction, gold labelling and teacher data."""
    return sarvam_scope(DataClass.PUBLIC, purpose=purpose)


# ---------------------------------------------------------------------------------------- consent


def _open_log(scope: SarvamScope) -> tuple[Any, bool]:
    """(event log, opened_here) for a scope with a case; (None, False) without one."""
    if scope.event_log is not None:
        return scope.event_log, False
    if scope.case_id:
        from vakeel_sahayak.record.event_log import EventLog

        return EventLog.for_case(scope.case_id), True
    return None, False


def record_consent(log: Any, case_id: str, granted: bool = True, note: str = "") -> Any:
    """Counsel's decision to let Sarvam read this case's raw pages and audio (or to withdraw it). Appends a USER_ACTION event."""
    from vakeel_sahayak.schemas.enums import EventKind
    from vakeel_sahayak.schemas.events import COUNSEL, Event

    return log.append(
        Event(
            event_id="", case_id=case_id, ts="", kind=EventKind.USER_ACTION, actor=COUNSEL, tool=CONSENT_TOOL,
            inputs={"action": CONSENT_TOOL, "granted": bool(granted), "note": note[:200]},
        )  # fmt: skip
    )


def has_consent(log: Any, case_id: str) -> bool:
    """True when the latest consent event of the case grants Sarvam access (a later revocation wins)."""
    from vakeel_sahayak.schemas.enums import EventKind
    from vakeel_sahayak.schemas.events import COUNSEL

    granted = False
    for ev in log.read(case_id, kind=EventKind.USER_ACTION):
        if ev.tool == CONSENT_TOOL and str(getattr(ev.actor, "value", ev.actor)) == COUNSEL:
            granted = bool(ev.inputs.get("granted"))
    return granted


def _audit(log: Any, scope: SarvamScope, capability: str, size: dict[str, int]) -> None:
    """Log one client-data call: capability, data class and sizes only. Never any payload content."""
    from vakeel_sahayak.schemas.enums import EventKind
    from vakeel_sahayak.schemas.events import Event

    log.append(
        Event(
            event_id="", case_id=str(scope.case_id), ts="", kind=EventKind.TOOL_CALL, actor=AUDIT_ACTOR, tool=f"sarvam.{capability}",
            inputs={"capability": capability, "data_class": scope.data.value, "purpose": scope.purpose[:80], **size},
        )  # fmt: skip
    )


# ---------------------------------------------------------------------------------------- the gate


def _size(text: str | None, nbytes: int | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if text is not None:
        out["chars"] = len(text)
    if nbytes is not None:
        out["bytes"] = int(nbytes)
    return out


def authorize(
    capability: str, scope: SarvamScope | None = None, *, text: str | None = None, nbytes: int | None = None, payload: dict | None = None
) -> SarvamScope:
    """Allow or refuse one Sarvam call. Call it before every request.

    Args:
        capability: 'chat', 'translate', 'speech_to_text', 'vision', ... (for the audit event)
        scope: default `current_scope()`
        text: text bound for Sarvam (boundary-checked for CLIENT_TEXT)
        nbytes: size of binary content (image or audio); binary content is never allowed as CLIENT_TEXT
        payload: the whole outbound structure when it is more than one string (chat messages); checked instead of `text`

    Returns:
        The scope that applied.

    Raises:
        SarvamPolicyError: mode too low, no case, or no counsel consent.
        PrivacyBoundaryError: CLIENT_TEXT that is not pseudonymised, or binary content declared as text.
    """
    scope = scope or current_scope()
    mode = sarvam_mode()
    need = _REQUIRED_MODE[scope.data]
    if mode is SarvamMode.OFF:
        raise SarvamPolicyError("Sarvam is off (VS_SARVAM=off); nothing was sent")
    if mode.rank < need.rank:
        raise SarvamPolicyError(
            f"Sarvam mode {mode.value!r} does not allow {scope.data.value} data (needs {need.value!r}); nothing was sent"
        )
    log: Any = None
    opened = False
    try:
        if scope.data is DataClass.CLIENT_TEXT:
            from vakeel_sahayak.privacy.boundary import assert_pseudonymised

            body = payload if payload is not None else {"text": text or ""}
            if nbytes:
                body = {**body, "raw_bytes": b"x"}  # binary content can never pass as pseudonymised text
            mapping = scope.mapping
            if mapping is None and scope.case_id:
                try:
                    from vakeel_sahayak.privacy.pseudonymise import load_map

                    mapping = load_map(scope.case_id)
                except (OSError, ValueError, KeyError):
                    mapping = None
            assert_pseudonymised(body, mapping=mapping)
        if scope.data is DataClass.CLIENT_RAW:
            if not scope.case_id:
                raise SarvamPolicyError("raw client data needs a case id so counsel's consent can be checked; nothing was sent")
            log, opened = _open_log(scope)
            if not has_consent(log, scope.case_id):
                raise SarvamPolicyError(
                    f"counsel has not consented to sending case {scope.case_id}'s raw pages or audio to Sarvam; nothing was sent"
                )
        if scope.data is not DataClass.PUBLIC and scope.case_id:
            if log is None:
                log, opened = _open_log(scope)
            _audit(log, scope, capability, _size(text if payload is None else str(payload), nbytes))
    finally:
        if opened and log is not None:
            log.close()
    return scope
