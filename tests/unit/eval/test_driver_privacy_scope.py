"""The evaluation driver's privacy declaration (plan §16; models/sarvam/policy.py `public_source_scope`).

Evaluation cases come from published court orders or are constructed, so the driver declares them public-source: a hosted agent call
needs no counsel consent there (and none is written), while the wire step and the boundary run as in production. A case marked
`data_class: client` gets no declaration. The manifest records the class; an evaluation case's date shift is reproducible.
"""

from __future__ import annotations

import json

import pytest

from tests.integration._helpers import full_pipeline_llm
from vakeel_sahayak.eval.runners.driver import _case_scope, build_context, file_facts, privacy_manifest
from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
from vakeel_sahayak.models.openai.api import ChatResult
from vakeel_sahayak.models.openai.errors import OpenAIPolicyError
from vakeel_sahayak.models.sarvam.policy import PUBLIC_SOURCE, DataClass, case_text_scope, current_scope
from vakeel_sahayak.privacy.pseudonymise import load_map
from vakeel_sahayak.privacy.quasi import deterministic_shift
from vakeel_sahayak.schemas.enums import EventKind

ORDER = "BA No. 9258 of 2023. FIR No. 87/2023 of Hili police station. The petitioner was arrested on 03.02.2023 under Section 302 IPC."


class FakeApi:
    def __init__(self) -> None:
        self.sent: list = []

    def chat(self, messages, **_kw):  # noqa: ANN001
        self.sent.append(messages)
        return ChatResult(text="ok", prompt_tokens=1, completion_tokens=1)


def test_driver_declares_public_source_cases_and_not_client_cases():
    with _case_scope({"case_id": "t1dev-000"}, "full"):
        assert current_scope().basis == PUBLIC_SOURCE and current_scope().data is DataClass.PUBLIC
    with _case_scope({"case_id": "t1dev-000", "data_class": "client"}, "full"):
        assert current_scope().basis == "" and current_scope().data is DataClass.CLIENT_RAW


def test_driver_public_eval_path_sends_without_consent_and_writes_none(monkeypatch, toolbox, paid_unlocked):  # RECONCILED: paid providers are locked by default (owner decision 2026-10-28); this exercises the mocked OpenAI path
    """A hosted agent call on a public-source case works without a consent event, uses the case's wire aliases, and writes no USER_ACTION."""
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    case = {"case_id": "t1dev-900", "facts": ORDER, "before": toolbox.world.case_date}
    ctx = build_context(case, tools=toolbox.tools, llm=full_pipeline_llm())
    file_facts(ctx, case, shelve=False)
    api = FakeApi()
    llm = OpenAILLMClient(api=api, data=DataClass.CLIENT_TEXT, where="ada")
    with _case_scope(case, "full", ctx), case_text_scope(case["case_id"], event_log=ctx.log):
        assert llm.chat([{"role": "user", "content": ORDER}]) == "ok"
    sent = api.sent[0][0]["content"]
    assert "87/2023" not in sent and "Hili" not in sent and "9258" not in sent and "03.02.2023" not in sent
    assert "Section 302 IPC" in sent
    assert not [e for e in ctx.log.read(case["case_id"], kind=EventKind.USER_ACTION) if "consent" in str(e.tool)]


def test_driver_client_case_needs_counsel_consent(monkeypatch, toolbox, paid_unlocked):  # RECONCILED: paid providers are locked by default (owner decision 2026-10-28); this exercises the mocked OpenAI path
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    case = {"case_id": "t1dev-901", "facts": ORDER, "before": toolbox.world.case_date, "data_class": "client"}
    ctx = build_context(case, tools=toolbox.tools, llm=full_pipeline_llm())
    llm = OpenAILLMClient(api=FakeApi(), data=DataClass.CLIENT_TEXT, where="ada")
    with _case_scope(case, "full", ctx), case_text_scope(case["case_id"], event_log=ctx.log), pytest.raises(OpenAIPolicyError, match="not consented"):
        llm.chat([{"role": "user", "content": "Accused-1 was arrested."}])


def test_driver_evaluation_case_gets_a_reproducible_date_shift(toolbox):
    case = {"case_id": "t1dev-902", "facts": ORDER, "before": toolbox.world.case_date}
    ctx = build_context(case, tools=toolbox.tools, llm=full_pipeline_llm())
    file_facts(ctx, case, shelve=False)
    assert load_map(case["case_id"], ctx.cases_dir).date_shift_days == deterministic_shift(case["case_id"])


def test_driver_manifest_records_the_data_class(tmp_path):
    cases = tmp_path / "cases.jsonl"
    rows = [{"case_id": "t1-001", "facts": "x"}, {"case_id": "t1-002", "facts": "y"}, {"case_id": "c-1", "facts": "z", "data_class": "client"}]
    cases.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    block = privacy_manifest(str(cases))
    assert block["cases_by_data_class"] == {"public": 2, "client": 1}
    assert block["agent_data_class"] == "client_text" and block["case_scope"].startswith("public_source")
