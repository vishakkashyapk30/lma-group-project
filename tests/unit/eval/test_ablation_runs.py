"""Ablations A1-A10 as RUNS (plan §15.4, §17): each ablation is the Full system with one switch flipped (skeleton convention: 'ablations are
Switches flags, not code forks'), run once on 100 T1 cases as resumable shards that save every case as it finishes.

test_registries.py already checks `make_switches()` flips exactly the documented flags and the 2x2 design. This file adds what the runs do.

* A1 no_dossier, A2 no_check_repair, A3 no_tools, A4 plain_retrieval, A6 fixed_router, A7 free_planner, A8 no_sparring, A9 both, A5 extractor
  in {finetuned_4b, base_4b, prompted_32b}, A10 knock out one store at a time (retrieval and slot-fill only, no drafting).

# SKELETON-GAP: how `run()` builds its AgentContext is not in the skeleton. The tests replace `eval.baselines.full_system.run_case` by a spy
# (the Full system is what every ablation perturbs) and `models.factory.get_llm` by a fake, and read what the spy was handed. They assume
# `run()` loads a JSON-lines file of T1 cases ({"case_id", "facts", "before"}), saves one output per case under out_dir, and that
# `eval.runners.shard_runner.load_progress(out_dir)` lists the saved case ids (the same convention the resume logic uses).
"""

from __future__ import annotations

import importlib

import pytest

from tests.fakes.models import ScriptedLLM
from tests.unit.eval.test_registries import ABLATION_SWITCH, ABLATIONS
from tests.unit.pipelines._helpers import patch_everywhere, write_jsonl
from vakeel_sahayak.eval.runners.shard_runner import load_progress
from vakeel_sahayak.orchestration.switches import Switches
from vakeel_sahayak.schemas.bail_brief import BailBrief
from vakeel_sahayak.schemas.enums import StoreName

SHARED_STORES = {s.value for s in StoreName if s.value.split(".")[0] in {"law", "caselaw", "advocacy"}}


class Spy:
    """Stands in for full_system.run_case; records the case id, the switches in the context and what had been saved already."""

    def __init__(self, out_dir) -> None:
        self.out_dir = str(out_dir)
        self.calls: list[tuple[str, dict, set[str]]] = []

    def __call__(self, case, ctx):
        self.calls.append((case["case_id"], ctx.switches.model_dump(), set(load_progress(self.out_dir))))
        return BailBrief(case_id=case["case_id"])


def rig(tmp_path, monkeypatch, n_cases: int = 5):
    cases = write_jsonl(tmp_path / "cases.jsonl", [{"case_id": f"t1-{i:03d}", "facts": f"facts {i}", "before": "2025-02-03"} for i in range(n_cases)])
    out = tmp_path / "out"
    spy = Spy(out)
    patch_everywhere(monkeypatch, "vakeel_sahayak.eval.baselines.full_system", "run_case", spy)
    patch_everywhere(monkeypatch, "vakeel_sahayak.models.factory", "get_llm", lambda *a, **k: ScriptedLLM(strict=False, default=""))
    return str(cases), str(out), spy


def run_module(ablation: str):
    return importlib.import_module(ABLATIONS[ablation])


SINGLE = sorted(ABLATION_SWITCH)  # a1 a2 a3 a4 a6 a7 a8 a9


@pytest.mark.parametrize("ablation", SINGLE)
def test_every_case_runs_under_the_ablations_switches(tmp_path, monkeypatch, ablation):
    """The context given to the Full system carries exactly the ablation's switches (and nothing else changed)."""
    cases, out, spy = rig(tmp_path, monkeypatch)
    run_module(ablation).run(cases, out)
    expected = run_module(ablation).make_switches().model_dump()
    assert [c[0] for c in spy.calls] == [f"t1-{i:03d}" for i in range(5)]
    assert all(switches == expected for _, switches, _ in spy.calls)
    default = Switches().model_dump()
    changed = {k: v for k, v in expected.items() if v != default[k]}
    assert changed == ABLATION_SWITCH[ablation]


@pytest.mark.parametrize("ablation", SINGLE)
def test_each_case_is_saved_before_the_next_one_starts(tmp_path, monkeypatch, ablation):
    """Plan §17: 'each case's output is saved as soon as it finishes': when case k starts, cases 0..k-1 are already on disk."""
    cases, out, spy = rig(tmp_path, monkeypatch)
    run_module(ablation).run(cases, out)
    for k, (_, _, saved) in enumerate(spy.calls):
        assert saved == {f"t1-{i:03d}" for i in range(k)}, (ablation, k, saved)
    assert load_progress(out) == {f"t1-{i:03d}" for i in range(5)}


@pytest.mark.parametrize("ablation", SINGLE)
def test_a_rerun_resumes_and_does_not_redo_saved_cases(tmp_path, monkeypatch, ablation):
    cases, out, spy = rig(tmp_path, monkeypatch)
    run_module(ablation).run(cases, out)
    spy.calls.clear()
    run_module(ablation).run(cases, out)
    assert spy.calls == []


def test_a_partial_directory_is_resumed_from_where_it_stopped(tmp_path, monkeypatch):
    """Two cases already saved (an earlier session) -> only the remaining three run. # ASSUMPTION: output files are out_dir/<case_id>.json."""
    cases, out, spy = rig(tmp_path, monkeypatch)
    import os

    os.makedirs(out)
    for i in (0, 1):
        with open(f"{out}/t1-{i:03d}.json", "w", encoding="utf-8") as fh:
            fh.write(BailBrief(case_id=f"t1-{i:03d}").model_dump_json())
    run_module("a1").run(cases, out)
    assert [c[0] for c in spy.calls] == ["t1-002", "t1-003", "t1-004"]


@pytest.mark.parametrize("ablation", ["a1", "a8"])
def test_shards_partition_the_cases(tmp_path, monkeypatch, ablation):
    """shard i of n takes its own cases: across all shards every case runs exactly once (three accounts, no duplicated work)."""
    cases, _, spy = rig(tmp_path, monkeypatch, n_cases=10)
    seen = []
    for shard in range(3):
        spy.out_dir = str(tmp_path / f"out{shard}")
        before = len(spy.calls)
        run_module(ablation).run(cases, spy.out_dir, shard=shard, n_shards=3)
        seen.append([c[0] for c in spy.calls[before:]])
    flat = [c for part in seen for c in part]
    assert sorted(flat) == [f"t1-{i:03d}" for i in range(10)] and len(flat) == len(set(flat))
    assert all(part for part in seen)


# ---------------------------------------------------------------- A5: three extractors
def test_a5_runs_each_case_under_all_three_extractors(tmp_path, monkeypatch):
    """A5 compares fine-tuned 4B vs base 4B vs prompted 32B: every case is run once per extractor (runs.yaml: 3 variants)."""
    cases, out, spy = rig(tmp_path, monkeypatch, n_cases=2)
    run_module("a5").run(cases, out)
    seen = {(cid, sw["extractor"]) for cid, sw, _ in spy.calls}
    assert seen == {(f"t1-{i:03d}", v) for i in range(2) for v in ("finetuned_4b", "base_4b", "prompted_32b")}


def test_a5_changes_only_the_extractor_switch(tmp_path, monkeypatch):
    cases, out, spy = rig(tmp_path, monkeypatch, n_cases=1)
    run_module("a5").run(cases, out)
    default = Switches().model_dump()
    for _, sw, _ in spy.calls:
        assert {k for k, v in sw.items() if v != default[k]} <= {"extractor"}


# ---------------------------------------------------------------- A10: one store at a time, retrieval and slot-fill only
def a10_rig(tmp_path, monkeypatch, n_cases: int):
    """A10 never drafts: it stops at Sutradhar's evidence packs. The spy sits on `SutradharAgent.pick_factors` (the step that fills slots).
    # ASSUMPTION: the agent keeps its context as `self.ctx`."""
    cases, out, full_spy = rig(tmp_path, monkeypatch, n_cases)
    seen: list[str | None] = []

    def pick_factors(self, state):
        seen.append(self.ctx.switches.knockout_store)
        return []

    monkeypatch.setattr("vakeel_sahayak.agents.sutradhar.agent.SutradharAgent.pick_factors", pick_factors)
    return cases, out, full_spy, seen


def test_a10_knocks_out_each_shared_store_once_per_case(tmp_path, monkeypatch):
    """'Remove one store at a time': each of the seven shared stores is knocked out for each case, one per run, never two together.
    # ASSUMPTION: the case-shelf stores (docs, timeline, facts) are the client's own record, not part of the knock-out study."""
    cases, out, _, seen = a10_rig(tmp_path, monkeypatch, 2)
    run_module("a10").run(cases, out)
    assert set(seen) == SHARED_STORES
    assert len(seen) == 2 * len(SHARED_STORES)
    assert all(seen.count(s) == 2 for s in SHARED_STORES)


def test_a10_is_retrieval_and_slot_fill_only_no_drafting(tmp_path, monkeypatch):
    """Plan §15.4: A10 is reported at retrieval and slot-fill level, so it must not run drafting: the Full system is never called."""
    cases, out, full_spy, _ = a10_rig(tmp_path, monkeypatch, 1)
    run_module("a10").run(cases, out)
    assert full_spy.calls == []


def test_a10_job_in_runs_yaml_is_retrieval_and_slot_fill(load_yaml):
    assert load_yaml("eval/runs.yaml")["jobs"]["a10_knockouts"]["level"] == "retrieval_and_slot_fill"
