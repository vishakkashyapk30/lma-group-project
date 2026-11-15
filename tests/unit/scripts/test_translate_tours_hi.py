"""scripts/demo/translate_tours_hi.py: what is sent, the hash and stale logic, the number and token checks, idempotence, --dry-run and
--check. Offline: the translator is a fake, no model is called."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("translate_tours_hi", REPO / "scripts" / "demo" / "translate_tours_hi.py")
mod = importlib.util.module_from_spec(spec)
sys.modules["translate_tours_hi"] = mod
spec.loader.exec_module(mod)

STAGES = ("INTAKE", "DOSSIER", "GATE_1", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "GATE_2", "FILE")


def tour_doc() -> dict:
    return {
        "slug": "01-x", "case_id": "demo-01", "title": "Demo · Cheating, co-accused on bail",
        "story": "Accused-1 is charged under IPC 420 and has been in custody for 167 days.",
        "variant": {"offence": "IPC 420/406 cheating", "custody": "charge sheet on day 55 of 60", "record": "complete file", "parity": "Co-accused-2 granted bail"},
        "recorded": {"date": "2026-11-14", "backend": "sarvam", "model": "m", "cost_inr": 1.0},
        "steps": [
            {"stage": s, "tab": "dossier", "title": f"Munshi reads {s}", "caption": f"Counsel uploaded 11 PDFs at {s}; s.479 applies to Accused-1.",
             "agent": None, "action": "approve_gate_2" if s == "GATE_2" else None,
             "filled": [{"label": "01_fir.pdf", "value": "born-digital PDF"}, {"label": "Counsel's answer", "value": "No other pending case"}]}
            for s in STAGES
        ],
    }


def fake(texts: list[str]) -> dict[int, str]:
    """A translator that keeps every protected token and number, and prefixes Hindi text (so it can be told from the English)."""
    return {n: "हिंदी: " + t for n, t in enumerate(texts)}


class Counting:
    def __init__(self, fn=fake):
        self.fn, self.requests, self.sent = fn, 0, []

    def __call__(self, texts):
        self.requests += 1
        self.sent.append(list(texts))
        return self.fn(texts)


def test_protected_tokens_cover_numbers_sections_roles_and_stage_terms():
    en = "Accused-1 and Co-accused-2 (IO-1) at PS-4: BNS 318(4), IPC 420/406, s.479, FIR 112/2024, 01_fir.pdf, GATE_2, ELIGIBLE."
    toks = mod.protected_tokens(en)
    for t in ["Accused-1", "Co-accused-2", "IO-1", "PS-4", "BNS 318(4)", "IPC 420/406", "s.479", "112/2024", "01_fir.pdf", "GATE_2", "ELIGIBLE", "FIR"]:
        assert t in toks, t
    assert len(toks) == len(set(toks))


def test_numbers_are_compared_as_digits_with_devanagari_digits_counted_as_ascii():
    assert mod.numbers_of("11 PDFs, 6,50,000, 14.08.2024") == mod.numbers_of("६,५०,००० रुपये, १४.०८.२०२४, 11")
    assert mod.check_translation("167 days in custody", "हिरासत के 167 दिन") is None
    assert mod.check_translation("167 days in custody", "हिरासत के १६७ दिन") is None
    assert "numbers differ" in mod.check_translation("167 days in custody", "हिरासत के 176 दिन")
    assert "numbers differ" in mod.check_translation("167 days in custody", "हिरासत के दिन")
    assert "numbers differ" in mod.check_translation("charge sheet on day 55", "आरोप-पत्र दिन 55 और 60")


def test_a_translation_that_loses_a_token_or_stays_english_is_rejected():
    en = "Accused-1 is charged under BNS 318(4) and s.479 applies."
    assert mod.check_translation(en, "Accused-1 पर BNS 318(4) के तहत आरोप है और s.479 लागू होती है।") is None
    assert "lost 'Accused-1'" in mod.check_translation(en, "अभियुक्त-1 पर BNS 318(4) के तहत आरोप है और s.479 लागू होती है।")
    assert "lost" in mod.check_translation(en, "Accused-1 पर BNS 318 के तहत आरोप है और s.479 लागू होती है।") or "numbers" in mod.check_translation(
        en, "Accused-1 पर BNS 318 के तहत आरोप है और s.479 लागू होती है।"
    )
    assert mod.check_translation(en, en) == "not in Devanagari"
    assert mod.check_translation(en, "  ") == "empty"
    assert mod.check_translation("born-digital PDF", "x" * 400) is not None


def test_terms_kept_in_english_by_design_are_copied_and_accepted_by_check():
    for term in ("Rights Radar", "fir"):
        assert term in mod.ENGLISH_BY_DESIGN
        assert not mod.needs_model(term)
        assert mod.check_translation(term, term) is None
    for key in ("previous_bail", "trial_stage", "co_accused_bail"):
        assert not mod.needs_model(key)  # a dossier field key shown as a label is code, not prose
    assert mod.needs_model("Previous bail")
    assert mod.needs_model("Rights Radar of the case")
    assert mod.needs_model("fir was filed")


def test_text_with_nothing_to_translate_is_copied_not_sent():
    assert not mod.needs_model("01_fir.pdf")
    assert not mod.needs_model("UNANSWERED:O7")
    assert not mod.needs_model("112/2024")
    assert mod.needs_model("born-digital PDF")
    assert mod.needs_model("objection O6: no supported reply")


def test_collect_lists_tour_texts_then_every_step_text_in_order():
    items = mod.collect(tour_doc())
    keys = [(i.step, i.key) for i in items]
    assert keys[:6] == [(None, "title"), (None, "story"), (None, "variant.offence"), (None, "variant.custody"), (None, "variant.record"), (None, "variant.parity")]
    assert (8, "filled.1.value") in keys and (0, "caption") in keys
    assert len(items) == 6 + 9 * (2 + 4)


def test_hash_and_stale_logic():
    t = tour_doc()
    item = mod.collect(t)[0]
    assert mod.status(t, item) == "missing"
    mod.apply(t, item, "डेमो")
    assert t["hi"]["title"] == "डेमो" and t["hi"]["src"]["title"] == mod.sha(item.en)
    assert mod.status(t, item) == "ok"
    t["title"] = "Demo · Cheating, changed"  # the English moved on
    assert mod.status(t, mod.collect(t)[0]) == "stale"
    assert mod.sha("a") == mod.sha("a") != mod.sha("b")
    # Hindi stored without a hash is not trusted.
    t2 = tour_doc()
    t2["hi"] = {"title": "डेमो"}
    assert mod.status(t2, mod.collect(t2)[0]) == "stale"


def test_apply_builds_variant_and_filled_and_tidy_drops_what_no_longer_exists():
    t = tour_doc()
    for it in mod.collect(t):
        mod.apply(t, it, "हिंदी: " + it.en)
    assert t["hi"]["variant"]["parity"].endswith("Co-accused-2 granted bail")
    assert t["steps"][2]["hi"]["filled"][1] == {"label": "हिंदी: Counsel's answer", "value": "हिंदी: No other pending case"}
    assert mod.pending(t) == []
    del t["steps"][2]["filled"][1]
    del t["variant"]["record"]
    mod.tidy(t)
    assert len(t["steps"][2]["hi"]["filled"]) == 1 and "filled.1.label" not in t["steps"][2]["hi"]["src"]
    assert "record" not in t["hi"]["variant"] and "variant.record" not in t["hi"]["src"]
    assert mod.pending(t) == []


def test_run_translates_once_per_distinct_text_and_a_second_run_sends_nothing():
    tours = {"a": tour_doc(), "b": tour_doc()}
    tr = Counting()
    result = mod.run(tours, tr, size=10)
    assert result["failed"] == {}
    sent = [t for batch in tr.sent for t in batch]
    assert len(sent) == len(set(sent))  # the two identical tours cost one translation each
    assert "01_fir.pdf" not in sent  # a file name is copied, not sent
    assert result["copied"] > 0
    for tour in tours.values():
        assert mod.pending(tour) == []
        assert tour["steps"][0]["hi"]["filled"][0] == {"label": "01_fir.pdf", "value": "हिंदी: born-digital PDF"}
        assert tour["steps"][0]["hi"]["caption"].startswith("हिंदी: Counsel uploaded 11 PDFs")
    again = Counting()
    result2 = mod.run(tours, again, size=10)
    assert again.requests == 0 and result2 == {"translated": 0, "copied": 0, "failed": {}}


def test_only_the_changed_english_is_translated_again():
    tours = {"a": tour_doc()}
    mod.run(tours, Counting(), size=10)
    tours["a"]["steps"][3]["caption"] = "Peshkar found 3 grounds for Accused-1."
    tr = Counting()
    mod.run(tours, tr, size=10)
    assert tr.sent == [["Peshkar found 3 grounds for Accused-1."]]
    assert tours["a"]["steps"][3]["hi"]["caption"] == "हिंदी: Peshkar found 3 grounds for Accused-1."


def test_a_bad_answer_is_asked_for_again_then_left_without_hindi():
    tours = {"a": tour_doc()}
    calls = {"n": 0}

    def wrong_number(texts):
        calls["n"] += 1
        return {n: "हिंदी " + t.replace("167", "176") for n, t in enumerate(texts)}

    result = mod.run(tours, Counting(wrong_number), size=10)
    story = tour_doc()["story"]
    assert story in result["failed"] and "numbers differ" in result["failed"][story]
    assert mod.status(tours["a"], mod.collect(tours["a"])[1]) == "missing"  # the English stays; the interface falls back to it
    # a retry that fixes it is accepted: the first answer is wrong, the second right
    answers = [lambda ts: {}]  # the first request gets no answer at all, every later one is good

    def flaky(texts):
        return (answers.pop(0) if answers else fake)(texts)

    t2 = {"a": tour_doc()}
    assert mod.run(t2, Counting(flaky), size=1000)["failed"] == {}
    assert mod.pending(t2["a"]) == []


def test_batches_respect_the_text_and_character_limits():
    texts = [f"text {i}" for i in range(23)]
    assert [len(b) for b in mod.batches(texts, 10)] == [10, 10, 3]
    assert [len(b) for b in mod.batches(["x" * 100] * 5, size=10, max_chars=250)] == [2, 2, 1]
    assert mod.batches([]) == []
    payload = json.loads(mod.request_payload(["a b", "c d"]))
    assert payload == [{"i": 0, "en": "a b"}, {"i": 1, "en": "c d"}]


def test_parse_answer_reads_the_models_json_and_ignores_the_rest():
    assert mod.parse_answer('noise {"translations": [{"i": 0, "hi": "क"}, {"i": "x", "hi": "y"}, {"i": 1}]} noise') == {0: "क"}
    assert mod.parse_answer("not json") == {}


def write_demo(root: Path, slugs=("01-x", "02-y")) -> Path:
    for s in slugs:
        (root / s).mkdir(parents=True)
        (root / s / "tour.json").write_text(json.dumps(tour_doc(), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return root


def test_dry_run_counts_and_writes_nothing(tmp_path, capsys):
    root = write_demo(tmp_path / "cases")
    before = {p: p.read_bytes() for p in root.glob("*/tour.json")}
    assert mod.main(["--demo-dir", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "dry run:" in out and "requests, nothing written" in out
    assert {p: p.read_bytes() for p in root.glob("*/tour.json")} == before
    plan = mod.plan(mod.load_tours(root), 10)
    assert plan["strings"] == 2 * (6 + 9 * 6) and plan["up_to_date"] == 0
    assert plan["distinct_to_translate"] < plan["to_translate"]  # both tours are the same text
    assert plan["requests"] >= -(-plan["distinct_to_translate"] // 10)


def test_check_fails_for_missing_or_stale_and_passes_when_current(tmp_path, capsys):
    root = write_demo(tmp_path / "cases", ("01-x",))
    assert mod.main(["--demo-dir", str(root), "--check"]) == 1
    tours = mod.load_tours(root)
    mod.run(tours, Counting(), save=lambda slug, t: mod.save_tour(root, slug, t))
    assert mod.main(["--demo-dir", str(root), "--check"]) == 0
    data = json.loads((root / "01-x" / "tour.json").read_text(encoding="utf-8"))
    data["steps"][4]["title"] = "Vakeel drafts again"
    (root / "01-x" / "tour.json").write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    assert mod.main(["--demo-dir", str(root), "--check"]) == 1
    assert "stale step 5 title" in capsys.readouterr().out


def test_saved_file_keeps_the_recorders_format_and_the_english(tmp_path):
    root = write_demo(tmp_path / "cases", ("01-x",))
    original = json.loads((root / "01-x" / "tour.json").read_text(encoding="utf-8"))
    tours = mod.load_tours(root)
    mod.run(tours, Counting(), save=lambda slug, t: mod.save_tour(root, slug, t))
    text = (root / "01-x" / "tour.json").read_text(encoding="utf-8")
    saved = json.loads(text)
    assert text.endswith("}\n") and "हिंदी" in text  # UTF-8 as is, not \u escapes
    stripped = copy.deepcopy(saved)
    stripped.pop("hi")
    for s in stripped["steps"]:
        s.pop("hi")
    assert stripped == original  # nothing of the English changed


def test_the_committed_tours_load_and_every_text_is_found():
    tours = mod.load_tours(REPO / "demo" / "cases")
    assert len(tours) >= 6
    for slug, tour in tours.items():
        items = mod.collect(tour)
        assert len(items) > 50, slug
        assert any(mod.protected_tokens(it.en) for it in items)


def test_a_status_word_or_id_in_front_of_a_sentence_is_never_sent_to_the_model():
    assert mod.split_prefix("SUPPORTED: The charge sheet was filed.") == ("SUPPORTED: ", "The charge sheet was filed.")
    assert mod.split_prefix("G4 · antecedents") == ("G4 · ", "antecedents")
    assert mod.split_prefix("born-digital PDF") == ("", "born-digital PDF")
    seen: list[str] = []

    def translator(texts: list[str]) -> dict[int, str]:
        seen.extend(texts)
        return {n: "आरोप पत्र दाखिल किया गया।" for n, _ in enumerate(texts)}

    done, why = mod.translate_texts(["SUPPORTED: The charge sheet was filed."], translator)
    assert seen == ["The charge sheet was filed."]
    assert done == {"SUPPORTED: The charge sheet was filed.": "SUPPORTED: आरोप पत्र दाखिल किया गया।"} and not why
