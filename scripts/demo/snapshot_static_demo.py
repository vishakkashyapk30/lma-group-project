"""Snapshot the six recorded evaluator-demo cases into the frontend, for the static (no-backend) demo build.

The recorded cases under demo/cases/ are normally served by the FastAPI backend (routers/demo.py). A demo build of the frontend
(NEXT_PUBLIC_API_MODE=demo, e.g. on Vercel) has no backend, so this script asks a running backend for every response the
workspace reads, and writes:

  frontend/lib/mock/recorded/index.json            tours and case summaries (small; bundled into the app)
  frontend/public/demo-cases/<case_id>.json        everything the workspace reads for one case (fetched on demand)
  frontend/public/demo-cases/<case_id>/pages/<doc>-<page>.png   the page images the PDF viewer shows
  frontend/public/api/cases/<case_id>/export/files/<name>       the real exported files, at the URL the client already uses

To capture the exported files it approves Gate 2 and exports on the backend it talks to, so point it at a throwaway data directory:

  VS_DATA_DIR=$(mktemp -d) VS_MODELS=offline VS_DEMO_CASES=on .venv/bin/python -m uvicorn vakeel_sahayak.api.asgi:app --port 8765
  .venv/bin/python scripts/demo/snapshot_static_demo.py --api http://localhost:8765

The browser keeps Gate 2 open until the evaluator approves it, exactly as on the live server.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
GETS = ("ingestion", "dossier", "dates", "rights", "brief", "spar", "prep", "budget", "chat")


def get(api: str, path: str) -> bytes:
    with urllib.request.urlopen(api + path, timeout=120) as r:
        return r.read()


def get_json(api: str, path: str):
    return json.loads(get(api, path))


def post_json(api: str, path: str, body: dict):
    req = urllib.request.Request(api + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def events_of(slug: str) -> list[dict]:
    lines = (ROOT / "demo" / "cases" / slug / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--api", default="http://localhost:8765")
    args = ap.parse_args()
    api = args.api.rstrip("/")

    public = FRONTEND / "public" / "demo-cases"
    files_root = FRONTEND / "public" / "api" / "cases"
    for d in (public, files_root):
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)

    index: dict[str, list] = {"tours": [], "cases": []}
    for summary in get_json(api, "/api/demo/tours"):
        slug, case_id = summary["slug"], summary["case_id"]
        tour = get_json(api, f"/api/demo/tours/{slug}")
        c = f"/api/cases/{case_id}"
        snap: dict = {"summary": get_json(api, c)}
        for ep in GETS:
            snap[ep] = get_json(api, f"{c}/{ep}")
        gate1 = get_json(api, f"{c}/gates/GATE_1_DOSSIER")
        gate2 = get_json(api, f"{c}/gates/GATE_2_EXPORT")
        snap["approvals"] = {"gate1": not gate1["open"], "gate2": not gate2["open"]}
        snap["events"] = events_of(slug)

        pages: list[str] = []
        for doc in snap["ingestion"].get("documents", []):
            first, last = doc["pages"]
            for n in range(1, last - first + 2):
                out = public / case_id / "pages" / f"{doc['doc_id']}-{n}.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(get(api, f"{c}/files/{doc['doc_id']}/pages/{n}"))
                pages.append(f"{doc['doc_id']}-{n}")
        snap["pages"] = pages

        # Approve Gate 2 here (the throwaway backend) only to write the real export files; the snapshot keeps Gate 2 open.
        if not gate2["open"]:
            raise SystemExit(f"{case_id}: Gate 2 is already approved on this backend; use a fresh data directory")
        ack = list(gate2["unresolved_unsupported"])
        ack += [f"NEEDS_REVIEW:{x}" for x in gate2["unresolved_needs_review"]]
        ack += [f"UNANSWERED:{x}" for x in gate2["unresolved_unanswered"]]
        post_json(api, f"{c}/gates/GATE_2_EXPORT/approve", {"acknowledged_fields": ack})
        exports: dict[str, list[str]] = {}
        for fmt in ("DOCX", "PDF"):
            names = []
            for p in post_json(api, f"{c}/export", {"format": fmt}):
                name = Path(p).name
                dest = files_root / case_id / "export" / "files" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(get(api, f"{c}/export/files/{name}"))
                names.append(name)
            # One zip per format, so the export button downloads a single file (several at once trigger a browser prompt).
            ext = "." + fmt.lower()
            zip_name = f"{case_id}-papers-{fmt.lower()}.zip"
            with zipfile.ZipFile(files_root / case_id / "export" / "files" / zip_name, "w", zipfile.ZIP_DEFLATED) as z:
                for name in names:
                    if name.endswith(ext):
                        z.write(files_root / case_id / "export" / "files" / name, name)
            exports[fmt] = [zip_name, *names]
        snap["exports"] = exports

        (public / f"{case_id}.json").write_text(json.dumps(snap, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        index["tours"].append(tour)
        index["cases"].append({**snap["summary"], "approvals": snap["approvals"]})
        print(f"{case_id}: {len(snap['events'])} events, {len(pages)} pages, exports {exports}")

    out = FRONTEND / "lib" / "mock" / "recorded" / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} and {public.relative_to(ROOT)}")
    # The demo shows the FIR filled from each case's own FIR page (the recorded extraction failed its schema check).
    import fill_demo_fir

    fill_demo_fir.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
