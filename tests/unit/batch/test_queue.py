"""Persistent job queue for the batch desk (plan §11 stage 2, §17 resumable shards).

Files are enqueued and get case ids; `next_stage2` picks cases for full runs within the session's GPU budget in urgency
order; `mark_done` persists so an interrupted shard resumes where it stopped.

ASSUMPTIONS: `TriageQueue(db_path)` opens or creates a SQLite file (skeleton fix: the class had no constructor, yet
resuming needs a path); a full run costs a fixed positive number of GPU-hours per case, so budget 0 selects nothing,
a very large budget selects every pending case, and a smaller budget selects a prefix of what a larger one selects;
a finished case is never offered again, also after reopening the same path.
"""

from __future__ import annotations

import pytest

from vakeel_sahayak.batch.queue import TriageQueue

HUGE = 10_000.0  # GPU-hours: far more than enough for any test fixture


@pytest.fixture()
def files(tmp_path):
    paths = []
    for i in range(4):
        p = tmp_path / f"case_file_{i}.pdf"
        p.write_bytes(f"%PDF-1.4 synthetic {i}".encode())
        paths.append(str(p))
    return paths


@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "queue.sqlite")


def test_enqueue_returns_one_distinct_case_id_per_file(db, files):
    """Plan §11: enqueue_files returns the case ids, one per uploaded file, all distinct."""
    q = TriageQueue(db)
    ids = q.enqueue_files(files)
    assert len(ids) == len(files)
    assert len(set(ids)) == len(files)
    assert all(isinstance(i, str) and i for i in ids)


def test_huge_budget_selects_every_pending_case_once(db, files):
    """Plan §11: with an unlimited budget all enqueued cases are selected, none twice."""
    q = TriageQueue(db)
    ids = q.enqueue_files(files)
    picked = q.next_stage2(HUGE)
    assert sorted(picked) == sorted(ids)
    assert len(picked) == len(set(picked))


def test_zero_budget_selects_nothing(db, files):
    """Plan §11: no GPU budget, no full runs."""
    q = TriageQueue(db)
    q.enqueue_files(files)
    assert q.next_stage2(0.0) == []


def test_smaller_budget_selects_a_prefix_of_the_larger_budget_order(db, files):
    """Plan §11: the selection follows one urgency order, so a smaller budget gets a prefix of a larger one's list."""
    q = TriageQueue(db)
    q.enqueue_files(files)
    full = q.next_stage2(HUGE)
    for budget in (0.5, 1.0, 2.0, 4.0):
        part = q.next_stage2(budget)
        assert part == full[: len(part)]
        assert len(part) <= len(full)


def test_selection_is_nondecreasing_in_the_budget(db, files):
    """Plan §11: more budget never selects fewer cases."""
    q = TriageQueue(db)
    q.enqueue_files(files)
    sizes = [len(q.next_stage2(b)) for b in (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, HUGE)]
    assert sizes == sorted(sizes)
    assert sizes[0] == 0 and sizes[-1] == len(files)


def test_done_cases_are_not_offered_again(db, files):
    """Plan §11/§17: a finished case is not repeated."""
    q = TriageQueue(db)
    ids = q.enqueue_files(files)
    first = q.next_stage2(HUGE)[0]
    q.mark_done(first)
    again = q.next_stage2(HUGE)
    assert first not in again
    assert sorted(again) == sorted(set(ids) - {first})


def test_all_done_leaves_nothing_to_run(db, files):
    """Plan §17: when every case is done the shard is finished."""
    q = TriageQueue(db)
    for cid in q.enqueue_files(files):
        q.mark_done(cid)
    assert q.next_stage2(HUGE) == []


def test_done_state_survives_a_new_queue_instance_on_the_same_path(db, files):
    """Plan §17: a session that ends resumes: a new TriageQueue on the same path remembers what is done and pending."""
    q1 = TriageQueue(db)
    ids = q1.enqueue_files(files)
    done = q1.next_stage2(HUGE)[:2]
    for cid in done:
        q1.mark_done(cid)
    q2 = TriageQueue(db)  # the interrupted shard is restarted
    remaining = q2.next_stage2(HUGE)
    assert sorted(remaining) == sorted(set(ids) - set(done))


def test_two_queues_on_different_paths_are_independent(tmp_path, files):
    """Plan §17: state belongs to the queue file, not to the process."""
    a = TriageQueue(str(tmp_path / "a.sqlite"))
    b = TriageQueue(str(tmp_path / "b.sqlite"))
    a.enqueue_files(files)
    assert b.next_stage2(HUGE) == []
