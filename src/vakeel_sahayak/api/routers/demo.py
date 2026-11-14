"""Router 'demo': the evaluator demo's tours (docs/handoff/evaluator-demo.md).

Six synthetic cases were run end to end on a hosted model and recorded under `demo/cases/<slug>/`; the API copies them into the data
directory at start-up (`demo.preload`, off with `VS_DEMO_CASES=off`). A tour walks an evaluator through one recorded case, stage by
stage; the cases themselves are served by the ordinary case routes. Gate 2 of every demo case is left open: the evaluator approves it
(POST /api/cases/{id}/gates/GATE_2_EXPORT/approve), which shows that export is impossible before counsel's approval.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from vakeel_sahayak.api import service
from vakeel_sahayak.api.deps import _data_dir, get_event_log
from vakeel_sahayak.demo import preload
from vakeel_sahayak.demo.preload import Tour, TourSummary
from vakeel_sahayak.record.event_log import EventLog

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _present(log: EventLog) -> list[Tour]:
    """The recorded tours whose case is in this data directory's record."""
    ids = set(service.all_case_ids(log))
    return [t for t in preload.load_tours() if t.case_id in ids]


@router.get("/tours", response_model=list[TourSummary])
async def list_tours(log: Annotated[EventLog, Depends(get_event_log)]) -> list[TourSummary]:
    """The demo tours whose case is loaded, by slug: `{slug, case_id, title, story, variant}` (empty with `VS_DEMO_CASES=off`)."""
    return [TourSummary(**t.model_dump(include={"slug", "case_id", "title", "story", "variant"})) for t in _present(log)]


@router.get("/tours/{slug}", response_model=Tour)
async def get_tour(slug: str, log: Annotated[EventLog, Depends(get_event_log)]) -> Tour:
    """One tour: the recorded run (date, backend, model, spend) and its nine steps, INTAKE to FILE; 404 for an unknown or unloaded slug."""
    tour = next((t for t in _present(log) if t.slug == slug), None)
    if tour is None:
        raise HTTPException(status_code=404, detail=f"no demo tour {slug!r}")
    return tour


@router.post("/tours/{slug}/reset", response_model=TourSummary)
async def reset_tour(slug: str, log: Annotated[EventLog, Depends(get_event_log)]) -> TourSummary:
    """Put the tour's case back exactly as recorded (Gate 2 open again, no export), so the next evaluator starts afresh."""
    if not any(t.slug == slug for t in preload.load_tours()):
        raise HTTPException(status_code=404, detail=f"no demo tour {slug!r}")
    preload.reset_demo_case(slug, _data_dir(), log)
    tour = next(t for t in preload.load_tours() if t.slug == slug)
    return TourSummary(**tour.model_dump(include={"slug", "case_id", "title", "story", "variant"}))
