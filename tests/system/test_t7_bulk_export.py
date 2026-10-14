"""T7 safety (plan §11, §15.2 T7, §16): bulk export in batch mode is refused; each case needs its own approval.

Metric: unapproved-export attempts that succeed = 0, including attempts that try to export many cases at once. Gate 2 belongs to one case:
approving case A unlocks A and nothing else, and no desk route, request body or agent exports a batch.

Real modules: PairokarAgent (stage 1 and 2), GateGuard, `export_case`, the desk and export routes, the log. Fakes: the batch toolbox, models,
stores (`Scenario`); the document writers are recording stubs.

ASSUMPTIONS: an export request that names other cases in its body (`case_ids`) exports only the case in the URL; an unknown or collective
case id ('all') is refused (403, 404, 405 or 422).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.fakes.data import build_world
from tests.system import _helpers as sh
from tests.unit.export._helpers import Spy
from tests.unit.pipelines._helpers import patch_everywhere
from vakeel_sahayak.export.exporter import export_case
from vakeel_sahayak.schemas.enums import AgentName, ExportFormat

pytestmark = pytest.mark.system

G2 = sh.G2
HUGE = 10_000.0
REFUSED_CODES = (403, 404, 405, 422)


@pytest.fixture()
def spy(monkeypatch) -> Spy:
    s = Spy()
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.application", "assemble_application_docx", s.application)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.hearing_card", "build_hearing_card", s.card)
    patch_everywhere(monkeypatch, "vakeel_sahayak.export.pdf", "docx_to_pdf", s.pdf)
    return s


def batch_desk(tmp_path, monkeypatch, n: int = 12):
    cases = sh.build_batch(n=n, planted_indexes=(3, 8), planted_days_left=(3, 1))
    sc = sh.Scenario(tmp_path, monkeypatch, toolbox=sh.BatchToolbox(build_world(), cases), ada=sh.ada_client())
    files = []
    for c in cases:
        f = sc.data_dir / "batch" / f"{c.case_id}.pdf"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"%PDF-1.4\n% stub\n")
        files.append(str(f))
    return sc, cases, files


def seeded_cases(tmp_path, monkeypatch, n: int = 10):
    """`n` cases that each have a clean brief and sparring (Gate 2 open, nobody approved)."""
    sc = sh.Scenario(tmp_path, monkeypatch)
    ids = [f"case-{i:04d}" for i in range(1, n + 1)]
    for cid in ids:
        sc.seed_record(cid, brief=sh.clean_brief(cid), sparring=sh.clean_sparring(cid))
    return sc, ids


def post_export(client, case_id: str, **extra) -> int:
    return client.post(f"/api/cases/{case_id}/export", json={"format": "DOCX", **extra}).status_code


# ---- after a whole batch ------------------------------------------------------------------------------------------------
def test_bulk_export_after_a_whole_batch_is_refused_case_by_case(tmp_path, monkeypatch):
    """After every brief is ready, exporting all of them is refused (403 each); no desk route exports in bulk; approving ONE case unlocks
    only that case. Successful unapproved exports: 0."""
    sc, _, files = batch_desk(tmp_path, monkeypatch)
    agent = sc.agent(AgentName.PAIROKAR)
    done = agent.stage2(agent.decide_next_steps(agent.stage1(files)), HUGE)
    assert len(done) >= 8
    client = sc.client()
    assert client.post("/api/desk/export").status_code in (404, 405)
    assert {post_export(client, c) for c in done} == {sh.HTTP_EXPORT_REFUSED}
    assert sc.toolbox.exports == []
    lucky = done[0]
    sc.seed_record(lucky, brief=sh.clean_brief(lucky), sparring=sh.clean_sparring(lucky))
    sc.approve(G2, case_id=lucky)
    after = {c: post_export(client, c) for c in done}
    assert [c for c, code in after.items() if code == 200] == [lucky]


def test_pairokar_has_no_export_in_its_toolset_and_never_calls_it(tmp_path, monkeypatch):
    sc, _, files = batch_desk(tmp_path, monkeypatch, n=6)
    agent = sc.agent(AgentName.PAIROKAR)
    agent.stage2(agent.decide_next_steps(agent.stage1(files)), HUGE)
    assert sc.toolbox.count("export") == 0 and sc.toolbox.exports == []
    assert sh.export_tool_calls(sc.events()) == []


# ---- attempts to export many at once ----------------------------------------------------------------------------------------
def test_ten_unapproved_exports_in_a_row_all_fail_and_write_nothing(tmp_path, monkeypatch, spy):
    """The metric over ten attempts: success rate 0, no writer ran, no file exists."""
    sc, ids = seeded_cases(tmp_path, monkeypatch)
    client = sc.client()
    codes = [post_export(client, cid) for cid in ids]
    assert codes == [sh.HTTP_EXPORT_REFUSED] * len(ids)
    assert spy.calls == [] and not [p for p in tmp_path.rglob("*") if p.suffix in (".docx", ".pdf")]


def test_the_exporter_itself_refuses_every_unapproved_case(tmp_path, monkeypatch, spy):
    """Below the API: `export_case` for each case raises, so a script cannot bypass the route either."""
    _, ids = seeded_cases(tmp_path, monkeypatch, n=5)
    for cid in ids:
        with pytest.raises(sh.REFUSED):
            export_case(cid, ExportFormat.DOCX)
    assert spy.calls == []


def test_one_approval_unlocks_one_case_only(tmp_path, monkeypatch, spy):
    """Ten cases with identical briefs; counsel approves the fourth; only the fourth exports, and every returned path belongs to it."""
    sc, ids = seeded_cases(tmp_path, monkeypatch)
    sc.approve(G2, case_id=ids[3])
    client = sc.client()
    results = {cid: client.post(f"/api/cases/{cid}/export", json={"format": "DOCX"}) for cid in ids}
    assert [cid for cid, r in results.items() if r.status_code == 200] == [ids[3]]
    assert all(ids[3] in str(Path(p)) for p in results[ids[3]].json())


def test_a_request_that_names_other_cases_exports_only_its_own(tmp_path, monkeypatch, spy):
    """ASSUMPTION: extra `case_ids` in the body are ignored; the URL's case is the only one exported."""
    sc, ids = seeded_cases(tmp_path, monkeypatch, n=3)
    sc.approve(G2, case_id=ids[0])
    res = sc.client().post(f"/api/cases/{ids[0]}/export", json={"format": "DOCX", "case_ids": ids})
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        assert not [p for p in res.json() if ids[1] in str(p) or ids[2] in str(p)]


@pytest.mark.parametrize("case_id", ["all", "*", "case-*", "case-0001,case-0002"])
def test_a_collective_case_id_is_refused(tmp_path, monkeypatch, case_id):
    sc, _ = seeded_cases(tmp_path, monkeypatch, n=2)
    assert post_export(sc.client(), case_id) in REFUSED_CODES


@pytest.mark.parametrize("path", ["/api/desk/export", "/api/desk/export-all", "/api/desk/board/export", "/api/export"])
def test_no_route_exports_in_bulk(tmp_path, monkeypatch, path):
    client = sh.Scenario(tmp_path, monkeypatch).client()
    assert client.post(path).status_code in (404, 405)
    assert not [r.path for r in client.app.routes if hasattr(r, "path") and r.path.startswith("/api/desk") and "export" in r.path]


def test_opening_cases_from_the_board_never_approves_them(tmp_path, monkeypatch):
    """Each case still needs its own approval: opening ten cases leaves ten open Gate 2 checklists and no approval event."""
    sc, ids = seeded_cases(tmp_path, monkeypatch)
    client = sc.client()
    for cid in ids:
        assert client.post(f"/api/desk/{cid}/open").status_code == 200
    assert sh.agent_approvals([e for cid in ids for e in sc.events(case_id=cid)]) == []
    assert all(sc.status(G2, cid).open is True for cid in ids)
