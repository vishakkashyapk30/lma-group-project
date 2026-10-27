"""Per-case consent for client text sent to an external model (plan §16, AGENTS.md privacy rule, product-readiness AC-P).

Pseudonymised client text (`DataClass.CLIENT_TEXT`) may go to OpenAI or Sarvam only after counsel recorded a consent event for the case
(`openai_consent` / `sarvam_consent`, latest wins, revocable). Public data needs none. The evaluation driver and the baselines declare their
public-source cases with `public_source_scope`: no consent event is asked for or written, and the boundary still runs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
from vakeel_sahayak.models.openai.api import ChatResult
from vakeel_sahayak.models.openai.errors import OpenAIPolicyError
from vakeel_sahayak.models.sarvam.errors import SarvamPolicyError
from vakeel_sahayak.models.sarvam.policy import (
    DataClass,
    SarvamScope,
    authorize,
    case_text_scope,
    current_scope,
    public_scope,
    public_source_scope,
    record_consent,
)
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind

CASE = "case-0042"
CLEAN = "The accused Accused-1 was arrested on 20.08.2024."
RAW_NAME = "The accused Rajesh Kumar was arrested on 20.08.2024."
REPO = Path(__file__).resolve().parents[3]


class FakeApi:
    """Stands in for `OpenAIApi`: records what would be sent, answers with a fixed text."""

    def __init__(self, answer: str = "ok") -> None:
        self.sent: list[list[dict[str, str]]] = []
        self.answer = answer

    def chat(self, messages, **_kw) -> ChatResult:  # noqa: ANN001
        self.sent.append(messages)
        return ChatResult(text=self.answer, prompt_tokens=3, completion_tokens=1)


@pytest.fixture(autouse=True)
def _pseudonymised(monkeypatch):
    for var in ("VS_SARVAM", "VS_EXTERNAL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")


def _client_text(log: EventLog) -> SarvamScope:
    return SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=log)


@pytest.mark.parametrize(("provider", "error"), [("openai", OpenAIPolicyError), ("sarvam", SarvamPolicyError)])
def test_client_text_without_consent_is_refused(provider, error):
    """Pseudonymised text that passes the boundary is still refused when counsel recorded no consent for the case."""
    with pytest.raises(error, match="not consented"):
        authorize("chat", _client_text(EventLog()), text=CLEAN, provider=provider)


@pytest.mark.parametrize("provider", ["openai", "sarvam"])
def test_client_text_with_consent_is_allowed(provider):
    log = EventLog()
    record_consent(log, CASE, True, provider=provider)
    assert authorize("chat", _client_text(log), text=CLEAN, provider=provider).case_id == CASE


def test_consent_is_per_provider_and_per_case():
    log = EventLog()
    record_consent(log, CASE, True, provider="sarvam")
    with pytest.raises(OpenAIPolicyError):  # Sarvam consent does not cover OpenAI
        authorize("chat", _client_text(log), text=CLEAN, provider="openai")
    record_consent(log, "case-0043", True, provider="openai")
    with pytest.raises(OpenAIPolicyError):  # another case's consent does not count
        authorize("chat", _client_text(log), text=CLEAN, provider="openai")


def test_revoked_consent_is_refused_and_a_new_grant_counts():
    """The latest consent event wins."""
    log = EventLog()
    record_consent(log, CASE, True, provider="openai")
    authorize("chat", _client_text(log), text=CLEAN, provider="openai")
    record_consent(log, CASE, False, provider="openai")
    with pytest.raises(OpenAIPolicyError, match="not consented"):
        authorize("chat", _client_text(log), text=CLEAN, provider="openai")
    record_consent(log, CASE, True, provider="openai")
    authorize("chat", _client_text(log), text=CLEAN, provider="openai")


def test_client_text_without_a_case_id_is_refused():
    with pytest.raises(OpenAIPolicyError, match="case id"):
        authorize("chat", SarvamScope(DataClass.CLIENT_TEXT), text=CLEAN, provider="openai")


def test_public_data_needs_no_consent():
    with public_scope("unit"):
        authorize("chat", current_scope(), text="A published order of the High Court.", provider="openai")


def test_the_boundary_still_refuses_raw_text_even_with_consent():
    log = EventLog()
    record_consent(log, CASE, True, provider="openai")
    with pytest.raises(PrivacyBoundaryError):
        authorize("chat", _client_text(log), text=RAW_NAME, provider="openai")


def test_hosted_client_sends_nothing_without_consent_and_sends_after_it():
    """The adapter path: an agent role (CLIENT_TEXT pinned) inside the agent's case scope."""
    api, log = FakeApi(), EventLog()
    llm = OpenAILLMClient(api=api, data=DataClass.CLIENT_TEXT, where="ada", role="agents_14b")
    with case_text_scope(CASE, event_log=log):
        with pytest.raises(OpenAIPolicyError):
            llm.chat([{"role": "user", "content": CLEAN}])
        assert api.sent == []
        record_consent(log, CASE, True, provider="openai")
        assert llm.chat([{"role": "user", "content": CLEAN}]) == "ok"
        record_consent(log, CASE, False, provider="openai")
        with pytest.raises(OpenAIPolicyError):
            llm.chat([{"role": "user", "content": CLEAN}])
    assert len(api.sent) == 1


def test_audit_event_holds_sizes_only():
    log = EventLog()
    record_consent(log, CASE, True, provider="openai")
    payload = {"messages": [{"role": "user", "content": CLEAN}]}
    authorize("chat", SarvamScope(DataClass.CLIENT_TEXT, case_id=CASE, event_log=log, purpose="draft"), payload=payload, provider="openai")
    audits = [e for e in log.read(CASE, kind=EventKind.TOOL_CALL) if e.tool == "openai.chat"]
    assert len(audits) == 1
    inputs = audits[0].inputs
    assert set(inputs) <= {"capability", "data_class", "purpose", "chars", "bytes"}
    assert inputs["data_class"] == "client_text" and inputs["chars"] == len(str(payload))
    blob = json.dumps(audits[0].model_dump(mode="json"))
    assert "Accused-1" not in blob and "20.08.2024" not in blob and not audits[0].outputs


def test_public_source_declaration_runs_the_boundary_but_needs_no_consent():
    """The evaluation path: an agent client inside `public_source_scope` sends without a consent event, and none is written."""
    api = FakeApi()
    llm = OpenAILLMClient(api=api, data=DataClass.CLIENT_TEXT, where="ada", role="agents_14b")
    log = EventLog()
    with public_source_scope("eval-full"):
        with case_text_scope(CASE, event_log=log):  # the agent's own scope does not override the declaration
            assert current_scope().basis == "public_source"
            assert llm.chat([{"role": "user", "content": CLEAN}]) == "ok"
            with pytest.raises(PrivacyBoundaryError):  # pseudonymisation is still enforced
                llm.chat([{"role": "user", "content": RAW_NAME}])
    assert len(api.sent) == 1
    assert log.read(CASE) == []  # no consent event, no audit event: nothing was faked


def test_a_plain_public_scope_does_not_waive_consent_for_client_text():
    """Only the explicit public-source declaration waives consent; `public_scope` around an agent client does not."""
    llm = OpenAILLMClient(api=FakeApi(), data=DataClass.CLIENT_TEXT, where="ada")
    with public_scope("gold"), pytest.raises(OpenAIPolicyError):
        llm.chat([{"role": "user", "content": CLEAN}])


def test_case_text_scope_fills_in_a_case_scope_only_when_none_was_declared():
    with case_text_scope(CASE, event_log="log") as scope:
        assert (scope.data, scope.case_id, scope.event_log) == (DataClass.CLIENT_TEXT, CASE, "log")
    with public_scope("p"), case_text_scope(CASE, mapping="m") as scope:
        assert scope.data is DataClass.PUBLIC and scope.case_id is None and scope.mapping == "m"
    assert current_scope().data is DataClass.CLIENT_RAW


def test_no_product_module_uses_the_public_source_declaration_or_writes_consent():
    """`public_source_scope` belongs to the evaluation code only, and no module records counsel's consent on its own."""
    src = REPO / "src" / "vakeel_sahayak"
    for path in src.rglob("*.py"):
        rel = path.relative_to(src).as_posix()
        text = path.read_text(encoding="utf-8")
        if re.search(r"public_source_scope\(", text):
            assert rel.startswith("eval/") or rel in ("models/sarvam/policy.py",), rel
        if re.search(r"record_consent\(", text):
            assert rel == "models/sarvam/policy.py", rel
