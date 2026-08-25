#!/usr/bin/env bash
# Legacy compatibility adapter. New callers invoke model-router role-dispatch.
set -euo pipefail
class=""; prompt=""; receipt=""; output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --class) class="$2"; shift 2 ;;
    --prompt) prompt="$2"; shift 2 ;;
    --receipt-file) receipt="$2"; shift 2 ;;
    --output-file) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
case "$class" in openrouter) role=builder-fast ;; codex|claude) role=builder-deep ;; *) exit 2 ;; esac
for cache_root in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  dispatcher="$(ls -t "$cache_root"/model-router/*/skills/model-router/references/role-dispatch.sh 2>/dev/null | head -1)"
  if [ -n "$dispatcher" ] && [ -x "$dispatcher" ]; then
    exec "$dispatcher" --role "$role" --capability read-repository --capability write-repository \
      --capability structured-output --effort medium --prompt-file "$prompt" \
      --output-file "$output" --receipt-file "$receipt"
  fi
done
printf '%s\n' 'cascade-dispatch: role router unavailable' >&2
exit 76
