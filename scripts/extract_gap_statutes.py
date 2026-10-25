"""Extract chosen sections of the CrPC 1973 and the NDPS Act 1985 from official PDFs into data/gaps/statutes/*.jsonl.

Sources (all official, retrieved on the date written into every row's `retrieved` field):

* CrPC 1973, India Code consolidated text on the Legislative Department / India Code CDN:
  https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf
  saved as `data/gaps/raw/crpc_candidate.pdf` (261 pages, text layer, footnotes in 9 pt).
* NDPS Act 1985, Department of Revenue (Ministry of Finance) consolidated text, "Last Update 3-1-2022":
  https://dor.gov.in/files/acts_files/NDPS_1985.pdf  saved as `data/gaps/raw/ndps_dor_clean.pdf` (54 pages, clean text layer).
  The other copy we had (`ndps_candidate.pdf`, dor.gov.in `Narcotic-Drugs-...-1985_0.pdf`) is a bad OCR scan ('Sec. 27Al', 'tns.')
  and is NOT used; `--ndps-pdf` can still point at it, in which case rows get `ocr: true` and the mechanical fixes in `OCR_FIXES`.

Nothing is typed from memory. Every statutory word comes from the PDF text layer. The only mechanical edits are:

1. spans in 7 pt or smaller are dropped (footnote reference numerals such as the "1" in "1[Provided that");
2. from the first footnote line of a page (first span 9.5 pt or smaller, starting "N. ", in the lower part of the page) down, text is
   dropped (amendment footnotes: "1. Ins. by Act 41 of 2010 ...");
3. page-number lines are dropped;
4. square brackets are deleted (in consolidated bare acts they only mark amended text);
5. a section ends at the next section heading, the next CHAPTER line, a "STATE AMENDMENT(S)" line, or the start of a Schedule, so
   state-amendment notes after a Central section are cut and the section's own provisos and explanations are kept;
6. lines are joined with spaces, new paragraphs start at "(1)", "(a)", "Provided", "Explanation" and "Illustration" lines.

First Schedule (CrPC, Part I, offences under the IPC): the table is read by x position into the six columns; "Ditto" repeats the cell
above, "According as the offence abetted is cognizable" and similar conditional cells give None; a section with several sub-rows whose
flags differ gets None for that flag. Flags go to `data/gaps/statutes/first_schedule_ipc.jsonl` as IPC rows with EMPTY text, which
`StatuteStore._merge_gap_rows` treats as "add the flags to the existing (IPC, section) row". NDPS flags are derived from the parsed s.37 text.

Usage: python scripts/extract_gap_statutes.py [--crpc-pdf P] [--ndps-pdf P] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pymupdf

RAW = Path("data/gaps/raw")
OUT = Path("data/gaps/statutes")
CRPC_URL = "https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf"
NDPS_URL = "https://dor.gov.in/files/acts_files/NDPS_1985.pdf"
CRPC_SECTIONS = ["41", "41A", "50", "57", "167", "436", "436A", "437", "438", "439"]
NDPS_SECTIONS = ["19", "24", "27A", "31A", "37"]

# Mechanical OCR repairs, used only with --ndps-pdf pointing at the OCR scan (rows then carry ocr: true).
OCR_FIXES: list[tuple[str, str]] = [
    (r"\bSec\.\s*(\d+[A-Z])l\b", r"Sec. \1"),  # 'Sec. 27Al' -> 'Sec. 27A'
    (r"\bPsychottopic\b", "Psychotropic"),
    (r"\btns\b\.?", "this"),
]

FOOT_SIZE = 9.5
SUPER_SIZE = 7.5


@dataclass
class Line:
    """One visual line of a PDF page: position, the spans' sizes and the text without superscript spans."""

    page: int
    x: float
    y: float
    size: float
    text: str


def pdf_lines(path: Path, first_page: int = 0, last_page: int | None = None) -> list[Line]:
    """Read the lines of a PDF, dropping superscript spans, footnote blocks and page numbers (rules 1 to 3 in the module docstring)."""
    doc = pymupdf.open(path)
    out: list[Line] = []
    end = len(doc) if last_page is None else last_page + 1
    for pno in range(first_page, end):
        page_lines: list[Line] = []
        for block in doc[pno].get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                spans = [s for s in ln["spans"] if s["size"] > SUPER_SIZE]
                text = "".join(s["text"] for s in spans).replace(" ", " ")
                if not text.strip():
                    continue
                size = spans[0]["size"]
                page_lines.append(Line(pno, ln["bbox"][0], ln["bbox"][1], size, text))
        page_lines.sort(key=lambda ln: (ln.y, ln.x))
        cut = None
        for ln in page_lines:
            if ln.y > 400 and ln.size <= FOOT_SIZE and re.match(r"\s*\d{1,2}\.\s", ln.text):
                cut = ln.y - 1
                break
        for ln in page_lines:
            if cut is not None and ln.y >= cut:
                continue
            if re.fullmatch(r"\s*\d{1,4}\s*", ln.text) and (ln.y > 740 or ln.y < 45):
                continue
            out.append(ln)
    return out


_PARA = re.compile(r"^\s*(\(\w{1,4}\)|Provided|Explanation|Illustration)")


def join_lines(lines: list[Line]) -> str:
    """Join lines into paragraphs (rule 6) and delete square brackets (rule 4)."""
    paras: list[str] = []
    for ln in lines:
        text = re.sub(r"[ \t]+", " ", ln.text.replace("[", "").replace("]", "")).strip()
        if not text:
            continue
        if not paras or _PARA.match(text):
            paras.append(text)
        else:
            paras[-1] += " " + text
    return re.sub(r"\.\.$", ".", "\n".join(paras))  # a closing amendment bracket after the final full stop leaves "..": keep one


_START = re.compile(r"^\s*\[*\s*(\d{1,3}[A-Z]{0,2})\.\s+(?=[A-Z])")
_STOP = re.compile(r"^\s*(CHAPTER\s+[IVXL]+|STATE AMENDMENTS?|THE\s+(FIRST|SECOND|SCHEDULE)\b)", re.I)


def _key(n: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d+)([A-Z]*)", n)
    assert m
    return int(m.group(1)), m.group(2)


def split_sections(lines: list[Line], wanted: list[str]) -> dict[str, str]:
    """Cut the body into sections; return {section: text} for the wanted ones.

    A section heading is a line "<num>. Heading" whose section ends with ".—" within its first 400 characters (this skips the table of
    arrangement of sections), with numbers that increase through the Act. The body ends at the first Schedule heading that follows body text.
    """
    starts: list[tuple[str, int]] = []  # (section, index into lines)
    last = (0, "")
    for i, ln in enumerate(lines):
        m = _START.match(ln.text)
        if not m:
            continue
        num = m.group(1)
        head = " ".join(x.text for x in lines[i : i + 4])
        if "—" not in head[:400] and ".-" not in head[:400]:
            continue
        k = _key(num)
        if last == (0, "") and k != (1, ""):
            continue
        if k > last and k[0] - last[0] <= 4:
            starts.append((num, i))
            last = k
    out: dict[str, str] = {}
    for n, (num, i) in enumerate(starts):
        if num not in wanted:
            continue
        end = starts[n + 1][1] if n + 1 < len(starts) else len(lines)
        body = [lines[i]]
        for ln in lines[i + 1 : end]:
            if _STOP.match(ln.text):
                break
            body.append(ln)
        out[num] = join_lines(body)
    return out


def apply_ocr_fixes(text: str) -> str:
    """Apply the fixed regex list OCR_FIXES (only for OCR-derived sources)."""
    for pat, rep in OCR_FIXES:
        text = re.sub(pat, rep, text)
    return text


def ndps_flags(sections: dict[str, str]) -> dict[str, dict[str, bool]]:
    """Cognisable / bailable flags for the NDPS rows, read from the parsed s.37 text (not assumed).

    cognisable=True for every NDPS section when s.37(1)(a) says every offence is cognizable; bailable=False for s.37 and for the sections
    that s.37(1)(b) names as barred from bail without the Public Prosecutor and twin-conditions test.
    """
    s37 = sections.get("37", "")
    flags: dict[str, dict[str, bool]] = {}
    cog = bool(re.search(r"every offence punishable under this Act shall be cognizable", s37))
    barred = {s for s in re.findall(r"section (\d+[A-Z]?)", s37.split("(b)", 1)[-1].split("(i)", 1)[0])}
    nb = "non-bailable" in s37.split("\n", 1)[0].lower() and "shall be released on bail or on his own bond unless" in s37
    for s in sections:
        f: dict[str, bool] = {}
        if cog:
            f["cognisable"] = True
        if nb and (s == "37" or s in barred):
            f["bailable"] = False
        flags[s] = f
    return flags


# ---------------------------------------------------------------- First Schedule

_SEC = re.compile(r"\d{1,3}[A-Z]{0,2}")
_HEADER_WORDS = {"Section", "Offence", "Punishment", "Cognizable or non-", "cognizable", "Bailable or Non-", "bailable", "By what", "Court triable"}
# Left edges that separate the six columns of the First Schedule (x in points; the second edge is re-estimated per page).
COL_EDGES = (81, 250, 350, 428, 472)
_COLNUM = re.compile(r"[1-6]")


def _col(x: float, bounds: list[float]) -> int:
    """Column index 0 to 5 of a left x position."""
    return sum(x >= b for b in bounds)


def schedule_pages(path: Path) -> tuple[int, int]:
    """Page range (0-based) of Part I of the First Schedule: from the 'I.-OFFENCES UNDER THE INDIAN PENAL CODE' line to the Part II line."""
    doc = pymupdf.open(path)
    first = last = None
    for p in range(len(doc)):
        t = doc[p].get_text()
        if first is None and re.search(r"I\.\W*OFFENCES UNDER THE INDIAN PENAL CODE", t) and "Cognizable or" in t:
            first = p
        if first is not None and re.search(r"II\.\W*CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS", t):
            last = p
            break
    if first is None or last is None:
        raise ValueError("First Schedule Part I not found")
    return first, last


def _cell_flag(cell: str, kind: str, prev: bool | None) -> tuple[bool | None, str]:
    """Read one cell: ('Cognizable'|'Non-cognizable') or ('Bailable'|'Non-bailable'); returns (value, status) status in ok/ditto/cond/none."""
    c = re.sub(r"\s+", "", cell.lower()).replace("-", "")
    if not c:
        return None, "none"
    if "ditto" in c:
        return prev, "ditto"
    if "accordingas" in c or "accordingto" in c:
        return None, "cond"
    if kind == "cog":
        if c.startswith("noncognizable"):
            return False, "ok"
        if c.startswith("cognizable"):
            return True, "ok"
    else:
        if c.startswith("nonbailable"):
            return False, "ok"
        if c.startswith("bailable"):
            return True, "ok"
    return None, "none"


def parse_first_schedule(path: Path) -> tuple[list[dict], list[str]]:
    """Parse Part I (IPC) of the CrPC First Schedule into per-section rows {section, bailable, cognisable, subrows}.

    Returns (rows, notes): notes list sections whose flags are conditional ('According as ...'), mixed across sub-rows, or unparsed.
    """
    first, last = schedule_pages(path)
    doc = pymupdf.open(path)
    items: list[tuple[int, float, int, str]] = []  # (page, y, column, text) of the table text
    for p in range(first, last + 1):
        page_items: list = []
        for block in doc[p].get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                text = "".join(s["text"] for s in ln["spans"] if s["size"] > 6).replace("[", "").replace("]", "").strip()
                size = next((sp["size"] for sp in ln["spans"] if sp["size"] > 6), 0)
                if not text or ln["bbox"][1] > 740 or ln["bbox"][1] < 70 or not 6.8 <= size <= 9.2:
                    continue
                if re.match(r"CHAPTER\b", text) or text in _HEADER_WORDS:
                    continue
                page_items.append((p, ln["bbox"][1], ln["bbox"][0], text))
        by_y: dict[int, int] = {}
        for _, y, _x, t in page_items:
            if _COLNUM.fullmatch(t):
                by_y[round(y / 4)] = by_y.get(round(y / 4), 0) + 1
        header = {k for k, v in by_y.items() if v >= 3}  # the "1 2 3 4 5 6" line of column numbers
        page_items = [it for it in page_items if not (_COLNUM.fullmatch(it[3]) and round(it[1] / 4) in header)]
        bounds = list(COL_EDGES)
        lefts = Counter(round(it[2]) for it in page_items if 225 <= it[2] <= 265)
        if lefts:  # the punishment column starts at a different x on different pages: use the commonest left edge in 225-265
            bounds[1] = lefts.most_common(1)[0][0] - 8
        page_items = [(pp, y, _col(x, bounds), t) for pp, y, x, t in page_items]
        foot = [y for _, y, x, t in page_items if y > 400 and x == 0 and re.match(r"\d{1,2}\.\s", t)]
        cut = min(foot) - 1 if foot else 10**6  # amendment footnotes at the foot of the page
        items.extend(it for it in page_items if it[1] < cut)
    items.sort()
    # row starts: a section number, or a col-2 line more than 14 pt below the previous col-2 line (or on a new page)
    starts: list[tuple[int, float]] = []
    prev: tuple[int, float] | None = None
    for p, y, col, t in items:
        if col == 0 and _SEC.fullmatch(re.sub(r"\s+", "", t)):  # a section number always opens a row
            if not starts or starts[-1] != (p, y):
                starts.append((p, y))
            prev = (p, y)
        elif col == 1:
            if prev is None or prev[0] != p or y - prev[1] > 14:
                starts.append((p, y))
            prev = (p, y)
    rows: list[dict] = []
    for n, (p, y) in enumerate(starts):
        nxt = starts[n + 1] if n + 1 < len(starts) else (10**6, 0)
        cells = {c: [] for c in range(6)}
        for ip, iy, ic, it in items:
            if (ip, iy) >= (p, y - 6) and (ip, iy) < (nxt[0], nxt[1] - 6):
                cells[ic].append((ip, iy, ic, it))
        rows.append({c: " ".join(t for *_, t in sorted(v)) for c, v in cells.items()})
    sections: dict[str, dict] = {}
    notes: list[str] = []
    cur: str | None = None
    prev_cog: bool | None = None
    prev_bail: bool | None = None
    for r in rows:
        sec = re.sub(r"\s+", "", r[0])
        if _SEC.fullmatch(sec):
            cur = sec
        if cur is None or not r[1] or re.fullmatch(r"\d", r[1].strip()):  # no offence text, or a repeated column-number line
            continue
        cog, cs = _cell_flag(r[3], "cog", prev_cog)
        bail, bs = _cell_flag(r[4], "bail", prev_bail)
        if cs == "ok" or cs == "ditto":
            prev_cog = cog
        if bs == "ok" or bs == "ditto":
            prev_bail = bail
        if cs == "cond":
            prev_cog = None
        if bs == "cond":
            prev_bail = None
        d = sections.setdefault(cur, {"cog": [], "bail": [], "n": 0, "status": []})
        d["cog"].append(cog)
        d["bail"].append(bail)
        d["n"] += 1
        d["status"].append((cs, bs))
    out: list[dict] = []
    for s, d in sections.items():
        row: dict = {"section": s, "subrows": d["n"]}
        for key, field in (("cog", "cognisable"), ("bail", "bailable")):
            vals = set(d[key])
            if len(vals) == 1 and None not in vals:
                row[field] = vals.pop()
            else:
                row[field] = None
                notes.append(f"s.{s} {field}: {'mixed' if len(vals - {None}) > 1 else 'conditional or unparsed'} across {d['n']} sub-rows")
        out.append(row)
    return out, notes


# ---------------------------------------------------------------- main


def build_rows(code: str, pdf: Path, url: str, wanted: list[str], today: str, ocr: bool = False) -> tuple[list[dict], list[str]]:
    """Extract the wanted sections of one Act into StatuteRow dicts; returns (rows, missing sections)."""
    lines = pdf_lines(pdf)
    found = split_sections(lines, wanted)
    flags = ndps_flags(found) if code == "NDPS" else {}
    rows, missing = [], []
    for s in wanted:
        if s not in found:
            missing.append(s)
            continue
        text = apply_ocr_fixes(found[s]) if ocr else found[s]
        row = dict(code=code, section=s, text=text, source_url=url, retrieved=today, **flags.get(s, {}))
        if ocr:
            row["ocr"] = True
        rows.append(row)
    return rows, missing


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Write one JSON object per line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run the extraction and print counts and failures."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--crpc-pdf", type=Path, default=RAW / "crpc_candidate.pdf")
    ap.add_argument("--ndps-pdf", type=Path, default=RAW / "ndps_dor_clean.pdf")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    today = date.today().isoformat()
    ocr = args.ndps_pdf.name == "ndps_candidate.pdf"
    failures = 0
    for code, pdf, url, wanted, name, is_ocr in (
        ("CrPC", args.crpc_pdf, CRPC_URL, CRPC_SECTIONS, "crpc.jsonl", False),
        ("NDPS", args.ndps_pdf, NDPS_URL, NDPS_SECTIONS, "ndps.jsonl", ocr),
    ):
        rows, missing = build_rows(code, pdf, url, wanted, today, is_ocr)
        write_jsonl(args.out / name, rows)
        print(code, [(r["section"], len(r["text"])) for r in rows])
        for s in missing:
            print(f"MISSING {code} s.{s}", file=sys.stderr)
            failures += 1
    sched, notes = parse_first_schedule(args.crpc_pdf)
    ipc_rows = [
        dict(code="IPC", section=r["section"], text="", bailable=r["bailable"], cognisable=r["cognisable"], source_url=CRPC_URL, retrieved=today)
        for r in sched
        if r["bailable"] is not None or r["cognisable"] is not None
    ]
    write_jsonl(args.out / "first_schedule_ipc.jsonl", ipc_rows)
    print(f"First Schedule Part I: {len(sched)} IPC sections parsed, {len(ipc_rows)} rows with at least one flag")
    for n in notes:
        print("NOTE", n)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
