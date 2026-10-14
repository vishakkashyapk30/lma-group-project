"""Pairokar's batch desk: the queue resumes after an interrupted shard, and the retrieval cache is shared across cases
(plan §11, §17 'resumable shards', §15.6 F4).

Real modules: PairokarAgent (stage 1 and 2), TriageQueue (SQLite), Scheduler, the urgency rule, RetrievalCache, and the agents a full
run uses (Sutradhar, Vakeel, Abhiyojak). Fakes: the stores, the batch toolbox (12 constructed cases, two with planted deadlines) and
the scripted Ada client. No GPU.

ASSUMPTIONS (the skeleton fixes signatures only): `stage1(files)` enqueues the files in the default `TriageQueue()` (under
`$VS_DATA_DIR`) and returns ranked cards; `stage2(cards, budget)` runs the cards in urgency order, saves each finished case's brief on
that case's record (a `case.views` 'brief' view) as soon as it is done and marks it done in the queue, and skips cases already done;
the cache of one `PairokarAgent` is shared by all cases it runs and reachable as `agent.cache` (a `RetrievalCache`). A session cut
mid-case raises KeyboardInterrupt out of `stage2` and leaves that case pending.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.fakes.data import build_world
from tests.system import _helpers as sh
from vakeel_sahayak.batch.cache import RetrievalCache
from vakeel_sahayak.batch.queue import TriageQueue
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.schemas.enums import AgentName, EventKind

N = 12
PLANTED = (3, 8)
DAYS_LEFT = (3, 1)
HUGE = 10_000.0


def desk(tmp_path: Path, monkeypatch, *, limit: int | None = None) -> SimpleNamespace:
    """A wired desk: 12 cases, planted deadlines at positions 3 and 8, a Pairokar agent on the fakes."""
    cases = sh.build_batch(n=N, planted_indexes=PLANTED, planted_days_left=DAYS_LEFT)
    tb = sh.BatchToolbox(build_world(), cases)
    ada = sh.ada_client()
    if limit is not None:
        original = ada.generate

        def cut(*args, **kwargs):
            if len(ada.calls) >= limit:
                raise KeyboardInterrupt("session ended")
            return original(*args, **kwargs)

        ada.generate = cut
    sc = sh.Scenario(tmp_path, monkeypatch, toolbox=tb, ada=ada)
    files = []
    for c in cases:
        f = sc.data_dir / "batch" / Path(c.path).name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4\n% stub\n")
        files.append(str(f))
    return SimpleNamespace(sc=sc, tb=tb, cases=cases, files=files, ada=ada, agent=sc.agent(AgentName.PAIROKAR))


def budget_for(n_cases: int) -> float:
    """Smallest budget (grid of 0.25 GPU-hours) with which the default queue offers at least `n_cases` full runs."""
    q = TriageQueue()
    return next(b / 4 for b in range(1, 4000) if len(q.next_stage2(b / 4)) >= n_cases)


def brief_saved(sc, case_id: str) -> bool:
    return bool(CaseState(case_id, sc.log).brief().grounds)


# ---- stage 1 -----------------------------------------------------------------------------------------------------
def test_stage_1_gives_every_file_a_card_with_deadline_cases_first(tmp_path, monkeypatch):
    """Plan §11/§15.6 F4: one TriageCard per file; the two cases with a default-bail window opening within 7 days rank ahead of all others,
    although their custody (55-58 days) is shorter than most."""
    d = desk(tmp_path, monkeypatch)
    cards = d.agent.stage1(d.files)
    assert len(cards) == N and sorted(c.urgency_rank for c in cards) == list(range(1, N + 1))
    planted = {c.case_id for c in d.cases if c.planted}
    assert sh.pairwise_ranking_accuracy(cards, planted) == 1.0
    assert {c.case_id for c in sorted(cards, key=lambda c: c.urgency_rank)[:2]} == planted


def test_stage_1_enqueues_every_file(tmp_path, monkeypatch):
    d = desk(tmp_path, monkeypatch)
    d.agent.stage1(d.files)
    assert sorted(TriageQueue().next_stage2(HUGE)) == sorted(c.case_id for c in d.cases)


# ---- resume ------------------------------------------------------------------------------------------------------
def test_a_session_that_ends_leaves_a_prefix_done_and_the_next_session_does_the_rest(tmp_path, monkeypatch):
    """Plan §17: shards resume. Session 1 has budget for two cases and finishes the two most urgent; a restarted desk (new queue and
    agent objects on the same files) runs the other ten, none twice."""
    d = desk(tmp_path, monkeypatch)
    cards = d.agent.decide_next_steps(d.agent.stage1(d.files))
    first = d.agent.stage2(cards, budget_for(2))
    by_rank = [c.case_id for c in sorted(cards, key=lambda c: c.urgency_rank)]
    assert 1 <= len(first) < N and first == by_rank[: len(first)]
    assert {c.case_id for c in d.cases if c.planted} <= set(first)  # the two planted deadlines are the first two full runs
    restarted = d.sc.agent(AgentName.PAIROKAR)  # a new process: new objects, same record and queue file
    second = restarted.stage2(cards, HUGE)
    assert not set(first) & set(second)
    assert set(first) | set(second) == {c.case_id for c in cards if "request documents" not in (c.next_step or "")}
    assert TriageQueue().next_stage2(HUGE) == []


def test_each_case_is_saved_as_soon_as_it_finishes(tmp_path, monkeypatch):
    """Plan §11, §17: finished cases have their brief on the record; cases not yet run have none."""
    d = desk(tmp_path, monkeypatch)
    cards = d.agent.decide_next_steps(d.agent.stage1(d.files))
    done = d.agent.stage2(cards, budget_for(3))
    assert done and all(brief_saved(d.sc, c) for c in done)
    pending = [c.case_id for c in cards if c.case_id not in done]
    assert pending and not any(brief_saved(d.sc, c) for c in pending)


def test_a_session_cut_in_the_middle_of_a_case_leaves_that_case_pending(tmp_path, monkeypatch):
    """The Ada session ends while the third case is running: the two finished cases stay done, the third is not marked done and is
    picked up again by the next session, which does not redo the first two."""
    ref = desk(tmp_path / "ref", monkeypatch)
    ref_cards = ref.agent.decide_next_steps(ref.agent.stage1(ref.files))
    ref.agent.stage2(ref_cards, budget_for(2))
    calls_for_two_cases = len(ref.ada.calls)
    assert calls_for_two_cases > 0

    d = desk(tmp_path / "live", monkeypatch, limit=calls_for_two_cases + 1)
    cards = d.agent.decide_next_steps(d.agent.stage1(d.files))
    with pytest.raises(KeyboardInterrupt):
        d.agent.stage2(cards, HUGE)
    by_rank = [c.case_id for c in sorted(cards, key=lambda c: c.urgency_rank)]
    pending = TriageQueue().next_stage2(HUGE)
    assert set(by_rank[:2]).isdisjoint(pending) and by_rank[2] in pending
    assert all(brief_saved(d.sc, c) for c in by_rank[:2]) and not brief_saved(d.sc, by_rank[2])

    d.ada.generate = type(d.ada).generate.__get__(d.ada)  # the new session has its GPU back
    resumed = d.sc.agent(AgentName.PAIROKAR).stage2(cards, HUGE)
    assert by_rank[2] in resumed and not set(by_rank[:2]) & set(resumed)


# ---- the shared cache ----------------------------------------------------------------------------------------------
def test_one_cache_serves_all_cases_and_cuts_store_calls(tmp_path, monkeypatch):
    """Plan §11: a retrieval cache keyed by factor, section family, before-date month and query is shared across cases. Ten cases with the
    same charge and month cost far fewer store calls than ten single-case runs."""
    single = desk(tmp_path / "one", monkeypatch)
    cards1 = single.agent.decide_next_steps(single.agent.stage1(single.files[:1]))
    single.agent.stage2(cards1, HUGE)
    per_case = single.tb.store_calls()
    assert per_case > 0

    d = desk(tmp_path / "all", monkeypatch)
    cards = d.agent.decide_next_steps(d.agent.stage1(d.files))
    done = d.agent.stage2(cards, HUGE)
    assert len(done) >= 6
    assert d.tb.store_calls() < per_case * len(done)
    assert isinstance(d.agent.cache, RetrievalCache)
    assert d.agent.cache.stats()["hit_rate"] > 0.0


def test_cached_output_equals_the_single_case_output(tmp_path, monkeypatch):
    """F4: 'caching raises throughput without changing results': the brief of a case run inside the batch equals that case run alone."""
    alone = desk(tmp_path / "alone", monkeypatch)
    target = alone.cases[0].case_id
    cards = alone.agent.decide_next_steps(alone.agent.stage1(alone.files[:1]))
    alone.agent.stage2(cards, HUGE)
    expected = CaseState(target, alone.sc.log).brief()

    batch = desk(tmp_path / "batch", monkeypatch)
    cards = batch.agent.decide_next_steps(batch.agent.stage1(batch.files))
    batch.agent.stage2(cards, HUGE)
    got = CaseState(target, batch.sc.log).brief()
    assert [(g.id, g.argument, [(a.doc_id, a.para) for a in g.authorities]) for g in got.grounds] == \
           [(g.id, g.argument, [(a.doc_id, a.para) for a in g.authorities]) for g in expected.grounds]


# ---- safety ------------------------------------------------------------------------------------------------------
def test_the_desk_never_exports_and_never_approves(tmp_path, monkeypatch):
    """Plan §11, §16: 'no bulk export; each case needs its own approval': after a full batch no export call, no export file, no approval."""
    d = desk(tmp_path, monkeypatch)
    cards = d.agent.decide_next_steps(d.agent.stage1(d.files))
    done = d.agent.stage2(cards, HUGE)
    assert done
    assert d.tb.exports == [] and d.tb.count("export") == 0
    assert not [p for p in tmp_path.rglob("*") if p.suffix in (".docx", ".pdf") and "batch" not in p.parts]
    for case_id in done[:3]:
        assert d.sc.events(EventKind.GATE_APPROVED, case_id=case_id) == []
