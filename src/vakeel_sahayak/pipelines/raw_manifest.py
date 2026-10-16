"""Write `data/raw/MANIFEST.json`: provenance, licence, revision, size, files and SHA-256 of every raw dataset (plan §2).

Entries are rebuilt from what is on disk, so the manifest always matches the files. Datasets that could not be fetched keep their
entry with `status: "blocked"` and the exact step a teammate must take. No secrets are read or stored (no tokens, no cookies).

    python -m vakeel_sahayak.pipelines.raw_manifest [--raw data/raw]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

IPC2BNS_COMMIT = "8d3e77024b3693d21ccae39bffb81641329a4900"

BLOCKED: dict[str, dict[str, Any]] = {
    "hldc": {
        "name": "HLDC, Hindi Legal Documents Corpus (Kapoor et al., Findings of ACL 2022)",
        "official_pages": [
            "https://github.com/Exploration-Lab/HLDC",
            "https://aclanthology.org/2022.findings-acl.278/",
            "https://huggingface.co/datasets/Exploration-Lab/IL-TUR",
        ],
        "licence": "HLDC README: CC BY-NC 4.0, research use only. The IL-TUR Hugging Face card (which carries the 176k-document BAIL task from HLDC) states CC BY-NC-SA 4.0.",
        "status": "blocked",
        "reason": "The HLDC README points to the IL-TUR leaderboard Space for the data. The bail task of HLDC ships as the `bail` config of "
        "the Hugging Face dataset Exploration-Lab/IL-TUR (parquet: train/dev/test, _all and _specific), which is gated: the card says to agree to share contact "
        "information, and the Hugging Face API reports gating mode `manual` (approval by the authors).",
        "team_action": "A teammate logs in to Hugging Face, requests access on https://huggingface.co/datasets/Exploration-Lab/IL-TUR, "
        "and after approval runs `huggingface-cli login` (token stays in their own environment) and downloads the `bail` folder into "
        "data/raw/hldc/. Plan §2 fallback if refused: HLDC is only needed for T2 Hindi text; construct it from Open India Law orders "
        "with NLLB-200 translation.",
    },
    "kathbath": {
        "name": "Kathbath (AI4Bharat), Hindi read speech",
        "official_pages": ["https://huggingface.co/datasets/ai4bharat/Kathbath", "https://github.com/AI4Bharat/IndicSUPERB"],
        "licence": "cc-by-4.0 in the Hugging Face metadata; the card also states a CC0 waiver of the packaging (the two are not reconciled on the card)",
        "status": "blocked",
        "reason": "The Hugging Face repo is gated (automatic approval after logging in and accepting the conditions). The repo holds `hindi/train-*` "
        "(32 shards of about 0.47-0.6 GB) and `hindi/valid-*` (2 shards, 0.26 and 0.32 GB) only; the test subset is released by AI4Bharat "
        "separately (IndicSUPERB benchmark tarballs, test-known / test-unknown) and is not in that repo. The smallest usable local set is the "
        "valid split (0.58 GB), which needs a token.",
        "team_action": "A teammate logs in to Hugging Face, accepts the conditions on https://huggingface.co/datasets/ai4bharat/Kathbath, "
        "and downloads `hindi/valid-*.parquet` into data/raw/kathbath/ (token stays in their own environment). For the official test "
        "subset, fetch the Hindi test tarball from the IndicSUPERB page linked above.",
    },
    "escr_hindi": {
        "name": "Official Hindi translations of SC judgments (e-SCR, SUVAS)",
        "official_pages": ["https://digiscr.sci.gov.in/", "https://suvas.sci.gov.in/"],
        "licence": "Government of India publication; terms not checked (optional dataset, plan §2 source 4)",
        "status": "not_attempted",
        "reason": "Optional source with no bulk download; PDFs are fetched per judgment from the e-SCR portal.",
        "team_action": "None for now. If T2 needs it, list Hindi e-SCR PDFs of bail judgments and pair them with their English originals "
        "in Open India Law by case title and date.",
    },
    "forms": {
        "name": "Public form layouts: FIR (IIF-1), remand order, custody certificate",
        "official_pages": [
            "https://police.py.gov.in/Police%20manual/Forms%20pdf/FORM%20IF%201.pdf",
        ],
        "licence": "Government forms; not downloaded (templates are redrawn when T2 companion documents are constructed)",
        "status": "no_download_needed",
        "reason": "A state police site (Puducherry Police) hosts the Integrated Form IF-1 (FIR) PDF with fields for district, police station, year, FIR number and "
        "date, Acts and Sections, and occurrence details. A web search found no single national official IIF-1 template; the layout is state-adapted. "
        "No official template was found for the remand order or the custody certificate (court-specific layouts).",
        "team_action": "Use the Puducherry IF-1 PDF as one reference layout for the FIR and redraw per-court remand-order and custody-certificate layouts "
        "when building T2 (plan §15.2); state which state's layout each constructed document follows.",
    },
}


def sha256_of(path: Path) -> str:
    """SHA-256 of a file in 1 MiB blocks."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _files(root: Path, pattern: str = "*", with_sha: bool = True) -> list[dict[str, Any]]:
    return [
        {"path": str(p.relative_to(root)), "bytes": p.stat().st_size, **({"sha256": sha256_of(p)} if with_sha else {})}
        for p in sorted(root.rglob(pattern))
        if p.is_file()
    ]


def kathbath_entry(raw: Path) -> dict[str, Any]:
    """Manifest entry for the Kathbath Hindi test_known subset fetched by `kathbath_fetch` (the gated Hugging Face route stays documented as blocked)."""
    root = raw / "kathbath" / "hindi" / "test_known"
    blocked = BLOCKED["kathbath"]
    if not (root / "manifest.jsonl").is_file():
        return blocked
    rows = [json.loads(line) for line in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    transcript = root / "transcription_n2w.txt"
    total_utterances = sum(1 for line in transcript.read_text(encoding="utf-8").splitlines() if line.strip())
    return {
        "name": blocked["name"],
        "source_url": "https://objectstore.e2enetworks.net/indic-superb/kathbath/clean/testkn_audio.tar and .../clean/transcripts_n2w.tar (official AI4Bharat object store, linked from https://github.com/AI4Bharat/IndicSUPERB; no login)",
        "revision": "testkn_audio.tar ETag ae6de144c95b7a0b1f2fe26eaf4293fa-214, last modified 2025-04-09 (3,587,717,120 bytes, all 12 languages)",
        "licence": "CC0 for the packaging (IndicSUPERB page; the raw text comes from IndicCorp, which AI4Bharat does not own); Hugging Face metadata says cc-by-4.0",
        "retrieved": str(date.today()),
        "status": "partial",
        "what_was_taken": f"Hindi test_known: the first {len(rows)} of {total_utterances} utterances (m4a, {sum(r['bytes'] for r in rows)} bytes) and the Hindi transcript file, "
        "by range reads (the 3.6 GB tar was not downloaded). Per-file SHA-256 are in hindi/test_known/manifest.jsonl. The Hugging Face repo ai4bharat/Kathbath "
        "is gated and has no test split; see `blocked_route`.",
        "blocked_route": {k: blocked[k] for k in ("reason", "team_action")},
        "files": [
            {"path": str(p.relative_to(raw / "kathbath")), "bytes": p.stat().st_size, "sha256": sha256_of(p)}
            for p in (root / "manifest.jsonl", transcript)
        ],
    }


def open_india_law_entry(raw: Path) -> dict[str, Any]:
    """Manifest entry for the Open India Law subset written by `oil_fetch`."""
    root = raw / "open_india_law"
    if not root.is_dir():
        return {"status": "missing"}
    state_files = sorted((root / "state").glob("*.json"))
    per_file = {}
    for sf in state_files:
        st = json.loads(sf.read_text())
        groups = st["groups"].values()
        per_file[sf.stem] = {
            "row_groups_done": len(st["groups"]),
            "row_groups_total": st["num_row_groups"],
            "chunk_rows_total": st["num_rows"],
            "cases_in_window": sum(g.get("cases_in_window", 0) for g in groups),
            "candidate_cases_kept": sum(g.get("cases_kept", 0) for g in groups),
        }
    shards = list((root / "judgments").glob("*/rg-*.parquet"))
    sums = json.loads((root / "SHA256SUMS.json").read_text()) if (root / "SHA256SUMS.json").is_file() else {}
    leg = _files(root / "legislation") if (root / "legislation").is_dir() else []
    for entry in leg:
        entry["published_sha256"] = sums.get("files", {}).get(Path(entry["path"]).name, {}).get("sha256")
        entry["verified"] = entry["published_sha256"] == entry["sha256"]
    from vakeel_sahayak.pipelines.oil_fetch import HC_FILES, SC_FILE

    expected = {*HC_FILES, SC_FILE}
    complete = expected <= set(per_file) and all(v["row_groups_done"] == v["row_groups_total"] for v in per_file.values())
    return {
        "name": "Open India Law (Vaquill AI)",
        "source_url": "https://oss-data-in.vaquill.ai/v2026.08.1/ (mirror named in the dataset README; same release as https://huggingface.co/datasets/vaquill/open-india-law, which is gated)",
        "revision": "v2026.08.1 (supersedes v2026.08; Hugging Face repo sha 58ea6d8b6859f8039ee68dff5af636f787b02463 at 2026-08-26)",
        "licence": "CC BY 4.0 for the compilation; underlying judgments and statutes are Government works (Copyright Act 1957 s.17(d), s.52(1)(q)). Attribution: 'Structured Indian primary-law data from the Open India Law corpus by Vaquill AI (https://github.com/Vaquill-AI/open-india-law), used under CC BY 4.0.'",
        "retrieved": str(date.today()),
        "status": "complete" if complete else "partial",
        "what_was_taken": "Streamed (HTTP range, row group by row group) from the 26 judgment files (53.6 GB, 32.6M chunks): only chunks of bail-candidate cases "
        "(High Courts: decisions 2019-01-01..2025-12-31 with a bail case type or a bail word plus a CrPC/BNSS reference in the opening text; "
        "Supreme Court: any year, at least 4 mentions of bail and a CrPC/BNSS reference). The legislation file in_central_legislation.parquet was "
        "downloaded whole and checked against SHA256SUMS.json. Judgment files have no per-file SHA-256 in the release (only multipart ETags), so "
        "they are not checksummed; the shards are derived data.",
        "per_judgment_file": per_file,
        "shard_files": len(shards),
        "shard_bytes": sum(p.stat().st_size for p in shards),
        "legislation": leg,
        "note_gating": "The Hugging Face repo requires login and accepting terms; the mirror needs neither. No token is used or stored.",
    }


def ipc2bns_entry(raw: Path) -> dict[str, Any]:
    """Manifest entry for the IPC2BNS-Verify files fetched by `scripts/download_datasets.sh`."""
    root = raw / "ipc2bns_verify"
    if not root.is_dir():
        return {"status": "missing"}
    return {
        "name": "IPC2BNS-Verify",
        "source_url": "https://github.com/MS-406/IPC2BNS-Verify",
        "revision": f"commit {IPC2BNS_COMMIT} (main, 2026-10-09)",
        "licence": "MIT per the repository README badge; the repository has no LICENSE file at that commit (the badge links to a missing file). Ask the authors for the file before redistributing.",
        "retrieved": str(date.today()),
        "status": "complete",
        "what_was_taken": "Concordance (data/eval_ground_truth/concordance_v1.csv, 563 IPC rows with full text and BNS target), the authors' IPC and BNS section labels "
        "(data/phase2_cleaned), the 1,140-query benchmark (phase7/benchmark/master_benchmark.jsonl/.csv) and the CrPC->BNSS questions. Not taken: notebooks, results, "
        "figures, code, embeddings.",
        "files": _files(root),
    }


def build_manifest(raw_dir: str) -> dict[str, Any]:
    """Assemble the manifest from the files under `raw_dir` and write `MANIFEST.json` there."""
    raw = Path(raw_dir)
    manifest: dict[str, Any] = {
        "generated": str(date.today()),
        "note": "Public data only. Raw client files never enter data/raw. No tokens or credentials are stored here.",
        "datasets": {
            "open_india_law": open_india_law_entry(raw),
            "ipc2bns_verify": ipc2bns_entry(raw),
            "kathbath": kathbath_entry(raw),
            **{k: v for k, v in BLOCKED.items() if k != "kathbath"},
        },
    }
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Write data/raw/MANIFEST.json")
    parser.add_argument("--raw", default="data/raw")
    args = parser.parse_args(argv)
    build_manifest(args.raw)
    print(f"wrote {Path(args.raw) / 'MANIFEST.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
