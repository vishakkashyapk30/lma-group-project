"""law.concordance store: IPC-BNS and CrPC-BNSS edges typed same/split/merged/reworded/new, with text diff (about 600 edges). Index: graph. (plan §5.1)"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from vakeel_sahayak.pipelines.concordance.refs import OLD_TO_NEW, make_ref, split_ref
from vakeel_sahayak.schemas.enums import ConcordanceEdgeType, Shelf, StoreName, TransferFlag
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge
from vakeel_sahayak.stores.base import SharedStore
from vakeel_sahayak.tools.types import MapSectionResult, TransferCheckResult


def _read_edges(target: Path) -> list[ConcordanceEdge]:
    """Edges from a SQLite file (table `edges`), or a JSON list / JSONL file of ConcordanceEdge objects."""
    with target.open("rb") as fh:
        is_sqlite = fh.read(16).startswith(b"SQLite format 3")
    if is_sqlite:
        with sqlite3.connect(str(target)) as conn:
            rows = conn.execute("SELECT old_ref, new_ref, type, text_diff FROM edges").fetchall()
        return [ConcordanceEdge(old_ref=o, new_ref=n, type=ConcordanceEdgeType(t), text_diff=d) for o, n, t, d in rows]
    text = target.read_text(encoding="utf-8").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
        items = data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        items = [json.loads(line) for line in text.splitlines() if line.strip()]
    return [ConcordanceEdge.model_validate(item) for item in items]


class ConcordanceStore(SharedStore):
    """law.concordance store: IPC-BNS and CrPC-BNSS edges typed same/split/merged/reworded/new, with text diff (about 600 edges). Index: graph."""

    name = StoreName.LAW_CONCORDANCE
    shelf = Shelf.LAW
    index_kind = "graph"

    def __init__(self) -> None:
        """Create an unopened store."""
        self._edges: list[ConcordanceEdge] = []

    def open(self, path: str | None = None) -> None:
        """Open the store: the SQLite file at `path` (default stores/law/concordance.sqlite), or the offline seed if absent.

        A JSON list or JSONL file of edges (`concordance_edges.jsonl`, the fixture format) is read too.

        Args:
            path: see behaviour
        """
        from vakeel_sahayak.config import load_config
        from vakeel_sahayak.pipelines.concordance.crpc_bnss_table import load_bail_sections_table
        from vakeel_sahayak.pipelines.concordance.seed import SEED_IPC_BNS_EDGES

        cfg = load_config()
        file_name = cfg.stores["law"]["concordance"]["path"]
        target = Path(path) if path else Path(cfg.paths.stores_dir) / file_name
        if target.is_dir():  # an out_dir written by `build`
            target = target / Path(file_name).name
        if target.is_file():
            self._edges = _read_edges(target)
        else:
            self._edges = [*SEED_IPC_BNS_EDGES, *load_bail_sections_table()]

    def close(self) -> None:
        """Close."""
        self._edges = []

    def count(self) -> int:
        """Row count.

        Returns:
            Count.
        """
        return len(self._edges)

    def build(self, source_dir: str, out_dir: str) -> None:
        """Build the SQLite edge table from `source_dir/concordance_edges.jsonl` plus the bail table (see `build_concordance`).

        Args:
            source_dir: directory holding concordance_edges.jsonl (IPC-BNS edges from pipelines/concordance/ipc2bns.py,
                plus the CrPC-BNSS bail table)
            out_dir: directory that receives the SQLite file named in configs/stores.yaml
        """
        from vakeel_sahayak.pipelines.store_builders.build_concordance import build_concordance

        build_concordance(source_dir, out_dir)

    def edges_for(self, ref: str) -> list[ConcordanceEdge]:
        """Edges touching a section: exact reference, or every sub-clause of it ('BNS 318' finds 'BNS 318(4)').

        Args:
            ref: full reference such as 'BNS 318(4)'

        Returns:
            Edges.
        """
        code, section = split_ref(ref)
        key = make_ref(code, section)
        exact = [e for e in self._edges if key in (e.old_ref, e.new_ref)]
        if exact:
            return exact
        return [e for e in self._edges if e.old_ref.startswith(key + "(") or e.new_ref.startswith(key + "(")]

    def map_section(self, code: str, section: str, offence_date: str) -> MapSectionResult:
        """Era-aware mapping.

        The equivalent is the section in the other act (BNS for IPC, IPC for BNS, and so on). `governing` is the
        reference that applies to an offence on `offence_date`: the new act from the BNS-era date (configs/splits.yaml),
        the old act before it.

        Args:
            code: IPC, BNS, CrPC or BNSS
            section: see behaviour
            offence_date: ISO date

        Returns:
            MapSectionResult.

        Raises:
            ValueError: for a malformed date or an unknown code.
        """
        from vakeel_sahayak.config import load_config
        from vakeel_sahayak.rights.day_count import parse_date

        ref = make_ref(code, section)
        era_start = parse_date(str(load_config().splits.get("bns_era_offence_on_or_after", "2024-07-01")))
        new_era = parse_date(offence_date) >= era_start
        edges = self.edges_for(ref)
        if not edges:  # never guess: an unknown section has no equivalent and is flagged ambiguous
            return MapSectionResult(equivalent=None, edge_type=ConcordanceEdgeType.NEW, ambiguous=True, governing=None)
        is_old = ref.split(" ", 1)[0] in OLD_TO_NEW
        others = [(e.old_ref if not is_old else e.new_ref) for e in edges]
        others = sorted({o for o in others if o})
        exact = [e for e in edges if ref in (e.old_ref, e.new_ref)]
        types = {e.type for e in edges}
        if not others:
            return MapSectionResult(equivalent=None, edge_type=ConcordanceEdgeType.NEW, governing=ref)
        if len(others) > 1 or not exact:
            return MapSectionResult(
                equivalent=None, edge_type=sorted(types, key=lambda t: t.value)[0], ambiguous=True, candidates=others
            )
        equivalent = others[0]
        governing = (equivalent if is_old else ref) if new_era else (ref if is_old else equivalent)
        return MapSectionResult(equivalent=equivalent, edge_type=exact[0].type, governing=governing)

    def transfer_flag(self, old_ref: str, new_ref: str) -> TransferCheckResult:
        """SAME_TEXT / CHANGED / NEW.

        SAME_TEXT needs a SAME edge between the two references and no recorded text difference. A NEW edge on
        `new_ref` gives NEW. Anything else known to the concordance is CHANGED, with the qualification the brief
        must state (plan §5.4).

        Args:
            old_ref: for example 'IPC 420'
            new_ref: for example 'BNS 318(4)'

        Returns:
            TransferCheckResult.

        Raises:
            ValueError: for an empty `old_ref` when the new section does have counterparts.
            LookupError: if the concordance knows neither reference.
        """
        new = make_ref(*split_ref(new_ref))
        if not old_ref.strip():  # the caller says there is no IPC/CrPC counterpart
            counterparts = sorted({e.old_ref for e in self._edges if e.new_ref == new and e.old_ref})
            if counterparts:
                raise ValueError(f"{new} has counterparts in the old act ({', '.join(counterparts)}): name one as old_ref")
            return TransferCheckResult(flag=TransferFlag.NEW)
        old = make_ref(*split_ref(old_ref))
        pair = [e for e in self._edges if e.old_ref == old and e.new_ref == new]
        if pair:
            edge = pair[0]
            if edge.type == ConcordanceEdgeType.SAME and not edge.text_diff:
                return TransferCheckResult(flag=TransferFlag.SAME_TEXT)
            if edge.type == ConcordanceEdgeType.NEW:
                return TransferCheckResult(flag=TransferFlag.NEW)
            return TransferCheckResult(
                flag=TransferFlag.CHANGED,
                text_diff=edge.text_diff,
                qualification=f"{old} -> {new} is a {edge.type.value.lower()} provision; state the change when relying on the precedent.",
            )
        if any(e.new_ref == new and not e.old_ref for e in self._edges):
            return TransferCheckResult(flag=TransferFlag.NEW)
        known = [e for e in self._edges if new in (e.old_ref, e.new_ref) or old in (e.old_ref, e.new_ref)]
        if known:
            return TransferCheckResult(
                flag=TransferFlag.CHANGED,
                qualification=f"{old} and {new} are not directly linked in the concordance; verify before relying on the precedent.",
            )
        raise LookupError(f"neither {old} nor {new} is in law.concordance")

    def family(self, ref: str) -> list[str]:
        """Section family used for section_family expansion (plan §5.2).

        Args:
            ref: see behaviour

        Returns:
            The reference, its counterparts in the other act, and sub-clauses sharing its main section.
        """
        code, section = split_ref(ref)
        key = make_ref(code, section)
        main = make_ref(code, section.split("(")[0])
        refs = {key}
        for e in self.edges_for(main):
            refs.update(r for r in (e.old_ref, e.new_ref) if r)
        for e in self.edges_for(key):
            refs.update(r for r in (e.old_ref, e.new_ref) if r)
        return sorted(refs)
