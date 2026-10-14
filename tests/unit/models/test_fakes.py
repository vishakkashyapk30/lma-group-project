"""The shared fakes in tests/fakes/models.py satisfy the model interfaces and behave as documented (plan §12).

The fakes carry every agent, integration and system test, so their own contract is tested here: schema-title dispatch,
Seq, strict mode, token counting and the deterministic NLI / OCR / vision / ASR / translation / embedding fakes.
"""

from __future__ import annotations

import re

import pytest

from tests.fakes.models import (
    FakeAsr,
    FakeEmbedder,
    FakeNli,
    FakeOcr,
    FakeTranslator,
    FakeVision,
    ScriptedLLM,
    Seq,
)
from vakeel_sahayak.models.base import (
    AsrClient,
    EmbeddingClient,
    LLMClient,
    NliClient,
    OcrClient,
    TranslationClient,
    VisionClient,
)
from vakeel_sahayak.schemas.retrieval_plan import PlanStep, RetrievalPlan

PLAN_SCHEMA = RetrievalPlan.model_json_schema()


@pytest.mark.parametrize(
    "fake,iface",
    [
        (ScriptedLLM(), LLMClient),
        (FakeNli(), NliClient),
        (FakeOcr(), OcrClient),
        (FakeVision(), VisionClient),
        (FakeAsr(), AsrClient),
        (FakeTranslator(), TranslationClient),
        (FakeEmbedder(), EmbeddingClient),
    ],
)
def test_fake_implements_interface(fake, iface):
    """Each fake is an instance of the interface it stands in for."""
    assert isinstance(fake, iface)


# ---------------------------------------------------------------------------------------------------------------------
# ScriptedLLM
# ---------------------------------------------------------------------------------------------------------------------
def test_dispatch_by_schema_title():
    """A call with a json_schema is answered by the responder keyed by the schema's title (pydantic class name)."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": '{"ok": 1}', "PlanStep": '{"ok": 2}'})
    assert llm.generate("p", json_schema=PLAN_SCHEMA) == '{"ok": 1}'
    assert llm.generate("p", json_schema=PlanStep.model_json_schema()) == '{"ok": 2}'
    assert [c.schema_title for c in llm.calls] == ["RetrievalPlan", "PlanStep"]
    assert llm.calls[0].json_schema == PLAN_SCHEMA


def test_schema_responder_literals_are_json_encoded():
    """dict, list and pydantic responders are JSON-encoded; a str is returned verbatim."""
    step = PlanStep(slot="s", tool="t")
    llm = ScriptedLLM(by_schema={"A": {"x": 1}, "B": [1, 2], "PlanStep": step, "C": "raw text"})
    assert llm.generate("p", json_schema={"title": "A"}) == '{"x": 1}'
    assert llm.generate("p", json_schema={"title": "B"}) == "[1, 2]"
    assert llm.generate("p", json_schema=PlanStep.model_json_schema()) == step.model_dump_json()
    assert llm.generate("p", json_schema={"title": "C"}) == "raw text"


def test_dispatch_by_prompt_substring_and_regex_in_order():
    """Schema-less calls use the first matching (substring or regex, in order) by_prompt entry."""
    llm = ScriptedLLM(by_prompt=[("alpha", "A"), (re.compile(r"beta\d+"), "B"), ("a", "late")])
    assert llm.generate("say alpha now") == "A"
    assert llm.generate("beta42 please") == "B"
    assert llm.generate("banana") == "late"


def test_unscripted_schema_title_falls_back_to_prompt_script():
    """A schema call whose title is not scripted falls back to by_prompt matching."""
    llm = ScriptedLLM(by_schema={"Other": "x"}, by_prompt=[("hello", "from prompt")])
    assert llm.generate("hello there", json_schema=PLAN_SCHEMA) == "from prompt"


def test_seq_gives_one_item_per_call_and_repeats_last():
    """Seq(a, b) answers a then b, and keeps answering b."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": Seq("first", "second")})
    assert [llm.generate("p", json_schema=PLAN_SCHEMA) for _ in range(4)] == ["first", "second", "second", "second"]


def test_callable_responder_receives_prompt_and_schema():
    """A callable responder gets (prompt, json_schema) and may return a literal."""
    seen = []

    def responder(prompt, schema):
        seen.append((prompt, schema["title"]))
        return {"echo": prompt}

    llm = ScriptedLLM(by_schema={"RetrievalPlan": responder})
    assert llm.generate("hi", json_schema=PLAN_SCHEMA) == '{"echo": "hi"}'
    assert seen == [("hi", "RetrievalPlan")]


def test_strict_mode_raises_on_unscripted_call_and_records_nothing():
    """strict=True (the default) raises AssertionError for an unscripted call so unexpected LLM use is noticed."""
    llm = ScriptedLLM(by_prompt=[("zzz", "ok")])
    with pytest.raises(AssertionError, match="no script"):
        llm.generate("an unscripted prompt")
    assert llm.calls == []


def test_non_strict_returns_default_or_empty():
    """strict=False returns `default` (or '') for an unscripted call and still records it."""
    assert ScriptedLLM(strict=False).generate("x") == ""
    llm = ScriptedLLM(strict=False, default="fallback")
    assert llm.generate("x") == "fallback"
    assert len(llm.calls) == 1


def test_default_makes_strict_mode_lenient():
    """A configured default is used even when strict is True."""
    assert ScriptedLLM(default="d").generate("anything") == "d"


def test_call_recording_and_calls_for():
    """Calls are recorded with prompt, title, max_tokens and completion; calls_for filters by schema title."""
    llm = ScriptedLLM(by_schema={"RetrievalPlan": "p"}, by_prompt=[("free", "f")])
    llm.generate("one", max_tokens=77, json_schema=PLAN_SCHEMA)
    llm.generate("free text")
    assert llm.prompts == ["one", "free text"]
    assert llm.calls[0].max_tokens == 77
    assert [c.completion for c in llm.calls] == ["p", "f"]
    assert len(llm.calls_for("RetrievalPlan")) == 1
    assert llm.calls_for("Nope") == []


def test_count_tokens_is_whitespace_words_and_total_tokens_sums_prompt_and_completion():
    """count_tokens counts whitespace-separated words; total_tokens adds prompt and completion words of every call."""
    llm = ScriptedLLM(by_prompt=[("q", "one two three")])
    assert llm.count_tokens("") == 0
    assert llm.count_tokens("a  b\tc\nd") == 4
    llm.generate("q a b")  # 3 prompt + 3 completion
    llm.generate("q")  # 1 + 3
    assert llm.total_tokens == 10


def test_where_defaults_to_laptop_and_is_settable():
    """`where` tags the client side ('laptop' default, 'ada') for privacy tests."""
    assert ScriptedLLM().where == "laptop"
    assert ScriptedLLM(where="ada").where == "ada"


# ---------------------------------------------------------------------------------------------------------------------
# other fakes
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "premise,hypothesis,supported",
    [
        ("The accused was arrested on 20.08.2024 at Delhi.", "arrested on 20.08.2024", True),
        ("The accused was arrested on 20.08.2024 at Delhi.", "arrested on 21.08.2024", False),  # changed date
        ("Charge sheet filed on 02.11.2024", "charge sheet filed 02.11.2024", True),
        ("Charge sheet filed on 02.11.2024", "bail granted to Ravi", False),  # unrelated words
        ("anything", "the of and", True),  # no content words
    ],
)
def test_fake_nli_flips_on_changed_numbers_and_unrelated_content(premise, hypothesis, supported):
    """FakeNli: 0.95 when numbers/dates and most content words are in the premise, else 0.05."""
    score = FakeNli().entails(premise, hypothesis)
    assert score == (0.95 if supported else 0.05)


def test_fake_ocr_returns_text_confidence_and_box_and_records_calls():
    """FakeOcr returns (text, conf, boxes) for known bytes and records (image, lang)."""
    ocr = FakeOcr(pages={b"img": ("hello", 0.9)})
    text, conf, boxes = ocr.ocr(b"img", "hi")
    assert (text, conf) == ("hello", 0.9)
    assert len(boxes) == 1 and len(boxes[0]) == 4
    assert ocr.calls == [(b"img", "hi")]


def test_fake_ocr_crash_and_unknown_image():
    """FakeOcr raises for fail_on images (an OCR crash) and KeyError for unknown ones."""
    ocr = FakeOcr(pages={b"ok": ("t", 0.5)}, fail_on={b"bad"})
    with pytest.raises(RuntimeError, match="OCR crash"):
        ocr.ocr(b"bad", "en")
    with pytest.raises(KeyError):
        ocr.ocr(b"unknown", "en")


def test_fake_vision_unknown_page_is_empty_string():
    """FakeVision returns '' (an unreadable page) for unknown images."""
    v = FakeVision(pages={b"p1": "transcript"})
    assert v.transcribe_page(b"p1") == "transcript"
    assert v.transcribe_page(b"zzz") == ""
    assert v.calls == [b"p1", b"zzz"]


def test_fake_asr_by_path():
    """FakeAsr maps audio path to transcript."""
    assert FakeAsr({"a.wav": "text"}).transcribe("a.wav", "hi") == "text"


def test_fake_translator_table_and_visible_fallback():
    """FakeTranslator uses its phrase table, extends it, and marks untranslated text with '[en] '."""
    t = FakeTranslator(table={"नमस्ते": "hello"})
    assert t.translate("धारा 318(4) बी.एन.एस.") == "Section 318(4) BNS"
    assert t.translate("नमस्ते") == "hello"
    assert t.translate("कुछ और") == "[en] कुछ और"
    assert len(t.calls) == 3


def test_fake_embedder_dimension_determinism_and_unit_norm():
    """FakeEmbedder: 32-dim, identical text gives identical unit vectors, different text differs."""
    vecs = FakeEmbedder().embed(["bail granted", "bail granted", "custody period"])
    assert all(len(v) == FakeEmbedder.DIM == 32 for v in vecs)
    assert vecs[0] == vecs[1] != vecs[2]
    assert sum(x * x for x in vecs[0]) == pytest.approx(1.0)
    assert FakeEmbedder().embed([""]) == [[0.0] * 32]
