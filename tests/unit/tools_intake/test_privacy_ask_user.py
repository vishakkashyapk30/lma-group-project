"""pseudonymise and ask_user (plan §4.3, §16)."""

from __future__ import annotations

import pytest

from tests.fakes.toolbox import PSEUDONYM_ALIASES, leaked_names
from tests.unit.tools_intake._helpers import assert_rejects, install_counsel, patch_everywhere
from vakeel_sahayak.tools.interaction import ask_user
from vakeel_sahayak.tools.intake.privacy_tool import pseudonymise


class _Map:
    """Minimal alias map used by the fake pseudonymiser."""

    def restore(self, text: str) -> str:
        return text


def _fake_pseudonymise_text(text, case_id, mapping=None):
    for name, alias in PSEUDONYM_ALIASES.items():
        text = text.replace(name, alias)
    return text, _Map()


def test_pseudonymise_removes_planted_names(monkeypatch, planted_names):
    """Plan §16: names are replaced by roles after OCR and before text leaves the laptop."""
    patch_everywhere(monkeypatch, "vakeel_sahayak.privacy.pseudonymise", "pseudonymise_text", _fake_pseudonymise_text)
    text = f"{planted_names[0]} was arrested on the complaint of {planted_names[1]}. Co-accused {planted_names[2]}."
    out = pseudonymise(text, "case-0007")
    assert isinstance(out, str)
    assert leaked_names([out], planted_names) == []
    assert "Accused-1" in out and "Complainant-1" in out


def test_pseudonymise_keeps_dates_and_sections(monkeypatch, planted_names):
    """Only names change: dates, sections and FIR numbers survive pseudonymisation."""
    patch_everywhere(monkeypatch, "vakeel_sahayak.privacy.pseudonymise", "pseudonymise_text", _fake_pseudonymise_text)
    out = pseudonymise(f"{planted_names[0]} arrested 20.08.2024 under Section 318(4) BNS, FIR 112/2024.", "case-0007")
    assert all(tok in out for tok in ("20.08.2024", "318(4)", "112/2024"))


def test_pseudonymise_rejects_empty_case_id():
    """The alias map is per case, so a case id is required."""
    assert_rejects(pseudonymise, "text", "")


# ---- ask_user ----------------------------------------------------------------------------------------------------
UNREADABLE = [f"Page {p} of the FIR is unreadable. Can you upload a clearer copy?" for p in (2, 3, 5)]
OTHERS = [
    "Has the charge sheet been filed? If so, please upload the order.",
    "Is there a jail custody certificate for the accused?",
    "Was any co-accused granted bail?",
    "What is the police station of the FIR?",
]


def test_ask_user_passes_up_to_three_questions_and_returns_answers(monkeypatch):
    """Up to 3 questions are asked in one round and answered in order."""
    channel = install_counsel(monkeypatch)
    answers = ask_user(OTHERS[:2], "case-0007")
    assert channel.asked == OTHERS[:2]
    assert len(answers) == 2 and all(isinstance(a, str) for a in answers)


def test_ask_user_three_questions_are_all_asked(monkeypatch):
    """Exactly the limit of three is allowed."""
    channel = install_counsel(monkeypatch)
    ask_user(OTHERS[:3], "case-0007")
    assert channel.asked == OTHERS[:3]


def test_ask_user_never_asks_more_than_three_per_round(monkeypatch):
    """Plan §4.3: at most 3 questions per round. ASSUMPTION: extra questions are deferred, not raised as an error."""
    channel = install_counsel(monkeypatch)
    answers = ask_user(OTHERS + ["Is the accused a first-time offender?"], "case-0007")
    assert channel.asked == OTHERS[:3], "only the first three are put to counsel; the rest are deferred"
    assert len(answers) == 3


def test_ask_user_groups_unreadable_pages_into_one_question(monkeypatch):
    """Plan §4.3: three unreadable pages are ONE question naming all three pages."""
    channel = install_counsel(monkeypatch)
    ask_user(UNREADABLE, "case-0007")
    assert len(channel.asked) == 1
    assert all(str(p) in channel.asked[0] for p in (2, 3, 5))


def test_grouping_unreadable_pages_leaves_room_for_other_questions(monkeypatch):
    """Three unreadable pages + two other questions = 3 questions asked (one grouped), none deferred."""
    channel = install_counsel(monkeypatch)
    ask_user(UNREADABLE + OTHERS[:2], "case-0007")
    assert len(channel.asked) == 3
    assert OTHERS[0] in channel.asked and OTHERS[1] in channel.asked
    assert sum(all(str(p) in q for p in (2, 3, 5)) for q in channel.asked) == 1


def test_ask_user_empty_question_list_asks_nothing(monkeypatch):
    """No questions, no interrupt."""
    channel = install_counsel(monkeypatch)
    assert ask_user([], "case-0007") == []
    assert channel.payloads == []


@pytest.mark.parametrize("questions", [[""], ["   "]])
def test_ask_user_rejects_blank_questions(monkeypatch, questions):
    """A blank question is a bug in the caller and is rejected."""
    install_counsel(monkeypatch)
    assert_rejects(ask_user, questions, "case-0007")
