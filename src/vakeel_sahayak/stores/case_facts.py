"""case.facts store: the CaseDossier, every field with status and source (about 15 fields). Index: exact. (plan §5.1)"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from vakeel_sahayak.schemas.common import TrackedField
from vakeel_sahayak.schemas.dossier import CaseDossier, DossierFields
from vakeel_sahayak.schemas.enums import Shelf, StoreName
from vakeel_sahayak.schemas.ids import check_case_id, check_iso_date
from vakeel_sahayak.stores.base import CaseStore
from vakeel_sahayak.stores.case_sqlite import connect_case_db
from vakeel_sahayak.stores.paths import resolve_case_path


class FactsStore(CaseStore):
    """case.facts store: the CaseDossier, every field with status and source (about 15 fields). Index: exact."""

    name = StoreName.CASE_FACTS
    shelf = Shelf.CASE
    index_kind = "exact"

    def __init__(self) -> None:
        """Create an unbound, unopened store."""
        self._case_id: str | None = None
        self._conn: sqlite3.Connection | None = None

    def open(self, path: str | None = None) -> None:
        """Open the store (creating it if new): table `facts` of `case.sqlite` of the bound case.

        Args:
            path: file, folder, or ':memory:'; default data/cases/<case_id>/case.sqlite
        """
        if not self._case_id:
            raise ValueError("bind_case(case_id) before open()")
        self._conn = connect_case_db(resolve_case_path(self.name, self._case_id, path))

    def close(self) -> None:
        """Close."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def count(self) -> int:
        """Row count.

        Returns:
            Count (fields written).
        """
        return int(self._need().execute("SELECT COUNT(*) FROM facts").fetchone()[0])

    def bind_case(self, case_id: str) -> None:
        """Select the case.

        Args:
            case_id: see behaviour
        """
        self._case_id = check_case_id(case_id)

    def _need(self) -> sqlite3.Connection:
        """The open connection (raises if the store was never opened)."""
        if self._conn is None:
            raise RuntimeError("case.facts is not open")
        return self._conn

    @staticmethod
    def _check_field(field: str) -> None:
        """Raise KeyError for a name that is not a dossier field."""
        if field not in DossierFields.model_fields:
            raise KeyError(f"{field!r} is not a dossier field: {sorted(DossierFields.model_fields)}")

    def get(self, field: str) -> TrackedField[Any]:
        """One field.

        Args:
            field: a dossier field name

        Returns:
            TrackedField; a field never written is an empty field with status UNSUPPORTED.

        Raises:
            KeyError: for a name that is not a dossier field.
        """
        self._check_field(field)
        row = self._need().execute("SELECT payload FROM facts WHERE field = ?", (field,)).fetchone()
        return TrackedField[Any].model_validate_json(row[0]) if row else TrackedField()

    def put(self, field: str, value: TrackedField[Any]) -> None:
        """Write a field (status and source mandatory).

        `TrackedField` itself refuses a VERIFIED, COMPUTED or USER_STATED value without its source (plan §7.1).

        Args:
            field: a dossier field name
            value: the tracked value

        Raises:
            KeyError: for a name that is not a dossier field.
        """
        self._check_field(field)
        conn = self._need()
        with conn:
            conn.execute("INSERT OR REPLACE INTO facts (field, payload) VALUES (?, ?)", (field, value.model_dump_json()))

    def set_meta(self, court: str | None = None, as_of: str | None = None) -> None:
        """Record the dossier-level court and as-of date.

        Raises:
            ValueError: for a malformed date.
        """
        conn = self._need()
        with conn:
            if court is not None:
                conn.execute("INSERT OR REPLACE INTO facts_meta VALUES ('court', ?)", (court,))
            if as_of is not None:
                conn.execute("INSERT OR REPLACE INTO facts_meta VALUES ('as_of', ?)", (check_iso_date(as_of),))

    def dossier(self) -> CaseDossier:
        """Whole dossier.

        Returns:
            CaseDossier built from the stored fields (fields never written stay empty).
        """
        conn = self._need()
        stored = {f: json.loads(p) for f, p in conn.execute("SELECT field, payload FROM facts")}
        meta = dict(conn.execute("SELECT key, value FROM facts_meta").fetchall())
        return CaseDossier(
            case_id=check_case_id(self._case_id or ""),
            court=meta.get("court"),
            as_of=meta.get("as_of"),
            fields=DossierFields(**stored),
        )
