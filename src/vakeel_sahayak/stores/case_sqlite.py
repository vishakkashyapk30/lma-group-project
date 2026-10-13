"""SQLite file shared by the exact-lookup case stores: `data/cases/<case_id>/case.sqlite` holds the `timeline` and `facts` tables (plan §5.1, configs/stores.yaml)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from vakeel_sahayak.stores.paths import MEMORY

SCHEMA = """
CREATE TABLE IF NOT EXISTS timeline (event_id TEXT PRIMARY KEY, date TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS timeline_date ON timeline (date);
CREATE TABLE IF NOT EXISTS facts (field TEXT PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS facts_meta (key TEXT PRIMARY KEY, value TEXT);
"""


def connect_case_db(path: str) -> sqlite3.Connection:
    """Open (creating the folder and tables if needed) a case's SQLite file; ':memory:' keeps it in memory."""
    if path != MEMORY:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.executescript(SCHEMA)
    return conn
