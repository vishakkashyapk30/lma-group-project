"""Pre-load the recorded evaluator demo cases into the data directory, and read their tours (docs/handoff/evaluator-demo.md).

A recorded demo lives in `demo/cases/<slug>/` (repository root; `VS_DEMO_DIR` overrides the `demo/` folder):

- `case/`: a copy of `<VS_DATA_DIR>/cases/<case_id>/` as the recording left it (the uploaded PDFs, the page index, the alias map, ...);
- `events.jsonl`: the case's rows of the shared case record (`record.sqlite`), one event per line, in order;
- `tour.json`: the evaluator's walk through the nine stages (contract: `Tour` below).

`import_demo_cases` runs when the API starts (`api.app.create_app`) unless `VS_DEMO_CASES=off`. For each snapshot whose case id is not
yet in the record, has no case folder and was not imported before, it copies `case/` into the cases folder and appends the events to
the record, keeping their ids and times (an append; nothing existing is overwritten). The ids it imported are kept in
`<cases>/.demo_imported.json`, so a demo case that counsel deletes stays deleted; `reset_demo_case` (POST /api/demo/tours/{slug}/reset)
puts one back as recorded.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.events import Event

log = logging.getLogger(__name__)

ENABLE_ENV = "VS_DEMO_CASES"
DIR_ENV = "VS_DEMO_DIR"
MARKER = ".demo_imported.json"
STAGES = ("INTAKE", "DOSSIER", "GATE_1", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "GATE_2", "FILE")


class TourFilled(BaseModel):
    """One thing that was filled in this step: a document uploaded, a question answered, a note given, a result."""

    label: str
    value: str


class TourFilledHi(BaseModel):
    """The Hindi of one filled-in line (`scripts/demo/translate_tours_hi.py`)."""

    label: str
    value: str


class TourStepHi(BaseModel):
    """Optional Hindi text of a step; the interface shows it when the language is Hindi. `src` holds, per field, a hash of the
    English text it was made from (`title`, `caption`, `filled.0.label`, ...), so a changed English text is found stale."""

    title: str | None = None
    caption: str | None = None
    filled: list[TourFilledHi] | None = None
    src: dict[str, str] = Field(default_factory=dict)


class TourHi(BaseModel):
    """Optional Hindi text of a tour (title, story, the four variant lines), with the same `src` hashes."""

    title: str | None = None
    story: str | None = None
    variant: dict[str, str] | None = None
    src: dict[str, str] = Field(default_factory=dict)


class TourStep(BaseModel):
    """One stage of the tour: what the agent did in the recorded run and where to look."""

    stage: Literal["INTAKE", "DOSSIER", "GATE_1", "RIGHTS", "BRIEF", "SPAR", "HEARING_PREP", "GATE_2", "FILE"]
    tab: Literal["dossier", "rights", "brief", "spar", "prep"]
    title: str
    caption: str
    agent: Literal["MUNSHI", "PESHKAR", "SUTRADHAR", "VAKEEL", "ABHIYOJAK"] | None = None
    filled: list[TourFilled] = Field(default_factory=list)
    action: Literal["approve_gate_2"] | None = None
    hi: TourStepHi | None = None


class TourRecorded(BaseModel):
    """How the run was made: date, backend, model and the hosted-model spend of the case."""

    date: str
    backend: str
    model: str
    cost_inr: float


class TourSummary(BaseModel):
    """A tour in the list (GET /api/demo/tours)."""

    slug: str
    case_id: str
    title: str
    story: str
    variant: dict[str, str]
    hi: TourHi | None = None


class Tour(TourSummary):
    """`demo/cases/<slug>/tour.json`: the recorded run of one demo case, stage by stage (GET /api/demo/tours/{slug})."""

    recorded: TourRecorded
    steps: list[TourStep]

    @field_validator("steps")
    @classmethod
    def _nine_stages_in_order(cls, steps: list[TourStep]) -> list[TourStep]:
        if tuple(s.stage for s in steps) != STAGES:
            raise ValueError(f"steps must be the stages {', '.join(STAGES)} in this order")
        for s in steps:
            if (s.action is not None) != (s.stage == "GATE_2"):
                raise ValueError("action is 'approve_gate_2' on the GATE_2 step and null on every other step")
        return steps


def enabled() -> bool:
    """False when `VS_DEMO_CASES` is off (also 0, false, no); on by default."""
    return (os.environ.get(ENABLE_ENV) or "on").strip().lower() not in ("off", "0", "false", "no")


def demo_dir() -> Path:
    """The `demo/` folder: `VS_DEMO_DIR`, else `demo/` at the repository (or image) root."""
    raw = os.environ.get(DIR_ENV)
    return Path(raw) if raw else Path(__file__).resolve().parents[3] / "demo"


def snapshot_dirs(root: Path | None = None) -> list[Path]:
    """Every `demo/cases/<slug>/` holding a tour.json, by slug."""
    base = (root or demo_dir()) / "cases"
    return sorted(p for p in base.iterdir() if (p / "tour.json").is_file()) if base.is_dir() else []


def load_tour(folder: Path) -> Tour:
    """Read and validate one tour.json."""
    return Tour.model_validate_json((folder / "tour.json").read_text(encoding="utf-8"))


def load_tours(root: Path | None = None) -> list[Tour]:
    """Every valid tour under `demo/cases/`, by slug; an invalid one is skipped with a warning."""
    tours = []
    for folder in snapshot_dirs(root):
        try:
            tours.append(load_tour(folder))
        except (OSError, ValueError) as exc:
            log.warning("demo tour %s is invalid and is skipped: %s", folder.name, exc)
    return tours


def read_events(folder: Path) -> list[Event]:
    """The recorded events of one snapshot (events.jsonl), in order."""
    path = folder / "events.jsonl"
    if not path.is_file():
        return []
    return [Event.model_validate_json(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _marker(cases_dir: Path) -> set[str]:
    try:
        return set(json.loads((cases_dir / MARKER).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _remember(cases_dir: Path, case_id: str) -> None:
    done = _marker(cases_dir) | {case_id}
    cases_dir.mkdir(parents=True, exist_ok=True)
    (cases_dir / MARKER).write_text(json.dumps(sorted(done)), encoding="utf-8")


def _install(folder: Path, case_id: str, cases_dir: Path, event_log: EventLog) -> None:
    """Copy one snapshot's case folder and append its events (ids and times kept)."""
    src = folder / "case"
    target = cases_dir / case_id
    if src.is_dir():
        shutil.copytree(src, target, dirs_exist_ok=False)
    else:
        target.mkdir(parents=True)
    for event in read_events(folder):
        if event.case_id != case_id:
            raise ValueError(f"{folder.name}/events.jsonl holds an event of {event.case_id!r}, not {case_id!r}")
        event_log.append(event)


def import_demo_cases(data_dir: Path, event_log: EventLog, root: Path | None = None) -> list[str]:
    """Copy every recorded demo case that is absent into the data directory; returns the case ids imported.

    Never overwrites: a case whose id is in the record, whose folder exists, or that was imported before (the marker) is skipped.
    Idempotent: a second call imports nothing.
    """
    cases_dir = Path(data_dir) / "cases"
    imported: list[str] = []
    seen = _marker(cases_dir)
    existing = set(event_log.case_ids()) if hasattr(event_log, "case_ids") else set()
    for folder in snapshot_dirs(root):
        try:
            case_id = load_tour(folder).case_id
            if case_id in existing or case_id in seen or (cases_dir / case_id).exists():
                continue
            _install(folder, case_id, cases_dir, event_log)
            _remember(cases_dir, case_id)
            imported.append(case_id)
        except Exception as exc:  # noqa: BLE001 - one broken snapshot must not keep the API (or the other demos) from starting
            log.warning("demo case %s was not imported: %s", folder.name, exc)
    return imported


def reset_demo_case(slug: str, data_dir: Path, event_log: EventLog, root: Path | None = None) -> str:
    """Put one demo case back exactly as recorded (its record rows and folder are replaced); returns its case id.

    Raises:
        KeyError: no recorded demo has this slug.
    """
    folder = next((f for f in snapshot_dirs(root) if f.name == slug), None)
    if folder is None:
        raise KeyError(slug)
    case_id = load_tour(folder).case_id
    cases_dir = Path(data_dir) / "cases"
    target = (cases_dir / case_id).resolve()
    if cases_dir.resolve() not in target.parents:
        raise KeyError(slug)
    shutil.rmtree(target, ignore_errors=True)
    event_log.purge_case(case_id)
    _install(folder, case_id, cases_dir, event_log)
    _remember(cases_dir, case_id)
    return case_id
