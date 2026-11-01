#!/usr/bin/env bash
# Create the freeze tags (local only, never pushed) when the owner asks for them.
#   scripts/freeze_tags.sh check                   check only: clean tree, tags absent, placeholders left in the preregistration
#   scripts/freeze_tags.sh create prereg-v1        annotated tag prereg-v1 on HEAD
#   scripts/freeze_tags.sh create eval-freeze-v1   annotated tag eval-freeze-v1 on HEAD (needs prereg-v1 first)
# Nothing is created without the explicit `create <tag>`; the script never runs `git push`.
# Order (docs/handoff/prereg.md): fill and commit docs/preregistration.md, create prereg-v1; then the code is frozen at the same or a later
# clean commit and eval-freeze-v1 is created. Push the tags yourself after review: git push origin <tag>.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
PREREG=docs/preregistration.md
mode="${1:-check}"
tag="${2:-}"

fail() { echo "freeze_tags: $*" >&2; exit 1; }

case "$mode" in
  check) ;;
  create) case "$tag" in prereg-v1|eval-freeze-v1) ;; *) fail "tag must be prereg-v1 or eval-freeze-v1" ;; esac ;;
  *) fail "usage: $0 check | create prereg-v1 | create eval-freeze-v1" ;;
esac

[ -z "$(git status --porcelain)" ] || fail "working tree is not clean (commit first; untracked files count)"

for t in prereg-v1 eval-freeze-v1; do
  if git rev-parse -q --verify "refs/tags/$t" >/dev/null; then
    if [ "$mode" = create ] && [ "$t" = "$tag" ]; then fail "tag $t already exists (tags are never moved)"; fi
    echo "note: tag $t already exists at $(git rev-parse --short "$t")"
  fi
done

left=$(grep -c '`<[^`]*>`' "$PREREG" || true)
if [ "$left" -gt 0 ]; then
  echo "warning: $PREREG has $left lines with a \`<placeholder>\` left (the freeze record of section 0 is filled by the owner at the freeze)" >&2
  if [ "$mode" = create ] && [ "$tag" = prereg-v1 ] && [ "${ALLOW_PLACEHOLDERS:-0}" != 1 ]; then
    fail "refusing prereg-v1 with placeholders left; fill them, or set ALLOW_PLACEHOLDERS=1 once the owner agrees"
  fi
fi

if [ "$mode" = check ]; then
  echo "ok: tree clean at $(git rev-parse --short HEAD)"
  exit 0
fi

if [ "$tag" = eval-freeze-v1 ] && ! git rev-parse -q --verify refs/tags/prereg-v1 >/dev/null; then
  fail "create prereg-v1 first"
fi
git tag -a "$tag" -m "$tag at $(git rev-parse HEAD)"
echo "created local tag $tag at $(git rev-parse --short HEAD); not pushed (git push origin $tag when ready)"
