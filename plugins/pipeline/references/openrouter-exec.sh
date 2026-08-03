#!/usr/bin/env bash
# openrouter-exec.sh -- agentic OpenRouter runner for bounded pipeline chunks.
#
# The runner accepts a chunk prompt on stdin, asks OpenRouter for a unified diff,
# applies it to the current worktree, performs fixed structural validation, commits
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
TIMEOUT="${OPENROUTER_EXEC_TIMEOUT:-3600}"
DEFERRED_VERIFY_CMD="${OPENROUTER_EXEC_VERIFY_CMD:-}"
COMMIT_MSG="${OPENROUTER_EXEC_COMMIT_MSG:-pipeline: implement openrouter chunk}"

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) MODE="dry-run"; shift;;
    --model) MODEL="$2"; shift 2;;
    --fallback-model) FALLBACK_MODEL="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --verify-cmd) DEFERRED_VERIFY_CMD="$2"; shift 2;;
    --commit-message) COMMIT_MSG="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done

for candidate in "$MODEL" "$FALLBACK_MODEL"; do
  [ -z "$candidate" ] && continue
  candidate_origin="$(printf '%s' "$candidate" | tr '[:upper:]' '[:lower:]')"
  case "$candidate_origin" in
    anthropic/*)
      echo "openrouter-exec: native-vendor-origin invariant rejected OpenRouter model '$candidate'" >&2
      exit 2
      ;;
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
KERNEL="${WORKFLOW_KERNEL:-$DIR/../../workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh}"
[ -x "$KERNEL" ] || { echo "openrouter-exec: workflow-kernel resolver unavailable" >&2; exit 2; }
ACTIVE_HOST=""
if [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ]; then
  ACTIVE_HOST="claude"
elif [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ]; then
  ACTIVE_HOST="codex"
fi
if [ -n "$ACTIVE_HOST" ]; then
  BUNDLE_JSON="$("$KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.8.0 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
    --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
    --active-host "$ACTIVE_HOST" 2>/dev/null)" || {
      echo "openrouter-exec: coherent OpenRouter bundle unavailable" >&2
      exit 2
    }
else
  BUNDLE_JSON="$("$KERNEL" resolve-plugin-bundle --plugin openrouter \
    --minimum-version 1.8.0 \
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh \
    --required-executable skills/openrouter-delegate/references/payload-authorization.sh \
    2>/dev/null)" || {
      echo "openrouter-exec: coherent OpenRouter bundle unavailable" >&2
      exit 2
    }
fi
BUNDLE_REF="$(printf '%s' "$BUNDLE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("selected_root",""))' 2>/dev/null)"
BUNDLE_VERSION="$(printf '%s' "$BUNDLE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("version",""))' 2>/dev/null)"
BUNDLE_CLASS="$(printf '%s' "$BUNDLE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("cache_class",""))' 2>/dev/null)"
BUNDLE_REASON="$(printf '%s' "$BUNDLE_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("reason",""))' 2>/dev/null)"
case "$BUNDLE_REF" in
  "~/"*) BUNDLE_ROOT="$HOME/${BUNDLE_REF#\~/}" ;;
  *) echo "openrouter-exec: invalid coherent bundle receipt" >&2; exit 2 ;;
esac
WRAPPER="$BUNDLE_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
POLICY="$BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY="$BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
AUTHORIZATION="$BUNDLE_ROOT/skills/openrouter-delegate/references/payload-authorization.sh"
[ -x "$WRAPPER" ] || { echo "openrouter-exec: coherent wrapper unavailable" >&2; exit 2; }
[ -f "$POLICY" ] && [ -x "$BOUNDARY" ] && [ -x "$AUTHORIZATION" ] || {
  echo "openrouter-exec: delegation security boundary unavailable" >&2
  exit 2
}

TASK_TMP_ROOT="${TMPDIR:-/tmp}"
SYSTEM="You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences."
PATCH_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.patch.XXXXXX")"
PROMPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.prompt.XXXXXX")"
SYSTEM_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.system.XXXXXX")"
ALLOWED_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.allowed.XXXXXX")"
PATCH_PATHS_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.paths.XXXXXX")"
MSG_FILE=""
WRAPPER_STDERR="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.stderr.XXXXXX")"
WRAPPER_RECEIPT="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.receipt.XXXXXX")"
AUTHORIZATION_RECEIPT="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.authorization.XXXXXX")"
trap 'rm -f "$PATCH_FILE" "$PROMPT_FILE" "$SYSTEM_FILE" "$ALLOWED_FILE" "$PATCH_PATHS_FILE" "$MSG_FILE" "$WRAPPER_STDERR" "$WRAPPER_RECEIPT" "$AUTHORIZATION_RECEIPT"' EXIT
cat > "$PROMPT_FILE"
printf '%s' "$SYSTEM" > "$SYSTEM_FILE"
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

if ! "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
    --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE"; then
  echo "openrouter-exec: exact outbound payload failed disclosure boundary" >&2
  exit 77
fi
PAYLOAD_SHA256="$("$AUTHORIZATION" snapshot --output "$AUTHORIZATION_RECEIPT" \
  --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE")"
AUTHORIZATION_MODE="${OPENROUTER_PAYLOAD_AUTHORIZATION:-trusted-boundary}"
case "$AUTHORIZATION_MODE" in
  exact-digest)
    [ -n "${OPENROUTER_PAYLOAD_APPROVAL_SHA256:-}" ] || {
      printf '{"status":"approval_required","payloadSha256":"%s","authority":"user"}\n' "$PAYLOAD_SHA256"
      exit 78
    }
    if ! "$AUTHORIZATION" verify --manifest "$AUTHORIZATION_RECEIPT" \
      --approved-sha256 "$OPENROUTER_PAYLOAD_APPROVAL_SHA256" \
      --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE" 2>/dev/null; then
      printf '{"status":"approval_required","payloadSha256":"%s","authority":"user","reason":"payload-or-approval-changed"}\n' "$PAYLOAD_SHA256"
      exit 78
    fi
    ;;
  trusted-boundary)
    if ! "$AUTHORIZATION" verify-trusted-boundary \
      --manifest "$AUTHORIZATION_RECEIPT" --policy "$POLICY" \
      --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE" >/dev/null; then
      echo "openrouter-exec: trusted boundary authorization failed" >&2
      exit 77
    fi
    ;;
  *)
    echo "openrouter-exec: invalid OPENROUTER_PAYLOAD_AUTHORIZATION" >&2
    exit 2
    ;;
esac

if RAW_OUT="$(OPENROUTER_SYSTEM="$(cat "$SYSTEM_FILE")" OPENROUTER_ZDR="${OPENROUTER_ZDR:-0}" \
    OPENROUTER_AUTHORIZATION_MODE="$AUTHORIZATION_MODE" \
    OPENROUTER_WORKLOAD=mechanical \
    OPENROUTER_RECEIPT_FILE="$WRAPPER_RECEIPT" \
    "$WRAPPER" "$MODEL" - "$TIMEOUT" "$FALLBACK_MODEL" < "$PROMPT_FILE" 2>"$WRAPPER_STDERR")"; then
  :
else
  rc=$?
  echo "openrouter-exec: provider failure (wrapper exit $rc)" >&2
  exit 1
fi
[ -s "$WRAPPER_RECEIPT" ] || {
  echo "openrouter-exec: provider receipt missing" >&2
  exit 1
}
ACTUAL_MODEL="$(jq -er '.responseModel' "$WRAPPER_RECEIPT")"
FALLBACK_USED="$(jq -r '.fallbackUsed' "$WRAPPER_RECEIPT")"

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

# Stage only the literal paths the model patch touched, not the whole tree. NUL
# framing preserves filename bytes; --literal-pathspecs separately prevents a
# filename such as :(glob)* from expanding to unrelated worktree changes.
git --literal-pathspecs add --pathspec-from-file="$PATCH_PATHS_FILE" --pathspec-file-nul
if git diff --cached --quiet; then
  echo "openrouter-exec: patch produced no staged changes" >&2
  exit 1
fi
git diff --check --cached

if [ -n "$DEFERRED_VERIFY_CMD" ]; then
  VERIFY_RESULT="deferred_to_native_reviewer: requested command not executed"
else
  VERIFY_RESULT="deferred_to_native_reviewer: no command supplied"
fi

MSG_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.msg.XXXXXX")"
printf '%s\n\nImplementedBy: openrouter\nStructuralValidation: git diff --check --cached\nVerification: %s\n' \
  "$COMMIT_MSG" "$VERIFY_RESULT" > "$MSG_FILE"
git commit -F "$MSG_FILE" >/dev/null

FILES_CHANGED="$(git diff --name-only HEAD~1..HEAD | tr '\n' ',' | sed 's/,$//')"
python3 - "$(git rev-parse --short HEAD)" "$FILES_CHANGED" "$VERIFY_RESULT" \
  "$MODEL" "$ACTUAL_MODEL" "$FALLBACK_USED" "$BUNDLE_VERSION" \
  "$BUNDLE_CLASS" "$BUNDLE_REASON" "$WRAPPER_RECEIPT" <<'PY'
import json
import sys

provider_receipt = {}
try:
    with open(sys.argv[10], encoding="utf-8") as handle:
        provider_receipt = json.load(handle)
except (OSError, json.JSONDecodeError):
    pass

print(json.dumps({
    "requestedProvider": "openrouter",
    "attemptedProvider": "openrouter",
    "attemptedModels": provider_receipt.get("attemptedModels", []),
    "actualImplementer": "openrouter",
    "implementedBy": "openrouter",
    "status": "committed",
    "commit": sys.argv[1],
    "filesChanged": sys.argv[2],
    "verification": sys.argv[3],
    "requestedModel": sys.argv[4],
    "actualModel": sys.argv[5],
    "responseModelProvenance": provider_receipt.get("responseModelProvenance"),
    "fallback": sys.argv[6] == "true",
    "fallbackReason": "primary-capacity" if sys.argv[6] == "true" else "none",
    "generationId": provider_receipt.get("generationId"),
    "servingProvider": provider_receipt.get("servingProvider"),
    "servingProviderProvenance": provider_receipt.get("servingProviderProvenance"),
    "nativeVendorOriginInvariant": "passed",
    "bundleResolution": {
        "version": sys.argv[7],
        "cacheClass": sys.argv[8],
        "reason": sys.argv[9],
    },
    "usage": provider_receipt.get("usage"),
}, indent=2))
PY
