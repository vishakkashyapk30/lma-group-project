"""Implementation of scripts/download_models.sh (kept as a script so `python -I` can run it from the repo root)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _fail(msg: str) -> "None":
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("tier", nargs="?", default=os.environ.get("VS_MODELS", "T1"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip", action="append", default=[], help="skip repos whose id contains this text (repeatable)")
    ap.add_argument("--yes", action="store_true", help="do not ask before downloading more than 5 GB")
    ap.add_argument("--min-free-gb", type=float, default=5.0)
    a = ap.parse_args()
    tiers = yaml.safe_load((ROOT / "configs/models.yaml").read_text(encoding="utf-8")).get("weights", {})
    tier = {"OFFLINE": "T0", "REAL": "T1"}.get(a.tier.upper(), a.tier.upper())  # VS_MODELS also holds offline|real elsewhere
    if tier not in tiers:
        _fail(f"unknown tier {a.tier!r}; choose from {', '.join(tiers)} (table: configs/models.yaml, key weights)")
    models = [m for m in tiers[tier].get("models", []) if not any(x in m["id"] for x in a.skip)]
    if not models:
        print(f"{tier}: nothing to download ({tiers[tier].get('note', 'no models')})")
        return 0
    try:
        from huggingface_hub import HfApi, snapshot_download
    except ImportError:
        _fail("huggingface_hub is not installed: .venv/bin/pip install huggingface_hub")
    from fnmatch import fnmatch

    out_dir = Path(os.environ.get("VS_MODELS_DIR", ROOT / "models/hf"))
    out_dir.mkdir(parents=True, exist_ok=True)
    api = HfApi(token=os.environ.get("HF_TOKEN") or None)
    plan = []
    for m in models:
        try:
            info = api.model_info(m["id"], files_metadata=True)
        except Exception as e:  # noqa: BLE001
            _fail(f"cannot read {m['id']} on Hugging Face ({type(e).__name__}); check the network, the repo name and, for gated repos, that HF_TOKEN is set and access was granted")
        files = [s for s in info.siblings if any(fnmatch(s.rfilename, p) for p in m["include"])]
        size = sum(s.size or 0 for s in files)
        plan.append((m, info, files, size))
    total = sum(p[3] for p in plan)
    free = shutil.disk_usage(out_dir).free
    print(f"tier {tier}: {len(plan)} model(s), {total / 1e9:.2f} GB; free disk {free / 1e9:.1f} GB; target {out_dir}")
    for m, info, files, size in plan:
        print(f"  {m['id']}  {size / 1e9:.2f} GB  licence {m.get('license', '?')}  role {m.get('role', '')}  revision {info.sha[:10]}")
    if a.dry_run:
        print("dry run: nothing downloaded")
        return 0
    if free - total < a.min_free_gb * 1e9:
        _fail(f"not enough disk: need {total / 1e9:.2f} GB plus a {a.min_free_gb} GB margin, have {free / 1e9:.1f} GB free")
    if total > 5e9 and not a.yes:
        _fail("this tier is over 5 GB; re-run with --yes to confirm (or use --dry-run first)")
    manifest_path = ROOT / "models/MANIFEST.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    for m, info, files, size in plan:
        print(f"licence {m.get('license', '?')} applies to {m['id']} (see its model card)")
        local = snapshot_download(m["id"], revision=info.sha, local_dir=str(out_dir / m["id"].replace("/", "--")), allow_patterns=m["include"], token=os.environ.get("HF_TOKEN") or None)
        bad = []
        for s in files:  # verify LFS files against the SHA-256 the Hub publishes
            want = getattr(getattr(s, "lfs", None), "sha256", None)
            if not want:
                continue
            h = hashlib.sha256()
            with open(Path(local) / s.rfilename, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != want:
                bad.append(s.rfilename)
        if bad:
            _fail(f"checksum mismatch for {m['id']}: {bad}; delete them and re-run")
        manifest[m["id"]] = {"tier": tier, "revision": info.sha, "bytes": size, "licence": m.get("license"), "path": str(Path(local).relative_to(ROOT)) if Path(local).is_relative_to(ROOT) else local, "downloaded": time.strftime("%Y-%m-%d"), "sha256_verified": True}
        manifest_path.parent.mkdir(exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"ok {m['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
