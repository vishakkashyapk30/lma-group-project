"""User flow 6 (plan §13.6, §11, §15.2 T5, §15.6 F4): the batch desk. A legal-aid office uploads 120 files, the triage board is ready within
minutes, full briefs run in urgency order, and next morning counsel opens the top cases; each one still needs its own approval.

Real modules: PairokarAgent (stage 1 and 2), TriageQueue, the urgency rule, RetrievalCache, GateGuard, the desk and export routes. Fakes: the
batch toolbox (`sh.build_batch`: 120 constructed cases, ten with a default-bail window opening within 7 days and a SHORT custody, so a
custody-length sort would rank them last), models and stores. No GPU.

ASSUMPTIONS: `stage1(files)` returns one card per file and enqueues it; `stage2(cards, budget)` runs the cards in urgency order within the
budget and returns the finished case ids; a case needing documents gets a next step that starts with 'request documents'; the board shows
the cards that Pairokar stored on the case records.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from tests.fakes.data import build_world
from tests.system import _helpers as sh
from tests.unit.api._helpers import UNSUPPORTED_MEDIA
from vakeel_sahayak.batch.queue import TriageQueue
from vakeel_sahayak.orchestration.gates import GateGuard
from vakeel_sahayak.record.case_state import CaseState
from vakeel_sahayak.schemas.enums import AgentName, EventKind

pytestmark = pytest.mark.system

G1, G2 = sh.G1, sh.G2
N = 120
HUGE = 10_000.0


def desk(tmp_path: Path, monkeypatch, n: int = N):
    kw = {} if n == N else {"planted_indexes": (3, 8), "planted_days_left": (3, 1)}
    cases = sh.build_batch(n=n, **kw)
    sc = sh.Scenario(tmp_path, monkeypatch, toolbox=sh.BatchToolbox(build_world(), cases), ada=sh.ada_client())
    files = []
    for c in cases:
        f = sc.data_dir / "batch" / Path(c.path).name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4\n% stub\n")
        files.append(str(f))
    return sc, cases, files


def budget_for(n_cases: int) -> float:
    """Smallest budget (grid of 0.25 GPU-hours) with which the default queue offers at least `n_cases` full runs."""
    q = TriageQueue()
    return next(b / 4 for b in range(1, 40000) if len(q.next_stage2(b / 4)) >= n_cases)


def triaged(tmp_path, monkeypatch, n: int = N):
    sc, cases, files = desk(tmp_path, monkeypatch, n)
    agent = sc.agent(AgentName.PAIROKAR)
    cards = agent.stage1(files)
    return sc, cases, files, agent, cards


# ---- the construction itself --------------------------------------------------------------------------------------------
def test_the_constructed_batch_defeats_a_custody_length_sort():
    """Sanity of T5: the ten planted cases have short custody, so sorting by custody alone would put them near the bottom."""
    cases = sh.build_batch(n=N)
    assert len(cases) == N and sum(c.planted for c in cases) == 10
    longest_first = sorted(cases, key=lambda c: -c.custody_days)
    assert not {c.case_id for c in longest_first[:10]} & {c.case_id for c in cases if c.planted}
    assert all(c.days_left is not None and c.days_left <= 7 for c in cases if c.planted)


# ---- step 1: 120 files become a board -------------------------------------------------------------------------------------
@pytest.mark.slow
def test_a_zip_of_120_files_becomes_120_cases(tmp_path, monkeypatch):
    sc, cases, _ = desk(tmp_path, monkeypatch)
    res = sc.client().post("/api/desk/upload", files={"file": ("files.zip", sh.zip_bytes(cases), "application/zip")})
    assert res.status_code == 200 and res.json() == [c.case_id for c in cases]


@pytest.mark.slow
def test_every_planted_deadline_ranks_ahead_of_every_other_case(tmp_path, monkeypatch):
    """Pairwise ranking accuracy 1.0 and a missed-deadline rate of 0 (plan §11, F4): ranks 1-10 are exactly the planted cases."""
    _, cases, _, _, cards = triaged(tmp_path, monkeypatch)
    planted = {c.case_id for c in cases if c.planted}
    assert len(cards) == N and sorted(c.urgency_rank for c in cards) == list(range(1, N + 1))
    assert sh.pairwise_ranking_accuracy(cards, planted) == 1.0
    assert {c.case_id for c in sorted(cards, key=lambda c: c.urgency_rank)[:10]} == planted


@pytest.mark.slow
def test_planted_cases_are_ordered_by_days_left_and_say_why(tmp_path, monkeypatch):
    """The fixed, explainable rule: a deadline in 1 day before one in 6; each card's reason names the default-bail window."""
    _, cases, _, _, cards = triaged(tmp_path, monkeypatch)
    left = {c.case_id: c.days_left for c in cases if c.planted}
    top = sorted(cards, key=lambda c: c.urgency_rank)[:10]
    days = [left[c.case_id] for c in top]
    assert days == sorted(days)
    assert all(re.search(r"opens in \d+ days", " ".join(c.reasons)) and "187(3)" in " ".join(c.reasons) for c in top)


@pytest.mark.slow
def test_cases_missing_a_document_ask_for_it_first(tmp_path, monkeypatch):
    _, cases, _, agent, cards = triaged(tmp_path, monkeypatch)
    missing = {c.case_id for c in cases if c.missing_docs}
    assert missing
    by_id = {c.case_id: c for c in agent.decide_next_steps(cards)}
    for cid in missing:
        assert by_id[cid].missing_docs and by_id[cid].next_step.startswith("request documents")


@pytest.mark.slow
def test_stage_1_is_cheap_no_ada_call_for_120_files(tmp_path, monkeypatch):
    """Plan §11 stage 1: Munshi, Peshkar and the radar run on each file on the laptop; the 14B is for stage 2."""
    sc, _, _, _, _ = triaged(tmp_path, monkeypatch)
    assert sc.ada.calls == []


@pytest.mark.slow
def test_the_board_over_http_is_sorted_by_urgency(tmp_path, monkeypatch):
    sc, cases, _, _, _ = triaged(tmp_path, monkeypatch)
    cards = sc.client().get("/api/desk/board").json()["cards"]
    ranks = [c["urgency_rank"] for c in cards]
    assert ranks == sorted(ranks) and len(cards) == N
    assert {c["case_id"] for c in cards[:10]} == {c.case_id for c in cases if c.planted}


# ---- step 2: full briefs in urgency order ---------------------------------------------------------------------------------
@pytest.mark.slow
def test_full_briefs_run_in_urgency_order_within_the_budget(tmp_path, monkeypatch):
    sc, cases, _, agent, cards = triaged(tmp_path, monkeypatch)
    done = agent.stage2(agent.decide_next_steps(cards), budget_for(10))
    ranked = [c.case_id for c in sorted(cards, key=lambda c: c.urgency_rank)]
    assert 10 <= len(done) < N and done == ranked[: len(done)]
    assert {c.case_id for c in cases if c.planted} <= set(done)
    assert all(CaseState(c, sc.log).brief().grounds for c in done)


# ---- step 3: each case needs its own approval -----------------------------------------------------------------------------
@pytest.mark.slow
def test_opening_a_case_from_the_board_approves_nothing_and_export_stays_403(tmp_path, monkeypatch):
    sc, _, _, agent, cards = triaged(tmp_path, monkeypatch)
    done = agent.stage2(agent.decide_next_steps(cards), budget_for(3))
    client = sc.client()
    top, other = done[0], done[1]
    assert client.post(f"/api/desk/{top}/open").status_code == 200
    assert sc.events(EventKind.GATE_APPROVED, case_id=top) == []
    for case in (top, other):
        assert client.post(f"/api/cases/{case}/export", json={"format": "DOCX"}).status_code == sh.HTTP_EXPORT_REFUSED
    assert sc.toolbox.exports == [] and sc.toolbox.count("export") == 0


def test_approving_one_case_unlocks_only_that_case(tmp_path, monkeypatch):
    """Gate 2 of case A leaves case B (same brief) locked, through the guard and through the route."""
    sc, _, _ = desk(tmp_path, monkeypatch, n=12)
    for cid in ("case-0001", "case-0002"):
        sc.seed_record(cid, brief=sh.clean_brief(cid), sparring=sh.clean_sparring(cid))
    sc.approve(G2, case_id="case-0001")
    GateGuard().assert_export_allowed("case-0001")
    with pytest.raises(sh.REFUSED):
        GateGuard().assert_export_allowed("case-0002")
    assert sc.client().post("/api/cases/case-0002/export", json={"format": "DOCX"}).status_code == sh.HTTP_EXPORT_REFUSED


def test_there_is_no_bulk_export_route(tmp_path, monkeypatch):
    client = sh.Scenario(tmp_path, monkeypatch).client()
    assert client.post("/api/desk/export").status_code in (404, 405)
    assert not [r.path for r in client.app.routes if hasattr(r, "path") and r.path.startswith("/api/desk") and "export" in r.path]


def test_a_zip_of_the_wrong_kind_is_refused(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("notes.txt", "hello")
    res = sh.Scenario(tmp_path, monkeypatch).client().post("/api/desk/upload", files={"file": ("notes.zip", buf.getvalue(), "application/zip")})
    assert res.status_code in (UNSUPPORTED_MEDIA, 422)


def test_the_batch_leaves_no_client_text_in_the_board(tmp_path, monkeypatch, planted_names):
    """The board shows reasons and flags, never page text or a planted name."""
    sc, _, _, _, _ = triaged(tmp_path, monkeypatch, n=12)
    assert not [n for n in planted_names if n in json.dumps(sc.client().get("/api/desk/board").json(), ensure_ascii=False)]
