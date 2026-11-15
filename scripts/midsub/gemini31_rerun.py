"""Resumable rerun of the six Gemini-3.1-flash-lite arms (A4, S11b, S11c, S12b, S15b, A5:base_4b) on t1dev-000 and t1dev-001.

One case at a time, one arm at a time in priority order. Before each case the quota ledger must show at least MIN_LEFT requests for the day;
otherwise the script sleeps (polling every 5 minutes) until the quota day resets. The driver skips saved cases, so a restart resumes.
Free tier, one key, public dev cases only (never a second key or a paid provider).
Usage: gemini31_rerun.py <dir holding t1dev-000.jsonl and t1dev-001.jsonl> <out_root>
"""

import subprocess
import sys
import time
from pathlib import Path

ARMS = ["A4", "S11b", "S11c", "S12b", "S15b", "A5:base_4b"]
CASES = ["t1dev-000", "t1dev-001"]
MODEL = "gemini-3.1-flash-lite"
MIN_LEFT = 60
MAX_ATTEMPTS = 6
src, out_root = Path(sys.argv[1]), Path(sys.argv[2])


def log(msg: str) -> None:
    print(time.strftime("%F %T"), msg, flush=True)


def remaining() -> int:
    from vakeel_sahayak.models.hosted.quota import provider_report

    rep = provider_report("gemini")
    return min((v["remaining"] for v in rep["by_key_model"].values() if v["model"] == MODEL), default=0)


def wait_for_quota(label: str) -> int:
    while True:
        try:
            left = remaining()
        except Exception as exc:  # ledger unreadable: refuse to call
            left = 0
            log(f"ledger error {type(exc).__name__}")
        if left >= MIN_LEFT:
            return left
        log(f"{label}: {left} requests left (< {MIN_LEFT}); waiting")
        time.sleep(300)


for arm in ARMS:
    d = out_root / arm.lower().replace(":", "_")
    for case in CASES:
        saved = d / f"{case}.json"
        attempts = 0
        while not saved.exists() and attempts < MAX_ATTEMPTS:
            attempts += 1
            left = wait_for_quota(f"{arm} {case}")
            log(f"start {arm} {case} attempt {attempts} (ledger left {left})")
            cmd = [sys.executable, "-m", "vakeel_sahayak.eval.runners.driver", "run", "--system", arm, "--cases", str(src / f"{case}.jsonl"),
                   "--out", str(d), "--run-index", "1"]  # fmt: skip
            r = subprocess.run(cmd, capture_output=True, text=True)
            tail = "\n".join(x for x in (r.stdout + r.stderr).splitlines() if "Warn" not in x and "Loading" not in x)[-500:]
            log(f"done {arm} {case}: rc={r.returncode} saved={saved.exists()}\n{tail}")
            if not saved.exists():
                time.sleep(300)
        if not saved.exists():
            log(f"GIVE_UP {arm} {case} after {MAX_ATTEMPTS} attempts")
log("RERUN_DONE")
