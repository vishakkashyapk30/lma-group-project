"""Entry point for `make stores`: build all seven shared stores in dependency order (plan §5, §18 weeks 1-3).

    python -m vakeel_sahayak.pipelines.store_builders.build_all --interim data/interim --out data/stores \
        [--splits data/interim/splits.json] [--only reasoning citations] [--embedder auto]

Order: statutes, concordance, citations, reasoning, arguments, objections, similar (the paragraph and similar stores read
the concordance that was just built). Test orders and same-FIR orders are left out of every store (plan §2): the test orders come from `--splits`, or from the
`split` column of `orders.jsonl` when it is not given.
The build report `build_report.json` in the output folder lists row counts against the plan's estimates.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vakeel_sahayak.pipelines.store_builders import corpus
from vakeel_sahayak.pipelines.store_builders.build_arguments import build_arguments
from vakeel_sahayak.pipelines.store_builders.build_citations import build_citations
from vakeel_sahayak.pipelines.store_builders.build_concordance import build_concordance
from vakeel_sahayak.pipelines.store_builders.build_objections import build_objections
from vakeel_sahayak.pipelines.store_builders.build_reasoning import build_reasoning
from vakeel_sahayak.pipelines.store_builders.build_similar import build_similar
from vakeel_sahayak.pipelines.store_builders.build_statutes import build_statutes
from vakeel_sahayak.schemas.enums import StoreName
from vakeel_sahayak.stores.paths import sqlite_name

BUILD_ORDER: list[tuple[str, str]] = [
    ("statutes", "law.statutes"),
    ("concordance", "law.concordance"),
    ("citations", "caselaw.citations"),
    ("reasoning", "caselaw.reasoning"),
    ("arguments", "advocacy.arguments"),
    ("objections", "advocacy.objections"),
    ("similar", "caselaw.similar"),
]
_EMBEDDING_STORES = {"reasoning", "arguments", "objections", "similar"}


def parse_estimate(value: Any) -> tuple[int, int] | None:
    """Plan estimate to (low, high): 1000 -> (1000, 1000); '100-300K' -> (100000, 300000); None if unparseable."""
    if isinstance(value, int):
        return value, value
    m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*([KkMm]?)\s*", str(value or ""))
    if not m:
        return None
    mult = {"": 1, "k": 1000, "m": 1_000_000}[m.group(3).lower()]
    return int(m.group(1)) * mult, int(m.group(2) or m.group(1)) * mult


def estimate_for(store_name: str) -> Any:
    """The estimate for a store in configs/stores.yaml (`est_rows` or `est_edges`)."""
    from vakeel_sahayak.config import load_config

    shelf, _, key = store_name.partition(".")
    entry = load_config().stores.get(shelf, {}).get(key, {})
    return entry.get("est_rows", entry.get("est_edges"))


def _builders(exclude: set[str], embedder: str | None, concordance: str | None) -> dict[str, Callable[[str, str], int]]:
    """Builder callables with the shared options bound."""
    return {
        "statutes": lambda i, o: build_statutes(i, o),
        "concordance": lambda i, o: build_concordance(i, o),
        "citations": lambda i, o: build_citations(i, o, exclude, concordance_path=concordance),
        "reasoning": lambda i, o: build_reasoning(i, o, exclude, embedder=embedder, concordance_path=concordance),
        "arguments": lambda i, o: build_arguments(i, o, exclude, embedder=embedder, concordance_path=concordance),
        "objections": lambda i, o: build_objections(i, o, exclude, embedder=embedder, concordance_path=concordance),
        "similar": lambda i, o: build_similar(i, o, exclude, embedder=embedder, concordance_path=concordance),
    }


def shelf_dir(out_dir: str, store_name: str) -> str:
    """Folder of a store's shelf under the output folder (`out/law`, `out/caselaw`, `out/advocacy`), the layout of configs/stores.yaml."""
    return str(Path(out_dir) / store_name.partition(".")[0])


def build_all(
    interim_dir: str,
    out_dir: str,
    only: list[str] | None = None,
    exclude_doc_ids: set[str] | None = None,
    embedder: str | None = None,
) -> dict[str, Any]:
    """Build the shared stores and write `build_report.json` (store name to `{rows, estimate, within_estimate}`) and
    `build_notes.json` (embedder, exclusions, corpus statistics).

    Args:
        interim_dir: folder with `orders.jsonl`, and optionally `statutes.jsonl` and `concordance_edges.jsonl`
        out_dir: output folder; files go to `<out_dir>/<shelf>/<name>.sqlite`, where `open_store` finds them when `out_dir` is the stores folder
        only: subset of store names (statutes, concordance, citations, reasoning, arguments, objections, similar)
        exclude_doc_ids: test and same-FIR orders to leave out of every store
        embedder: embedder name for the vector stores; None uses VS_EMBEDDER or 'auto'

    Returns:
        The report: `stores` (per-store rows against the plan estimate), plus embedder, exclusions and corpus statistics.

    Raises:
        ValueError: for an unknown store name in `only`.
    """
    from vakeel_sahayak.models.embeddings import get_embedder
    from vakeel_sahayak.stores.hybrid import embedder_name_of

    known = [short for short, _ in BUILD_ORDER]
    unknown = sorted(set(only or []) - set(known))
    if unknown:
        raise ValueError(f"unknown store(s) {unknown}: choose from {known}")
    exclude = set(exclude_doc_ids or ())
    corpus.clear_cache()
    report: dict[str, Any] = {"excluded_orders": len(exclude), "stores": {}}
    if embedder or _EMBEDDING_STORES.intersection(only or known):
        from vakeel_sahayak.models import factory

        report["embedder"] = embedder_name_of(get_embedder(embedder) if embedder else factory.get_embedder())
    concordance: str | None = None
    for short, full in BUILD_ORDER:
        if only and short not in only:
            continue
        if short == "citations":  # the stores built from here on read the concordance that was just built (or the default one)
            built = Path(shelf_dir(out_dir, "law.concordance")) / sqlite_name(StoreName.LAW_CONCORDANCE)
            concordance = str(built) if built.is_file() else None
        rows = _builders(exclude, embedder, concordance)[short](interim_dir, shelf_dir(out_dir, full))
        est = estimate_for(full)
        span = parse_estimate(est)
        report["stores"][full] = {
            "rows": rows,
            "estimate": est,
            "within_estimate": None if span is None else span[0] <= rows <= span[1],
        }
    if {"reasoning", "arguments", "objections", "similar", "citations"}.intersection(only or known):
        report["corpus"] = corpus.process_corpus(interim_dir, exclude, concordance_path=concordance).report
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    (Path(out_dir) / "build_report.json").write_text(json.dumps(report["stores"], indent=2, default=str), encoding="utf-8")
    notes = {k: v for k, v in report.items() if k != "stores"}
    (Path(out_dir) / "build_notes.json").write_text(json.dumps(notes, indent=2, default=str), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    """CLI: build all or selected stores; write a build report with row counts vs plan estimates.

    Args:
        argv: command-line arguments (default sys.argv)

    Returns:
        Exit code (0 on success, 2 for bad arguments or a missing interim folder).
    """
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    parser = argparse.ArgumentParser(description="Build the shared stores (plan §5).")
    parser.add_argument("--interim", default=paths.interim_dir, help="folder with orders.jsonl (default: paths.interim)")
    parser.add_argument("--out", default=paths.stores_dir, help="output folder (default: paths.stores)")
    parser.add_argument("--only", nargs="*", choices=[s for s, _ in BUILD_ORDER], help="build only these stores")
    parser.add_argument(
        "--splits", help="splits file from pipelines.splits; without it the `split` column of orders.jsonl marks the test orders"
    )
    parser.add_argument("--embedder", help="hashed-ngram, bge-m3 or auto (default VS_EMBEDDER or auto)")
    args = parser.parse_args(argv)
    if not Path(args.interim).is_dir():
        print(f"interim folder not found: {args.interim}", file=sys.stderr)
        return 2
    orders_file = str(Path(args.interim) / corpus.ORDERS_FILE)
    exclude: set[str] = set()
    if args.splits:
        from vakeel_sahayak.pipelines.leakage import excluded_doc_ids

        exclude = excluded_doc_ids(args.splits, orders_file)
    elif Path(orders_file).is_file():
        from vakeel_sahayak.pipelines.leakage import excluded_from_orders

        exclude = excluded_from_orders(orders_file)
    report = build_all(args.interim, args.out, args.only, exclude, args.embedder)
    for name, info in report["stores"].items():
        print(f"{name}: {info['rows']} rows (plan estimate {info['estimate']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
