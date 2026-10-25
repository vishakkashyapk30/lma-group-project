"""T9 citation formats: about 500 OIL judgments cited in each format the resolver handles, plus near-miss distractors; about 2,000 strings (plan §15.2).

Input: a metadata JSONL (`doc_id`, `court`, `date`, `title`, and the citations `neutral_citation`, `scc`, `air`, `scc_online`, `cri_lj`; a `citations` list is
read for the neutral citation, so `data/raw/open_india_law/sc_metadata.jsonl` works as it is). From the judgments with a neutral citation and a title the
builder draws 500 (seeded; fewer if the pool is smaller, and the set shrinks in proportion: about four strings per judgment). Per judgment it writes three
true strings in three of the six formats (neutral citation, SCC, AIR, SCC OnLine, Cri LJ, case name; the formats rotate so each appears about 250 times)
and one near-miss distractor.

True strings are rendered from the judgment's own metadata. IMPORTANT, data limit: the Open India Law metadata carries only the neutral citation and the
SCR citation; it has no SCC, AIR, SCC OnLine or Cri LJ reference. For those four formats the builder therefore constructs a reference (seeded; year from the
judgment's date, court code from its court, volume and page drawn at random and unique) and writes the completed record to `metadata_used.jsonl` with the
constructed fields named in `synthetic_fields`; that file is the index the resolver is tested against. The set measures whether the resolver reads and looks
up each format, not whether it knows the real SCC volume of a judgment. The manifest counts real versus constructed references.

A distractor is a string of one of the five citation formats, changed from a real one by a one-character edit of a number (distance 1 to 2), and not equal to any
citation in the whole metadata file, so it must not resolve (`doc_id` None, `near_to` the judgment it imitates).

Outputs in `out_dir`: `strings.jsonl` (string, format, doc_id or None, distractor, near_to), `metadata_used.jsonl`, `manifest.json`.
CLI: `python -m vakeel_sahayak.testsets.t9_citation_formats [--metadata PATH --out DIR]`.
"""

from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any

from vakeel_sahayak.testsets.common import TestSetManifest, rows_from_file, rows_to_file, sha256_file, write_manifest

SEED = 20260427
N_JUDGMENTS = 500
FORMATS = ["neutral", "scc", "air", "scc_online", "cri_lj", "case_name"]
CITE_FORMATS = FORMATS[:5]
KEY = {"neutral": "neutral_citation", "scc": "scc", "air": "air", "scc_online": "scc_online", "cri_lj": "cri_lj"}
INSC = re.compile(r"\b(?:19|20)\d{2}\s+INSC\s+\d{1,5}\b")
COURT_CODE = {"supreme": "SC", "delhi": "Del", "bombay": "Bom", "madras": "Mad", "calcutta": "Cal", "allahabad": "All", "karnataka": "Kar", "kerala": "Ker",
              "gujarat": "Guj", "patna": "Pat", "orissa": "Ori", "punjab": "P&H", "rajasthan": "Raj", "madhya": "MP", "gauhati": "Gau", "jharkhand": "Jhar",
              "chhattisgarh": "Chh", "andhra": "AP", "telangana": "Tel", "himachal": "HP", "uttarakhand": "Utt", "meghalaya": "Megh", "jammu": "J&K"}  # fmt: skip
_SMALL = {"of", "and", "the", "in", "for", "by", "to", "a", "an", "v.", "&"}


def _year(row: dict[str, Any]) -> int:
    return int(str(row.get("date") or "0000")[:4])


def _neutral(row: dict[str, Any]) -> str | None:
    if row.get("neutral_citation"):
        return str(row["neutral_citation"])
    cites = row.get("citations")
    for c in cites if isinstance(cites, list) else [cites or ""]:
        m = INSC.search(str(c))
        if m:
            return m.group(0)
    return None


def _court_code(court: str) -> str:
    low = (court or "").lower()
    return next((code for key, code in COURT_CODE.items() if key in low), "SC")


def _case_name(title: str) -> str:
    """'A versus B' (any case) as 'A v. B' in title case; titles already containing ' v. ' keep their wording."""
    name = title.strip()
    if " v. " not in name:
        name = re.sub(r"\s+(?:versus|vs\.?|v)\s+", " v. ", name, flags=re.I)
    if name.replace(" v. ", " V. ").isupper():
        words = name.title().split()
        words = [w.lower() if w.lower() in _SMALL and i and words[i - 1] != "V." else w for i, w in enumerate(words)]
        name = " ".join(words).replace(" V. ", " v. ")
    return re.sub(r"\s+", " ", name).rstrip(" .")


def _construct(field: str, y: int, code: str, rng: random.Random) -> str:
    """A constructed reference of one format (volume and page drawn at random)."""
    if field == "scc":
        return f"({y}) {rng.randrange(1, 13)} SCC {rng.randrange(1, 1200)}"
    if field == "air":
        return f"AIR {y} {code} {rng.randrange(1, 4000)}"
    if field == "scc_online":
        return f"{y} SCC OnLine {code} {rng.randrange(1, 9000)}"
    return f"{y} Cri LJ {rng.randrange(1, 4500)}"


def _complete(rows: list[dict[str, Any]], rng: random.Random, taken: set[str]) -> list[dict[str, Any]]:
    """The rows with every citation field present; missing ones are constructed and named in `synthetic_fields`."""
    out = []
    for r in rows:
        y = _year(r)
        rec = {"doc_id": r["doc_id"], "court": r.get("court"), "date": r.get("date"), "title": r.get("title"), "neutral_citation": _neutral(r), "synthetic_fields": []}
        code = _court_code(str(r.get("court") or ""))
        for field in ("scc", "air", "scc_online", "cri_lj"):
            if r.get(field):
                rec[field] = str(r[field])
                taken.add(rec[field])
                continue
            for _ in range(200):
                cand = _construct(field, y, code, rng)
                if cand not in taken:
                    break
            taken.add(cand)
            rec[field] = cand
            rec["synthetic_fields"].append(field)
        rec["citations"] = [rec[k] for k in ("neutral_citation", "scc", "air", "scc_online", "cri_lj")]  # the list the resolver's index reads
        out.append(rec)
    return out


def _near_miss(text: str, universe: set[str], rng: random.Random) -> str | None:
    """A one-character edit of a number in `text` that is not in `universe` (None if every try collides).

    A year (four digits starting 19 or 20) only has its last digit replaced, so the result still looks like a citation; other numbers may also gain or
    lose a last digit (staying between 1 and 5 digits).
    """
    cands: list[str] = []
    for m in re.finditer(r"\d+", text):
        a, b = m.span()
        num = m.group(0)
        is_year = len(num) == 4 and num[:2] in ("19", "20")
        for d in "0123456789":
            if d != num[-1]:
                cands.append(text[:a] + num[:-1] + d + text[b:])
            if not is_year and len(num) < 5:
                cands.append(text[:b] + d + text[b:])
        if not is_year and len(num) > 1:
            cands.append(text[: b - 1] + text[b:])
    rng.shuffle(cands)
    return next((c for c in cands if c not in universe and c != text), None)


def build_t9(metadata_path: str, out_dir: str) -> TestSetManifest:
    """Generate citation strings with doc-id truth.

    Args:
        metadata_path: see behaviour
        out_dir: see behaviour

    Returns:
        Manifest.
    """
    rng = random.Random(SEED)
    all_rows = rows_from_file(metadata_path)
    universe: set[str] = set()
    for r in all_rows:
        for k in ("neutral_citation", "scc", "air", "scc_online", "cri_lj"):
            if r.get(k):
                universe.add(str(r[k]))
        cites = r.get("citations")
        universe |= {str(c) for c in cites} if isinstance(cites, list) else set()
        n = _neutral(r)
        if n:
            universe.add(n)
    name_counts = Counter(_case_name(str(r["title"])).lower() for r in all_rows if r.get("title"))
    names_universe = set(name_counts)
    pool = sorted((r for r in all_rows if r.get("doc_id") and r.get("title") and _neutral(r) and r.get("date")), key=lambda r: str(r["doc_id"]))
    chosen = sorted(rng.sample(pool, min(N_JUDGMENTS, len(pool))), key=lambda r: str(r["doc_id"]))
    docs = _complete(chosen, rng, universe)
    by_id = {d["doc_id"]: d for d in docs}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def emit(string: str, fmt: str, doc_id: str | None, distractor: bool, near_to: str | None = None) -> bool:
        if string in seen:
            return False
        seen.add(string)
        rows.append({"string": string, "format": fmt, "doc_id": doc_id, "distractor": distractor, "near_to": near_to})
        return True

    def render(doc: dict[str, Any], fmt: str) -> str:
        return _case_name(str(doc["title"])) if fmt == "case_name" else str(doc[KEY[fmt]])

    for i, doc in enumerate(docs):
        first = i % len(FORMATS)
        for fmt in [FORMATS[(first + k * 2) % len(FORMATS)] for k in range(3)]:  # three of the six, rotating: each format ~ n/2 times
            if fmt == "case_name" and name_counts[render(doc, fmt).lower()] > 1:
                continue  # the same case name belongs to several judgments in the file: no single answer
            emit(render(doc, fmt), fmt, doc["doc_id"], False)
    for i, doc in enumerate(docs):
        for attempt in range(6):
            fmt = CITE_FORMATS[(i + attempt) % len(CITE_FORMATS)]
            miss = _near_miss(render(doc, fmt), universe, rng)
            if miss and emit(miss, fmt, None, True, doc["doc_id"]):
                break
    # case-name near misses replace a share of the citation ones: same first party, another judgment's second party
    for doc in rng.sample(docs, min(len(docs) // 5, len(docs))):
        other = by_id[rng.choice(docs)["doc_id"]]
        left = _case_name(str(doc["title"])).split(" v. ")[0]
        right = _case_name(str(other["title"])).split(" v. ")[-1]
        name = f"{left} v. {right}"
        if left != right and name.lower() not in names_universe and name != render(doc, "case_name"):
            emit(name, "case_name", None, True, doc["doc_id"])
    rows.sort(key=lambda r: (r["distractor"], str(r["near_to"] or r["doc_id"]), r["format"]))
    out = Path(out_dir)
    rows_to_file(out / "strings.jsonl", rows)
    rows_to_file(out / "metadata_used.jsonl", docs)
    true_rows = [r for r in rows if not r["distractor"]]
    synthetic = Counter(f for d in docs for f in d["synthetic_fields"])
    details = {
        "seed": SEED, "judgments": len(docs), "pool_with_neutral_citation_and_title": len(pool), "metadata_rows": len(all_rows),
        "true_strings": len(true_rows), "distractors": len(rows) - len(true_rows),
        "per_format_true": dict(Counter(r["format"] for r in true_rows)), "per_format_distractor": dict(Counter(r["format"] for r in rows if r["distractor"])),
        "per_court": dict(Counter(str(d["court"]) for d in docs)), "per_decade": dict(sorted(Counter(f"{_year(d) // 10 * 10}s" for d in docs).items())),
        "constructed_references": dict(synthetic), "real_references": {"neutral": len(docs), "case_name": len(docs)},
        "note": "SCC, AIR, SCC OnLine and Cri LJ references are constructed when the metadata lacks them (the Open India Law metadata has only the neutral and SCR citations); metadata_used.jsonl is the index to resolve against",
        "source_metadata_sha256": sha256_file(metadata_path), "not_built": [] if len(docs) >= N_JUDGMENTS else [f"only {len(docs)} judgments in the pool (target {N_JUDGMENTS})"],
    }
    manifest = TestSetManifest(set_id="T9", size=len(rows), answers_from="the judgment's document id; strings rendered from its metadata (constructed references where the metadata has none)",
                               used_for=["F7"], path=str(out), details=details)
    write_manifest(manifest, str(out))
    return manifest


def main(argv: list[str] | None = None) -> int:
    """CLI."""
    from vakeel_sahayak.config import load_config

    paths = load_config().paths
    ap = argparse.ArgumentParser(description="Build T9 (citation formats)")
    ap.add_argument("--metadata", default=str(Path(paths.raw_dir) / "open_india_law" / "sc_metadata.jsonl"))
    ap.add_argument("--out", default=str(Path(paths.testsets_dir) / "t9"))
    args = ap.parse_args(argv)
    m = build_t9(args.metadata, args.out)
    print(json.dumps({"size": m.size, **{k: m.details[k] for k in ("judgments", "true_strings", "distractors", "per_format_true", "constructed_references")}}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
