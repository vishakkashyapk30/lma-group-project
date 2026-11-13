"""`GET /api/cases/{id}/brief` carries `withheld`: per ground, the sentences strict abstention (X4, c1457) left out and why.

Vakeel records each removal as an `abstain` decision (agents/vakeel/agent.py `_abstain`); the brief route folds the latest one per
ground, counted only when it follows Vakeel's latest `draft` of that ground. The stored brief is unchanged (the field is API-only).
"""

from __future__ import annotations

from tests.system import _helpers as sh
from tests.system._helpers import make_event
from tests.unit.api._helpers import CASE, scenario
from vakeel_sahayak.api.service import withheld_by_ground
from vakeel_sahayak.schemas.enums import EventKind

SILENT = "only says the record is silent"
UNSUPPORTED = "not supported by the dossier quote (fact support 0.31)"


def draft(gid: str, factor: str):
    return make_event(CASE, EventKind.AGENT_MESSAGE, "VAKEEL", tool="draft",
                      outputs={"type": "draft", "text": f"{gid} drafted.", "ground": gid, "factor": factor, "sentences": 3})


def abstain(claim: str, factor: str, withheld: list[tuple[str, str]], kept: int = 1):
    return make_event(CASE, EventKind.AGENT_MESSAGE, "VAKEEL", tool="abstain", outputs={
        "type": "abstain", "text": f"{claim}: left out.", "claim": claim, "factor": factor, "removed": len(withheld), "kept": kept,
        "withheld": [{"sentence": s, "reason": r} for s, r in withheld], "variant": "X4", "abstention": "strict"})


def test_brief_lists_the_withheld_sentences_per_ground(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    for ev in (
        draft("G1", "parity_with_co_accused"),
        abstain("G1", "parity_with_co_accused", [("The co-accused had the same role.", UNSUPPORTED)]),
        draft("G2", "trial_delay"),
        abstain("G2", "trial_delay", [("The record does not say when the trial will begin.", SILENT)], kept=0),
    ):
        sc.log.append(ev)
    sc.seed_record(brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    body = sc.client().get(f"/api/cases/{CASE}/brief").json()
    assert [g["id"] for g in body["grounds"]] == ["G1"]  # the stored brief is unchanged
    assert body["withheld"] == [
        {"ground": "G1", "factor": "parity_with_co_accused", "dropped": False,
         "sentences": [{"sentence": "The co-accused had the same role.", "reason": UNSUPPORTED}]},
        {"ground": "G2", "factor": "trial_delay", "dropped": True,
         "sentences": [{"sentence": "The record does not say when the trial will begin.", "reason": SILENT}]},
    ]


def test_brief_without_strict_abstention_has_an_empty_withheld_list(tmp_path, monkeypatch):
    sc = scenario(tmp_path, monkeypatch)
    sc.seed_record(brief=sh.clean_brief(CASE), sparring=sh.clean_sparring(CASE))
    assert sc.client().get(f"/api/cases/{CASE}/brief").json()["withheld"] == []


def test_a_later_draft_of_the_ground_clears_its_old_withheld_sentences():
    events = [
        draft("G1", "custody_period"),
        abstain("G1", "custody_period", [("Old sentence.", SILENT)]),
        draft("G1", "custody_period"),  # redraft with nothing withheld
    ]
    assert withheld_by_ground(events) == []


def test_the_latest_abstain_of_a_draft_counts_and_replies_are_not_grounds():
    events = [
        draft("G3", "custody_period"),
        abstain("G3", "custody_period", [("First.", SILENT)]),
        abstain("G3", "custody_period", [("First.", SILENT), ("Second.", UNSUPPORTED)]),
        abstain("reply:O1", "parity_with_co_accused", [("A reply sentence.", SILENT)]),
        make_event(CASE, EventKind.AGENT_MESSAGE, "ABHIYOJAK", outputs={"type": "abstain", "claim": "G9", "withheld": [{"sentence": "x", "reason": "y"}]}),
    ]
    out = withheld_by_ground(events)
    assert [g.ground for g in out] == ["G3"]
    assert [s.sentence for s in out[0].sentences] == ["First.", "Second."]
