"""Which T1 gold is read: the AGREED gold (primary) or the RULE-only gold (pre-declared secondary), and the swap between the two layouts.

Decision of the owner (2026-10-26): the gold agreed between the rules and a non-Qwen labeler with span grounding (`pipelines/gold/agreement.py`) is the PRIMARY T1 gold; the
rule-only gold is kept as a pre-declared SECONDARY gold, and every gold-dependent metric is rescored on it as one declared sensitivity analysis (`docs/evaluation-plan.md`
"Gold-source sensitivity"; the job `gold_source_sweep` of `configs/eval/runs.yaml`, no model call, cost 0).

Layout under `<testsets>/`:
* `t1/`              the primary gold (after the swap: agreed). The case ids, the dev, open and blind id sets and their hashes are the same in both.
* `t1_rule_only/`    the rule-only gold (the T1 directory as it was built before the swap), self-consistent manifests.
* `t1_gold_candidate/` the agreed `cases.jsonl` and `dev.jsonl` as written by `pipelines.gold.agreement apply` (the source of the swap; kept).

The source is chosen by the `gold_source` argument (`agreed` default, `rule`) or the environment variable `VS_GOLD_SOURCE`. Both directories carry `manifest.json` with
`details.gold = {source, cases_sha256, dev_sha256, gold_sha256}`; run manifests (`MANIFEST.json`) copy `gold_source` and `gold_sha256`.

CLI (wrapped by `scripts/swap_gold.sh`): `python -m vakeel_sahayak.testsets.gold_source swap --primary agreed|rule [--backup DIR]`, `info`, `refresh DIR --source S`.
Nothing here reads the sealed blind ids: the blind slice is recognised by the salted hashes of `manifest_blind.json`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SOURCES = ("agreed", "rule")
DEFAULT_SOURCE = "agreed"
ENV_VAR = "VS_GOLD_SOURCE"
RULE_DIR = "t1_rule_only"
CANDIDATE_DIR = "t1_gold_candidate"
PRIMARY_DIR = "t1"
GOLD_FILES = ("cases.jsonl", "dev.jsonl")
# Files that describe ids only (never the gold): copied unchanged by the swap.
ID_FILES = ("manifest.json", "manifest_dev.json", "manifest_open.json", "manifest_blind.json", "blind_sealed.json")


def resolve_source(source: str | None = None) -> str:
    """`source` if given, else `$VS_GOLD_SOURCE`, else `agreed`; anything else is a ValueError."""
    value = str(source or os.environ.get(ENV_VAR) or DEFAULT_SOURCE).strip().lower()
    if value not in SOURCES:
        raise ValueError(f"gold_source must be one of {SOURCES}, got {value!r}")
    return value


def testsets_root(testsets_dir: str | Path | None = None) -> Path:
    """`testsets_dir`, else the configured `paths.testsets_dir` (`VS_DATA_DIR` rebases it)."""
    if testsets_dir:
        return Path(testsets_dir)
    from vakeel_sahayak.config import load_config

    return Path(load_config().paths.testsets_dir)


def file_sha256(path: Path) -> str:
    """SHA-256 (hex) of a file's bytes."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def gold_hashes(d: str | Path) -> dict[str, str]:
    """`cases_sha256`, `dev_sha256` and `gold_sha256` (SHA-256 over the two file hashes) of a T1 directory."""
    base = Path(d)
    cases, dev = file_sha256(base / "cases.jsonl"), file_sha256(base / "dev.jsonl")
    return {"cases_sha256": cases, "dev_sha256": dev, "gold_sha256": hashlib.sha256(f"{cases}\n{dev}".encode()).hexdigest()}


def manifest_gold(d: str | Path) -> dict[str, Any] | None:
    """The `details.gold` record of `<d>/manifest.json`, or None when the manifest or the record is missing."""
    p = Path(d) / "manifest.json"
    if not p.is_file():
        return None
    return (json.loads(p.read_text(encoding="utf-8")).get("details") or {}).get("gold")


def t1_dir(source: str | None = None, testsets_dir: str | Path | None = None) -> Path:
    """The directory of the requested gold: `agreed` is `t1/` when its manifest says so (else `t1_gold_candidate/`), `rule` is `t1_rule_only/`."""
    src, root = resolve_source(source), testsets_root(testsets_dir)
    if src == "rule":
        return root / RULE_DIR
    primary = root / PRIMARY_DIR
    rec = manifest_gold(primary)
    if rec is not None and rec.get("source") == "rule" and (root / CANDIDATE_DIR / "cases.jsonl").is_file():
        return root / CANDIDATE_DIR  # t1/ currently holds the rule gold (swapped back); the agreed copy is the candidate folder
    return primary


def gold_info(source: str | None = None, testsets_dir: str | Path | None = None) -> dict[str, Any]:
    """`{gold_source, gold_dir, gold_sha256, cases_sha256, dev_sha256}` of the requested gold (hashes None when the files are absent)."""
    src = resolve_source(source)
    d = t1_dir(src, testsets_dir)
    try:
        h = gold_hashes(d)
    except FileNotFoundError:
        h = {"cases_sha256": None, "dev_sha256": None, "gold_sha256": None}
    return {"gold_source": src, "gold_dir": str(d), **h}


def gold_info_for_cases(cases_path: str | Path | None) -> dict[str, Any]:
    """What a run manifest records: the gold of the T1 directory that holds `cases_path` (from its manifest), else the environment's gold source."""
    if cases_path:
        p = Path(cases_path)
        rec = manifest_gold(p.parent)
        if rec and rec.get("source") in SOURCES:
            return {"gold_source": rec["source"], "gold_sha256": rec.get("gold_sha256")}
        if p.name in GOLD_FILES and p.parent.name in (PRIMARY_DIR, RULE_DIR, CANDIDATE_DIR) and p.is_file():
            src = "rule" if p.parent.name == RULE_DIR else "agreed"
            try:
                return {"gold_source": src, "gold_sha256": gold_hashes(p.parent)["gold_sha256"]}
            except FileNotFoundError:
                return {"gold_source": src, "gold_sha256": None}
    try:
        info = gold_info()
    except Exception:  # noqa: BLE001  (a manifest must never fail on a missing test-set directory)
        return {"gold_source": resolve_source(), "gold_sha256": None}
    return {"gold_source": info["gold_source"], "gold_sha256": info["gold_sha256"]}


def load_t1(split: str = "test", gold_source: str | None = None, testsets_dir: str | Path | None = None) -> list[dict[str, Any]]:
    """T1 case rows of the requested gold: `split` is `test` (`cases.jsonl`, 200) or `dev` (`dev.jsonl`, 50). The case ids and their order are the same for both sources."""
    if split not in ("test", "dev"):
        raise ValueError("split must be 'test' or 'dev'")
    path = t1_dir(gold_source, testsets_dir) / ("cases.jsonl" if split == "test" else "dev.jsonl")
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------------------------------------------------------- manifests
def refresh_manifest(d: str | Path, source: str) -> dict[str, Any]:
    """Recompute the gold-dependent parts of `<d>/manifest.json` with the T1 builder's `_stats`, and record the gold source and hashes.

    Only `details.{test,dev,open,blind}` (coverage statistics) and `details.gold` / `path` change. The blind slice is found through the salted hashes of
    `manifest_blind.json` (the sealed ids are not read); `manifest_dev.json`, `manifest_open.json`, `manifest_blind.json` and `blind_sealed.json` are not touched
    (they hold ids and id hashes, which a gold swap does not change). Raises ValueError when the blind hashes do not match the cases.
    """
    from vakeel_sahayak.testsets.blind import blind_hash, set_hash
    from vakeel_sahayak.testsets.t1_court_grounded import _stats

    base, src = Path(d), resolve_source(source)
    cases, dev = load_rows(base / "cases.jsonl"), load_rows(base / "dev.jsonl")
    blind_manifest = json.loads((base / "manifest_blind.json").read_text(encoding="utf-8"))
    hashes = set(blind_manifest["hashes"])
    blind = [c for c in cases if blind_hash(c["case_id"]) in hashes]
    if len(blind) != int(blind_manifest["n"]) or set_hash([blind_hash(c["case_id"]) for c in blind]) != blind_manifest["set_hash"]:
        raise ValueError(f"the blind hashes of {base} do not match its cases")
    open_ids = set(json.loads((base / "manifest_open.json").read_text(encoding="utf-8"))["case_ids"])
    open_cases = [c for c in cases if c["case_id"] in open_ids]
    manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    details = manifest.setdefault("details", {})
    details["test"], details["dev"], details["open"] = _stats(cases), _stats(dev), _stats(open_cases)
    details["blind"] = {**_stats(blind), "per_court": None, "note": "ids are hashes only in manifest_blind.json; only counts are public here"}
    details["gold"] = {"source": src, **gold_hashes(base)}
    manifest["path"] = str(base)
    (base / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def load_rows(path: Path) -> list[dict[str, Any]]:
    """UTF-8 JSON lines (blank lines skipped)."""
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _same_ids(a: Path, b: Path) -> bool:
    return [(r["case_id"], r["doc_id"]) for f in GOLD_FILES for r in load_rows(a / f)] == [(r["case_id"], r["doc_id"]) for f in GOLD_FILES for r in load_rows(b / f)]


# ---------------------------------------------------------------------------------------------------------------- swap
def swap_t1(primary: str, testsets_dir: str | Path | None = None, backup: str | Path | None = None) -> dict[str, Any]:
    """Make `primary` (`agreed` or `rule`) the gold in `t1/`, keeping the other gold in its own folder. Idempotent; refuses to overwrite a gold it cannot restore.

    * First run on a rule-only `t1/` (no manifest record, or `source == rule`, and no `t1_rule_only/`): `t1/` is MOVED to `t1_rule_only/` (that is the backup; nothing is copied).
    * `agreed`: `t1/` becomes `t1_gold_candidate/{cases,dev}.jsonl` plus the id/manifest files of `t1_rule_only/`, with `manifest.json` refreshed.
    * `rule`: `t1/` becomes a copy of `t1_rule_only/`. A `t1/` whose gold is neither of the two (hash not equal to the candidate or the rule gold) is first moved to `backup`
      (required in that case, must not exist); otherwise it is replaced because both of its possible contents are kept elsewhere.
    * The case ids, the doc ids and the blind id set must be identical in both golds, else ValueError and nothing is replaced.

    Returns: a dict of what was done (`action`, hashes).
    """
    if primary not in SOURCES:
        raise ValueError(f"--primary must be one of {SOURCES}")
    root = testsets_root(testsets_dir)
    t1, rule, cand = root / PRIMARY_DIR, root / RULE_DIR, root / CANDIDATE_DIR
    done: dict[str, Any] = {"primary": primary, "actions": []}
    if not rule.exists():
        if not t1.is_dir():
            raise FileNotFoundError(f"{t1} does not exist: build T1 first")
        rec = manifest_gold(t1)
        if rec is not None and rec.get("source") == "agreed":
            raise ValueError(f"{t1} already holds the agreed gold and {rule} does not exist: refusing to guess where the rule-only gold is")
        t1.rename(rule)
        done["actions"].append(f"moved {t1} -> {rule}")
        refresh_manifest(rule, "rule")
        done["actions"].append(f"refreshed {rule}/manifest.json (source rule)")
    if not (cand / "cases.jsonl").is_file() or not (cand / "dev.jsonl").is_file():
        raise FileNotFoundError(f"{cand}/cases.jsonl or dev.jsonl missing: run `python -m vakeel_sahayak.pipelines.gold.agreement apply` first")
    if not _same_ids(rule, cand):
        raise ValueError("the candidate (agreed) and the rule-only gold do not list the same case ids and doc ids: not swapping")
    want_dir = cand if primary == "agreed" else rule
    want_hash = gold_hashes(want_dir)["gold_sha256"]
    have = gold_hashes(t1)["gold_sha256"] if (t1 / "cases.jsonl").is_file() and (t1 / "dev.jsonl").is_file() else None
    if have == want_hash and (manifest_gold(t1) or {}).get("gold_sha256") == want_hash:
        done["actions"].append(f"nothing to do: {t1} already holds the {primary} gold")
        done["gold_sha256"] = want_hash
        return done
    kept_elsewhere = {gold_hashes(rule)["gold_sha256"], gold_hashes(cand)["gold_sha256"]}
    if t1.exists() and have is not None and have not in kept_elsewhere:
        if backup is None or Path(backup).exists():
            raise ValueError(f"{t1} holds a gold that is not stored anywhere else: pass --backup DIR (must not exist yet); refusing to overwrite it")
        t1.rename(Path(backup))
        done["actions"].append(f"moved {t1} -> {backup}")
    elif t1.exists() and have is None and any(t1.iterdir()):
        if backup is None or Path(backup).exists():
            raise ValueError(f"{t1} is not a recognisable T1 directory: pass --backup DIR (must not exist yet); refusing to overwrite it")
        t1.rename(Path(backup))
        done["actions"].append(f"moved {t1} -> {backup}")
    t1.mkdir(parents=True, exist_ok=True)
    for name in ID_FILES:
        if (rule / name).is_file():
            shutil.copyfile(rule / name, t1 / name)
    for name in GOLD_FILES:
        shutil.copyfile(want_dir / name, t1 / name)
    refresh_manifest(t1, primary)
    done["actions"].append(f"{t1} now holds the {primary} gold")
    done["gold_sha256"] = gold_hashes(t1)["gold_sha256"]
    return done


def swap_interim_gold(primary: str, work_dir: str | Path, candidate_dir: str | Path) -> list[str]:
    """Make `<work>/gold/g*.jsonl` the agreed records (merged over the rule-only rows by doc id, so orders outside the 250 keep their rows) or the rule-only ones.

    The rule-only originals of every replaced file are MOVED to `<work>/gold/rule_only/` once (never overwritten); `agreed` merges into the originals there.
    """
    gold, cand = Path(work_dir) / "gold", Path(candidate_dir)
    ro = gold / "rule_only"
    log: list[str] = []
    for k in (1, 3, 4, 5, 6, 7):
        name, new = f"g{k}.jsonl", cand / f"g{k}.jsonl"
        if not new.is_file():
            continue
        if not (ro / name).is_file():
            ro.mkdir(parents=True, exist_ok=True)
            (gold / name).rename(ro / name)
            log.append(f"moved {gold / name} -> {ro / name}")
        if primary == "rule":
            shutil.copyfile(ro / name, gold / name)
            log.append(f"restored rule-only {name}")
            continue
        merged = {str(r["doc_id"]): r for r in load_rows(ro / name) if r.get("doc_id")}
        agreed = {str(r["doc_id"]): r for r in load_rows(new) if r.get("doc_id")}
        merged.update(agreed)
        tmp = gold / (name + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for r in merged.values():
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(gold / name)
        log.append(f"wrote agreed {name}: {len(agreed)} agreed rows over {len(merged) - len(agreed)} rule-only rows")
    return log


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="T1 gold source: swap, info, refresh")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("swap")
    s.add_argument("--primary", choices=SOURCES, required=True)
    s.add_argument("--testsets", default=None)
    s.add_argument("--backup", default=None)
    s.add_argument("--work", default=None, help="interim T1 work folder (default <interim>/t1_work); its gold/ files follow the swap")
    s.add_argument("--candidate", default=None, help="folder with the agreed g*.jsonl (default <interim>/gold_candidate)")
    s.add_argument("--no-interim", action="store_true")
    i = sub.add_parser("info")
    i.add_argument("--testsets", default=None)
    r = sub.add_parser("refresh")
    r.add_argument("dir")
    r.add_argument("--source", choices=SOURCES, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "info":
        print(json.dumps({s_: gold_info(s_, a.testsets) for s_ in SOURCES}, indent=1))
        return 0
    if a.cmd == "refresh":
        refresh_manifest(a.dir, a.source)
        print(json.dumps(gold_hashes(a.dir), indent=1))
        return 0
    try:
        out = swap_t1(a.primary, a.testsets, a.backup)
        if not a.no_interim:
            from vakeel_sahayak.config import load_config

            interim = Path(load_config().paths.interim_dir)
            out["interim"] = swap_interim_gold(a.primary, a.work or interim / "t1_work", a.candidate or interim / "gold_candidate")
    except (ValueError, FileNotFoundError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
