"""T2 messy bundles: 100 T1 cases bundled with 2-3 companions rendered as K1-K6, plus about 200 HLDC Hindi documents and optional e-SCR Hindi judgments; about 600 bundles, 4,800 pages; answers by construction (plan §15.2).

Each of the (default) 100 T1 cases, drawn with a seed from the open part of T1 (Latin-script orders first; the sealed blind slice is never used), becomes six
bundles, one per input kind K1 (born-digital) to K6 (legacy-font Hindi). A bundle holds the case's own document and constructed companions: the FIR on the
IIF-1 layout and a remand order always, a custody certificate in about two bundles of three (so 3 or 4 documents), in a seeded order. The English kinds
(K1 to K4) use the T1 facts text as the court order (the facts part only, never the reasoning or outcome) and English companions; the Hindi kinds (K5, K6)
use a Hindi order summary and Hindi companions templated from the case values (no translation model; see `companions.py`).

Answers come from construction: `pages` (the exact text laid out on each page), `documents` (type and first and last page, consecutive), `fields` (the
G3 values the documents were filled from: copied unchanged when T1's G3 has them, else constructed with a seed and listed in `constructed`; `custody_days`
and `as_of` appear only when a custody certificate is in the bundle). `text_layer` says what an extractor should find: `exact` (K1, K5), `none` (K2 to K4)
or `legacy_gibberish` (K6, ASCII text in a Kruti-Dev-style encoding, no Devanagari).

HLDC Hindi district-court documents (`hldc_dir/*.jsonl`, rows {doc_id, text}, up to 200) and e-SCR Hindi judgments (`escr_dir/*.jsonl`, up to 100) are each one
K5 bundle of one document, with no field values; both inputs are optional (HLDC needs a Hugging Face access that nobody here has yet, e-SCR has no bulk
path). The manifest says which were available. Size: 100 cases x 6 kinds = 600 bundles (about 2,500 to 4,800 pages depending on the order lengths).

Native Hindi fallback (opt-in, `native_path`): while HLDC is gated, `data/interim/hindi_native.jsonl` (`pipelines/hindi_native.py`: native Hindi High Court bail
orders from Open India Law, not leaked into T1) supplies up to 200 seeded documents, each one K5 bundle of one `COURT_JUDGMENT_HI` document (text cut at
`MAX_ORDER_CHARS` on a space), rendered like the HLDC ones. Their ids start with `hnat-`, their truth row carries `origin: "native_hc"` and a `source` block (case id,
court, year, decision date, characters cut), so results are reported apart from `translated` and from HLDC. Without `native_path` the output is byte-identical to before.
`--native-only` builds just those bundles (`--out data/testsets/t2_hindi_native`).

Outputs in `out_dir`: `bundles/<bundle_id>.pdf`, `truth.jsonl`, `manifest.json`. `scripted_counsel` is the counsel stub of plan §15.5.

CLI: `python -m vakeel_sahayak.testsets.t2_messy_bundles [--t1 DIR --hldc DIR --escr DIR --hindi-native FILE [--native-only] --out DIR --cases N --small]` (`--small`: 12 cases, for CI and a quick check).
"""

from __future__ import annotations

import argparse
import json
import random
import re
import time
from collections import Counter
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets import companions, rendering
from vakeel_sahayak.testsets.common import (
    TestSetManifest,
    g3_fields,
    load_t1_cases,
    rows_from_file,
    rows_to_file,
    sha256_file,
    write_manifest,
)

SEED = 20260429
N_CASES = 100
SMALL_CASES = 12
KINDS = ("K1", "K2", "K3", "K4", "K5", "K6")
HINDI_KINDS = {"K5", "K6"}
HLDC_MAX, ESCR_MAX = 200, 100
NATIVE_MAX = 200
MAX_ORDER_CHARS = 5000
TEXT_LAYER = {"K1": "exact", "K2": "none", "K3": "none", "K4": "none", "K5": "exact", "K6": "legacy_gibberish"}
KIND_NAMES = {
    "K1": "born-digital",
    "K2": "scanned",
    "K3": "degraded scan",
    "K4": "phone photo",
    "K5": "Hindi born-digital",
    "K6": "legacy-font Hindi",
}


def _iso(value: Any) -> str | None:
    if isinstance(value, str) and len(value) == 10:
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            return None
    return None


def _fields(case: dict[str, Any], rng: random.Random) -> tuple[dict[str, Any], list[str]]:
    """The record the companions are filled from, and the names of the values constructed rather than read from G3."""
    g3 = g3_fields(case)
    constructed: list[str] = []
    order_date = _iso(case.get("date"))
    arrest = _iso(g3.get("arrest_date"))
    if arrest is None:
        base = date.fromisoformat(order_date) if order_date else date(2025, 3, 1)
        arrest = (base - timedelta(days=rng.randrange(40, 330))).isoformat()
        constructed.append("arrest_date")
    a = date.fromisoformat(arrest)
    first_remand = _iso(g3.get("first_remand"))
    if first_remand is None:
        first_remand = (a + timedelta(days=1)).isoformat()
        constructed.append("first_remand")
    fir = dict(g3["fir"]) if isinstance(g3.get("fir"), dict) else {}
    offence = _iso(g3.get("offence_date"))
    if offence is None:
        offence = (a - timedelta(days=rng.randrange(3, 40))).isoformat()
        constructed.append("offence_date")
    if not fir.get("date"):
        fir["date"] = (date.fromisoformat(offence) + timedelta(days=rng.randrange(0, 3))).isoformat()
        constructed.append("fir.date")
    if not fir.get("number"):
        fir["number"] = f"{rng.randrange(11, 990)}/{date.fromisoformat(fir['date']).year}"
        constructed.append("fir.number")
    if not fir.get("police_station"):
        fir["police_station"] = f"PS-{rng.randrange(1, 60)}"
        constructed.append("fir.police_station")
    sections = g3.get("sections")
    if not (isinstance(sections, list) and sections):
        sections = ["318(4) BNS"]
        constructed.append("sections")
    days = g3.get("custody_days")
    if isinstance(days, int) and days > 0:
        as_of = (a + timedelta(days=days)).isoformat()
    else:
        as_of = (
            order_date
            if order_date and date.fromisoformat(order_date) > a
            else (a + timedelta(days=rng.randrange(30, 300))).isoformat()
        )
        days = (date.fromisoformat(as_of) - a).days
        constructed.append("custody_days")
    cs = g3.get("charge_sheet")
    filed = cs.get("filed") if isinstance(cs, dict) else g3.get("charge_sheet_filed")
    record = {"fir": fir, "offence_date": offence, "sections": [str(s) for s in sections], "arrest_date": arrest, "first_remand": first_remand,
              "custody_days": days, "as_of": as_of, "charge_sheet": {"filed": filed if isinstance(filed, bool) else False}}  # fmt: skip
    return record, constructed


def _case_bundle(
    case: dict[str, Any],
    record: dict[str, Any],
    kind: str,
    with_certificate: bool,
    order: list[str],
    rng_docs: random.Random,
) -> list[tuple[str, str, str]]:
    """(doc_id, type, text) of each document of one bundle, in bundle order."""
    hindi = kind in HINDI_KINDS
    lang = "hi" if hindi else "en"
    if hindi:
        main = companions.make_hindi_order(record, case.get("court"))
    else:
        main = str(case.get("facts_text") or "")[:MAX_ORDER_CHARS]
    docs = {
        "COURT_ORDER": main,
        "FIR": companions.make_fir(record, lang),
        "REMAND_ORDER": companions.make_remand_order(record, lang),
        "CUSTODY_CERTIFICATE": companions.make_custody_certificate(record, lang) if with_certificate else None,
    }
    present = [t for t in order if docs.get(t)]
    rng_docs.shuffle(present)
    return [(f"d{i + 1}", t, str(docs[t])) for i, t in enumerate(present)]


def _bundle(
    bundle_id: str,
    case_id: str,
    kind: str,
    docs: list[tuple[str, str, str]],
    fields: dict[str, Any],
    constructed: list[str],
    out: Path,
    seed: int,
) -> dict[str, Any]:
    lang = "hi" if kind in HINDI_KINDS else "en"
    pages: list[str] = []
    spans: list[dict[str, Any]] = []
    for doc_id, doc_type, text in docs:
        first = len(pages) + 1
        pages.extend(rendering.paginate(text, lang))
        spans.append({"doc_id": doc_id, "type": doc_type, "pages": [first, len(pages)]})
    pdf = out / "bundles" / f"{bundle_id}.pdf"
    rendering.render_pages(pages, str(pdf), kind, lang, seed)
    return {"bundle_id": bundle_id, "case_id": case_id, "kind": kind, "kind_name": KIND_NAMES[kind], "lang": lang, "text_layer": TEXT_LAYER[kind],
            "pdf": f"bundles/{bundle_id}.pdf", "pages": [{"page": i + 1, "text": t} for i, t in enumerate(pages)], "documents": spans, "fields": fields,
            "constructed": constructed}  # fmt: skip


def _hindi_docs(directory: str | None, limit: int, rng: random.Random) -> list[dict[str, Any]]:
    if not directory or not Path(directory).is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for f in sorted(Path(directory).glob("*.jsonl")):
        rows.extend(r for r in rows_from_file(f) if r.get("doc_id") and str(r.get("text") or "").strip())
    rows.sort(key=lambda r: str(r["doc_id"]))
    rng.shuffle(rows)
    return rows[:limit]


def _native_docs(path: str | None, limit: int, rng: random.Random) -> list[dict[str, Any]]:
    """Seeded draw of native Hindi High Court orders from `hindi_native.jsonl` (rows with `case_id` and `text`)."""
    if not path or not Path(path).is_file():
        return []
    rows = [r for r in rows_from_file(path) if r.get("case_id") and str(r.get("text") or "").strip()]
    rows.sort(key=lambda r: str(r["case_id"]))
    rng.shuffle(rows)
    return rows[:limit]


def _cut(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters at the last space or newline (the whole text when it is short)."""
    if len(text) <= limit:
        return text
    head = text[:limit]
    cut = max(head.rfind(" "), head.rfind("\n"))
    return head[:cut] if cut > limit // 2 else head


def build_t2_with(
    t1_dir: str,
    hldc_dir: str | None,
    escr_dir: str | None,
    out_dir: str,
    *,
    n_cases: int = N_CASES,
    kinds: tuple[str, ...] = KINDS,
    seed: int = SEED,
    native_path: str | None = None,
) -> TestSetManifest:
    """`build_t2` with the size and kinds spelled out (the CLI uses this); `native_path` adds the native Hindi High Court bundles (origin `native_hc`)."""
    started = time.time()
    rng = random.Random(seed)
    cases = sorted(load_t1_cases(t1_dir), key=lambda c: c["case_id"])
    rng.shuffle(cases)
    latin = [c for c in cases if c.get("script", "latin") == "latin"]
    chosen = (latin + [c for c in cases if c not in latin])[:n_cases]
    out = Path(out_dir)
    rows: list[dict[str, Any]] = []
    for i, case in enumerate(chosen):
        crng = random.Random(f"{seed}|{case['case_id']}")
        record, constructed = _fields(case, crng)
        with_cert = crng.random() < 2 / 3
        order = ["COURT_ORDER", "FIR", "REMAND_ORDER", "CUSTODY_CERTIFICATE"]
        fields = dict(record) if with_cert else {k: v for k, v in record.items() if k not in ("custody_days", "as_of")}
        for k, kind in enumerate(kinds):
            docs = _case_bundle(case, record, kind, with_cert, order, random.Random(f"{seed}|{case['case_id']}|{kind}"))
            rows.append(
                _bundle(
                    f"{case['case_id']}_{kind}",
                    case["case_id"],
                    kind,
                    docs,
                    fields,
                    [c for c in constructed if with_cert or c != "custody_days"],
                    out,
                    seed + 100 * i + k,
                )
            )
    available = {"hldc": False, "escr": False}
    for tag, directory, limit, doc_type in (
        ("hldc", hldc_dir, HLDC_MAX, "COURT_JUDGMENT_HI"),
        ("escr", escr_dir, ESCR_MAX, "SC_JUDGMENT_HI"),
    ):
        docs = _hindi_docs(directory, limit, rng)
        available[tag] = bool(docs)
        for n, d in enumerate(docs):
            bid = f"{tag}-{d['doc_id']}"
            rows.append(
                _bundle(
                    bid, bid, "K5", [("d1", doc_type, str(d["text"])[:MAX_ORDER_CHARS])], {}, [], out, seed + 7000 + n
                )
            )
    native = _native_docs(native_path, NATIVE_MAX, random.Random(f"{seed}|hindi_native"))
    for n, d in enumerate(native):
        bid = f"hnat-{d['case_id']}"
        text = _cut(str(d["text"]), MAX_ORDER_CHARS)
        row = _bundle(bid, bid, "K5", [("d1", "COURT_JUDGMENT_HI", text)], {}, [], out, seed + 9000 + n)
        row["origin"] = "native_hc"
        row["source"] = {"case_id": d["case_id"], "court": d.get("court"), "year": d.get("year"), "decision_date": d.get("decision_date"),
                         "chars_cut": len(str(d["text"])) - len(text)}  # fmt: skip
        rows.append(row)
    rows_to_file(out / "truth.jsonl", rows)
    pages = sum(len(r["pages"]) for r in rows)
    own = [r for r in rows if not r["bundle_id"].startswith(("hldc-", "escr-", "hnat-"))]
    details = {
        "seed": seed, "t1_cases": len(chosen), "kinds": list(kinds), "bundles": len(rows), "pages": pages,
        "bundles_per_kind": dict(sorted(Counter(r["kind"] for r in rows).items())), "pages_per_kind": {k: sum(len(r["pages"]) for r in rows if r["kind"] == k) for k in kinds},
        "documents_per_bundle": dict(sorted(Counter(len(r["documents"]) for r in own).items())),
        "per_court": dict(Counter(str(c.get("court")) for c in chosen)), "per_script": dict(Counter(str(c.get("script", "latin")) for c in chosen)),
        "bns_era_cases": sum(bool(c.get("bns_era")) for c in chosen),
        "fields_read_from_g3": {k: sum(1 for r in own if r["kind"] == kinds[0] and k not in r["constructed"]) for k in ("arrest_date", "first_remand", "sections", "custody_days")},
        "hldc_available": available["hldc"], "escr_available": available["escr"],
        "hldc_documents": sum(r["bundle_id"].startswith("hldc-") for r in rows), "escr_documents": sum(r["bundle_id"].startswith("escr-") for r in rows),
        "pdf_bytes": sum((out / r["pdf"]).stat().st_size for r in rows), "build_seconds": round(time.time() - started, 1),
        "source_cases_sha256": sha256_file(Path(t1_dir) / "cases.jsonl"), "blind_slice_used": False,
        "renderer": "PyMuPDF; Pillow/NumPy degradation (no Augraphy); K6 = raster page plus invisible Kruti-Dev-style text layer",
        "hindi_order_is_templated_summary": True,
        "not_built": [m for m, ok in (("HLDC Hindi documents: no input directory (Hugging Face access pending)", available["hldc"]), ("e-SCR Hindi judgments: no input directory", available["escr"])) if not ok],
    }  # fmt: skip
    if native_path:
        details["hindi_native"] = {"origin": "native_hc", "documents": len(native), "source": "High Court (Open India Law), not district-court Hindi like HLDC", "per_court": dict(sorted(Counter(str(d.get("court")) for d in native).items())),
                                   "per_year": dict(sorted(Counter(str(d.get("year")) for d in native).items())), "input_sha256": sha256_file(Path(native_path))}  # fmt: skip
    manifest = TestSetManifest(
        set_id="T2",
        size=len(rows),
        answers_from="construction: page text, document boundaries and types, field values",
        used_for=["RQ2", "F8"],
        path=str(out),
        details=details,
    )
    write_manifest(manifest, str(out))
    return manifest


def build_t2(t1_dir: str, hldc_dir: str | None, escr_dir: str | None, out_dir: str) -> TestSetManifest:
    """Build bundles with known page text, document boundaries, types and field values.

    Args:
        t1_dir: see behaviour
        hldc_dir: see behaviour
        escr_dir: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    return build_t2_with(t1_dir, hldc_dir, escr_dir, out_dir)


_SYNONYMS = {
    "number": ("number", "no"),
    "station": ("station", "ps"),
    "remand": ("remand", "remanded"),
    "days": ("days", "long", "period"),
}
_CLEAN_COPY = re.compile(
    r"clear|clean|re-?scan|re-?upload|upload|another copy|better copy|legible|unreadable", re.IGNORECASE
)


def _flatten(truth: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in truth.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "_"))
        else:
            out[key] = v
    return out


def _say(value: Any) -> str:
    text = str(value)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        y, m, d = text.split("-")
        return f"{d}.{m}.{y}"
    return text


def scripted_counsel(truth: dict[str, Any]) -> Callable[[str], str]:
    """Counsel stub that knows the true values and supplies a clean copy when asked (plan §15.5).

    The stub is more cooperative than real counsel (it never refuses and never takes time); it never invents a value: a question about something that is
    not in `truth` gets a non-answer without digits. `truth` keys are matched by their words (`arrest_date` answers "What is the date of arrest?");
    nested values are flattened (`fir.number` becomes `fir_number`); dates are given as dd.mm.yyyy; `clean_copy` is the reply to a request for a clearer copy.

    Args:
        truth: see behaviour

    Returns:
        Answer function.
    """
    flat = _flatten(truth)
    clean = flat.pop("clean_copy", None)

    def answer(question: str) -> str:
        q = question.lower()
        if clean is not None and _CLEAN_COPY.search(q) and re.search(r"copy|upload|scan|page|legible|unreadable", q):
            return str(clean)
        words = set(re.findall(r"[a-z0-9]+", q))
        best: tuple[int, str] | None = None
        for key in flat:
            tokens = key.lower().split("_")
            if all(any(alt in words for alt in _SYNONYMS.get(t, (t,))) for t in tokens):
                if best is None or len(tokens) > best[0]:
                    best = (len(tokens), key)
        if best:
            return f"{_say(flat[best[1]])}."
        return "I do not have that information in the file."

    return answer


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    base = Path(paths.testsets_dir)
    ap = argparse.ArgumentParser(description="Build T2 (messy bundles)")
    ap.add_argument("--t1", default=str(base / "t1"))
    ap.add_argument("--hldc", default=str(Path(paths.raw_dir) / "hldc"))
    ap.add_argument("--escr", default=str(Path(paths.raw_dir) / "escr"))
    ap.add_argument(
        "--hindi-native",
        default=None,
        help="data/interim/hindi_native.jsonl: add up to 200 native Hindi High Court bundles (origin native_hc)",
    )
    ap.add_argument(
        "--native-only",
        action="store_true",
        help="build only the native Hindi bundles (use --out data/testsets/t2_hindi_native)",
    )
    ap.add_argument("--out", default=str(base / "t2"))
    ap.add_argument("--cases", type=int, default=N_CASES)
    ap.add_argument("--small", action="store_true", help=f"{SMALL_CASES} cases (CI-sized)")
    args = ap.parse_args(argv)
    n_cases = 0 if args.native_only else SMALL_CASES if args.small else args.cases
    if args.native_only and not args.hindi_native:
        ap.error("--native-only needs --hindi-native FILE")
    m = build_t2_with(
        args.t1,
        None if args.native_only else args.hldc,
        None if args.native_only else args.escr,
        args.out,
        n_cases=n_cases,
        native_path=args.hindi_native,
    )
    print(
        json.dumps(
            {
                "size": m.size,
                **{
                    k: m.details[k]
                    for k in (
                        "t1_cases",
                        "bundles",
                        "pages",
                        "bundles_per_kind",
                        "documents_per_bundle",
                        "pdf_bytes",
                        "build_seconds",
                        "not_built",
                    )
                },
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
