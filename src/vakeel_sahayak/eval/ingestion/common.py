"""Shared pieces of the RQ2 ingestion pipelines P1-P6 and Munshi (plan §15.5): the result record, single-document reports for the
page-reading baselines, a Tesseract command-line fallback for P2, and local scoring helpers.

The local helpers (`edit_distance`, `character_error_rate`, `boundary_f1`, `by_kind`, `escalation_rate`, `questions_asked`, `field_scores`) exist because
`eval/metrics/ingestion.py` is still a stub owned by another teammate. They have the interface the tests of that module expect, so the module can
adopt them unchanged.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vakeel_sahayak.ingestion.hindi import lang_of
from vakeel_sahayak.models.base import ModelUnavailable, OcrClient
from vakeel_sahayak.schemas.enums import DocumentType, PageStatus
from vakeel_sahayak.schemas.ingestion_report import DocumentEntry, IngestionReport, PageRoute

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
TRUTH_DOC_TYPES: dict[str, str] = {  # T2 construction labels -> the labels Munshi assigns
    "FIR": "FIR", "COURT_ORDER": "BAIL_ORDER", "REMAND_ORDER": "REMAND_ORDER", "CUSTODY_CERTIFICATE": "CUSTODY_CERTIFICATE",
    "COURT_JUDGMENT_HI": "BAIL_ORDER",
}


class ArmUnavailable(RuntimeError):
    """A pipeline's backend is not installed here; the runner records the arm as unavailable instead of a number."""


@dataclass
class BundleResult:
    """What one pipeline produced for one bundle: the report, the page texts it read (kept in memory, never in the report) and notes."""

    report: IngestionReport
    page_texts: list[str] = field(default_factory=list)
    counsel_answers: list[tuple[str, str]] = field(default_factory=list)  # (question, answer) of the scripted counsel
    notes: list[str] = field(default_factory=list)


def case_id_for(pdf_path: str) -> str:
    """A valid case id for a bundle file name (letters, digits and hyphens)."""
    stem = re.sub(r"[^A-Za-z0-9]+", "-", Path(pdf_path).stem).strip("-").lower() or "bundle"
    return stem if stem[0].isalnum() else f"b-{stem}"


def page_route_of(page: int, outcome: Any, kind: str = "unclassified") -> PageRoute:
    """The report entry of one page read by a baseline (a `RouteOutcome`)."""
    return PageRoute(page=page, kind=kind, route=list(outcome.log) or [str(outcome.route.value)],
                     ocr_conf=round(outcome.ocr_conf, 2) if outcome.ocr_conf is not None else None, status=outcome.status)


def single_document_report(pdf_path: str, routes: list[PageRoute], texts: list[str]) -> IngestionReport:
    """The report of a baseline that neither splits nor labels: one OTHER document that covers pages 1..N."""
    body = "\n".join(t for t in texts if t.strip())
    doc = DocumentEntry(doc_id="d1", type=DocumentType.OTHER, pages=[1, max(1, len(routes))], lang=lang_of(body) if body.strip() else "en",
                        page_routes=routes)
    return IngestionReport(case_id=case_id_for(pdf_path), file=Path(pdf_path).name, documents=[doc] if routes else [])


def page_count(pdf_path: str) -> int:
    """Pages of a file through the page-source abstraction (PyMuPDF for PDFs)."""
    from vakeel_sahayak.ingestion.source import open_source

    return open_source(pdf_path).page_count


# ---------------------------------------------------------------------------------------------- Tesseract command line
def tesseract_languages() -> set[str]:
    """Languages the installed Tesseract binary has data for (empty when there is no binary)."""
    exe = shutil.which("tesseract")
    if not exe:
        return set()
    out = subprocess.run([exe, "--list-langs"], capture_output=True, text=True, timeout=30).stdout.splitlines()
    return {ln.strip() for ln in out[1:] if ln.strip()}


class TesseractCliOcr(OcrClient):
    """Tesseract through its command line (no pytesseract needed), for the P2 arm when no OCR client is configured.

    Asked for 'hin+eng' it uses the languages the machine has: when Hindi data is missing it reads with English only, and `last_note` says so
    (the plan names eng+hin; a Hindi page then scores a high CER, which is the measured effect of the missing data, not of the pipeline).
    """

    name = "tesseract-cli"

    def __init__(self) -> None:
        """No state until the first call."""
        self.last_note = ""

    def ocr(self, image: bytes, lang: str) -> tuple[str, float, list[list[float]]]:
        """Text, mean word confidence (0-1) and word boxes of a page image.

        Raises:
            ModelUnavailable: no tesseract binary.
        """
        exe = shutil.which("tesseract")
        if not exe:
            raise ModelUnavailable("the tesseract binary is not installed", "ocr")
        have = tesseract_languages()
        want = [x for x in lang.replace("hin+eng", "hin+eng").split("+") if x]
        use = [x for x in want if x in have] or (["eng"] if "eng" in have else [])
        self.last_note = "" if len(use) == len(want) else f"tesseract data missing for {sorted(set(want) - set(use))}; read with {use}"
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "page.png"
            src.write_bytes(image)
            proc = subprocess.run([exe, str(src), "stdout", "-l", "+".join(use), "tsv"], capture_output=True, text=True, timeout=300)
        lines, words, confs, boxes, current, key = [], 0, [], [], [], None
        for row in proc.stdout.splitlines()[1:]:
            cols = row.split("\t")
            if len(cols) < 12 or not cols[11].strip():
                continue
            k = (cols[2], cols[3], cols[4])
            if key is not None and k != key:
                lines.append(" ".join(current))
                current = []
            key = k
            current.append(cols[11])
            words += 1
            confs.append(max(0.0, float(cols[10])) / 100.0)
            x, y, w, h = (float(cols[i]) for i in (6, 7, 8, 9))
            boxes.append([x, y, x + w, y + h])
        if current:
            lines.append(" ".join(current))
        return "\n".join(lines), (sum(confs) / len(confs) if confs else 0.0), boxes


def ocr_client() -> OcrClient:
    """The configured OCR client; when only the offline stand-in is configured and a Tesseract binary exists, Tesseract through its command line."""
    from vakeel_sahayak.models import factory
    from vakeel_sahayak.models.offline import OfflineOcrClient

    client = factory.get_ocr()
    if isinstance(client, OfflineOcrClient) and shutil.which("tesseract"):
        return TesseractCliOcr()
    return client


# ---------------------------------------------------------------------------------------------- local metrics
def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance (Hyyro's bit-parallel form; exact)."""
    if a == b:
        return 0
    while a and b and a[0] == b[0]:
        a, b = a[1:], b[1:]
    while a and b and a[-1] == b[-1]:
        a, b = a[:-1], b[:-1]
    if not a or not b:
        return len(a) or len(b)
    if len(b) > len(a):
        a, b = b, a
    m = len(b)
    full = (1 << m) - 1
    high = 1 << (m - 1)
    peq: dict[str, int] = {}
    for i, ch in enumerate(b):
        peq[ch] = peq.get(ch, 0) | (1 << i)
    pv, mv, score = full, 0, m
    for ch in a:
        eq = peq.get(ch, 0)
        xv = eq | mv
        xh = (((eq & pv) + pv) ^ pv) | eq
        ph = (mv | ~(xh | pv)) & full
        mh = pv & xh
        if ph & high:
            score += 1
        elif mh & high:
            score -= 1
        ph = ((ph << 1) | 1) & full
        mh = (mh << 1) & full
        pv = (mh | ~(xv | ph)) & full
        mv = ph & xv
    return score


def normalise_text(text: str) -> str:
    """Whitespace collapsed (layout differs between a page and its reading; the characters are what the CER compares)."""
    return re.sub(r"\s+", " ", text or "").strip()


def character_error_rate(hyp: str, ref: str) -> float:
    """CER = edit distance over reference length, after whitespace normalisation. An empty reference gives 0.0 for an empty hypothesis, else 1.0."""
    h, r = normalise_text(hyp), normalise_text(ref)
    if not r:
        return 0.0 if not h else 1.0
    return edit_distance(h, r) / len(r)


def script_of(text: str) -> str:
    """'devanagari' when more than 30% of the letters are Devanagari, else 'latin'."""
    letters = [c for c in text if c.isalpha()]
    return "devanagari" if letters and sum(bool(DEVANAGARI.match(c)) for c in letters) / len(letters) > 0.3 else "latin"


def boundary_f1(pred: list[tuple[int, int]], gold: list[tuple[int, int]]) -> float:
    """F1 of predicted against true (first page, last page) ranges, by exact match."""
    p, g = {tuple(x) for x in pred}, {tuple(x) for x in gold}
    if not p and not g:
        return 1.0
    hit = len(p & g)
    if not hit:
        return 0.0
    prec, rec = hit / len(p), hit / len(g)
    return 2 * prec * rec / (prec + rec)


def by_kind(values: list[tuple[str, float]]) -> dict[str, float]:
    """Mean score per input kind (K1-K6); a kind with no bundles does not appear."""
    sums: dict[str, list[float]] = {}
    for kind, v in values:
        sums.setdefault(kind, []).append(float(v))
    return {k: sum(v) / len(v) for k, v in sums.items()}


def escalation_rate(report: IngestionReport) -> float:
    """Share of pages whose route log reaches the vision model."""
    routes = [pr for d in report.documents for pr in d.page_routes]
    if not routes:
        return 0.0
    return sum(any(step.lower().startswith("vision") for step in pr.route) for pr in routes) / len(routes)


def questions_asked(report: IngestionReport) -> int:
    """Questions to counsel in the report."""
    return len(report.questions)


def unreadable_share(report: IngestionReport) -> float:
    """Share of pages left UNREADABLE."""
    routes = [pr for d in report.documents for pr in d.page_routes]
    return sum(pr.status == PageStatus.UNREADABLE for pr in routes) / len(routes) if routes else 0.0


# ---------------------------------------------------------------------------------------------- downstream fields
FIELD_NAMES = ("arrest_date", "offence_date", "first_remand", "fir.number", "fir.date", "fir.police_station", "sections")


def _norm_section(s: str) -> str:
    return re.sub(r"[^a-z0-9()]+", "", s.lower().replace("section", "").replace("sec", ""))


def read_fields(passages: list[dict[str, Any]]) -> dict[str, Any]:
    """The dossier fields read from passages by the offline rule extractor (the stand-in of the fine-tuned 4B that plan §15.5 names).

    Args:
        passages: `{"doc", "page", "doc_type", "text"}` per page (plus counsel answers as passages without a doc type)

    Returns:
        Field name -> value (None when nothing was read); `sections` is a list.
    """
    from types import SimpleNamespace

    from vakeel_sahayak.agents.peshkar.fields import TASK_FIELD_NAMES
    from vakeel_sahayak.agents.peshkar.offline import extract_field_offline

    out: dict[str, Any] = {}
    for name in TASK_FIELD_NAMES:
        if name not in ("fir", "offence_date", "arrest_date", "first_remand", "sections"):
            continue
        try:
            got = extract_field_offline(SimpleNamespace(case={"field": name, "passages": passages, "timeline": [], "retry": 0}))  # type: ignore[arg-type]
        except Exception:  # noqa: BLE001 - a reader crash on garbled text is a missed field, not a failed bundle
            got = {"items": []}
        items = got.get("items") or []
        if name == "fir":
            val = next((i["value"] for i in items if isinstance(i.get("value"), dict)), None) or {}
            out["fir.number"], out["fir.date"], out["fir.police_station"] = val.get("number"), val.get("date"), val.get("police_station")
        elif name == "sections":
            out["sections"] = [i["value"].get("as_written", "") for i in items if isinstance(i.get("value"), dict)]
        else:
            out[name] = items[0]["value"] if items else None
    return out


def _truth_value(fields: dict[str, Any], name: str) -> Any:
    cur: Any = fields
    for part in name.split("."):
        cur = cur.get(part) if isinstance(cur, dict) else None
    return cur


def field_scores(read: dict[str, Any], truth_fields: dict[str, Any]) -> dict[str, bool]:
    """Per field present in the construction truth: whether the reading matches (dates as ISO strings, sections as sets)."""
    scores: dict[str, bool] = {}
    for name in FIELD_NAMES:
        want = _truth_value(truth_fields, name)
        if want in (None, "", []):
            continue
        got = read.get(name)
        if name == "sections":
            scores[name] = {_norm_section(s) for s in (got or [])} == {_norm_section(str(s)) for s in want}
        else:
            scores[name] = str(got or "").strip().lower() == str(want).strip().lower()
    return scores


def passages_from(report: IngestionReport, page_texts: list[str], counsel: list[tuple[str, str]] | None = None) -> list[dict[str, Any]]:
    """Passages for the field reader: each page with the label of the document it sits in; counsel's answers as unlabelled passages."""
    label: dict[int, str] = {}
    for d in report.documents:
        for p in range(d.pages[0], d.pages[1] + 1):
            label[p] = d.type.value
    passages = [{"doc": f"d-p{i}", "page": i, "doc_type": label.get(i), "text": t} for i, t in enumerate(page_texts, start=1) if t.strip()]
    passages += [{"doc": "counsel", "page": None, "doc_type": None, "text": f"{q} {a}"} for q, a in (counsel or []) if a.strip()]
    return passages
