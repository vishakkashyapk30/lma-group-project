"""`make stores` entry point (plan §5, §18 weeks 1-3): build the seven shared stores, in dependency order, and write a build
report with row counts against the plan estimates.

ASSUMPTIONS (the skeleton fixes only `main(argv) -> exit code`): the CLI reads `--interim DIR` and `--out DIR`; with no
store names it builds all seven; `--only NAME [NAME ...]` selects stores by short name (statutes, concordance, reasoning,
citations, similar, arguments, objections); `--exclude-from SPLITS ORDERS` is replaced here by the `split` column of
`orders.jsonl`; the report is `build_report.json` in `--out`, a mapping store name -> {rows, estimate}.
"""

from __future__ import annotations

import json

import pytest

from vakeel_sahayak.pipelines.store_builders.build_all import main
from vakeel_sahayak.schemas.enums import StoreName

SHARED = [s for s in StoreName if not s.value.startswith("case.")]


def test_there_are_seven_shared_stores():
    """Plan §5.1: ten stores, three of them per-case, so seven are built offline."""
    assert len(SHARED) == 7


def test_main_builds_all_seven_and_returns_zero(interim, tmp_path):
    out = tmp_path / "stores"
    assert main(["--interim", str(interim), "--out", str(out)]) == 0
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert {k for k in report} >= {s.value for s in SHARED}


def test_report_has_row_counts_and_plan_estimates(interim, tmp_path):
    """Each entry lists the rows written and the plan's size estimate (plan §5.1 'Size (est.)')."""
    out = tmp_path / "stores"
    main(["--interim", str(interim), "--out", str(out)])
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    for name, entry in report.items():
        assert entry["rows"] > 0, name
        assert "estimate" in entry, name


def test_leakage_exclusions_are_applied_to_every_order_store(interim, tmp_path):
    """The test order and the same-FIR order (found from the FIR key of the test order) reach none of the order-derived stores."""
    out = tmp_path / "stores"
    main(["--interim", str(interim), "--out", str(out)])
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert report["caselaw.similar"]["rows"] == 5
    assert report["advocacy.arguments"]["rows"] == 5
    assert report["advocacy.objections"]["rows"] == 5
    assert report["caselaw.citations"]["rows"] == 3


def test_only_selects_stores(interim, tmp_path):
    out = tmp_path / "stores"
    assert main(["--interim", str(interim), "--out", str(out), "--only", "statutes", "concordance"]) == 0
    report = json.loads((out / "build_report.json").read_text(encoding="utf-8"))
    assert set(report) == {"law.statutes", "law.concordance"}


def test_reasoning_is_built_after_citations_and_concordance(interim, tmp_path, monkeypatch):
    """Dependency order: `caselaw.reasoning` needs the citation graph (cites, authority) and the concordance (section_family) first."""
    order: list[str] = []
    import vakeel_sahayak.pipelines.store_builders.build_all as mod

    for short in ("statutes", "concordance", "citations", "reasoning", "similar", "arguments", "objections"):
        original = getattr(mod, f"build_{short}", None)
        if original is None:
            pytest.skip(f"build_all does not import build_{short} by name; order cannot be observed this way")
        monkeypatch.setattr(mod, f"build_{short}", lambda *a, _s=short, _o=original, **k: (order.append(_s), _o(*a, **k))[1])
    main(["--interim", str(interim), "--out", str(tmp_path / "stores")])
    assert order.index("citations") < order.index("reasoning")
    assert order.index("concordance") < order.index("reasoning")


def test_missing_interim_directory_is_a_failure_exit_code(tmp_path):
    """A missing input directory must not look like success."""
    code = main(["--interim", str(tmp_path / "nope"), "--out", str(tmp_path / "o")])
    assert code != 0
