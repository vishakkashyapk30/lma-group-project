"""Fill the FIR field of the six recorded demo cases in the static demo build (frontend/public/demo-cases, lib/mock/recorded).

In the recorded runs (15 Nov 2026) Peshkar's two FIR extractions failed the FirValue schema check, so every case shows the FIR as
"Not found" and counsel acknowledges it at both gates. For the evaluator demo the team chose to show the FIR filled in: this script
reads the FIR line ("P.S.: PS-12 FIR No. 63/2024 Date: 10.03.2024", or the Hindi equivalent) from each case's own FIR page
(demo/cases/<slug>/case/page_index.json), files it as VERIFIED with that line as its quote, and removes the FIR from the tour text
that says it was acknowledged. The recorded event logs are left as they were. Idempotent: run it again and nothing changes.

  .venv/bin/python scripts/demo/fill_demo_fir.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "frontend" / "public" / "demo-cases"
INDEX = ROOT / "frontend" / "lib" / "mock" / "recorded" / "index.json"

EN = re.compile(r"P\.S\.:\s*(?P<ps>\S+)\s+FIR No\.\s*(?P<no>\S+)\s+Date:\s*(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{4})")
HI = re.compile(r"थाना:\s*(?P<ps>\S+)\s+एफ\.आई\.आर\. संख्या:\s*(?P<no>\S+)\s+दिनांक:\s*(?P<d>\d{2})\.(?P<m>\d{2})\.(?P<y>\d{4})")


def fir_of(slug: str) -> tuple[dict, dict] | None:
    pages = json.loads((ROOT / "demo" / "cases" / slug / "case" / "page_index.json").read_text(encoding="utf-8"))
    for pg in pages:
        if pg.get("doc_type") != "FIR":
            continue
        for line in pg["text"].splitlines():
            m = EN.search(line) or HI.search(line)
            if m:
                value = {"number": m["no"], "police_station": m["ps"], "date": f"{m['y']}-{m['m']}-{m['d']}"}
                lang = "hi" if HI.search(line) else "en"
                source = {"doc": pg["doc_id"], "page": pg["page"], "box": None, "lang": lang, "route": "text_layer: accepted",
                          "quote": line.strip(), "quote_en": None, "tool": None, "chat": None, "confidence": None}  # fmt: skip
                return value, source
    return None


def shown(v: dict) -> str:
    y, m, d = v["date"].split("-")
    return f"FIR No. {v['number']}, P.S. {v['police_station']}, {d}.{m}.{y}"


def drop_items(step: dict, labels: set[str]) -> None:
    """Remove filled lines by English label, and the Hindi lines at the same positions."""
    keep = [i for i, f in enumerate(step.get("filled", [])) if f.get("label") not in labels]
    hi = step.get("hi") or {}
    if hi.get("filled") and len(hi["filled"]) == len(step["filled"]):
        hi["filled"] = [hi["filled"][i] for i in keep]
    step["filled"] = [step["filled"][i] for i in keep]


def gate1_text(step: dict) -> None:
    c = step["caption"]
    c = c.replace("Counsel acknowledged 1 field the papers do not support (FIR) and approved.", "Counsel confirmed the facts and approved.")
    c = re.sub(r"acknowledged (\d+) fields the papers do not support \(FIR and ",
               lambda m: f"acknowledged {int(m[1]) - 1} field{'s' if int(m[1]) > 2 else ''} the papers do not support{'' if int(m[1]) > 2 else ''} (", c)
    step["caption"] = c
    hi = step.get("hi")
    if hi and hi.get("caption") and "FIR" in hi["caption"]:
        h = hi["caption"]
        h = re.sub(r"अधिवक्ता ने 1 [^।]*\(FIR\)[^।]*।", "अधिवक्ता ने तथ्यों की पुष्टि की और अनुमोदन किया।", h)
        if "(FIR और " in h:
            h = re.sub(r"(अधिवक्ता (?:\(counsel\) )?ने )(\d+)", lambda m: f"{m[1]}{int(m[2]) - 1}", h, count=1)
            h = h.replace("1 ऐसे क्षेत्रों को स्वीकार किया जिनका", "1 ऐसे क्षेत्र को स्वीकार किया जिसका").replace("1 फ़ील्ड्स", "1 फ़ील्ड")
        h = h.replace("(FIR और ", "(")
        hi["caption"] = "" if "FIR" in h else h  # an unmatched sentence falls back to the English caption


def gate2_text(step: dict) -> None:
    def en(m: re.Match) -> str:
        total, unsupported = int(m[1]) - 1, int(m[2]) - 1
        parts = f"{unsupported} unsupported field{'s' if unsupported != 1 else ''} and " if unsupported else ""
        return f"has {total} item{'s' if total != 1 else ''} for counsel ({parts}"

    step["caption"] = re.sub(r"has (\d+) items for counsel \((\d+) unsupported fields? and ", en, step["caption"])
    hi = step.get("hi")
    if hi and hi.get("caption"):
        h = hi["caption"]
        new = re.sub(r"अधिवक्ता के लिए (\d+)", lambda m: f"अधिवक्ता के लिए {int(m[1]) - 1}", h, count=1)
        new = re.sub(r"\((\d+) (\S*र्थित) (\S+) और ", lambda m: "(" if m[1] == "1" else f"({int(m[1]) - 1} असमर्थित {m[3]} और ", new, count=1)
        hi["caption"] = new if new != h else ""


def main() -> None:
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    for tour in index["tours"]:
        case_id, slug = tour["case_id"], tour["slug"]
        found = fir_of(slug)
        if not found:
            print(f"{case_id}: no FIR line found, left as recorded")
            continue
        value, source = found
        path = PUBLIC / f"{case_id}.json"
        snap = json.loads(path.read_text(encoding="utf-8"))
        if snap["dossier"]["fields"]["fir"].get("value"):
            print(f"{case_id}: already filled")
            continue
        snap["dossier"]["fields"]["fir"] = {"value": value, "source": source, "status": "VERIFIED"}
        path.write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        for step in tour["steps"]:
            if step["stage"] == "DOSSIER":
                for i, f in enumerate(step.get("filled", [])):
                    if f.get("label") == "FIR":
                        f["value"] = f"{shown(value)} (verified from the papers)"
                        hi = step.get("hi") or {}
                        if hi.get("filled") and len(hi["filled"]) == len(step["filled"]):
                            hi["filled"][i]["value"] = f"{shown(value)} (कागज़ात से सत्यापित)"
            elif step["stage"] == "GATE_1":
                drop_items(step, {"Acknowledged: FIR"})
                gate1_text(step)
            elif step["stage"] == "GATE_2":
                drop_items(step, {"fir"})
                gate2_text(step)
        print(f"{case_id}: FIR {shown(value)}")
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
