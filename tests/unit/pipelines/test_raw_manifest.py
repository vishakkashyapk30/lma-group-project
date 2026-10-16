"""`data/raw/MANIFEST.json`: provenance of every raw dataset, blocked datasets with the exact team action, no secrets."""

from __future__ import annotations

import json

from vakeel_sahayak.pipelines.raw_manifest import build_manifest


def test_blocked_and_optional_datasets_are_listed_with_actions(tmp_path):
    m = build_manifest(str(tmp_path))["datasets"]
    assert m["hldc"]["status"] == "blocked"
    assert "Exploration-Lab/IL-TUR" in m["hldc"]["team_action"]
    assert m["kathbath"]["status"] == "blocked"
    assert m["escr_hindi"]["status"] == "not_attempted"
    assert m["open_india_law"]["status"] == "missing"
    assert (tmp_path / "MANIFEST.json").is_file()


def test_ipc2bns_files_get_a_sha256_and_the_pinned_commit(tmp_path):
    root = tmp_path / "ipc2bns_verify" / "data"
    root.mkdir(parents=True)
    (root / "a.csv").write_text("x", encoding="utf-8")
    entry = build_manifest(str(tmp_path))["datasets"]["ipc2bns_verify"]
    assert entry["status"] == "complete"
    assert "8d3e77024b3693d21ccae39bffb81641329a4900" in entry["revision"]
    assert entry["files"][0]["sha256"] == "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"


def test_kathbath_subset_is_reported_as_partial(tmp_path):
    root = tmp_path / "kathbath" / "hindi" / "test_known"
    (root / "audio").mkdir(parents=True)
    (root / "audio" / "u1.m4a").write_bytes(b"abc")
    (root / "transcription_n2w.txt").write_text("u1.m4a\tनमस्ते\nu2.m4a\tधन्यवाद\n", encoding="utf-8")
    (root / "manifest.jsonl").write_text(json.dumps({"audio": "audio/u1.m4a", "bytes": 3, "sha256": "x", "transcript": "नमस्ते"}) + "\n", encoding="utf-8")
    entry = build_manifest(str(tmp_path))["datasets"]["kathbath"]
    assert entry["status"] == "partial"
    assert "first 1 of 2 utterances" in entry["what_was_taken"]
    assert "team_action" in entry["blocked_route"]


def test_manifest_holds_no_secret_like_strings(tmp_path):
    build_manifest(str(tmp_path))
    text = (tmp_path / "MANIFEST.json").read_text(encoding="utf-8").lower()
    for needle in ("hf_", "token=", "bearer", "api_key"):
        assert needle not in text.replace("huggingface_hub", "")
