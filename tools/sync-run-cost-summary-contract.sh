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
# Dependencies: POSIX sh utilities only (awk, mktemp, mv, rm).
# Bash 3.2+ compatible for macOS.
#
# Two properties this script must never violate, because its targets are
# distributed plugin entrypoints:
#
#   1. ONE PREDICATE. Counting anchor lines and replacing anchor lines use the
#      same literal prefix test, in awk. An earlier version counted with `grep
#      -c "^$ANCHOR"` and replaced with awk's `index()`; grep applies regular
#      expression semantics to the anchor while awk applies literal semantics,
#      so a file could pass the count check and then have a different set of
#      lines replaced.
#   2. ATOMIC REPLACEMENT. The rewritten file is built in the target's own
#      directory and moved into place with `mv`, which is atomic within a
#      filesystem. An earlier version used `cat "$tmp" > "$f"`, where the shell
#      truncates the target before `cat` writes; any failure mid-copy left a
#      shipped command file empty or half-written with no way back.

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

# Exactly one start marker and exactly one end marker, in that order.
marker_counts=$(awk '
  /<!-- CANONICAL-PARAGRAPH-START -->/ { starts++ }
  /<!-- CANONICAL-PARAGRAPH-END -->/   { ends++ }
  END { printf "%d %d", starts, ends }
' "$CANONICAL")
if [ "$marker_counts" != "1 1" ]; then
  printf 'FAIL canonical source must have exactly one start and one end marker (found: %s)\n' \
    "$marker_counts" >&2
  exit 2
fi

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

# Every consumer's paragraph begins with this literal. It is the replacement
# anchor, matched as a literal prefix -- never as a pattern.
ANCHOR='The `run-cost-summary` command emits'

expected_consumers=0
for _ in $CONSUMERS; do expected_consumers=$((expected_consumers + 1)); done

drift=0
synced=0
unusable=0

for rel in $CONSUMERS; do
  f="$REPO_ROOT/$rel"
  if [ ! -f "$f" ]; then
    printf 'FAIL consumer missing: %s\n' "$rel" >&2
    unusable=$((unusable + 1))
    continue
  fi

  # One awk pass, one predicate: count the anchored lines and capture the
  # current paragraph using the exact test the rewrite will use.
  probe=$(ANCH="$ANCHOR" awk '
    index($0, ENVIRON["ANCH"]) == 1 { hits++; current = $0 }
    END { printf "%d\n%s", hits, current }
  ' "$f")
  hits=$(printf '%s' "$probe" | head -1)
  current=$(printf '%s' "$probe" | tail -n +2)

  if [ "$hits" != "1" ]; then
    printf 'FAIL %s has %s paragraph anchors, expected exactly 1\n' "$rel" "$hits" >&2
    unusable=$((unusable + 1))
    continue
  fi

  if [ "$current" = "$PARAGRAPH" ]; then
    continue
  fi

  drift=$((drift + 1))
  if [ "$CHECK_ONLY" -eq 1 ]; then
    printf 'DRIFT %s\n' "$rel" >&2
    continue
  fi

  # Build the replacement beside the target so `mv` stays within one
  # filesystem and is therefore atomic.
  target_dir=$(dirname -- "$f")
  tmp=$(mktemp "$target_dir/.sync-rcs.XXXXXX") || exit 2
  if ! PARA="$PARAGRAPH" ANCH="$ANCHOR" awk '
        index($0, ENVIRON["ANCH"]) == 1 { print ENVIRON["PARA"]; next }
        { print }
      ' "$f" > "$tmp"; then
    rm -f "$tmp"
    printf 'FAIL could not generate replacement for %s\n' "$rel" >&2
    exit 2
  fi

  # A replacement that lost the paragraph, or lost content, is not written.
  replaced=$(ANCH="$ANCHOR" awk '
    index($0, ENVIRON["ANCH"]) == 1 { hits++ } END { print hits + 0 }
  ' "$tmp")
  if [ "$replaced" != "1" ]; then
    rm -f "$tmp"
    printf 'FAIL replacement for %s has %s anchors, expected 1\n' "$rel" "$replaced" >&2
    exit 2
  fi
  if [ "$(wc -l < "$tmp" | tr -d ' ')" != "$(wc -l < "$f" | tr -d ' ')" ]; then
    rm -f "$tmp"
    printf 'FAIL replacement for %s changed the line count\n' "$rel" >&2
    exit 2
  fi

  chmod --reference="$f" "$tmp" 2>/dev/null || chmod 644 "$tmp"
  if ! mv -f "$tmp" "$f"; then
    rm -f "$tmp"
    printf 'FAIL could not replace %s\n' "$rel" >&2
    exit 2
  fi
  synced=$((synced + 1))
  printf 'SYNC  %s\n' "$rel"
done

if [ "$unusable" -ne 0 ]; then
  printf '\nFAIL %s consumer(s) unusable\n' "$unusable" >&2
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ "$drift" -ne 0 ]; then
    printf '\nFAIL %s consumer(s) drifted from the canonical paragraph\n' "$drift" >&2
    printf 'FIX  tools/sync-run-cost-summary-contract.sh\n' >&2
    exit 1
  fi
  printf 'ok    %s consumers match the canonical run-cost-summary paragraph\n' \
    "$expected_consumers"
  exit 0
fi

printf '\nok    %s consumer(s) rewritten, %s already current\n' \
  "$synced" "$((expected_consumers - synced))"
exit 0
