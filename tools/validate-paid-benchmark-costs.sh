#!/usr/bin/env bash
# Fail closed unless every retained paid attempt has provider-billed cost.
set -euo pipefail

if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
  printf 'usage: %s <openrouter-attempt-root>\n' "$0" >&2
  exit 2
fi

attempt_root="$1"
attempts=0
while IFS= read -r -d '' attempt_dir; do
  attempts=$((attempts + 1))
  receipt="$attempt_dir/receipt.json"
  if [ ! -f "$receipt" ] || [ -L "$receipt" ] ||
    ! jq -e '(.usage.cost | type) == "number" and .usage.cost >= 0' \
      "$receipt" >/dev/null 2>&1; then
    printf 'missing provider-billed cost: %s\n' "$attempt_dir" >&2
    exit 1
  fi
done < <(find "$attempt_root" -type d -name 'run-*' -print0)

if [ "$attempts" -eq 0 ]; then
  printf 'no paid benchmark attempts found: %s\n' "$attempt_root" >&2
  exit 1
fi
