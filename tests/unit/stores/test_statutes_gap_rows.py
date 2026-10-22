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
