#!/usr/bin/env bash
# openrouter-exec.sh -- agentic OpenRouter runner for bounded pipeline chunks.
#
# The runner accepts a chunk prompt on stdin, asks OpenRouter for a unified diff,
# applies it to the current worktree, runs a project verification command, commits
# the result, and emits a receipt shape consumed by the execution-orchestrator:
# implementedBy: openrouter
# It is intended for config/docs/mechanical-logic chunks, not UI/integration.

set -euo pipefail

# Fixed PATH reset -- prevent caller-controlled hijack of git/sed/mktemp/bash during
# autonomous execution (matches openrouter-wrapper.sh). Depot shell-script convention.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="run"
MODEL="${OPENROUTER_EXEC_MODEL:-z-ai/glm-5.2}"
FALLBACK_MODEL="${OPENROUTER_EXEC_FALLBACK_MODEL:-}"
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

[ -n "${OPENROUTER_EXEC_ALLOWED_PATHS:-}" ] || {
  echo "openrouter-exec: OPENROUTER_EXEC_ALLOWED_PATHS is required" >&2
  exit 2
}

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAPPER="${OPENROUTER_EXEC_WRAPPER_PATH:-}"
if [ -z "$WRAPPER" ]; then
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    WRAPPER="$(ls -t "$cache"/openrouter/*/skills/openrouter-delegate/references/openrouter-wrapper.sh 2>/dev/null | head -1 || true)"
    [ -n "$WRAPPER" ] && break
  done
fi
[ -z "$WRAPPER" ] && WRAPPER="$DIR/../../openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
[ -x "$WRAPPER" ] || { echo "openrouter-exec: openrouter-wrapper.sh not found" >&2; exit 1; }

POLICY="$DIR/../../openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
if [ ! -f "$POLICY" ]; then
  POLICY=""
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    POLICY="$(ls -t "$cache"/openrouter/*/skills/openrouter-delegate/references/delegation-security-policy.json 2>/dev/null | head -1 || true)"
    [ -n "$POLICY" ] && break
  done
fi
BOUNDARY="$(dirname "$POLICY")/delegation-boundary.sh"
[ -f "$POLICY" ] && [ -x "$BOUNDARY" ] || {
  echo "openrouter-exec: delegation security boundary unavailable" >&2
  exit 2
}

TASK_TMP_ROOT="${TMPDIR:-/tmp}"
PATCH_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.XXXXXX.patch")"
PROMPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.XXXXXX.prompt")"
ALLOWED_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.XXXXXX.allowed")"
PATCH_PATHS_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.XXXXXX.paths")"
MSG_FILE=""
WRAPPER_STDERR="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.XXXXXX.stderr")"
trap 'rm -f "$PATCH_FILE" "$PROMPT_FILE" "$ALLOWED_FILE" "$PATCH_PATHS_FILE" "$MSG_FILE" "$WRAPPER_STDERR"' EXIT
cat > "$PROMPT_FILE"
[ -s "$PROMPT_FILE" ] || { echo "openrouter-exec: empty prompt" >&2; exit 2; }
printf '%s\n' "$OPENROUTER_EXEC_ALLOWED_PATHS" > "$ALLOWED_FILE"
if "$BOUNDARY" --policy "$POLICY" --changed-files "$ALLOWED_FILE" --content-file "$PROMPT_FILE"; then
  :
else
  rc=$?
  [ "$rc" -eq 3 ] && {
    echo "openrouter-exec: delegation declined; return chunk to Codex" >&2
    exit 77
  }
  echo "openrouter-exec: delegation boundary validation failed" >&2
  exit 2
fi

SYSTEM="You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences."
if RAW_OUT="$(OPENROUTER_SYSTEM="$SYSTEM" OPENROUTER_ZDR="${OPENROUTER_ZDR:-0}" \
    "$WRAPPER" "$MODEL" - "$TIMEOUT" "$FALLBACK_MODEL" < "$PROMPT_FILE" 2>"$WRAPPER_STDERR")"; then
  :
else
  rc=$?
  echo "openrouter-exec: provider failure (wrapper exit $rc)" >&2
  exit 1
fi
ACTUAL_MODEL="$MODEL"
FALLBACK_USED=false
if [ -n "$FALLBACK_MODEL" ] &&
    grep -Fq "falling back to $FALLBACK_MODEL" "$WRAPPER_STDERR"; then
  ACTUAL_MODEL="$FALLBACK_MODEL"
  FALLBACK_USED=true
fi

printf '%s\n' "$RAW_OUT" > "$PATCH_FILE"

if [ ! -s "$PATCH_FILE" ]; then
  echo "openrouter-exec: model returned no unified diff" >&2
  exit 1
fi

if "$BOUNDARY" --policy "$POLICY" --changed-files "$ALLOWED_FILE" \
    --diff-file "$PATCH_FILE" --output-paths "$PATCH_PATHS_FILE"; then
  :
else
  rc=$?
  [ "$rc" -eq 3 ] && {
    echo "openrouter-exec: model patch exceeded chunk/security boundary; return to Codex" >&2
    exit 77
  }
  echo "openrouter-exec: model patch could not be validated" >&2
  exit 2
fi

git apply --check "$PATCH_FILE"
git apply "$PATCH_FILE"

if [ -n "$VERIFY_CMD" ]; then
  env PATH="$PATH" bash --noprofile --norc -c "$VERIFY_CMD"
  VERIFY_RESULT="passed: $VERIFY_CMD"
else
  VERIFY_RESULT="skipped: no OPENROUTER_EXEC_VERIFY_CMD"
fi

# Stage only the paths the model patch touched, not the whole tree -- an
# incidental/pre-existing worktree change must not be folded into this commit.
git add --pathspec-from-file="$PATCH_PATHS_FILE" --pathspec-file-nul
if git diff --cached --quiet; then
  echo "openrouter-exec: patch produced no staged changes" >&2
  exit 1
fi

MSG_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.XXXXXX.msg")"
printf '%s\n\nImplementedBy: openrouter\nVerification: %s\n' "$COMMIT_MSG" "$VERIFY_RESULT" > "$MSG_FILE"
git commit -F "$MSG_FILE" >/dev/null

FILES_CHANGED="$(git diff --name-only HEAD~1..HEAD | tr '\n' ',' | sed 's/,$//')"
# usage: the single-turn wrapper prints only model text (the diff), no usage envelope,
# so exec-lane token spend is not measurable here. Emit null; the post-mortem treats the
# OpenRouter exec bucket as best-effort/estimated (see run-postmortem-schema.md).
python3 - "$(git rev-parse --short HEAD)" "$FILES_CHANGED" "$VERIFY_RESULT" \
  "$MODEL" "$ACTUAL_MODEL" "$FALLBACK_USED" <<'PY'
import json
import sys

print(json.dumps({
    "implementedBy": "openrouter",
    "status": "committed",
    "commit": sys.argv[1],
    "filesChanged": sys.argv[2],
    "verification": sys.argv[3],
    "requestedModel": sys.argv[4],
    "actualModel": sys.argv[5],
    "fallback": sys.argv[6] == "true",
    "usage": None,
}, indent=2))
PY
