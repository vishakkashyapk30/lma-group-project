#!/bin/bash
# Laptop side of scripts/ada/embed_bge_m3.sbatch: pull every finished BGE-M3 shard from ~/vs_bge/outbox on Ada, check its sha256, then delete it
# there (the job waits while the outbox holds 4 shards) and record it in ~/vs_bge/received.txt so a rerun of the job skips it.
#   setsid nohup bash scripts/ada/pull_bge_shards.sh <job id> > /tmp/claude-1000/bge_pull.log 2>&1 < /dev/null &
# Stops when the job wrote EMBED_DONE.json and the outbox is empty, or when the job left the queue without it (then resubmit: it resumes).
# Never copies anything to Ada; needs the ssh alias `ada`. Free disk is checked before each pull (MIN_FREE_MB, default 600).
set -uo pipefail
JOB=${1:?job id}
REPO=$(cd "$(dirname "$0")/../.." && pwd)
DEST=${DEST:-$REPO/data/bge_work/shards}
SLEEP=${SLEEP:-60}
MIN_FREE_MB=${MIN_FREE_MB:-600}
mkdir -p "$DEST"
log() { echo "$(date '+%F %T') $*"; }
log "pull loop for job $JOB into $DEST"
while true; do
  free_mb=$(df -Pm "$DEST" | awk 'NR==2 {print $4}')
  if [ "$free_mb" -lt "$MIN_FREE_MB" ]; then log "only ${free_mb} MB free on the laptop: waiting"; sleep "$SLEEP"; continue; fi
  listing=$(ssh -o BatchMode=yes -o ConnectTimeout=30 ada 'cd ~/vs_bge/outbox 2>/dev/null && ls -1; echo "@@state $(squeue -h -j '"$JOB"' -o %T 2>/dev/null)"') || { log "ssh failed, retrying"; sleep "$SLEEP"; continue; }
  state=$(printf '%s\n' "$listing" | sed -n 's/^@@state //p')
  stems=$(printf '%s\n' "$listing" | grep -E '\.[0-9]{3}\.json$' | sed 's/\.json$//' | sort)
  for s in $stems; do
    if ! scp -q -o BatchMode=yes "ada:vs_bge/outbox/$s.json" "ada:vs_bge/outbox/$s.npy" "ada:vs_bge/outbox/$s.ids.npy" "$DEST/"; then log "scp $s failed"; continue; fi
    if python3 - "$DEST" "$s" <<'PY'
import hashlib, json, sys
d, s = sys.argv[1], sys.argv[2]
info = json.load(open(f"{d}/{s}.json"))
ok = all(hashlib.sha256(open(f"{d}/{s}{suf}", "rb").read()).hexdigest() == info[key] for suf, key in ((".npy", "npy_sha256"), (".ids.npy", "ids_sha256")))
sys.exit(0 if ok else 1)
PY
    then
      ssh -o BatchMode=yes ada "cd ~/vs_bge/outbox && rm -f '$s.npy' '$s.ids.npy' '$s.json' && echo '$s' >> ~/vs_bge/received.txt" && log "pulled $s"
    else
      log "sha256 mismatch for $s: removed the local copy, will pull again"; rm -f "$DEST/$s.json" "$DEST/$s.npy" "$DEST/$s.ids.npy"
    fi
  done
  for f in equivalence_check.json EMBED_DONE.json; do
    printf '%s\n' "$listing" | grep -qx "$f" && scp -q -o BatchMode=yes "ada:vs_bge/outbox/$f" "$DEST/" 2>/dev/null
  done
  if [ -f "$DEST/EMBED_DONE.json" ] && [ -z "$stems" ]; then log "EMBED_DONE and outbox empty: finished"; break; fi
  if [ -z "$state" ] && [ -z "$stems" ]; then
    sleep 30
    if ssh -o BatchMode=yes ada 'ls ~/vs_bge/outbox/EMBED_DONE.json' >/dev/null 2>&1; then continue; fi
    log "job $JOB is no longer queued and wrote no EMBED_DONE.json: see ~/vs_bge/logs/embed_$JOB.log, resubmit to resume"; break
  fi
  [ -n "$stems" ] || log "job $JOB state=${state:-gone}, nothing new"
  sleep "$SLEEP"
done
