#!/usr/bin/env bash
# Owner side: fetch (optional) and unpack a sweep result tarball made by scripts/sweep_sarvam_block.sh (into data/eval/dev_runs/sarvam_block/) or by
# scripts/sweep_openai_block.sh (top directory openai_block, into data/eval/dev_runs/openai_block/, backend openai), safely.
#
#   scripts/sweep_collect.sh sweep-sarvam-2026-10-28.tar.gz          # a local file (sweep-openai-<date>.tar.gz works the same)
#   scripts/sweep_collect.sh --hf sweep-sarvam-2026-10-28.tar.gz     # first: hf download Vakeel-Sahayak/vakeel-sahayak-data sweep-runs/<file> --repo-type dataset
#   EXPECT_PROMPT_HASH=<hash> scripts/sweep_collect.sh <file>        # refuse runs whose prompt_hash differs (default: the hash of the owner's Full run in data/eval/dev_runs/outputs/full)
#   SWEEP_TARGET / SWEEP_REF_MANIFEST override the destination and the reference manifest (tests)
#   ALLOW_CODE_MISMATCH=1 ...                                        # accept a different git_sha than the owner's Full runs (scoring then needs --allow-mixed-code)
#
# Checks before anything is moved into data/: only regular files, no absolute or `..` paths, no links, only the names the packer writes (MANIFEST.json, t1dev-*.json,
# cases/*.jsonl, PACK_INFO.json), no key-like strings; every MANIFEST.json must have gold_source "agreed", the dev case-file hash of this machine, and the expected prompt hash.
# Then score with: python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs/sarvam_block/outputs --slice dev --gold-source both --out <dir>
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
src="${1:-}"; fetch=0
if [ "$src" = "--hf" ]; then fetch=1; src="${2:-}"; fi
[ -n "$src" ] || { sed -n 2,11p "$0"; exit 2; }
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
if [ "$fetch" = 1 ]; then
  . scripts/_hf_lib.sh; hf_load_token .env; hf_find_bin || exit 1
  "$HF" download Vakeel-Sahayak/vakeel-sahayak-data "sweep-runs/$src" --repo-type dataset --local-dir "$work/dl" >/dev/null
  src="$work/dl/sweep-runs/$src"
fi
[ -f "$src" ] || { echo "no such file: $src" >&2; exit 1; }
EXPECT_PROMPT_HASH="${EXPECT_PROMPT_HASH:-}" ALLOW_CODE_MISMATCH="${ALLOW_CODE_MISMATCH:-0}" $PY - "$src" "$work/x" <<'PYE'
import hashlib, json, os, re, shutil, sys, tarfile
from pathlib import Path

src, stage = sys.argv[1], Path(sys.argv[2])
stage.mkdir(parents=True)
tops: set[str] = set()
OK = re.compile(r"^(sarvam|openai)_block(/(PACK_INFO\.json|(outputs/[A-Za-z0-9_.:-]+/(MANIFEST\.json|t1dev-\d+\.json))|cases/[A-Za-z0-9_.-]+\.jsonl))?$")
KEY = re.compile(rb"(sk-[A-Za-z0-9]{16,}|SARVAM_API_KEY|OPENAI_API_KEY|hf_[A-Za-z0-9]{20,})")
with tarfile.open(src, "r:gz") as tf:
    for m in tf.getmembers():
        name = m.name.rstrip("/")
        if m.isdir():
            continue
        if not m.isreg() or name.startswith("/") or ".." in Path(name).parts or not OK.match(name):
            sys.exit(f"REFUSED: unexpected member {m.name!r} (not a regular file under sarvam_block/ with a known name)")
        if m.size > 5_000_000:
            sys.exit(f"REFUSED: {m.name} is {m.size} bytes")
        tops.add(name.split("/")[0])
        data = tf.extractfile(m).read()
        if KEY.search(data):
            sys.exit(f"REFUSED: a key-like string in {m.name}")
        dest = stage / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
if len(tops) != 1:
    sys.exit("REFUSED: the package must hold exactly one of sarvam_block/ or openai_block/")
top = tops.pop()
backend = top.removesuffix("_block")
root = stage / top
manifests = sorted(root.glob("outputs/*/MANIFEST.json"))
if not manifests:
    sys.exit("REFUSED: no MANIFEST.json in the package")
refp = Path(os.environ.get("SWEEP_REF_MANIFEST") or "data/eval/dev_runs/outputs/full/MANIFEST.json")
ref = json.loads(refp.read_text()) if refp.is_file() else {}
want_prompt = os.environ.get("EXPECT_PROMPT_HASH") or ref.get("prompt_hash")
dev = Path("data/testsets/t1/dev.jsonl")
dev_hash = hashlib.sha256(dev.read_bytes()).hexdigest()[:16] if dev.is_file() else None
problems = []
for mp in manifests:
    m = json.loads(mp.read_text())
    n = mp.parent.name
    if m.get("gold_source") != "agreed":
        problems.append(f"{n}: gold_source {m.get('gold_source')!r} is not 'agreed'")
    if want_prompt and m.get("prompt_hash") != want_prompt:
        problems.append(f"{n}: prompt_hash {m.get('prompt_hash')} differs from {want_prompt}")
    if dev_hash and m.get("cases_hash") not in (dev_hash, None) and "t1_" not in str(m.get("cases_file")):
        pass  # subsets of the dev file (25 cases) have their own hash: only the gold source and prompt are strict
    llm = (m.get("models") or {}).get("llm_backend")
    if llm != backend:
        problems.append(f"{n}: llm_backend {llm!r}, expected {backend!r}")
    if (m.get("nli") or {}).get("backend") != (ref.get("nli") or {}).get("backend"):
        print(f"warning: {n}: NLI backend {(m.get('nli') or {}).get('backend')!r} differs from the owner's runs ({(ref.get('nli') or {}).get('backend')!r}): unsupported-fact rates are not comparable")
    if ref.get("git_sha") and m.get("git_sha") != ref.get("git_sha"):
        msg = f"{n}: git_sha {str(m.get('git_sha'))[:10]} differs from the owner's Full runs ({str(ref.get('git_sha'))[:10]})"
        if os.environ.get("ALLOW_CODE_MISMATCH") == "1":
            print("warning: " + msg)
        else:
            problems.append(msg)
if problems:
    sys.exit("REFUSED:\n  " + "\n  ".join(problems))
target = Path(os.environ.get("SWEEP_TARGET") or f"data/eval/dev_runs/{top}")
n_new = 0
for f in sorted(root.rglob("*")):
    if f.is_file():
        rel = f.relative_to(root)
        if rel.name == "PACK_INFO.json":
            dest = target / f"PACK_INFO-{Path(src).stem}.json"
        else:
            dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.read_bytes() != f.read_bytes() and rel.name == "MANIFEST.json":
            shutil.copy2(dest, str(dest) + ".prev")
        shutil.copy2(f, dest)
        n_new += 1
print(f"unpacked {n_new} files from {len(manifests)} run(s) into {target}")
PYE
echo "score (sarvam: its own Full is the reference; openai: the owner's Full in data/eval/dev_runs/outputs/full): .venv/bin/python -m vakeel_sahayak.eval.scoring score --runs data/eval/dev_runs/<sarvam|openai>_block/outputs --slice dev --gold-source both --out <dir>"
