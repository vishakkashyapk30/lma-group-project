#!/usr/bin/env python3
"""Seed one reproducible local demo from the public Open India Law T2 bundle.

The source PDF and the generated SQLite/event data deliberately remain local:
they are installed by ``make data`` and are not committed.  This script creates
the same ``public-demo-t2`` case on every machine from that approved bundle.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from vakeel_sahayak.api.routers.upload import _run_intake
from vakeel_sahayak.record.event_log import EventLog
from vakeel_sahayak.schemas.enums import EventKind
from vakeel_sahayak.schemas.events import COUNSEL, Event

CASE_ID = "public-demo-t2"
SOURCE_NAME = "t1-003_K1.pdf"


def seed(*, title: str = "Public court demo — T2 bail bundle", run_intake: bool = True) -> tuple[Path, EventLog]:
    """Reset the public T2 demo and return its local directory and record."""
    data = Path(os.environ.get("VS_DATA_DIR", "data")).resolve()
    source = data / "testsets" / "t2" / "bundles" / SOURCE_NAME
    if not source.is_file():
        raise SystemExit(f"missing {source}; run 'make data' first")
    case_dir = data / "cases" / CASE_ID
    log = EventLog(str(data / "record.sqlite"))
    if log.read(CASE_ID):
        log.purge_case(CASE_ID)
    shutil.rmtree(case_dir, ignore_errors=True)
    case_dir.mkdir(parents=True)
    target = case_dir / SOURCE_NAME
    shutil.copy2(source, target)
    log.append(Event(event_id="", ts="", case_id=CASE_ID, kind=EventKind.USER_ACTION, actor=COUNSEL,
                     inputs={"action": "create_case", "title": title,
                             "source": "Open India Law / Vaquill AI, CC BY 4.0"}))
    log.append(Event(event_id="", ts="", case_id=CASE_ID, kind=EventKind.USER_ACTION, actor=COUNSEL,
                     inputs={"action": "upload", "files": [SOURCE_NAME], "source": "public_test_bundle"}))
    questions = _run_intake(log, CASE_ID, [str(target)]) if run_intake else []
    status = f"intake questions: {len(questions)}" if run_intake else "intake deferred"
    print(f"seeded {CASE_ID} from {source.name}; {status}")
    return case_dir, log


def main() -> None:
    seed()


if __name__ == "__main__":
    main()
