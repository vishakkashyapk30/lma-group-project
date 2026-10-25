#!/usr/bin/env python3
"""Print the blind-slice hash for docs/preregistration.md. Writes nothing and never creates the git tag.

Two sources, both reading hashes only (the sealed ids in `blind_sealed.json` are never read here, so nothing is peeked at):

* default (`--source manifest`): `data/testsets/t1/manifest_blind.json`, written by the T1 builder, which drew the 80 blind ids with its seeded draw (stratified: at least 25 BNS-era,
  post-release orders first; seed 20241024). The script recomputes the set hash from the per-id hashes and checks it equals the manifest's, then prints it.
* `--source splits`: a seeded draw of `--n` (default 80) ids from the `test` entries of `data/interim/splits.json` (document ids), for use before T1 is built. It is NOT the T1 draw
  (T1 case ids are not document ids and its draw is stratified), so use it only as a placeholder and say so in the preregistration.

Run: `.venv/bin/python scripts/prereg_hash.py [--source manifest|splits] [--seed N] [--n 80] [--testsets DIR] [--splits FILE]`
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from vakeel_sahayak.testsets.blind import SALT, blind_hash, set_hash  # noqa: E402

DEFAULT_SEED = 20241024  # the T1 builder's seed (testsets/t1_court_grounded.py SEED)


def from_manifest(path: Path) -> dict[str, object]:
    """The set hash of a sealed blind manifest, recomputed from its per-id hashes; raises when it does not match the stored one."""
    m = json.loads(path.read_text(encoding="utf-8"))
    hashes = [str(h) for h in m["hashes"]]
    recomputed = set_hash(hashes)
    if m.get("set_hash") and m["set_hash"] != recomputed:
        raise SystemExit(f"manifest set_hash {m['set_hash']} does not match the hashes ({recomputed}): the file was edited or is from another salt")
    return {"source": str(path), "n": len(hashes), "salt": m.get("salt_id", SALT), "set_hash": recomputed}


def from_splits(path: Path, n: int, seed: int) -> dict[str, object]:
    """A seeded draw of `n` ids from the test entries of splits.json, hashed with the project salt."""
    splits = json.loads(path.read_text(encoding="utf-8"))
    test = sorted(k for k, v in splits.items() if v == "test")
    if len(test) < n:
        raise SystemExit(f"only {len(test)} test ids in {path}, need {n}")
    drawn = sorted(random.Random(seed).sample(test, n))
    return {"source": f"{path} (seeded draw, seed {seed}; NOT the T1 stratified draw)", "n": n, "salt": SALT, "set_hash": set_hash([blind_hash(i) for i in drawn])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", choices=["manifest", "splits"], default="manifest")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--testsets", default=str(REPO / "data" / "testsets"))
    ap.add_argument("--splits", default=str(REPO / "data" / "interim" / "splits.json"))
    args = ap.parse_args(argv)
    if args.source == "manifest":
        out = from_manifest(Path(args.testsets) / "t1" / "manifest_blind.json")
    else:
        out = from_splits(Path(args.splits), args.n, args.seed)
    print(f"blind_set_hash: {out['set_hash']}")
    print(f"n: {out['n']}  salt: {out['salt']}  source: {out['source']}")
    print("paste the hash into docs/preregistration.md; this script wrote nothing and did not create the tag prereg-v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
