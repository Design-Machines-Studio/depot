#!/usr/bin/env bash
# openrouter-exec.sh -- agentic OpenRouter runner for bounded pipeline chunks.
#
# The runner accepts a chunk prompt on stdin, asks OpenRouter for a unified diff,
# applies it to the current worktree, runs a project verification command, commits
# the result, and emits a receipt shape consumed by the execution-orchestrator:
# implementedBy: openrouter
# It is intended for config/docs/mechanical-logic chunks, not UI/integration.

set -euo pipefail

MODE="run"
MODEL="${OPENROUTER_EXEC_MODEL:-z-ai/glm-5.2}"
TIMEOUT="${OPENROUTER_EXEC_TIMEOUT:-180}"
VERIFY_CMD="${OPENROUTER_EXEC_VERIFY_CMD:-}"
COMMIT_MSG="${OPENROUTER_EXEC_COMMIT_MSG:-pipeline: implement openrouter chunk}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift;;
    --model) MODEL="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --verify-cmd) VERIFY_CMD="$2"; shift 2;;
    --commit-message) COMMIT_MSG="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

if [ "$MODE" = "dry-run" ]; then
  cat <<'JSON'
{
  "implementedBy": "openrouter",
  "status": "dry-run",
  "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
  "verification": "skipped"
}
JSON
  exit 0
fi

PROMPT="$(cat)"
[ -n "$PROMPT" ] || { echo "openrouter-exec: empty prompt" >&2; exit 2; }

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER=""
for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  WRAPPER="$(ls -t "$cache"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1)"
  [ -n "$WRAPPER" ] && break
done
[ -z "$WRAPPER" ] && WRAPPER="$DIR/../../openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
[ -x "$WRAPPER" ] || { echo "openrouter-exec: openrouter-wrapper.sh not found" >&2; exit 1; }

SYSTEM="You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences."
RAW_OUT="$(OPENROUTER_SYSTEM="$SYSTEM" OPENROUTER_ZDR="${OPENROUTER_ZDR:-1}" "$WRAPPER" "$MODEL" "$PROMPT" "$TIMEOUT")"

TMPDIR="${TMPDIR:-/tmp}"
PATCH_FILE="$(mktemp "$TMPDIR/openrouter-exec.XXXXXX.patch")"
RECEIPT_FILE="$(mktemp "$TMPDIR/openrouter-exec.XXXXXX.receipt")"
printf '%s\n' "$RAW_OUT" | sed -n '/^diff --git /,$p' > "$PATCH_FILE"

if [ ! -s "$PATCH_FILE" ]; then
  echo "openrouter-exec: model returned no unified diff" >&2
  exit 1
fi

git apply --check "$PATCH_FILE"
git apply "$PATCH_FILE"

if [ -n "$VERIFY_CMD" ]; then
  bash -lc "$VERIFY_CMD"
  VERIFY_RESULT="passed: $VERIFY_CMD"
else
  VERIFY_RESULT="skipped: no OPENROUTER_EXEC_VERIFY_CMD"
fi

git add -A
if git diff --cached --quiet; then
  echo "openrouter-exec: patch produced no staged changes" >&2
  exit 1
fi

MSG_FILE="$(mktemp "$TMPDIR/openrouter-exec.XXXXXX.msg")"
printf '%s\n\nImplementedBy: openrouter\nVerification: %s\n' "$COMMIT_MSG" "$VERIFY_RESULT" > "$MSG_FILE"
git commit -F "$MSG_FILE" >/dev/null

FILES_CHANGED="$(git diff --name-only HEAD~1..HEAD | tr '\n' ',' | sed 's/,$//')"
cat > "$RECEIPT_FILE" <<JSON
{
  "implementedBy": "openrouter",
  "status": "committed",
  "commit": "$(git rev-parse --short HEAD)",
  "filesChanged": "${FILES_CHANGED}",
  "verification": "${VERIFY_RESULT}",
  "usage": "see OpenRouter API usage object from wrapper output when available"
}
JSON
cat "$RECEIPT_FILE"
