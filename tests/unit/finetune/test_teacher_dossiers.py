"""Fine-tuning data step 1 (plan §12, §17): the teacher reads the facts section of ~4K TRAIN orders and outputs a CaseDossier, quoting a
source sentence for each field. It runs as an Ada interactive shard (about 5 h), saves each output as it finishes and resumes from what
is on disk, so a session that ends after 6 hours loses nothing.

The teacher is replaced by a spy on `TeacherClient.dossier_from_facts` (no GPU, no API). Orders file rows: {"doc_id", "facts"}.
# ASSUMPTION: a shard is the set of orders whose position i satisfies i % n_shards == shard; tests only rely on the shards being
# disjoint and complete. Output rows are the pair rows of tests/unit/finetune/_helpers.py.
"""

from __future__ import annotations

import inspect

import pytest

from tests.unit.finetune._helpers import read_rows, teacher_dossier, valued_fields, write_jsonl
from vakeel_sahayak.finetune.teacher_dossiers import run_shard
from vakeel_sahayak.schemas.dossier import CaseDossier


class Teacher:
    """Spy teacher: returns the case-0007 teacher dossier for any facts text; optionally dies on the k-th call (session killed)."""

    def __init__(self, die_on_call: int | None = None) -> None:
        self.seen: list[str] = []
        self.die_on_call = die_on_call

    def __call__(self, facts_text: str) -> CaseDossier:
        if self.die_on_call is not None and len(self.seen) + 1 == self.die_on_call:
            raise KeyboardInterrupt("the Ada session ended")
        self.seen.append(facts_text)
        return CaseDossier.model_validate(teacher_dossier())


def install(monkeypatch, teacher: Teacher) -> Teacher:
    monkeypatch.setattr("vakeel_sahayak.models.teacher.TeacherClient.dossier_from_facts", lambda self, text: teacher(text))
    return teacher


def orders(tmp_path, n: int):
    rows = [{"doc_id": f"o{i:03d}", "facts": f"Facts of order {i}: arrested on 20.08.2024."} for i in range(n)]
    return write_jsonl(tmp_path / "orders.jsonl", rows), rows


def test_signature():
    assert list(inspect.signature(run_shard).parameters) == ["orders_path", "out_path", "shard", "n_shards"]


def test_one_dossier_per_order_with_a_quote_for_every_valued_field(tmp_path, monkeypatch):
    """Plan §12 step 1: the output for each order is a CaseDossier in which each field quotes a source sentence."""
    teacher = install(monkeypatch, Teacher())
    path, rows = orders(tmp_path, 6)
    out = tmp_path / "dossiers.jsonl"
    assert run_shard(str(path), str(out), 0, 1) == 6
    saved = read_rows(out)
    assert [r["doc_id"] for r in saved] == [r["doc_id"] for r in rows]
    assert teacher.seen == [r["facts"] for r in rows]
    for r in saved:
        dossier = r["dossier"]
        CaseDossier.model_validate(dossier)
        for name in valued_fields(dossier):
            assert dossier["fields"][name]["source"]["quote"], name
        assert r["facts"] in teacher.seen


def test_shards_are_disjoint_and_together_cover_every_order(tmp_path, monkeypatch):
    """4 shards of 10 orders: each order is done by exactly one shard (no duplicated teacher work across the three accounts)."""
    install(monkeypatch, Teacher())
    path, rows = orders(tmp_path, 10)
    done = []
    for shard in range(4):
        out = tmp_path / f"d{shard}.jsonl"
        n = run_shard(str(path), str(out), shard, 4)
        ids = [r["doc_id"] for r in read_rows(out)]
        assert n == len(ids) > 0
        done.append(ids)
    flat = [i for ids in done for i in ids]
    assert sorted(flat) == [r["doc_id"] for r in rows] and len(flat) == len(set(flat))


def test_each_output_is_saved_as_soon_as_it_finishes(tmp_path, monkeypatch):
    """If the session dies on the third order, the first two dossiers are already on disk (plan §17: saved per case)."""
    install(monkeypatch, Teacher(die_on_call=3))
    path, _ = orders(tmp_path, 8)
    out = tmp_path / "d.jsonl"
    with pytest.raises(KeyboardInterrupt):
        run_shard(str(path), str(out), 0, 1)
    assert [r["doc_id"] for r in read_rows(out)] == ["o000", "o001"]


def test_a_rerun_resumes_where_the_last_session_stopped(tmp_path, monkeypatch):
    """Resume: after the interrupted run, a second run asks the teacher only for the six missing orders and leaves no duplicates."""
    path, rows = orders(tmp_path, 8)
    out = tmp_path / "d.jsonl"
    install(monkeypatch, Teacher(die_on_call=3))
    with pytest.raises(KeyboardInterrupt):
        run_shard(str(path), str(out), 0, 1)
    second = install(monkeypatch, Teacher())
    run_shard(str(path), str(out), 0, 1)
    assert second.seen == [r["facts"] for r in rows[2:]]
    ids = [r["doc_id"] for r in read_rows(out)]
    assert ids == [r["doc_id"] for r in rows]


def test_a_finished_shard_does_nothing_when_rerun(tmp_path, monkeypatch):
    path, _ = orders(tmp_path, 5)
    out = tmp_path / "d.jsonl"
    install(monkeypatch, Teacher())
    run_shard(str(path), str(out), 0, 1)
    again = install(monkeypatch, Teacher())
    run_shard(str(path), str(out), 0, 1)
    assert again.seen == [] and len(read_rows(out)) == 5


@pytest.mark.parametrize(("shard", "n_shards"), [(2, 2), (-1, 3), (0, 0)])
def test_a_shard_index_outside_the_range_is_rejected(tmp_path, monkeypatch, shard, n_shards):
    """ASSUMPTION: shard must satisfy 0 <= shard < n_shards, and the teacher is never called for a bad index."""
    teacher = install(monkeypatch, Teacher())
    path, _ = orders(tmp_path, 4)
    with pytest.raises(ValueError):
        run_shard(str(path), str(tmp_path / "d.jsonl"), shard, n_shards)
    assert teacher.seen == []


def test_the_run_never_touches_the_laptop_only_case_files(tmp_path, monkeypatch):
    """The teacher reads public orders only (plan §17, models.yaml `public_orders_only`): only the facts text reaches it, never a path."""
    teacher = install(monkeypatch, Teacher())
    path, rows = orders(tmp_path, 3)
    run_shard(str(path), str(tmp_path / "d.jsonl"), 0, 1)
    assert all(str(tmp_path) not in text for text in teacher.seen)
    assert teacher.seen == [r["facts"] for r in rows]
