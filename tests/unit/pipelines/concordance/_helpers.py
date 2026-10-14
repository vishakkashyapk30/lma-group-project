"""Helpers for the concordance pipeline tests: a synthetic IPC2BNS-Verify directory and a statutes file.

ASSUMPTION (the plan names the source, IPC2BNS-Verify (MIT), but not its file layout): `verify_dir/pairs.jsonl` holds one
JSON object per line, `{"ipc": [<IPC sections>], "bns": [<BNS sections>]}`: one IPC section to one BNS section (same or
reworded), one IPC section to several BNS sections (split), several IPC sections to one BNS section (merged), and an empty
`ipc` list for a BNS section with no IPC equivalent (new). `statutes_path` is a JSON list of `StatuteRow` objects
(tests/fixtures/law/statutes.json has this shape); the edge type is decided by comparing the two texts.
ASSUMPTION: `out_path` receives one `ConcordanceEdge` JSON object per line (the `concordance_edges.jsonl` of the store tests),
and an edge for a NEW provision has `old_ref == ""` (as in tests/unit/tools_law_case/test_transfer_check.py).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vakeel_sahayak.schemas.enums import ConcordanceEdgeType
from vakeel_sahayak.schemas.store_rows import ConcordanceEdge

T = ConcordanceEdgeType

COMMON = "[synthetic] Punishment for criminal breach of trust."

# (code, section, text, max_punishment)
STATUTE_ROWS: list[tuple[str, str, str, str | None]] = [
    ("IPC", "406", COMMON, "3 years"),
    ("BNS", "316(2)", COMMON, "5 years"),  # identical text: SAME
    ("IPC", "420", "[synthetic] Cheating and dishonestly inducing delivery of property.", "7 years"),
    ("BNS", "318(4)", "[synthetic] Cheating and thereby dishonestly inducing the person deceived to deliver property.", "7 years"),
    ("IPC", "999", "[synthetic] An omnibus offence with two limbs.", "5 years"),
    ("BNS", "888(1)", "[synthetic] First limb of the omnibus offence.", "3 years"),
    ("BNS", "888(2)", "[synthetic] Second limb of the omnibus offence.", "2 years"),
    ("IPC", "777", "[synthetic] First of two merged offences.", "1 year"),
    ("IPC", "778", "[synthetic] Second of two merged offences.", "1 year"),
    ("BNS", "666", "[synthetic] The merged offence.", "2 years"),
    ("BNS", "111", "[synthetic] Organised crime (no IPC counterpart).", "life"),
]

PAIRS: list[dict[str, list[str]]] = [
    {"ipc": ["406"], "bns": ["316(2)"]},
    {"ipc": ["420"], "bns": ["318(4)"]},
    {"ipc": ["999"], "bns": ["888(1)", "888(2)"]},
    {"ipc": ["777", "778"], "bns": ["666"]},
    {"ipc": [], "bns": ["111"]},
]


def write_statutes(path: Path) -> Path:
    rows = [{"code": c, "section": s, "text": t, "max_punishment": m} for c, s, t, m in STATUTE_ROWS]
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def write_verify_dir(root: Path, pairs: list[dict[str, Any]] | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pairs.jsonl").write_text("\n".join(json.dumps(p) for p in (pairs or PAIRS)) + "\n", encoding="utf-8")
    return root


def read_edges(path: str | Path) -> list[ConcordanceEdge]:
    return [ConcordanceEdge.model_validate_json(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def edge_map(edges: list[ConcordanceEdge]) -> dict[tuple[str, str], ConcordanceEdge]:
    return {(e.old_ref, e.new_ref): e for e in edges}
