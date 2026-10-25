"""law.statutes build merges official-source gap rows from <data>/gaps/statutes/*.jsonl."""

import json

from vakeel_sahayak.stores.law_statutes import StatuteStore


def test_gap_rows_are_merged(tmp_path):
    interim = tmp_path / "interim"
    gaps = tmp_path / "gaps" / "statutes"
    interim.mkdir()
    gaps.mkdir(parents=True)
    (interim / "statutes.jsonl").write_text(json.dumps({"code": "IPC", "section": "420", "text": "cheating"}) + "\n")
    (gaps / "crpc.jsonl").write_text(
        json.dumps({"code": "crpc", "section": "436", "text": "bail in bailable offence", "source_url": "x"}) + "\n"
    )
    out = tmp_path / "out"
    store = StatuteStore()
    store.build(str(interim), str(out))
    store.open(str(out))
    try:
        assert store.count() == 2
        assert store.get("CrPC", "436").text == "bail in bailable offence"
    finally:
        store.close()


def test_flags_only_gap_row_adds_flags_and_keeps_text(tmp_path):
    interim = tmp_path / "interim"
    gaps = tmp_path / "gaps" / "statutes"
    interim.mkdir()
    gaps.mkdir(parents=True)
    (interim / "statutes.jsonl").write_text(json.dumps({"code": "IPC", "section": "420", "text": "cheating"}) + "\n")
    (gaps / "first_schedule_ipc.jsonl").write_text(
        json.dumps({"code": "IPC", "section": "420", "text": "", "bailable": False, "cognisable": True})
        + "\n"
        + json.dumps({"code": "IPC", "section": "9999", "text": "", "bailable": True})  # not in the store: no new row
        + "\n"
    )
    out = tmp_path / "out"
    store = StatuteStore()
    store.build(str(interim), str(out))
    store.open(str(out))
    try:
        assert store.count() == 1
        row = store.get("IPC", "420")
        assert (row.text, row.bailable, row.cognisable) == ("cheating", False, True)
    finally:
        store.close()
