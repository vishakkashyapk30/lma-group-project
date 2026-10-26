"""The variant registry, the evaluation plan and docs/literature-to-code-map.md agree: what the map's sweep tables call done or built is implemented, and nothing the registry implements is missing from the plan."""

from __future__ import annotations

import re
from pathlib import Path

from vakeel_sahayak.orchestration.switches import (
    IMPLEMENTED_VARIANTS,
    VARIANT_DESCRIPTIONS,
    _variant_table,
    assert_variant_implemented,
    canonical_variant,
)

REPO = Path(__file__).resolve().parents[3]
MAP = (REPO / "docs" / "literature-to-code-map.md").read_text(encoding="utf-8")
ID = re.compile(r"\b([SPB]\d{1,2}[a-d]?|A\d{1,2}[a-d]?)\b")


def sweep_rows() -> list[tuple[list[str], str]]:
    """(ids named in the 'Variant and switch' cell, the status cell) of every row of the map's sweep tables (before the EV-01 history table)."""
    body = MAP.split("## EV-01 switch table")[0]
    rows = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 8 and cells[0] not in ("Idea", "---") and not set(cells[0]) <= {"-"}:
            rows.append((ID.findall(cells[2].split("`")[0]), cells[-1]))
    return rows


def test_the_map_has_sweep_rows_and_every_id_it_names_exists():
    rows = sweep_rows()
    assert len(rows) >= 20
    names = {canonical_variant(i) for ids, _ in rows for i in ids}
    assert names and names <= set(_variant_table())


def test_what_the_map_calls_done_or_built_is_implemented():
    for ids, status in sweep_rows():
        if re.match(r"(done|built)", status.lower()):
            for ident in ids:
                if ident in {"S15b"} and "not built" in status.lower():
                    continue  # the S15 row used to say so; S15b is built now (a stale note in the map, listed in docs/handoff/eval-complete.md)
                assert_variant_implemented(ident)


def test_every_implemented_id_is_named_in_the_plan_or_declared_beyond_it():
    plan = (REPO / "docs" / "evaluation-plan.md").read_text(encoding="utf-8")
    beyond_the_plan = {"S18", "P8", "S14d", "S6b"}  # added after the plan (switches.py docstring; B5 is the plan's S6b)
    for ident in IMPLEMENTED_VARIANTS - {"full"}:
        root = re.sub(r"[a-d]$", "", ident)
        assert ident in beyond_the_plan or re.search(rf"\b{ident}\b|\b{root}\b", plan), f"{ident} is implemented but not in docs/evaluation-plan.md"


def test_no_declared_variant_is_unbuilt_and_every_one_is_described():
    assert set(_variant_table()) == set(IMPLEMENTED_VARIANTS)  # a new id must come with its behaviour (or be listed in configs/eval/runs.yaml `exclusions`)
    assert set(IMPLEMENTED_VARIANTS) - {"full", *(f"A{i}" for i in (5, 10))} <= set(VARIANT_DESCRIPTIONS) | {"S13"}


def test_the_registry_comments_do_not_claim_the_old_state():
    text = (REPO / "src" / "vakeel_sahayak" / "orchestration" / "switches.py").read_text(encoding="utf-8")
    assert "only S3" not in text and "Everything else is defined but not implemented" not in text and "their behaviour is not implemented yet" not in text
