#!/usr/bin/env bash
# sync-run-cost-summary-contract.sh -- generate the run-cost-summary emission
# paragraph into every pipeline and dm-review consumer from one canonical source.
#
# Depot command and skill files must stay self-contained: Claude Desktop caches
# each plugin independently and resolves no cross-file references at read time.
# So the paragraph is duplicated by design -- but generated, never hand-edited,
# so eleven copies cannot drift.
#
# Canonical source:
#   plugins/workflow-kernel/skills/workflow-kernel/references/run-cost-summary-contract.md
#   (the text between CANONICAL-PARAGRAPH-START and CANONICAL-PARAGRAPH-END)
#
# Usage:
#   tools/sync-run-cost-summary-contract.sh            rewrite every consumer
#   tools/sync-run-cost-summary-contract.sh --check     report drift, exit 1
#
# Dependencies: POSIX sh utilities only (grep, sed, awk, mktemp, cmp).
# Bash 3.2+ compatible for macOS.

set -uo pipefail
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"   # fixed PATH: prevent caller-controlled hijack

REPO_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
CANONICAL="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/run-cost-summary-contract.md"

CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "") ;;
  *) printf 'usage: %s [--check]\n' "$0" >&2; exit 2 ;;
esac

if [ ! -f "$CANONICAL" ]; then
  printf 'FAIL canonical source missing: %s\n' "${CANONICAL#$REPO_ROOT/}" >&2
  exit 2
fi

# The paragraph is one line between the two markers. Extract it exactly.
PARAGRAPH=$(awk '
  /<!-- CANONICAL-PARAGRAPH-START -->/ { capture = 1; next }
  /<!-- CANONICAL-PARAGRAPH-END -->/   { capture = 0 }
  capture { print }
' "$CANONICAL")

if [ -z "$PARAGRAPH" ]; then
  printf 'FAIL canonical paragraph block is empty in %s\n' "${CANONICAL#$REPO_ROOT/}" >&2
  exit 2
fi
if [ "$(printf '%s\n' "$PARAGRAPH" | wc -l | tr -d ' ')" != "1" ]; then
  printf 'FAIL canonical paragraph must be exactly one line\n' >&2
  exit 2
fi

CONSUMERS="
plugins/dm-review/skills/review/SKILL.md
plugins/dm-review/commands/dm-review.md
plugins/dm-review/skills/dm-review/SKILL.md
plugins/dm-review/commands/dm-review-loop.md
plugins/dm-review/skills/dm-review-loop/SKILL.md
plugins/dm-review/commands/dm-review-visual.md
plugins/dm-review/skills/dm-review-visual/SKILL.md
plugins/pipeline/commands/pipeline.md
plugins/pipeline/skills/pipeline/SKILL.md
plugins/pipeline/commands/pipeline-run.md
plugins/pipeline/skills/pipeline-run/SKILL.md
"

# Every consumer's paragraph begins with this literal. It is the replacement anchor.
ANCHOR='The `run-cost-summary` command emits'

drift=0
synced=0
missing=0

for rel in $CONSUMERS; do
  f="$REPO_ROOT/$rel"
  if [ ! -f "$f" ]; then
    printf 'FAIL consumer missing: %s\n' "$rel" >&2
    missing=$((missing + 1))
    continue
  fi

  hits=$(grep -c "^$ANCHOR" "$f")
  if [ "$hits" != "1" ]; then
    printf 'FAIL %s has %s paragraph anchors, expected exactly 1\n' "$rel" "$hits" >&2
    missing=$((missing + 1))
    continue
  fi

  current=$(grep "^$ANCHOR" "$f")
  if [ "$current" = "$PARAGRAPH" ]; then
    continue
  fi

  drift=$((drift + 1))
  if [ "$CHECK_ONLY" -eq 1 ]; then
    printf 'DRIFT %s\n' "$rel" >&2
    continue
  fi

  tmp=$(mktemp "${TMPDIR:-/tmp}/sync-rcs.XXXXXX") || exit 2
  # Replace the whole anchored line with the canonical paragraph. awk avoids
  # sed's delimiter and backslash interpretation on arbitrary paragraph text.
  PARA="$PARAGRAPH" ANCH="$ANCHOR" awk '
    index($0, ENVIRON["ANCH"]) == 1 { print ENVIRON["PARA"]; next }
    { print }
  ' "$f" > "$tmp" || { rm -f "$tmp"; exit 2; }
  cat "$tmp" > "$f" || { rm -f "$tmp"; exit 2; }
  rm -f "$tmp"
  synced=$((synced + 1))
  printf 'SYNC  %s\n' "$rel"
done

if [ "$missing" -ne 0 ]; then
  printf '\nFAIL %s consumer(s) unusable\n' "$missing" >&2
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ "$drift" -ne 0 ]; then
    printf '\nFAIL %s consumer(s) drifted from the canonical paragraph\n' "$drift" >&2
    printf 'FIX  tools/sync-run-cost-summary-contract.sh\n' >&2
    exit 1
  fi
  printf 'ok    11 consumers match the canonical run-cost-summary paragraph\n'
  exit 0
fi

printf '\nok    %s consumer(s) rewritten, %s already current\n' "$synced" "$((11 - synced))"
exit 0
