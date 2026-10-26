"""The run manifest records the code that ran: git_sha, git_dirty and code_tree_hash."""

from __future__ import annotations

import re

from vakeel_sahayak.eval.runners import driver
from vakeel_sahayak.orchestration.switches import Switches


def test_manifest_has_code_stamp(tmp_path):
    m = driver.write_run_manifest(tmp_path, system="full", switches=Switches(), seed=1)
    assert m["git_sha"] == "unknown" or re.fullmatch(r"[0-9a-f]{40}", m["git_sha"])
    assert isinstance(m["git_dirty"], bool)
    assert re.fullmatch(r"[0-9a-f]{64}", m["code_tree_hash"])


def test_tree_hash_changes_with_a_source_edit(monkeypatch, tmp_path):
    (tmp_path / "src").mkdir()
    f = tmp_path / "src" / "a.py"
    f.write_text("x = 1\n")
    monkeypatch.setattr(driver, "REPO", tmp_path)
    monkeypatch.setattr(driver, "_git", lambda *a: "src/a.py\0")
    driver.code_tree_hash.cache_clear()
    first = driver.code_tree_hash()
    f.write_text("x = 2\n")
    driver.code_tree_hash.cache_clear()
    assert driver.code_tree_hash() != first
    driver.code_tree_hash.cache_clear()
