"""`transfer_check` (plan §5.4): SAME_TEXT / CHANGED / NEW flags for IPC-era precedents applied to BNS-era cases.

* SAME_TEXT: carried over unchanged, so the precedent applies.
* CHANGED: split, merged or reworded: usable only with a qualification, which the brief must state.
* NEW: no IPC equivalent.
# ASSUMPTION: store-level tests build a ConcordanceStore from `source_dir/concordance_edges.jsonl` (see test_map_section).
"""

import pytest

from tests.unit.tools_law_case._helpers import write_jsonl
from vakeel_sahayak.schemas.enums import TransferFlag
from vakeel_sahayak.stores.law_concordance import ConcordanceStore
from vakeel_sahayak.tools.law.concordance import transfer_check
from vakeel_sahayak.tools.types import TransferCheckResult


@pytest.fixture()
def store(tmp_path, concordance_edges):
    src, out = tmp_path / "s", tmp_path / "o"
    src.mkdir()
    out.mkdir()
    write_jsonl(src / "concordance_edges.jsonl", [e.model_dump(mode="json") for e in concordance_edges])
    s = ConcordanceStore()
    s.build(str(src), str(out))
    s.open(str(out))
    return s


@pytest.mark.parametrize(
    ("old", "new", "flag"),
    [
        ("IPC 406", "BNS 316(2)", TransferFlag.SAME_TEXT),
        ("CrPC 439", "BNSS 483", TransferFlag.SAME_TEXT),
        ("IPC 420", "BNS 318(4)", TransferFlag.CHANGED),  # plan §8.1: DLHC-2021-0420 interprets IPC 420, wording differs
        ("IPC 999", "BNS 888(1)", TransferFlag.CHANGED),  # split
        ("IPC 777", "BNS 666", TransferFlag.CHANGED),  # merged
        ("CrPC 436A", "BNSS 479", TransferFlag.CHANGED),  # reworded
        ("", "BNS 111", TransferFlag.NEW),  # ASSUMPTION: an empty old_ref means no IPC equivalent
    ],
)
def test_store_flags(store, old, new, flag):
    """Flag table for the tiny concordance."""
    res = store.transfer_flag(old, new)
    assert isinstance(res, TransferCheckResult)
    assert res.flag == flag


def test_changed_carries_a_diff_and_a_qualification(store):
    """CHANGED is usable only with a qualification the brief must state, and shows the text diff."""
    res = store.transfer_flag("IPC 420", "BNS 318(4)")
    assert res.text_diff and "wording" in res.text_diff
    assert res.qualification and "IPC 420" in res.qualification and "BNS 318(4)" in res.qualification


def test_same_text_needs_no_qualification(store):
    """SAME_TEXT precedents apply as they are."""
    assert store.transfer_flag("IPC 406", "BNS 316(2)").qualification in (None, "")


def test_tool_passes_flag_through(install_stores):
    """The transfer_check tool returns the store's flag."""
    install_stores()
    assert transfer_check("IPC 406", "BNS 316(2)").flag == TransferFlag.SAME_TEXT
    assert transfer_check("IPC 420", "BNS 318(4)").flag == TransferFlag.CHANGED
