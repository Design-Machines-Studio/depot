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
# Dependencies: POSIX sh utilities only (awk, cp, mkdir, mktemp, mv, rm, rmdir).
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

REPO_ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
CANONICAL="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/run-cost-summary-contract.md"

CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "") ;;
  *) printf 'usage: %s [--check]\n' "$0" >&2; exit 2 ;;
esac

if [ ! -f "$CANONICAL" ]; then
  printf 'FAIL canonical source missing: %s\n' "${CANONICAL#"$REPO_ROOT"/}" >&2
  exit 2
fi

# Exactly one start marker and exactly one end marker, IN THAT ORDER. Counting
# alone accepted an end marker that preceded its start, in which case the
# extraction below would capture from the start marker to end of file and
# silently treat the rest of the document as the paragraph.
marker_state=$(awk '
  /<!-- CANONICAL-PARAGRAPH-START -->/ { starts++; if (!first_start) first_start = NR }
  /<!-- CANONICAL-PARAGRAPH-END -->/   { ends++;   if (!first_end)   first_end   = NR }
  END { printf "%d %d %d %d", starts, ends, first_start, first_end }
' "$CANONICAL")
marker_starts=$(printf '%s' "$marker_state" | cut -d" " -f1)
marker_ends=$(printf '%s' "$marker_state" | cut -d" " -f2)
marker_start_line=$(printf '%s' "$marker_state" | cut -d" " -f3)
marker_end_line=$(printf '%s' "$marker_state" | cut -d" " -f4)
if [ "$marker_starts" != "1" ] || [ "$marker_ends" != "1" ]; then
  printf 'FAIL canonical source needs exactly one start and one end marker (found %s and %s)\n' \
    "$marker_starts" "$marker_ends" >&2
  exit 2
fi
if [ "$marker_start_line" -ge "$marker_end_line" ]; then
  printf 'FAIL canonical end marker (line %s) precedes its start marker (line %s)\n' \
    "$marker_end_line" "$marker_start_line" >&2
  exit 2
fi

PARAGRAPH=$(awk '
  /<!-- CANONICAL-PARAGRAPH-START -->/ { capture = 1; next }
  /<!-- CANONICAL-PARAGRAPH-END -->/   { capture = 0 }
  capture { print }
' "$CANONICAL")

if [ -z "$PARAGRAPH" ]; then
  printf 'FAIL canonical paragraph block is empty in %s\n' \
    "${CANONICAL#"$REPO_ROOT"/}" >&2
  exit 2
fi
if [ "$(printf '%s\n' "$PARAGRAPH" | wc -l | tr -d ' ')" != "1" ]; then
  printf 'FAIL canonical paragraph must be exactly one line\n' >&2
  exit 2
fi

INVOCATION_FLAG=$(sed -n 's/^<!-- CANONICAL-INVOCATION-FLAG: \(.*\) -->$/\1/p' "$CANONICAL")
if [ -z "$INVOCATION_FLAG" ] || [ "$(printf '%s\n' "$INVOCATION_FLAG" | wc -l | tr -d ' ')" != "1" ]; then
  printf 'FAIL canonical invocation flag must appear exactly once\n' >&2
  exit 2
fi
MATRIX_RESOLUTION=$(sed -n 's/^<!-- CANONICAL-MATRIX-RESOLUTION: \(.*\) -->$/\1/p' "$CANONICAL")
if [ -z "$MATRIX_RESOLUTION" ] || [ "$(printf '%s\n' "$MATRIX_RESOLUTION" | wc -l | tr -d ' ')" != "1" ]; then
  printf 'FAIL canonical matrix resolution must appear exactly once\n' >&2
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
# Backticks are literal Markdown in this anchor.
# shellcheck disable=SC2016
ANCHOR='The `emit-cost-summary` command is one transaction'

expected_consumers=0
for _ in $CONSUMERS; do expected_consumers=$((expected_consumers + 1)); done

drift=0
synced=0
rollback_count=0
unusable=0
prepared_rels=()
prepared_targets=()
prepared_temps=()
prepared_backups=()
owned_paths=()
lock_dir="$REPO_ROOT/.sync-rcs.lock"
lock_owned=0

cleanup_invocation_paths() {
  cleanup_failed=0
  cleanup_index=0
  while [ "$cleanup_index" -lt "${#owned_paths[@]}" ]; do
    if ! rm -f -- "${owned_paths[$cleanup_index]}"; then
      cleanup_failed=1
    fi
    cleanup_index=$((cleanup_index + 1))
  done
  if [ "$lock_owned" -eq 1 ]; then
    if rmdir -- "$lock_dir"; then
      lock_owned=0
    else
      cleanup_failed=1
    fi
  fi
  return "$cleanup_failed"
}

rollback_committed() {
  rollback_failed=0
  rollback_index=0
  while [ "$rollback_index" -lt "$rollback_count" ]; do
    if ! cp -p "${prepared_backups[$rollback_index]}" \
         "${prepared_targets[$rollback_index]}"; then
      rollback_failed=1
      printf 'FAIL could not roll back %s\n' \
        "${prepared_rels[$rollback_index]}" >&2
    fi
    rollback_index=$((rollback_index + 1))
  done
  return "$rollback_failed"
}

# Invoked indirectly by the signal trap below.
# shellcheck disable=SC2329
handle_signal() {
  trap '' INT TERM HUP
  if ! rollback_committed; then
    printf 'FAIL rollback was incomplete after interruption\n' >&2
  fi
  printf 'FAIL interrupted; rolled back %s replacement(s)\n' \
    "$rollback_count" >&2
  exit 130
}

trap 'cleanup_invocation_paths || :' EXIT
trap 'handle_signal' INT TERM HUP

if mkdir -- "$lock_dir"; then
  lock_owned=1
else
  printf 'FAIL contract synchronization is already running\n' >&2
  exit 2
fi

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
  invocation_probe=$(awk -v flag="$INVOCATION_FLAG" '
    function count_literal(text, needle, hits, at) {
      while ((at = index(text, needle)) != 0) {
        hits++
        text = substr(text, at + length(needle))
      }
      return hits
    }
    index($0, "emit-cost-summary --events") {
      flag_hits += count_literal($0, flag)
      marker_hits += count_literal($0, " --repository-commit")
    }
    END { printf "%d %d", flag_hits + 0, marker_hits + 0 }
  ' "$f")
  invocation_hits=$(printf '%s' "$invocation_probe" | cut -d" " -f1)
  repository_commit_hits=$(printf '%s' "$invocation_probe" | cut -d" " -f2)
  resolution_hits=$(awk -v resolution="$MATRIX_RESOLUTION" '
    $0 == resolution { hits++ } END { print hits + 0 }
  ' "$f")
  resolution_line_hits=$(awk '
    index($0, "MODEL_MATRIX_ASSET=$(\"$WORKFLOW_KERNEL\" resolve-plugin-asset ") ||
    index($0, "if MODEL_MATRIX_ASSET=$(\"$WORKFLOW_KERNEL\" resolve-plugin-asset ") { hits++ }
    END { print hits + 0 }
  ' "$f")
  legacy_matrix_hits=$(awk '
    index($0, "emit-cost-summary --events") &&
    index($0, "--matrix trusted-openrouter-bundle") { hits++ }
    END { print hits + 0 }
  ' "$f")

  if [ "$hits" != "1" ]; then
    printf 'FAIL %s has %s paragraph anchors, expected exactly 1\n' "$rel" "$hits" >&2
    unusable=$((unusable + 1))
    continue
  fi

  if [ "$current" = "$PARAGRAPH" ] && [ "$invocation_hits" = "1" ] \
     && [ "$repository_commit_hits" = "1" ] \
     && [ "$resolution_hits" = "1" ] && [ "$legacy_matrix_hits" = "0" ]; then
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
  owned_paths+=("$tmp")
  if ! PARA="$PARAGRAPH" ANCH="$ANCHOR" FLAG="$INVOCATION_FLAG" \
       RESOLUTION="$MATRIX_RESOLUTION" awk '
        function remove_literal(text, needle, at) {
          while ((at = index(text, needle)) != 0) {
            text = substr(text, 1, at - 1) substr(text, at + length(needle))
          }
          return text
        }
        index($0, ENVIRON["ANCH"]) == 1 { print ENVIRON["PARA"]; next }
        index($0, "MODEL_MATRIX_ASSET=$(\"$WORKFLOW_KERNEL\" resolve-plugin-asset ") ||
        index($0, "if MODEL_MATRIX_ASSET=$(\"$WORKFLOW_KERNEL\" resolve-plugin-asset ") { next }
        index($0, "emit-cost-summary --events") {
          $0 = remove_literal($0, " --matrix trusted-openrouter-bundle")
          $0 = remove_literal($0, " " ENVIRON["FLAG"])
          marker = " --repository-commit"
          if (!index($0, marker)) exit 3
          sub(marker, " " ENVIRON["FLAG"] marker)
          print ENVIRON["RESOLUTION"]
        }
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
  generated_flag_hits=$(awk -v flag="$INVOCATION_FLAG" '
    function count_literal(text, needle, hits, at) {
      while ((at = index(text, needle)) != 0) {
        hits++
        text = substr(text, at + length(needle))
      }
      return hits
    }
    index($0, "emit-cost-summary --events") {
      hits += count_literal($0, flag)
    }
    END { print hits + 0 }
  ' "$tmp")
  if [ "$generated_flag_hits" != "1" ]; then
    rm -f "$tmp"
    printf 'FAIL replacement for %s has %s generated invocation flags, expected 1\n' \
      "$rel" "$generated_flag_hits" >&2
    exit 2
  fi
  generated_resolution_hits=$(awk -v resolution="$MATRIX_RESOLUTION" '
    $0 == resolution { hits++ } END { print hits + 0 }
  ' "$tmp")
  if [ "$generated_resolution_hits" != "1" ]; then
    rm -f "$tmp"
    printf 'FAIL replacement for %s has %s matrix resolutions, expected 1\n' \
      "$rel" "$generated_resolution_hits" >&2
    exit 2
  fi
  source_lines=$(wc -l < "$f" | tr -d ' ')
  expected_lines=$((source_lines + 1 - resolution_line_hits))
  if [ "$(wc -l < "$tmp" | tr -d ' ')" != "$expected_lines" ]; then
    rm -f "$tmp"
    printf 'FAIL replacement for %s changed the line count\n' "$rel" >&2
    exit 2
  fi

  # `chmod --reference` is GNU-only; macOS has no such flag, so the previous
  # fallback silently reset every consumer to 644 on the platform this repo is
  # developed on. Read the mode portably and fail closed rather than guessing.
  mode=$(stat -f '%Lp' "$f" 2>/dev/null || stat -c '%a' "$f" 2>/dev/null)
  case "$mode" in
    [0-7][0-7][0-7]|[0-7][0-7][0-7][0-7]) ;;
    *) rm -f "$tmp"
       printf 'FAIL could not read the mode of %s\n' "$rel" >&2
       exit 2 ;;
  esac
  if ! chmod "$mode" "$tmp"; then
    rm -f "$tmp"
    printf 'FAIL could not apply mode %s to the replacement for %s\n' "$mode" "$rel" >&2
    exit 2
  fi
  backup=$(mktemp "$target_dir/.sync-rcs-backup.XXXXXX") || exit 2
  owned_paths+=("$backup")
  if ! cp -p "$f" "$backup"; then
    rm -f "$tmp"
    rm -f "$backup"
    printf 'FAIL could not preserve the original %s\n' "$rel" >&2
    exit 2
  fi
  prepared_rels+=("$rel")
  prepared_targets+=("$f")
  prepared_temps+=("$tmp")
  prepared_backups+=("$backup")
done

if [ "$unusable" -ne 0 ]; then
  printf '\nFAIL %s consumer(s) unusable\n' "$unusable" >&2
  exit 1
fi

if [ "$CHECK_ONLY" -eq 1 ]; then
  if [ "$drift" -ne 0 ]; then
    printf '\nFAIL %s consumer(s) drifted from the canonical contract\n' "$drift" >&2
    printf 'FIX  tools/sync-run-cost-summary-contract.sh\n' >&2
    exit 1
  fi
  printf 'ok    %s consumers match the canonical run-cost-summary contract\n' \
    "$expected_consumers"
  exit 0
fi

commit_index=0
while [ "$commit_index" -lt "${#prepared_temps[@]}" ]; do
  rollback_count=$((synced + 1))
  if mv -f "${prepared_temps[$commit_index]}" \
       "${prepared_targets[$commit_index]}"; then
    synced=$((synced + 1))
    rollback_count="$synced"
    commit_index=$((commit_index + 1))
    continue
  fi

  failed_rel="${prepared_rels[$commit_index]}"
  rollback_count="$synced"
  rollback_committed
  rollback_failed=$?
  printf 'FAIL could not replace %s; rolled back %s earlier replacement(s)\n' \
    "$failed_rel" "$synced" >&2
  if [ "$rollback_failed" -ne 0 ]; then
    printf 'FAIL rollback was incomplete; restore the named consumers before continuing\n' >&2
  fi
  exit 2
done

if [ "$synced" -ne 0 ]; then
  for rel in "${prepared_rels[@]}"; do
    printf 'SYNC  %s\n' "$rel"
  done
fi
trap '' INT TERM HUP
if ! cleanup_invocation_paths; then
  printf 'FAIL could not remove synchronization staging files or lock\n' >&2
  exit 2
fi
trap - EXIT

printf '\nok    %s consumer(s) rewritten, %s already current\n' \
  "$synced" "$((expected_consumers - synced))"
exit 0
