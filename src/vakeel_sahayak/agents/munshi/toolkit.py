"""Munshi's work through the registered tools (plan §4.3): the page ladder over the intake tools, and a filer whose writes are `file_item` calls.

Page reads return client text before it is pseudonymised, and `BaseAgent.call_tool` logs every tool result, so the read
tools are called through `RawCaller` (permission-checked, not logged); the page's route is logged separately without its
text (`MunshiAgent._log_page`). Everything that carries pseudonymised text goes through `call_tool`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vakeel_sahayak.ingestion.filing import Filer
from vakeel_sahayak.ingestion.ladder import RouteOutcome, acceptable, finish_outcome, plan_routes, weak_layer_read
from vakeel_sahayak.ingestion.signals import text_layer_rejection
from vakeel_sahayak.schemas.common import SourceRef, TrackedField
from vakeel_sahayak.schemas.enums import PageStatus, ParseRoute, StoreName
from vakeel_sahayak.tools.base import ToolError

RawCaller = Callable[..., Any]


def route_page_with_tools(
    call: RawCaller,
    path: str,
    page: int,
    thresholds: dict[str, float],
    max_route: ParseRoute = ParseRoute.ASK_COUNSEL,
    min_route: ParseRoute | None = None,
    keep_weak: bool = False,
) -> RouteOutcome | ToolError:
    """The routing ladder of `ingestion.ladder.route_page_from`, with every rung run through its tool.

    Args:
        call: `call(name, **kwargs)` for the intake tools (raw page text, so not logged)
        path: the file
        page: page number from 1
        thresholds: dev-tuned values
        max_route: strongest rung allowed (baselines)
        min_route: weakest rung allowed (a gap re-read)
        keep_weak: keep a near-miss text layer as a low-confidence read before asking counsel (`munshi_keep_weak_text`)

    Returns:
        The outcome, or the ToolError of `inspect_page` (no signals: for example the page is past the end of the file).
    """
    signals = call("inspect_page", file_path=path, page=page)
    if isinstance(signals, ToolError):
        return signals
    log: list[str] = []
    rejection = text_layer_rejection(signals, thresholds)
    if rejection and rejection != "no text layer" and min_route != ParseRoute.TEXT_LAYER:
        log.append(f"text_layer: rejected ({rejection})")
    plan = plan_routes(signals, thresholds, max_route, min_route)
    last: RouteOutcome | None = None
    accepted: RouteOutcome | None = None
    ocr_conf: float | None = None
    for route in plan:
        if route == ParseRoute.ASK_COUNSEL:
            if keep_weak and (layer := _run_rung(call, ParseRoute.TEXT_LAYER, path, page)) is not None:
                weak = weak_layer_read(signals, thresholds, layer.text, log)
                if weak is not None:
                    return finish_outcome(weak, weak.log, signals, thresholds, ocr_conf)
            out = RouteOutcome(route=route, status=PageStatus.UNREADABLE, log=["ask_counsel: no route could read this page"])
            return finish_outcome(out, [*log, *out.log], signals, thresholds, ocr_conf)
        out = _run_rung(call, route, path, page)
        if out is None:
            log.append(f"{route.value}: unavailable")
            continue
        if route == ParseRoute.OCR:
            ocr_conf = out.ocr_conf
        ok, why = acceptable(route, out.text, ocr_conf if route == ParseRoute.OCR else None, signals, thresholds)
        log.extend(out.log)
        last = out
        if ok:
            log.append(f"{route.value}: accepted")
            accepted = out
            if route == ParseRoute.TEXT_LAYER and ParseRoute.LAYOUT in plan:
                continue  # the layout parser refines a good text layer with columns or tables
            break
        log.append(f"{route.value}: rejected ({why})")
    if accepted is not None:
        return finish_outcome(accepted, log, signals, thresholds, ocr_conf)
    if last is not None:
        return finish_outcome(last, [*log, f"stopped at {max_route.value} (route cap)"], signals, thresholds, ocr_conf)
    return finish_outcome(RouteOutcome(route=max_route, status=PageStatus.UNREADABLE), [*log, "no route could read this page"], signals, thresholds, ocr_conf)


def _run_rung(call: RawCaller, route: ParseRoute, path: str, page: int) -> RouteOutcome | None:
    """One rung through its tool; None when the tool failed (the ladder goes on to the next rung)."""
    if route == ParseRoute.TEXT_LAYER:
        got = call("read_text_layer", file_path=path, page=page)
        return None if isinstance(got, ToolError) else RouteOutcome(route=route, text=got.text, boxes=got.boxes, log=["text_layer"])
    if route == ParseRoute.LAYOUT:
        got = call("parse_layout", file_path=path, page=page)
        return None if isinstance(got, ToolError) else RouteOutcome(route=route, text=got.text, tables=got.tables, log=["layout"])
    if route == ParseRoute.OCR:
        got = call("ocr_page", file_path=path, page=page, lang="hin+eng")
        if isinstance(got, ToolError):
            return None
        return RouteOutcome(route=route, text=got.text, boxes=got.boxes, confidence=got.mean_conf, ocr_conf=got.mean_conf, log=["ocr"])
    got = call("vision_read_page", file_path=path, page=page)
    return None if isinstance(got, ToolError) else RouteOutcome(route=route, text=str(got), log=["vision"])


class _Tee:
    """A case store that remembers what was written to it, so the filer can hand the rows to `file_item`."""

    def __init__(self, inner: Any, pending: list[Any]) -> None:
        self._inner, self._pending = inner, pending

    def add_chunks(self, rows: list[Any]) -> Any:
        self._pending.extend(rows)
        return self._inner.add_chunks(rows)

    def add_event(self, row: Any) -> Any:
        self._pending.append(row)
        return self._inner.add_event(row)

    def put(self, field: str, tracked: TrackedField[Any]) -> Any:
        self._pending.append((field, tracked))
        return self._inner.put(field, tracked)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class ToolFiler(Filer):
    """A Filer that keeps its working copy of the case shelf in memory and writes every item through `file_item`.

    The in-memory copy serves the reads (the timeline for the gap check and the conflict check, the merged list
    fields); the case shelf itself is written by the tool, which also logs the STORE_WRITE. Text is pseudonymised here
    before it reaches the tool.
    """

    def __init__(
        self,
        *args: Any,
        sink: Callable[[StoreName, dict[str, Any], SourceRef], Any],
        pseudonymise: Callable[[str], str],
        **kwargs: Any,
    ) -> None:
        kwargs["case_path"] = ":memory:"
        super().__init__(*args, **kwargs)
        self._sink, self._pseudonymise = sink, pseudonymise
        self._pending: list[Any] = []
        self._tees: dict[StoreName, _Tee] = {}

    def clean(self, text: str) -> str:
        """Replace the names learned so far, then run the `pseudonymise` tool over the result (a second pass, never logged)."""
        return self._pseudonymise(super().clean(text))

    def _store(self, name: StoreName):  # noqa: ANN202
        if name not in self._tees:
            self._tees[name] = _Tee(super()._store(name), self._pending)
        return self._tees[name]

    def close(self) -> None:
        """Close the working copy."""
        self._tees.clear()
        super().close()

    def _write(self, inputs: dict[str, Any], outputs: dict[str, Any], sources: list[SourceRef]) -> None:
        """Send the rows just written to `file_item` (one call per chunk, event or field)."""
        store, rows, self._pending[:] = StoreName(inputs["store"]), list(self._pending), []
        if store == StoreName.CASE_DOCS:
            for row, source in zip(rows, sources, strict=False):
                self._sink(store, row.model_dump(mode="json"), source)
        elif store == StoreName.CASE_TIMELINE and rows:
            row = rows[0]
            item = {"event_id": row.event_id, "date": row.date, "label": row.label, "status": row.status.value, "conflicts_with": list(row.conflicts_with)}
            self._sink(store, item, row.source or (sources[0] if sources else SourceRef()))
        elif store == StoreName.CASE_FACTS and rows:
            field, tracked = rows[0]
            item = {"field": field, "value": tracked.value, "status": tracked.status.value}
            self._sink(store, item, tracked.source or SourceRef())
