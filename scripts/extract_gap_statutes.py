"""Extract chosen sections of the CrPC 1973, the NDPS Act 1985, the BNSS 2023 and the Companies Act 2013 from official PDFs into data/gaps/statutes/*.jsonl.

Sources (all official, retrieved on the date written into every row's `retrieved` field):

* CrPC 1973, India Code consolidated text on the Legislative Department / India Code CDN:
  https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf
  saved as `data/gaps/raw/crpc_candidate.pdf` (261 pages, text layer, footnotes in 9 pt).
* NDPS Act 1985, Department of Revenue (Ministry of Finance) consolidated text, "Last Update 3-1-2022":
  https://dor.gov.in/files/acts_files/NDPS_1985.pdf  saved as `data/gaps/raw/ndps_dor_clean.pdf` (54 pages, clean text layer).
  The other copy we had (`ndps_candidate.pdf`, dor.gov.in `Narcotic-Drugs-...-1985_0.pdf`) is a bad OCR scan ('Sec. 27Al', 'tns.')
  and is NOT used; `--ndps-pdf` can still point at it, in which case rows get `ocr: true` and the mechanical fixes in `OCR_FIXES`.
* BNSS 2023 (No. 46 of 2023), the Gazette of India, Extraordinary, Part II Section 1, 25 December 2023 (Legislative Department):
  https://egazette.gov.in/WriteReadData/2023/250884.pdf  saved as `data/gaps/raw/bnss_gazette.pdf` (249 pages). `--fetch` downloads it
  over verified TLS and refuses any file whose SHA-256 is not `BNSS_SHA256`. Only s.58 is taken: the Open India Law row for BNSS s.58
  carries the heading of s.58 and the body of s.59 (`docs/handoff/rights-fixes.md`); the gap row replaces it in the statute store. The
  Gazette prints a section's heading as a margin note, so `gazette_sections` reads the body from the text column and the heading from the
  margin note level with it.
* Companies Act 2013, the Ministry of Corporate Affairs text with its amendment footnotes as hosted by the Technology Development Board
  (Government of India): https://tdb.gov.in/sites/default/files/2024-05/companiesact2013.pdf  saved as `data/gaps/raw/companies_act_2013.pdf`
  (288 pages, PDF dated 3 March 2016, so amendments after that date are not in it; mca.gov.in answers Access Denied to scripts and India
  Code was down when this was written). `--fetch` refuses any file whose SHA-256 is not `COMPANIES_SHA256`. Only s.212 is taken: the Rights
  rule `antil_category` cites s.212(6).

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
above, "According as the offence abetted is cognizable", "Cognizable if ..." and similar conditional cells give None; a section with
several sub-rows whose flags differ gets None for that flag. Flags go to `data/gaps/statutes/first_schedule_ipc.jsonl` as IPC rows with
EMPTY text, which `StatuteStore._merge_gap_rows` treats as "add the flags to the existing (IPC, section) row". The whole table (offence,
punishment, normalised maximum, cognisable, bailable, triable by, the sub-rows as printed, source URL and SHA-256) goes to the committed
`configs/first_schedule_crpc_ipc.jsonl` with a `.meta.json` sidecar (source, date, coverage, every unresolved cell). Fixes of 13 Nov 2026
over the first parser (which read a flag the wrong way round for 43 sections, e.g. IPC 364, 365, 452 to 461 as bailable): cell words are read
left to right within a line, not alphabetically; sub-rows are cut where a flag cell starts, so sub-rows printed 11 pt apart and sub-rows
with a blank offence cell are separate; "Ditto" counts only when the cell starts with it; the bailable column edge is found per page; the
Part II table on the last page and the column headings are not read as rows. A "Ditto" under an amended entry whose own sub-rows differ
(s.355 under the 2013 entries for ss.354A to 354D) is left unresolved.

BNSS First Schedule (Part I, offences under the BNS), from the same pinned Gazette PDF (`parse_bnss_schedule`): read word by word in
the Gazette's fixed columns, entries such as "318(4)" become sub-rows of section 318 with `subsection` "(4)"; flags go to
`data/gaps/statutes/first_schedule_bns.jsonl` (empty-text BNS rows) and the table to `configs/first_schedule_bnss_bns.jsonl`.

First Schedule Part II ("II.-CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS") of both the CrPC and the BNSS (`parse_part2`, key `part2`,
also run when both schedules are): the three rows of each, read from the heading down to the end of the table (a footnote, a page number,
"STATE AMENDMENTS" or "THE SECOND SCHEDULE"), "Ditto" resolved to the cell above, and the punishment band of each row derived by rule from
the printed offence cell (`part2_band`), go to the committed `configs/first_schedule_part2.jsonl` with a `.meta.json` sidecar.

NDPS: every section of the Act is extracted (the store had only five, so `get('NDPS', '22')` failed); cognisable / bailable flags are read
from the parsed s.37 text and given to the sections that say "shall be punishable" or "shall be punished", which also get
`max_punishment` by the store's own rule (`oil_ingest.max_punishment`).

Usage: python scripts/extract_gap_statutes.py [--crpc-pdf P] [--ndps-pdf P] [--bnss-pdf P] [--companies-pdf P] [--only crpc,ndps,bnss,companies,schedule,bnss_schedule,part2] [--fetch [--cafile PEM]] [--out DIR] [--schedule-out JSONL]
(The India Code bitstreams of the CrPC and the NDPS Act answered HTTP 504 on 13 Nov 2026, so the pinned copies named above are used.)
(egazette.gov.in sends its certificate without the intermediates; if the download fails verification, pass `--cafile` with the
intermediates named by the certificate's "CA Issuers" URLs, appended to the system bundle. Verification is never switched off.)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

import pymupdf

RAW = Path("data/gaps/raw")
OUT = Path("data/gaps/statutes")
CRPC_URL = "https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf"
NDPS_URL = "https://dor.gov.in/files/acts_files/NDPS_1985.pdf"
CRPC_SECTIONS = ["41", "41A", "50", "57", "167", "436", "436A", "437", "438", "439"]
NDPS_SECTIONS = ["19", "24", "27A", "31A", "36A", "37"]  # named for the flags; the extraction takes every section (NDPS_ALL)
NDPS_ALL = None  # `wanted=None`: every section of the Act, so that s.20, 21, 22, 29 ... (the penal sections the brief cites) are in the store
_PENAL = re.compile(r"shall be (punishable|punished)\b")
BNSS_URL = "https://egazette.gov.in/WriteReadData/2023/250884.pdf"
BNSS_SHA256 = "5e60e2afe30d0fe7eca4f8126301146b76c86a444e690581f81eb564843517fe"
BNSS_SECTIONS = ["58"]
COMPANIES_URL = "https://tdb.gov.in/sites/default/files/2024-05/companiesact2013.pdf"
COMPANIES_SHA256 = "325a7d09574541cd2cd48f558c42d8a8f9109830a271007c46196caa6675a832"
COMPANIES_SECTIONS = ["212"]
CRPC_SHA256 = "8ddde136bbdd3501b70d2e64607c96a762580784012d8decbeac7da7edd7c1e1"
NDPS_SHA256 = "8cd8e71f5e1bd5a5d98a414d553c76838ae8bf9b493097981220305ef70deac2"
# The India Code bitstreams of the same Acts answered HTTP 504 (and the handle pages timed out) on 13 Nov 2026:
# https://www.indiacode.nic.in/bitstream/123456789/13624/1/the_code_of_criminal_procedure%2c_1973.pdf,
# https://indiacode.nic.in/bitstream/123456789/15381/1/ccp1973.pdf and https://www.indiacode.nic.in/bitstream/123456789/1791/5/a1985-61.pdf.
CRPC_SOURCE_NOTE = (
    "India Code consolidated text of the CrPC 1973 (Legislative Department file A1974-02, PDF of 24 Feb 2020) as hosted on the "
    "Government of India S3WaaS CDN; the indiacode.nic.in bitstreams answered HTTP 504 on 2026-11-13"
)
SCHEDULE_OUT = Path("configs/first_schedule_crpc_ipc.jsonl")
BNSS_SCHEDULE_OUT = Path("configs/first_schedule_bnss_bns.jsonl")
BNS_SPOT_CHECK = ["103", "115", "117", "118", "303", "309", "318", "351", "352", "85", "74"]
SPOT_CHECK = ["302", "323", "324", "332", "341", "143", "353", "354", "376", "379", "406", "420", "498A", "506"]

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


def split_sections(lines: list[Line], wanted: list[str] | None) -> dict[str, str]:
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
        if wanted is not None and num not in wanted:
            continue
        end = starts[n + 1][1] if n + 1 < len(starts) else len(lines)
        body = [lines[i]]
        for ln in lines[i + 1 : end]:
            if _STOP.match(ln.text):
                break
            body.append(ln)
        out[num] = join_lines(body)
    return out


# ---------------------------------------------------------------- Gazette of India layout (BNSS)

GAZ_BODY_SIZE = 9.5  # body text is 10 pt; margin notes, running heads and footnotes are 8 pt
GAZ_MARGIN_X = (110.0, 450.0)  # margin notes sit left of x = 110 on odd pages and right of x = 450 on even pages; body text lies between
_GAZ_START = re.compile(r"^\s*(\d{1,3}[A-Z]{0,2})\.\s+\S")


def gazette_sections(path: Path, wanted: list[str]) -> dict[str, tuple[str, str]]:
    """{section: (heading, body)} for the wanted sections of an Act printed in the Gazette of India.

    A section starts at a body line "<num>. ..." that has a margin note level with it (within 4 pt): the margin note is the heading (left
    margin on odd pages, right margin on even pages). The
    arrangement of sections at the front has no margin notes, and a body line inside a section that happens to start with a number is not
    level with a note, so neither opens a section. Numbers must increase through the Act. A section ends where the next one starts or at
    a CHAPTER line; lines are joined as in `join_lines`.
    """
    doc = pymupdf.open(path)
    body: list[Line] = []
    notes: list[Line] = []
    for pno in range(len(doc)):
        for block in doc[pno].get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                spans = ln["spans"]
                text = "".join(s["text"] for s in spans).replace("\u00a0", " ")
                if not text.strip():
                    continue
                x, y, size = ln["bbox"][0], ln["bbox"][1], next(s["size"] for s in spans if s["text"].strip())
                if y < 60 or y > 790:  # running head, rule lines and page foot
                    continue
                in_margin = x < GAZ_MARGIN_X[0] or x >= GAZ_MARGIN_X[1]
                if size > GAZ_BODY_SIZE and not in_margin:
                    body.append(Line(pno, x, y, size, text))
                elif size <= GAZ_BODY_SIZE and in_margin:
                    notes.append(Line(pno, x, y, size, text))
    body.sort(key=lambda ln: (ln.page, ln.y, ln.x))
    notes.sort(key=lambda ln: (ln.page, ln.y, ln.x))
    starts: list[tuple[str, int]] = []
    last = (0, "")
    for i, ln in enumerate(body):
        m = _GAZ_START.match(ln.text)
        if not m or not any(n.page == ln.page and abs(n.y - ln.y) <= 4 for n in notes):
            continue
        k = _key(m.group(1))
        if k > last and k[0] - last[0] <= 4:
            starts.append((m.group(1), i))
            last = k
    out: dict[str, tuple[str, str]] = {}
    for n, (num, i) in enumerate(starts):
        if num not in wanted:
            continue
        end = starts[n + 1][1] if n + 1 < len(starts) else len(body)
        lines = [body[i]]
        for ln in body[i + 1 : end]:
            if _STOP.match(ln.text):
                break
            lines.append(ln)
        first = body[i]
        nxt = body[starts[n + 1][1]] if n + 1 < len(starts) else None
        head = [
            nt.text.strip() for nt in notes
            if (nt.page, nt.y) >= (first.page, first.y - 4) and (nxt is None or (nt.page, nt.y) < (nxt.page, nxt.y - 4))
        ]
        heading = re.sub(r"\s+", " ", " ".join(head)).strip().rstrip(".")
        out[num] = (heading, join_lines(lines))
    return out


def build_gazette_rows(code: str, pdf: Path, url: str, wanted: list[str], today: str) -> tuple[list[dict], list[str]]:
    """StatuteRow dicts in the store's BNSS form ("<heading>\\n\\n<num>. <heading>.—<body>"); returns (rows, missing sections)."""
    found = gazette_sections(pdf, wanted)
    rows, missing = [], []
    for s in wanted:
        if s not in found:
            missing.append(s)
            continue
        heading, body = found[s]
        rest = re.sub(rf"^\s*{re.escape(s)}\.\s*", "", body)
        rows.append(dict(code=code, section=s, text=f"{heading}\n\n{s}. {heading}.—{rest}", source_url=url, retrieved=today))
    return rows, missing


def sha256_of(path: Path) -> str:
    """Hex SHA-256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_pinned(url: str, dest: Path, sha256: str, cafile: Path | None = None) -> Path:
    """Download `url` to `dest` (verified TLS; `cafile` adds intermediates) unless present, and refuse a file whose SHA-256 is not `sha256`."""
    if not dest.exists():
        import ssl

        dest.parent.mkdir(parents=True, exist_ok=True)
        ctx = ssl.create_default_context(cafile=str(cafile) if cafile else None)
        with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=300, context=ctx) as r:  # noqa: S310 (fixed official URL)
            data = r.read()
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(dest)
    got = sha256_of(dest)
    if got != sha256:
        raise ValueError(f"{dest}: SHA-256 {got} is not the pinned {sha256}; delete it and fetch again, or check the source")
    return dest


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
ROW_GAP = 12  # lines inside a cell are about 10.4 pt apart; a new sub-row of the same section starts 13 pt or more below
_COLNUM = re.compile(r"[1-6]")


_FUSED = re.compile(r"^\[?(\d{1,3}[A-Z]{0,2})(?:\([a-z]\))?\s+([A-Z].*)$")
_SEC_ROW = re.compile(r"(\d{1,3}[A-Z]{0,2})((?:\(\w{1,4}\))*)")  # "302", "498A", "318(4)", "248(a)"
# Left edges of columns 2 to 6 of the BNSS First Schedule in the Gazette (section 58, offence 94, punishment 193, cognizable 286-298,
# bailable 370-385, court 453-454).
BNSS_COL_EDGES = (90, 185, 280, 365, 445)
_FLAG_START = re.compile(r"\s*\[?\s*(Ditto|Cognizable|Non-|Bailable|According)")
_PART2 = re.compile(r"II\.\W*CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS")


def _col(x: float, bounds: list[float]) -> int:
    """Column index 0 to 5 of a left x position."""
    return sum(x >= b for b in bounds)


def _columns(xs: list[float], texts: list[str] | None = None) -> list[int]:
    """Columns of the line starts of one page. The punishment column (3) starts at x 231 on some pages and at about 258 on the others
    (where its cells are often centred, so lines start anywhere from 258 to 285): the edge is 229 when at least three lines of the
    page start within 229 to 233, else 250. The offence column (2) ends before either edge. The bailable column (5) starts between
    420 and 461: its edge is just left of the leftmost "Bailable" / "Non-bailable" / "Ditto" / "According" line between 410 and 470
    (428 when there is none), so a word such as "if" continuing a "Cognizable if ..." cell stays in column 4."""
    edge = 229 if sum(229 <= x <= 233 for x in xs) >= 3 else 250
    bounds = list(COL_EDGES)
    bounds[1] = edge
    starts = [x for x, t in zip(xs, texts or [], strict=False) if 410 <= x <= 470 and re.match(r"\s*\[?\s*(Bailable|Non-\s*bailable|Ditto|According)", t)]
    if starts:
        bounds[3] = min(starts) - 2
    return [_col(x, bounds) for x in xs]


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
    if c.startswith("ditto"):
        return prev, "ditto"
    if "accordingas" in c or "accordingto" in c or re.search(r"\b(if|unless|except|when)\b", cell.lower()):
        return None, "cond"  # "According as the offence abetted is ...", "Cognizable if information ... is given by the person aggrieved"
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


def _cell_text(parts: list[tuple[int, float, float, str]]) -> str:
    """Text of one cell from its (page, y, x, text) pieces: pieces within 3 pt of height form one visual line, read left to right
    (justified lines come out of the PDF as several pieces, and a numeral can sit a point higher than the words around it)."""
    lines: list[list[tuple[int, float, float, str]]] = []
    for part in sorted(parts):
        if lines and lines[-1][0][0] == part[0] and part[1] - lines[-1][0][1] <= 3:
            lines[-1].append(part)
        else:
            lines.append([part])
    return " ".join(t for ln in lines for *_, t in sorted(ln, key=lambda q: q[2]))


def parse_first_schedule(path: Path) -> tuple[list[dict], list[str]]:
    """Parse Part I (IPC) of the CrPC First Schedule into per-section rows {section, bailable, cognisable, subrows}.

    Returns (rows, notes): notes list sections whose flags are conditional ('According as ...'), mixed across sub-rows, or unparsed.
    """
    first, last = schedule_pages(path)
    doc = pymupdf.open(path)
    items: list[tuple[int, float, int, float, str]] = []  # (page, y, column, x, text) of the table text
    part2_y = next(
        (ln["bbox"][1] for block in doc[last].get_text("dict")["blocks"] for ln in block.get("lines", [])
         if _PART2.search("".join(s["text"] for s in ln["spans"]))),
        None,
    )  # fmt: skip
    first_row_y = next(
        (ln["bbox"][1] for block in doc[first].get_text("dict")["blocks"] for ln in block.get("lines", [])
         if ln["bbox"][0] < COL_EDGES[0] and _SEC.fullmatch("".join(s["text"] for s in ln["spans"]).strip())),
        10**6,
    )  # fmt: skip
    for p in range(first, last + 1):
        page_items: list = []
        for block in doc[p].get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                raw = "".join(s["text"] for s in ln["spans"] if s["size"] > 6).strip()  # square brackets kept: they mark amended entries
                text = raw.replace("[", "").replace("]", "").strip()
                size = next((sp["size"] for sp in ln["spans"] if sp["size"] > 6), 0)
                if not text or ln["bbox"][1] > 740 or ln["bbox"][1] < 70 or not 6.8 <= size <= 9.2:
                    continue
                if re.match(r"CHAPTER\b", text) or (p == first and text in _HEADER_WORDS and ln["bbox"][1] < first_row_y):
                    continue  # the column headings stand only above the first row of the first page ("Punishment" can also open a cell)
                x, y = ln["bbox"][0], ln["bbox"][1]
                if p == last and part2_y is not None and y >= part2_y - 2:
                    continue  # Part II (offences against other laws) starts lower on the last page
                fused = _FUSED.match(text) if x < COL_EDGES[0] else None
                if fused:  # "501(a) Printing or engraving matter knowing": one PDF line holding the section number and the offence
                    page_items.append((p, y, x, fused.group(1)))
                    page_items.append((p, y, float(COL_EDGES[0] + 10), fused.group(2) + ("]" if "]" in raw else "")))
                    continue
                page_items.append((p, y, x, raw if raw.replace("[", "").replace("]", "").strip() else text))
        by_y: dict[int, int] = {}
        for _, y, _x, t in page_items:
            if _COLNUM.fullmatch(t):
                by_y[round(y / 4)] = by_y.get(round(y / 4), 0) + 1
        header = {k for k, v in by_y.items() if v >= 3}  # the "1 2 3 4 5 6" line of column numbers
        page_items = [it for it in page_items if not (_COLNUM.fullmatch(it[3]) and round(it[1] / 4) in header)]
        cols = _columns([it[2] for it in page_items], [it[3] for it in page_items])
        tri_left = min((x for (_pp, _y, x, t), c in zip(page_items, cols, strict=True) if c == 5 and t.lstrip("[ ")[:1].isupper()), default=0)
        for i, (_pp, _y, x, t) in enumerate(page_items):  # a word of column 5 justified past its edge ("According as" with "as" at 492)
            if cols[i] == 5 and x < tri_left - 2 and t[:1].islower():
                cols[i] = 4
        page_items = [(pp, y, c, x, t) for (pp, y, x, t), c in zip(page_items, cols, strict=True)]
        foot = [y for _, y, c, _x, t in page_items if y > 400 and c == 0 and re.match(r"\d{1,2}\.\s", t)]
        cut = min(foot) - 1 if foot else 10**6  # amendment footnotes at the foot of the page
        items.extend(it for it in page_items if it[1] < cut)
    return _schedule_sections(_table_rows(items))


def _table_rows(items: list[tuple[int, float, int, float, str]]) -> list[dict]:
    """Cut the (page, y, column, x, text) pieces of a schedule table into rows of six cells (plus `closes`, see below)."""
    items = sorted(items)
    # row starts: a section number; or an offence (column 2) line on a new page, or more than ROW_GAP pt below the previous offence
    # line, or (sub-rows printed closer together) level with the first line of a cell in column 4 or 5 ("Ditto", "Cognizable", ...)
    starts: list[tuple[int, float]] = []
    prev: tuple[int, float, str] | None = None
    for p, y, col, _x, t in items:
        if col == 0 and _SEC.fullmatch(re.sub(r"[\s\[\]]+", "", t)):  # a section number always opens a row
            starts.append((p, y))
            prev = (p, y, "")
        elif col == 1:
            if prev is None or prev[0] != p or y - prev[1] > ROW_GAP:
                starts.append((p, y))
            prev = (p, y, t)
        elif col in (3, 4) and _FLAG_START.match(t):  # the first line of a flag cell opens a sub-row even when its offence cell is blank
            starts.append((p, y))
    starts = _merge_starts(starts)
    rows: list[dict] = []
    for n, (p, y) in enumerate(starts):
        nxt = starts[n + 1] if n + 1 < len(starts) else (10**6, 0)
        cells = {c: [] for c in range(6)}
        for ip, iy, ic, ix, it in items:
            if (ip, iy) >= (p, y - 6) and (ip, iy) < (nxt[0], nxt[1] - 6):
                cells[ic].append((ip, iy, ix, it))
        row: dict = {c: _cell_text(v) for c, v in cells.items()}
        row["closes"] = any("]" in t for t in row.values())  # the row ends an entry inserted or substituted by an amending Act
        rows.append({k: (v.replace("[", "").replace("]", "") if isinstance(v, str) else v) for k, v in row.items()})
    return rows


def bnss_schedule_pages(path: Path) -> tuple[int, int]:
    """Page range (0-based) of Part I of the BNSS First Schedule (offences under the BNS) in the Gazette of India text."""
    doc = pymupdf.open(path)
    first = last = None
    for p in range(len(doc)):
        t = doc[p].get_text()
        if first is None and re.search(r"I\.\W*OFFENCES UNDER THE BHARATIYA NYAYA SANHITA", t):
            first = p
        if first is not None and _PART2.search(t):
            last = p
            break
    if first is None or last is None:
        raise ValueError("BNSS First Schedule Part I not found")
    return first, last


def parse_bnss_schedule(path: Path) -> tuple[list[dict], list[str]]:
    """Parse Part I (offences under the BNS) of the BNSS 2023 First Schedule from the Gazette of India PDF, like `parse_first_schedule`.

    The Gazette sets the table in fixed columns (`BNSS_COL_EDGES`) but often prints neighbouring cells as one PDF line ("Imprisonment
    for 7 years According as offence"), so the table is read span by span. An entry numbered "318(4)" or "248(a)" becomes a sub-row of
    section 318 or 248 with `subsection` "(4)" or "(a)": the statute store keys BNS rows by the bare section number.
    """
    first, last = bnss_schedule_pages(path)
    doc = pymupdf.open(path)
    lines_of = {p: [ln for block in doc[p].get_text("dict")["blocks"] for ln in block.get("lines", [])] for p in (first, last)}
    part2_y = next((ln["bbox"][1] for ln in lines_of[last] if _PART2.search("".join(s["text"] for s in ln["spans"]))), None)
    first_row_y = next(
        (ln["bbox"][1] for ln in lines_of[first]
         if ln["bbox"][0] < BNSS_COL_EDGES[0] and re.match(r"\d{1,3}", "".join(s["text"] for s in ln["spans"]).strip())),
        10**6,
    )  # fmt: skip
    items: list[tuple[int, float, int, float, str]] = []
    for p in range(first, last + 1):
        page_items: list[tuple[int, float, float, str]] = []
        lines: dict[tuple[int, int], list[tuple[float, float, str]]] = {}
        for x0, y0, x1, _y1, word, bno, lno, _wno in doc[p].get_text("words"):
            lines.setdefault((bno, lno), []).append((x0, y0, word, x1))
        for words in lines.values():  # words, not spans: one span can hold the ends of two cells ("assembly Imprisonment for 2 years,")
            words.sort()
            y = min(w[1] for w in words)
            if y < 70 or y > 790 or (p == first and y < first_row_y - 4) or (p == last and part2_y is not None and y >= part2_y - 4):
                continue
            if words[0][2] == "CHAPTER":
                continue
            groups: dict[int, list] = {}
            col, prev_x1 = -1, -100.0
            for w in words:  # a long "Cognizable if ..." cell runs past the bailable edge: a lower-case word under 4.5 pt after it stays in it
                c = _col(w[0], list(BNSS_COL_EDGES))
                col = col if (col == 3 and c == 4 and w[2][:1].islower() and w[0] - prev_x1 < 4.5) else c
                groups.setdefault(col, []).append(w)
                prev_x1 = w[3]
            for ws in groups.values():
                page_items.append((p, y, ws[0][0], " ".join(w[2] for w in ws)))
        by_y: dict[int, int] = {}
        for _, y, _x, t in page_items:
            if _COLNUM.fullmatch(t):
                by_y[round(y / 4)] = by_y.get(round(y / 4), 0) + 1
        header = {k for k, v in by_y.items() if v >= 3}  # the "1 2 3 4 5 6" line of column numbers
        items.extend(
            (pp, y, _col(x, list(BNSS_COL_EDGES)), x, t) for pp, y, x, t in page_items if not (_COLNUM.fullmatch(t) and round(y / 4) in header)
        )
    return _schedule_sections(_table_rows(items))


def _merge_starts(starts: list[tuple[int, float]]) -> list[tuple[int, float]]:
    """Sort the row starts and keep the first of any that lie within 5 pt of each other ("Ditto" cells sit 3 pt above the line)."""
    out: list[tuple[int, float]] = []
    for p, y in sorted(set(starts)):
        if out and out[-1][0] == p and y - out[-1][1] <= 5:
            continue
        out.append((p, y))
    return out


def _clean_cell(text: str) -> str:
    """Collapse the spaces of a table cell (the PDF pads justified lines) and join words hyphenated across lines ("non- bailable")."""
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(\w)- (?=[a-z])", r"\1-", text)


def _is_ditto(cell: str) -> bool:
    return re.fullmatch(r"ditto\.?", cell.strip().lower()) is not None


def _schedule_sections(rows: list[dict[int, str]]) -> tuple[list[dict], list[str]]:
    """Group the table rows (cells 0 to 5) into sections; resolve "Ditto" in columns 3 to 6 to the resolved cell above.

    Each section row: {section, offence, punishment, max_punishment, cognisable, bailable, triable_by, subrows: [...]}. With one sub-row
    the section fields are that sub-row's; with several, `offence` / `punishment` / `triable_by` are the sub-rows' cells joined with
    " | " (in table order), `max_punishment` is the heaviest sub-row maximum (None if any sub-row's maximum is unknown), and a flag is
    set only when every sub-row has the same known value.
    """
    sections: dict[str, dict] = {}
    notes: list[str] = []
    cur: str | None = None
    cur_sub = ""
    prev_cog: bool | None = None
    prev_bail: bool | None = None
    prev_pun = prev_cog_t = prev_bail_t = prev_tri = ""
    # A "Ditto" is read as the printed table reads: the resolved cell above. When the cell above belongs to an entry an amending Act
    # inserted or substituted (its row closes a "[...]"), the Ditto was printed against the entry that stood there before, so the
    # sub-row lists that column in `ditto_from_amended_entry`. If that amended section's own sub-rows also differ in the column (s.355
    # below the 2013 entries for ss.354A to 354D: bailable for a first conviction, non-bailable after), the Ditto is left unresolved
    # (`ditto_ambiguous`, value None), and so is every Ditto that repeats it.
    amended = dict.fromkeys(("punishment", "cognisable", "bailable", "triable_by"), False)
    # (section, its sub-rows differ in this column, last explicit cell) of the cell a Ditto would repeat
    source: dict[str, tuple[str | None, bool, str]] = dict.fromkeys(("punishment", "cognisable", "bailable", "triable_by"), (None, False, ""))
    for r in rows:
        sec = re.sub(r"\s+", "", r[0])
        m = _SEC_ROW.fullmatch(sec)
        if m:
            cur, cur_sub = m.group(1), m.group(2)
        has_cells = any(r[c].strip() for c in (2, 3, 4, 5))
        if cur is None or re.fullmatch(r"\d", r[1].strip()) or not (r[1].strip() or has_cells):
            continue  # nothing yet, a repeated column-number line, or an empty band
        if not has_cells:  # "Omission to apprehend ... provided for:–" above sub-rows (a) and (b)
            sections.setdefault(cur, {"sub": [], "head": []})["head"].append(_clean_cell(r[1]))
            continue
        pun, cog_t, bail_t, tri = (_clean_cell(r[c]) for c in (2, 3, 4, 5))
        flagged, ambiguous = [], []
        for name, cell in (("punishment", pun), ("cognisable", cog_t), ("bailable", bail_t), ("triable_by", tri)):
            if _is_ditto(cell):
                if amended[name]:
                    flagged.append(name)
                if amended[name] and source[name][0] != cur and source[name][1]:
                    ambiguous.append(name)
            else:
                amended[name] = bool(r.get("closes"))
                same = source[name][0] == cur
                source[name] = (cur, same and (source[name][1] or source[name][2] != cell), cell)
        if ambiguous:  # Ditto under an amended section whose sub-rows differ in that column: no reading of it is safe
            prev_cog, prev_bail = (None if "cognisable" in ambiguous else prev_cog), (None if "bailable" in ambiguous else prev_bail)
            prev_pun, prev_cog_t, prev_bail_t, prev_tri = (
                "" if n in ambiguous else v
                for n, v in (("punishment", prev_pun), ("cognisable", prev_cog_t), ("bailable", prev_bail_t), ("triable_by", prev_tri))
            )
        cog, cs = _cell_flag(cog_t, "cog", prev_cog)
        bail, bs = _cell_flag(bail_t, "bail", prev_bail)
        prev_cog = None if cs == "cond" else (cog if cs in ("ok", "ditto") else prev_cog)
        prev_bail = None if bs == "cond" else (bail if bs in ("ok", "ditto") else prev_bail)
        pun = prev_pun if _is_ditto(pun) else pun
        cog_t = prev_cog_t if _is_ditto(cog_t) else cog_t
        bail_t = prev_bail_t if _is_ditto(bail_t) else bail_t
        tri = prev_tri if _is_ditto(tri) else tri
        prev_pun, prev_cog_t, prev_bail_t, prev_tri = pun, cog_t, bail_t, tri
        d = sections.setdefault(cur, {"sub": [], "head": []})
        sub = {
            "offence": _clean_cell(r[1]) or None, "punishment": pun or None, "max_punishment": schedule_max_punishment(pun),
            "cognisable": cog, "bailable": bail, "triable_by": tri.rstrip(".") or None,
            "cognisable_text": cog_t.rstrip(".") or None, "bailable_text": bail_t.rstrip(".") or None,
        }  # fmt: skip
        if cur_sub:
            sub = {"subsection": cur_sub, **sub}
        if flagged:
            sub["ditto_from_amended_entry"] = flagged
        if ambiguous:
            sub["ditto_ambiguous"] = ambiguous
        d["sub"].append(sub)
    out: list[dict] = []
    for s, d in sections.items():
        sub = d["sub"]
        if not sub:
            notes.append(f"s.{s}: offence text without any other cell, skipped")
            continue
        row: dict = {"section": s}
        for field in ("offence", "punishment", "triable_by"):
            vals = [x[field] for x in sub]
            row[field] = None if all(v is None for v in vals) else " | ".join(v or "" for v in vals)
        if d["head"]:
            row["offence"] = " ".join(d["head"]) + " " + (row["offence"] or "")
        maxima = [x["max_punishment"] for x in sub]
        row["max_punishment"] = None if None in maxima else max(maxima, key=punishment_rank)
        if row["max_punishment"] is None:
            notes.append(f"s.{s} max_punishment: not parsed from {[x['punishment'] for x in sub]}")
        for field in ("cognisable", "bailable"):
            vals = {x[field] for x in sub}
            if len(vals) == 1 and None not in vals:
                row[field] = vals.pop()
            else:
                row[field] = None
                notes.append(f"s.{s} {field}: {'mixed' if len(vals - {None}) > 1 else 'conditional or unparsed'} across {len(sub)} sub-rows")
        flagged = sorted({f for x in sub for f in x.get("ditto_from_amended_entry", [])})
        if flagged:
            row["ditto_from_amended_entry"] = flagged
            notes.append(f"s.{s} {', '.join(flagged)}: 'Ditto' below an amended entry, read as printed")
        row["subrows"] = sub
        out.append(row)
    return out, notes


_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
              "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20}  # fmt: skip
_TERM_RE = re.compile(r"\b(\d{1,2}|" + "|".join(_NUM_WORDS) + r")\s+(years?|months?|weeks?|days?|hours?)\b", re.I)
_UNIT_DAYS = {"year": 365.0, "month": 30.0, "week": 7.0, "day": 1.0, "hour": 1 / 24}
# "Same as for offence abetted", "a quarter part of the longest term", "the punishment provided for the offence": no own maximum.
_RELATIVE_RE = re.compile(r"same as|longest term|provided for (the|that) offence|for the offence|according as", re.I)


def schedule_max_punishment(cell: str | None) -> str | None:
    """Normalise a First Schedule punishment cell to its heaviest punishment: "death", "life imprisonment", "N years" / "N months" /
    "N days" / "N hours", or "fine" when the cell names only a fine. None when the cell is empty or relative ("Same as for offence abetted",
    "a quarter part of the longest term provided for the offence"), so the reader never takes a guess for a fact.
    """
    if not cell:
        return None
    low = cell.lower()
    if re.search(r"\bdeath\b", low):
        return "death"
    if re.search(r"imprisonment\s+for\s+life|life\s+imprisonment|remainder of (that|his|the) person'?s? natural life", low):
        return "life imprisonment"
    if _RELATIVE_RE.search(low):
        return None
    best: tuple[float, str] | None = None
    for m in _TERM_RE.finditer(cell):
        raw, unit = m.group(1).lower(), m.group(2).lower().rstrip("s")
        n = int(raw) if raw.isdigit() else _NUM_WORDS[raw]
        days = n * _UNIT_DAYS[unit]
        label = f"{n} {unit}{'s' if n != 1 else ''}"
        if best is None or days > best[0]:
            best = (days, label)
    if best:
        return best[1]
    if re.fullmatch(r"(simple\s+)?fine(\s+of\s+[\w ,]+rupees)?\.?", low.strip()) or re.match(r"^fine\b", low.strip()):
        return "fine"
    return None


def punishment_rank(label: str) -> float:
    """Order normalised maxima: fine < hours < days < months < years < life imprisonment < death."""
    if label == "death":
        return 1e9
    if label == "life imprisonment":
        return 1e8
    if label == "fine":
        return 0.0
    n, unit = label.split()
    return int(n) * _UNIT_DAYS[unit.rstrip("s")]


# ---------------------------------------------------------------- First Schedule, Part II (offences against other laws)

PART2_OUT = Path("configs/first_schedule_part2.jsonl")
PART2_SCHEDULES = {  # --only key of the PDF -> (schedule name, url, pinned sha256, page-range function of Part I)
    "schedule": ("CrPC 1973", CRPC_URL, CRPC_SHA256, schedule_pages),
    "bnss_schedule": ("BNSS 2023", BNSS_URL, BNSS_SHA256, bnss_schedule_pages),
}
_PART2_ANCHORS = (r"Offence\b", r"Cognizable\b", r"Bailable\b", r"By what court\b")  # the four column headings, in order
_PART2_STOP = re.compile(r"^\s*(STATE AMENDMENTS?|THE\s+(SECOND|THIRD)\s+SCHEDULE|CHAPTER\b)", re.I)
PART2_TABLE_SIZE = 8.5  # the table is set in 8 pt; the first larger line below it (a footnote in 9 pt, a page number, a heading) ends it


def _part2_lines(doc, page: int) -> list[tuple[int, float, float, float, str]]:
    """(page, y, x0, x1, text) of the lines below the Part II heading on `page` and of the pages after it, up to the end of the table:
    a "STATE AMENDMENTS", "THE SECOND SCHEDULE" or "CHAPTER" line, or the first line set larger than the table (a footnote such as
    "1. Subs. by Act 13 of 2013 ...", a page number, a heading). Running heads (above y 70) of a following page are skipped."""
    out: list[tuple[int, float, float, float, str]] = []
    heading_y = None
    for p in range(page, len(doc)):
        lines = []
        for block in doc[p].get_text("dict")["blocks"]:
            for ln in block.get("lines", []):
                spans = [s for s in ln["spans"] if s["size"] > 6]  # footnote reference numerals are 5 pt
                text = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
                if text and not re.fullmatch(r"_+", text):
                    lines.append((ln["bbox"][1], ln["bbox"][0], ln["bbox"][2], max(s["size"] for s in spans), text))
        for y, x0, x1, size, text in sorted(lines):
            if heading_y is None:
                if p == page and _PART2.search(text):
                    heading_y = y
                continue
            if p > page and y < 70:
                continue
            if _PART2_STOP.match(text) or size > PART2_TABLE_SIZE:
                return out
            out.append((p, y, x0, x1, text))
    if heading_y is None:
        raise ValueError(f"Part II heading not found on PDF page {page + 1}")
    return out


def part2_band(text: str) -> dict:
    """The punishment band of a printed Part II offence cell, by rule: `death` / `life` (named in the cell), `fine_only` ("with fine
    only"), a lower bound in years ("more than N years": exclusive; "N years and upwards": inclusive) and an upper bound ("not more than
    N years": inclusive; "less than N years": exclusive), and a `band` id built from them ("death_life_or_more_than_7", "3_to_7",
    "less_than_3_or_fine"; None when the bounds do not fit one of these shapes)."""
    low = re.sub(r"\s+", " ", text.lower())
    lower = upper = None
    if m := re.search(r"(\d+) years? and upwards", low):
        lower = (int(m.group(1)), True)
    elif m := re.search(r"(?<!not )more than (\d+) years?", low):
        lower = (int(m.group(1)), False)
    if m := re.search(r"not more than (\d+) years?", low):
        upper = (int(m.group(1)), True)
    elif m := re.search(r"less than (\d+) years?", low):
        upper = (int(m.group(1)), False)
    death = re.search(r"\bdeath\b", low) is not None
    life = re.search(r"imprisonment for life|life imprisonment", low) is not None
    fine_only = re.search(r"fine only", low) is not None
    band = None
    if lower and upper and lower[1] and upper[1]:
        band = f"{lower[0]}_to_{upper[0]}"
    elif lower and not lower[1] and upper is None and (death or life):
        band = f"{'death_' if death else ''}{'life_' if life else ''}or_more_than_{lower[0]}"
    elif upper and not upper[1] and lower is None:
        band = f"less_than_{upper[0]}{'_or_fine' if fine_only else ''}"
    return {
        "band": band,
        "death": death,
        "life": life,
        "fine_only": fine_only,
        "min_years": lower[0] if lower else None,
        "min_inclusive": lower[1] if lower else None,
        "max_years": upper[0] if upper else None,
        "max_inclusive": upper[1] if upper else None,
    }


def parse_part2(path: Path, page: int | None = None) -> tuple[list[dict], list[str]]:
    """Parse Part II ("II.-CLASSIFICATION OF OFFENCES AGAINST OTHER LAWS") of a First Schedule into its rows.

    `page` (0-based) holds the heading; by default the last page of Part I (`schedule_pages` / `bnss_schedule_pages` stop there), else the
    first page that prints it. The four column headings (Offence; Cognizable or non-cognizable; Bailable or non-bailable; By what court
    triable) fix the columns: a line belongs to the column whose heading centre is nearest its own centre (the cells are separate PDF
    lines in both pinned PDFs). A row starts at an offence line more than ROW_GAP pt below the previous one or level with the first line
    of a flag cell; the lines above the first row (the headings, the "1 2 3 4" column numbers) are dropped. "Ditto" repeats the resolved
    cell above. Returns (rows, notes): each row {row, offence, cognisable_text, bailable_text, triable_by_text, cognisable, bailable,
    triable_by, **part2_band(offence)}.
    """
    doc = pymupdf.open(path)
    if page is None:
        page = next((p for p in range(len(doc)) if _PART2.search(doc[p].get_text())), None)
        if page is None:
            raise ValueError("Part II heading not found")
    lines = _part2_lines(doc, page)
    anchors: list[tuple[float, float]] = []  # (y, centre x) of the four column headings
    for pat in _PART2_ANCHORS:
        hit = next(((y, (x0 + x1) / 2) for _p, y, x0, x1, t in lines if re.match(pat, t, re.I)), None)
        if hit is None:
            raise ValueError(f"Part II column heading {pat!r} not found")
        anchors.append(hit)
    centres = [c for _y, c in anchors]
    if centres != sorted(centres):
        raise ValueError(f"Part II column headings out of order: {centres}")
    head_y = max(y for y, _c in anchors)
    edges = [(a + b) / 2 for a, b in zip(centres, centres[1:], strict=False)]
    body = [(p, y, _col((x0 + x1) / 2, edges), t) for p, y, x0, x1, t in lines if (p, y) > (page, head_y)]
    starts: list[tuple[int, float]] = []
    prev: tuple[int, float] | None = None
    for p, y, col, t in body:
        if col == 0 and not re.fullmatch(r"\d", t):  # the "1" of the column numbers stands in the offence column
            if prev is None or prev[0] != p or y - prev[1] > ROW_GAP:
                starts.append((p, y))
            prev = (p, y)
        elif col == 1 and _FLAG_START.match(t) and starts:
            starts.append((p, y))
    starts = _merge_starts(starts)
    if not starts:
        raise ValueError("Part II has no rows")
    first = starts[0]
    cells: list[dict[int, list[str]]] = [{c: [] for c in range(4)} for _ in starts]
    for p, y, col, t in body:
        if (p, y) < (first[0], first[1] - 5):
            continue  # headings and column numbers
        i = max(k for k, s in enumerate(starts) if (s[0], s[1] - 5) <= (p, y))  # a "Ditto" sits up to 3 pt above its row's first line
        cells[i][col].append(t)
    rows: list[dict] = []
    notes: list[str] = []
    above: dict[int, str | None] = {1: None, 2: None, 3: None}
    for n, c in enumerate(cells, 1):
        text = {k: _clean_cell(" ".join(v)) for k, v in c.items()}
        resolved: dict[int, str | None] = {}
        for k in (1, 2, 3):
            if _is_ditto(text[k]):
                resolved[k] = above[k]
                if above[k] is None:
                    notes.append(f"row {n}: 'Ditto' in column {k + 1} with no cell above")
            else:
                resolved[k] = text[k] or None
            above[k] = resolved[k]
        cog, _ = _cell_flag(resolved[1] or "", "cog", None)
        bail, _ = _cell_flag(resolved[2] or "", "bail", None)
        band = part2_band(text[0])
        for name, val in (("offence", text[0]), ("cognisable", cog), ("bailable", bail), ("band", band["band"])):
            if val in (None, ""):
                notes.append(f"row {n}: {name} not read from {text}")
        rows.append({
            "row": n,
            "offence": text[0],
            **band,
            "cognisable_text": text[1] or None,
            "bailable_text": text[2] or None,
            "triable_by_text": text[3] or None,
            "cognisable": cog,
            "bailable": bail,
            "triable_by": (resolved[3] or "").rstrip(".") or None,
        })  # fmt: skip
    return rows, notes


def part2_table(parsed: dict[str, tuple[list[dict], list[str], Path, int]], today: str) -> tuple[list[dict], dict]:
    """Rows of `configs/first_schedule_part2.jsonl` and its sidecar from {--only key: (rows, notes, pdf, heading page)}."""
    table: list[dict] = []
    sources: dict[str, dict] = {}
    notes: list[str] = []
    for key, (rows, row_notes, pdf, page) in parsed.items():
        name, url, _pin, _pages = PART2_SCHEDULES[key]
        source = {"url": url, "sha256": sha256_of(pdf)}
        sources[name] = {**source, "pdf_page": page + 1}
        table.extend({"schedule": name, "part": "II", **r, "source": source} for r in rows)
        notes.extend(f"{name} {x}" for x in row_notes)
    meta = {
        "title": "First Schedule, Part II (classification of offences against other laws) of the Code of Criminal Procedure, 1973 and "
        "the Bharatiya Nagarik Suraksha Sanhita, 2023",
        "sources": sources,
        "generated": today,
        "script": "scripts/extract_gap_statutes.py --only part2",
        "fields": {
            "offence": "the printed offence cell (whitespace collapsed)",
            "band": "id of the punishment band, built by rule from the printed offence cell (part2_band)",
            "death / life / fine_only": "whether the offence cell names death, imprisonment for life, or 'fine only'",
            "min_years / min_inclusive": "lower bound in years: 'more than N years' (exclusive) or 'N years and upwards' (inclusive)",
            "max_years / max_inclusive": "upper bound in years: 'not more than N years' (inclusive) or 'less than N years' (exclusive)",
            "cognisable_text / bailable_text / triable_by_text": "the cells as printed ('Ditto' kept)",
            "cognisable / bailable / triable_by": "the cells with 'Ditto' replaced by the cell above, read as flags",
        },
        "coverage": {"rows": len(table), "per_schedule": {PART2_SCHEDULES[k][0]: len(v[0]) for k, v in parsed.items()}},
        "notes": notes,
    }
    return table, meta


# ---------------------------------------------------------------- main


SCHEDULE_SOURCES = {  # code -> (url, title, source note, page-range function, --only key)
    "IPC": (
        CRPC_URL,
        "The Code of Criminal Procedure, 1973, First Schedule, Part I: classification of offences under the Indian Penal Code",
        CRPC_SOURCE_NOTE,
        schedule_pages,
        "schedule",
    ),
    "BNS": (
        BNSS_URL,
        "The Bharatiya Nagarik Suraksha Sanhita, 2023 (46 of 2023), First Schedule, Part I: classification of offences under the "
        "Bharatiya Nyaya Sanhita",
        "Gazette of India, Extraordinary, Part II Section 1, 25 December 2023 (Legislative Department), as enacted; egazette.gov.in sends "
        "its certificate without the Let's Encrypt YR1 intermediate (http://yr1.i.lencr.org/), so --cafile is needed with --fetch",
        bnss_schedule_pages,
        "bnss_schedule",
    ),
}


def build_rows(code: str, pdf: Path, url: str, wanted: list[str] | None, today: str, ocr: bool = False) -> tuple[list[dict], list[str]]:
    """Extract the wanted sections (None: every section) of one Act into StatuteRow dicts; returns (rows, missing sections).

    NDPS rows: the cognisable / bailable flags of `ndps_flags` go to the sections it names and to every section whose text says "shall
    be punishable with" (s.37(1)(a) makes every offence under the Act cognizable; definitions and procedure get no flag), and each row
    carries `max_punishment` read from its own text by `oil_ingest.max_punishment` (the store's IPC/BNS rule).
    """
    lines = pdf_lines(pdf)
    found = split_sections(lines, wanted)
    if wanted is None:
        wanted = list(found)
    flags: dict[str, dict[str, bool]] = {}
    if code == "NDPS":
        flags = ndps_flags({s: t for s, t in found.items() if s in NDPS_SECTIONS or s == "37" or _PENAL.search(t)})
        from vakeel_sahayak.pipelines.oil_ingest import max_punishment
    rows, missing = [], []
    for s in wanted:
        if s not in found:
            missing.append(s)
            continue
        text = apply_ocr_fixes(found[s]) if ocr else found[s]
        row = dict(code=code, section=s, text=text, source_url=url, retrieved=today, **flags.get(s, {}))
        if code == "NDPS" and _PENAL.search(text):
            row["max_punishment"] = max_punishment(text)
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
    ap.add_argument("--bnss-pdf", type=Path, default=RAW / "bnss_gazette.pdf")
    ap.add_argument("--companies-pdf", type=Path, default=RAW / "companies_act_2013.pdf")
    ap.add_argument(
        "--only", default="crpc,ndps,bnss,companies",
        help="comma list of crpc, ndps, bnss, companies, schedule, bnss_schedule, part2 (crpc includes the CrPC First Schedule, bnss the "
        "BNSS one; crpc and bnss together, or schedule and bnss_schedule together, also run part2, which reads both PDFs)",
    )  # fmt: skip
    ap.add_argument("--fetch", action="store_true", help="download the PDFs that are missing (verified TLS, checked against the pinned SHA-256)")
    ap.add_argument("--schedule-out", type=Path, default=SCHEDULE_OUT, help="the committed First Schedule table (a .meta.json sidecar is written next to it)")
    ap.add_argument("--bnss-schedule-out", type=Path, default=BNSS_SCHEDULE_OUT, help="the committed BNSS First Schedule table (BNS offences)")
    ap.add_argument("--part2-out", type=Path, default=PART2_OUT, help="the committed First Schedule Part II table (CrPC and BNSS rows)")
    ap.add_argument("--cafile",type=Path, default=None, help="CA bundle with the intermediates egazette.gov.in leaves out (with --fetch)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    today = date.today().isoformat()
    ocr = args.ndps_pdf.name == "ndps_candidate.pdf"
    failures = 0
    if "crpc" in only:
        only.add("schedule")
    if "bnss" in only:
        only.add("bnss_schedule")
    if {"schedule", "bnss_schedule"} <= only:
        only.add("part2")
    for key, pdf, url, pin in (
        ("bnss_schedule", args.bnss_pdf, BNSS_URL, BNSS_SHA256),
        ("companies", args.companies_pdf, COMPANIES_URL, COMPANIES_SHA256),
        ("schedule", args.crpc_pdf, CRPC_URL, CRPC_SHA256),
        ("ndps", args.ndps_pdf, NDPS_URL, NDPS_SHA256),
    ):
        if (key not in only and not (key in PART2_SCHEDULES and "part2" in only)) or (key == "ndps" and ocr):
            continue
        if args.fetch:
            fetch_pinned(url, pdf, pin, args.cafile)
        elif sha256_of(pdf) != pin:
            print(f"WARNING {pdf} is not the pinned PDF (SHA-256 differs)", file=sys.stderr)
    if "bnss" in only:
        rows, missing = build_gazette_rows("BNSS", args.bnss_pdf, BNSS_URL, BNSS_SECTIONS, today)
        write_jsonl(args.out / "bnss.jsonl", rows)
        print("BNSS", [(r["section"], len(r["text"])) for r in rows])
        for s in missing:
            print(f"MISSING BNSS s.{s}", file=sys.stderr)
            failures += 1
    for key, code, pdf, url, wanted, name, is_ocr in (
        ("crpc", "CrPC", args.crpc_pdf, CRPC_URL, CRPC_SECTIONS, "crpc.jsonl", False),
        ("ndps", "NDPS", args.ndps_pdf, NDPS_URL, NDPS_ALL, "ndps.jsonl", ocr),
        ("companies", "Companies Act", args.companies_pdf, COMPANIES_URL, COMPANIES_SECTIONS, "companies_act.jsonl", False),
    ):
        if key not in only:
            continue
        rows, missing = build_rows(code, pdf, url, wanted, today, is_ocr)
        write_jsonl(args.out / name, rows)
        print(code, [(r["section"], len(r["text"])) for r in rows])
        for s in missing:
            print(f"MISSING {code} s.{s}", file=sys.stderr)
            failures += 1
    for key, code, parse, pdf, out, spot in (
        ("schedule", "IPC", parse_first_schedule, args.crpc_pdf, args.schedule_out, SPOT_CHECK),
        ("bnss_schedule", "BNS", parse_bnss_schedule, args.bnss_pdf, args.bnss_schedule_out, BNS_SPOT_CHECK),
    ):
        if key not in only:
            continue
        sched, notes = parse(pdf)
        flag_rows = [
            dict(code=code, section=r["section"], text="", bailable=r["bailable"], cognisable=r["cognisable"], source_url=SCHEDULE_SOURCES[code][0], retrieved=today)
            for r in sched
            if r["bailable"] is not None or r["cognisable"] is not None
        ]
        write_jsonl(args.out / f"first_schedule_{code.lower()}.jsonl", flag_rows)
        table, meta = schedule_table(sched, notes, pdf, today, code)
        write_jsonl(out, table)
        out.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"First Schedule Part I ({code}): {len(sched)} sections parsed, {len(flag_rows)} rows with at least one flag")
        print(f"wrote {out} ({len(table)} rows) and its .meta.json")
        for k, v in meta["coverage"].items():
            print(f"  {k}: {v}")
        print("spot check (read from the table, not asserted):")
        by = {r["section"]: r for r in table}
        for sec in spot:
            r = by.get(sec)
            if r is None:
                print(f"  s.{sec}: not in the table")
                continue
            texts = " / ".join(x["bailable_text"] or "-" for x in r["subrows"])
            print(f"  {code} {sec}: cognisable={r['cognisable']} bailable={r['bailable']} max={r['max_punishment']!r} [{texts}]")
        for n in notes:
            print("NOTE", n)
    if "part2" in only:
        parsed = {}
        for key, pdf in (("schedule", args.crpc_pdf), ("bnss_schedule", args.bnss_pdf)):
            page = PART2_SCHEDULES[key][3](pdf)[1]  # Part I ends on the page that prints the Part II heading
            rows, notes = parse_part2(pdf, page)
            parsed[key] = (rows, notes, pdf, page)
        table, meta = part2_table(parsed, today)
        write_jsonl(args.part2_out, table)
        args.part2_out.with_suffix(".meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"First Schedule Part II: wrote {args.part2_out} ({len(table)} rows) and its .meta.json")
        for r in table:
            print(f"  {r['schedule']} row {r['row']} [{r['band']}]: cognisable={r['cognisable']} bailable={r['bailable']} "
                  f"triable_by={r['triable_by']!r} | {r['offence']}")  # fmt: skip
        for n in meta["notes"]:
            print("NOTE Part II", n, file=sys.stderr)
            failures += 1
    return 1 if failures else 0


def schedule_table(sched: list[dict], notes: list[str], pdf: Path, today: str, code: str = "IPC") -> tuple[list[dict], dict]:
    """Rows of `configs/first_schedule_crpc_ipc.jsonl` (code IPC) or `configs/first_schedule_bnss_bns.jsonl` (code BNS) and the sidecar
    metadata (source, date, script, coverage, notes)."""
    url, title, note, pages, only = SCHEDULE_SOURCES[code]
    digest = sha256_of(pdf)
    source = {"url": url, "sha256": digest}
    keys = ("offence", "punishment", "max_punishment", "cognisable", "bailable", "triable_by")
    table = []
    for r in sched:
        row = {"code": code, "section": r["section"], **{k: r[k] for k in keys}}
        if "ditto_from_amended_entry" in r:
            row["ditto_from_amended_entry"] = r["ditto_from_amended_entry"]
        row["subrows"] = r["subrows"]
        row["source"] = source
        table.append(row)
    n = len(table)

    def share(field: str) -> str:
        k = sum(r[field] is not None for r in table)
        return f"{k}/{n} ({k / n:.1%})" if n else "0/0"

    first, last = pages(pdf)
    meta = {
        "title": title,
        "source_url": url,
        "source_sha256": digest,
        "source_note": note,
        "pdf_pages": f"{first + 1}-{last + 1} (1-based PDF page numbers)",
        "generated": today,
        "script": f"scripts/extract_gap_statutes.py --only {only}",
        "fields": {
            "max_punishment": "heaviest punishment named in the punishment cell: 'death', 'life imprisonment', 'N years' / 'N months' / "
            "'N days' / 'N hours', or 'fine'; with several sub-rows the heaviest of them; null when any sub-row's cell is relative "
            "('Same as for offence abetted') or empty",
            "cognisable / bailable": "true/false only when every sub-row reads the same; null when sub-rows differ, a cell is conditional "
            "('According as ...', 'Cognizable if ...') or a 'Ditto' cannot be resolved; the sub-rows keep the printed text",
            "offence / punishment / triable_by": "cell text; several sub-rows joined with ' | ', 'Ditto' replaced by the cell it repeats",
            "ditto_from_amended_entry": "columns where a 'Ditto' repeats a cell of an entry an amending Act inserted or substituted",
            "subsection": "(BNS) the printed entry number after the section, e.g. '(4)' for the entry '318(4)'; the row's section is '318'",
        },
        "coverage": {
            "rows": n,
            "bailable_non_null": share("bailable"),
            "cognisable_non_null": share("cognisable"),
            "max_punishment_non_null": share("max_punishment"),
            "triable_by_non_null": share("triable_by"),
        },
        "notes": notes,
    }
    return table, meta


if __name__ == "__main__":
    raise SystemExit(main())
