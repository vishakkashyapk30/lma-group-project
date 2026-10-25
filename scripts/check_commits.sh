#!/bin/sh
# Fail if any commit in the range names an AI assistant in its message or as a co-author.
# Usage: scripts/check_commits.sh [range]   (default: origin/main..HEAD)
range="${1:-origin/main..HEAD}"
pattern='claude|anthropic|chatgpt|copilot|gemini|codex|cursor|co-authored-by:[^\n]*(bot|ai)\b'
bad=$(git log "$range" -i -E --grep="$pattern" --format='%h %an: %s')
if [ -n "$bad" ]; then
  echo "AI attribution found in these commits:"; echo "$bad"; exit 1
fi
echo "ok: no AI attribution in $range ($(git rev-list --count "$range") commits)"
