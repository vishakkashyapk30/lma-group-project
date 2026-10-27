"""Quasi-identifiers and the per-case date shift on the wire to a hosted model (plan §16; privacy/quasi.py).

The local text keeps every real value; only what a hosted model receives is changed, and its reply is turned back. All inputs below are
constructed sentences (no client data, no labels): each test states what must be replaced, what must stay, and what must come back.
"""

from __future__ import annotations

import datetime as dt
import re

import pytest

from vakeel_sahayak.models.openai.adapters import OpenAILLMClient
from vakeel_sahayak.models.openai.api import ChatResult
from vakeel_sahayak.models.sarvam.policy import DataClass, public_source_scope
from vakeel_sahayak.privacy.boundary import PrivacyBoundaryError, assert_pseudonymised, name_token_leaks
from vakeel_sahayak.privacy.pseudonymise import PseudonymMap, pseudonymise_text
from vakeel_sahayak.privacy.quasi import (
    ALIAS_RE,
    DATE_RE,
    SHIFT_RANGE,
    WireCodec,
    age_band,
    deterministic_shift,
    find_quasi,
    random_shift,
    shift_dates,
    unshift_dates,
)

SHIFT = -91
ORDER = (
    "FIR No. 87/2023 was registered at Hili police station. The applicant, aged about 38 years, R/o Village Kandaber, P.S. Barkagaon, "
    "District Hazaribagh, PIN - 825301, was arrested on 03.02.2023 under Sections 21(c), 22(c) and 27A of the NDPS Act read with "
    "Section 34 IPC. Vehicle JH01AB1234 was seized. BA No. 9258 of 2023 was heard by the High Court of Jharkhand at Ranchi on "
    "16th February, 2024. A/c No. 123456789012 with IFSC SBIN0001234 and UPI ram.k@okaxis; mobile 98765 43210; mail ram@example.com; "
    "PAN ABCDE1234F; voter ID ABC1234567; passport K1234567; D.O.B. 12.03.1985; H.No. 12/4, Station Road. The surety is R/o Mangalwari."
)
CATEGORIES_IN_ORDER = {"FIR", "PS", "AGE", "PLACE", "ADDRESS", "PIN", "VEHICLE", "CASE", "ACCOUNT", "AADHAAR", "IFSC", "UPI", "PHONE", "EMAIL", "PAN", "VOTER-ID",
                       "PASSPORT", "DOB", "HOUSE"}  # the 12-digit account number also reads as an Aadhaar number


def codec(mapping: PseudonymMap | None = None) -> WireCodec:
    return WireCodec(mapping or PseudonymMap(), SHIFT)


def _date(s: str) -> dt.date:
    from vakeel_sahayak.privacy.quasi import _parts

    _form, d, m, y = _parts(DATE_RE.fullmatch(s))
    return dt.date(y, m, d)


def test_every_category_is_replaced_by_an_alias():
    assert set(find_quasi(ORDER)) == CATEGORIES_IN_ORDER
    sent = codec().encode_text(ORDER)
    assert find_quasi(sent) == []
    for raw in ("87/2023", "Hili", "Kandaber", "Barkagaon", "825301", "JH01AB1234", "9258", "123456789012", "SBIN0001234", "ram.k@okaxis",
                "98765 43210", "ram@example.com", "ABCDE1234F", "ABC1234567", "K1234567", "12.03.1985", "12/4", "Station Road", "38 years", "Mangalwari"):
        assert raw not in sent, raw


def test_legal_content_and_coarse_places_stay():
    """Sections, acts, the court, the district and the FIR year are not masked."""
    sent = codec().encode_text(ORDER)
    for kept in ("Sections 21(c), 22(c) and 27A of the NDPS Act", "Section 34 IPC", "High Court of Jharkhand at Ranchi", "District Hazaribagh", "/2023 was registered",
                 "of 2023"):
        assert kept in sent, kept


def test_fir_number_keeps_its_year_and_age_keeps_its_band():
    sent = codec().encode_text("FIR No. 87/2023 and the accused, aged 19 years.")
    assert re.search(r"FIR No\. \[FIR-1\]/2023", sent)
    assert "[AGE-1 18-25]" in sent
    assert [age_band(a) for a in (15, 18, 25, 26, 40, 60, 70)] == ["under-18", "18-25", "18-25", "26-35", "36-50", "51-64", "65-plus"]


def test_aliases_are_consistent_within_and_across_calls_of_a_case():
    mapping = PseudonymMap()
    first = codec(mapping).encode_text("P.S. Barkagaon registered the FIR. Later P.S. Barkagaon arrested him. Vehicle JH01AB1234.")
    assert first.count("[PS-1]") == 2
    second = codec(mapping).encode_text("Vehicle JH01AB1234 was released by P.S. Barkagaon.")
    assert "[VEHICLE-1]" in second and "[PS-1]" in second


def test_reply_is_restored_exactly():
    c = codec()
    sent = c.encode_text(ORDER)
    assert c.decode_text(sent) == ORDER
    assert ALIAS_RE.search(sent)


@pytest.mark.parametrize(
    ("written", "shifted"),
    [
        ("03.02.2023", "04.11.2022"),
        ("3.2.2023", "4.11.2022"),
        ("03/02/2023", "04/11/2022"),
        ("03-02-23", "04-11-22"),
        ("2023-02-03", "2022-11-04"),
        ("3rd February, 2023", "4th November, 2022"),
        ("03 Feb 2023", "04 Nov 2022"),
        ("3-Feb-2023", "4-Nov-2022"),
        ("FEBRUARY 3, 2023", "NOVEMBER 4, 2022"),
        ("3rd day of February 2023", "4th day of November 2022"),
    ],
)
def test_every_date_form_moves_by_the_same_shift_in_its_own_format(written, shifted):
    table: dict[str, str] = {}
    assert shift_dates(written, SHIFT, table) == shifted
    assert unshift_dates(shifted, SHIFT, table) == written  # exact, through the table of what was sent
    assert _date(unshift_dates(shifted, SHIFT)) == _date(written)  # and the same day by arithmetic alone


def test_the_shift_preserves_intervals_and_weekdays():
    """Custody days, the 60/90-day clock and s.479 BNSS arithmetic give the same answer on the shifted dates."""
    text = "Arrested on 03.02.2023; charge sheet filed on 2023-05-04; bail heard on 16th February, 2024."
    sent = shift_dates(text, SHIFT)
    real = [_date(m.group(0)) for m in DATE_RE.finditer(text)]
    moved = [_date(m.group(0)) for m in DATE_RE.finditer(sent)]
    assert [(b - a).days for a, b in zip(real, real[1:], strict=False)] == [(b - a).days for a, b in zip(moved, moved[1:], strict=False)]
    assert [d.weekday() for d in real] == [d.weekday() for d in moved]
    assert all(m - r == dt.timedelta(days=SHIFT) for r, m in zip(real, moved, strict=True))


def test_a_date_the_model_computed_from_a_shifted_date_comes_back_real():
    c = codec()
    sent = c.encode_text("The applicant was arrested on 03.02.2023.")
    arrest_sent = _date(DATE_RE.search(sent).group(0))
    reply = f"The 90-day period ended on {(arrest_sent + dt.timedelta(days=90)).isoformat()}."
    assert c.decode_text(reply) == f"The 90-day period ended on {(dt.date(2023, 2, 3) + dt.timedelta(days=90)).isoformat()}."


def test_invalid_dates_and_section_lists_are_left_alone():
    for text in ("Sections 302/34/120B IPC", "31.02.2023", "u/s 21/22/29 NDPS", "Order No.04/Dated", "HPHC010225332022", "(2022) 10 SCC 51"):
        assert shift_dates(text, SHIFT) == text


def test_shifts_are_negative_whole_weeks_in_range():
    for value in [random_shift() for _ in range(50)] + [deterministic_shift(f"t1-{i:03d}") for i in range(50)]:
        assert SHIFT_RANGE[0] <= value <= SHIFT_RANGE[1] and value % 7 == 0
    assert deterministic_shift("t1-001") == deterministic_shift("t1-001")


def test_intake_learns_the_values_and_the_shift_but_keeps_the_local_text():
    """The dossier and the date tools read the local text, so it keeps the real FIR number, station and dates."""
    text = "The accused Ramesh Kumar Yadav was arrested on 20.08.2024 in FIR No. 112/2024 of P.S. Kotwali."
    out, mapping = pseudonymise_text(text, "case-0007")
    assert "Ramesh Kumar Yadav" not in out
    assert "FIR No. 112/2024" in out and "P.S. Kotwali" in out and "20.08.2024" in out
    assert mapping.date_shift_days is not None and mapping.quasi_original("[FIR-1]") == "112"
    again = PseudonymMap.from_dict(mapping.to_dict())
    assert again.date_shift_days == mapping.date_shift_days and again.quasi_alias("PS", "Kotwali", "Kotwali") == mapping.quasi_alias("PS", "Kotwali", "Kotwali")
    assert again.restore("[PS-1]") == "Kotwali"


def test_relatives_named_by_the_relation_word_are_pseudonymised():
    out, mapping = pseudonymise_text("His father Ram Lal and his wife Smt. Sunita Devi stood surety.", "case-0007")
    assert "Ram Lal" not in out and "Sunita Devi" not in out
    assert mapping.restore(out) == "His father Ram Lal and his wife Smt. Sunita Devi stood surety."


def test_wire_boundary_refuses_quasi_identifiers_and_accepts_the_encoded_text():
    with pytest.raises(PrivacyBoundaryError, match="quasi-identifier"):
        assert_pseudonymised({"prompt": "FIR No. 87/2023 of Hili police station"}, wire=True)
    assert_pseudonymised({"prompt": codec().encode_text("FIR No. 87/2023 of Hili police station")}, wire=True)


def test_default_boundary_is_unchanged_for_the_agents_own_guard():
    """The agents' guard (laptop and Ada side) keeps its old rule: a real FIR number in local case data is not a refusal there."""
    assert_pseudonymised({"prompt": "FIR No. 87/2023 of Hili police station, arrested on 03.02.2023."})


def test_wire_boundary_refuses_a_learned_name_left_in_part_or_glued():
    mapping = PseudonymMap()
    mapping.alias_for("Teerath Prasad Kushwaha", "accused")
    assert name_token_leaks("statement of TEERATH PRASHADKUSHWAHA", mapping.known_names()) == ["Teerath", "Kushwaha"]
    with pytest.raises(PrivacyBoundaryError, match="learned name"):
        assert_pseudonymised({"prompt": "the call made by Kushwaha"}, mapping=mapping, wire=True)
    assert_pseudonymised({"prompt": "the call made by Accused-1"}, mapping=mapping, wire=True)


class FakeApi:
    def __init__(self, answer: str) -> None:
        self.sent: list = []
        self.answer = answer

    def chat(self, messages, **_kw):  # noqa: ANN001
        self.sent.append(messages)
        return ChatResult(text=self.answer, prompt_tokens=1, completion_tokens=1)


def test_hosted_client_sends_the_wire_form_and_returns_real_values(monkeypatch):
    monkeypatch.setenv("VS_EXTERNAL", "pseudonymised")
    mapping = PseudonymMap()
    mapping.date_shift_days = SHIFT
    api = FakeApi('{"fir": "[FIR-1]/2023", "arrest_date": "2022-11-04"}')
    llm = OpenAILLMClient(api=api, data=DataClass.CLIENT_TEXT, where="ada")
    with public_source_scope("eval-test", mapping=lambda: mapping):
        reply = llm.chat([{"role": "user", "content": "Accused-1 was arrested on 03.02.2023 in FIR No. 87/2023 of Hili police station."}])
    sent = api.sent[0][0]["content"]
    assert "87/2023" not in sent and "Hili" not in sent and "03.02.2023" not in sent and "04.11.2022" in sent
    assert reply == '{"fir": "87/2023", "arrest_date": "2023-02-03"}'
