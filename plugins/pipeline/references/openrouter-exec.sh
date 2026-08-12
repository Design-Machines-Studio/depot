#!/usr/bin/env bash
# openrouter-exec.sh -- bounded configured-key OpenRouter Pipeline adapter.

set -euo pipefail
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
if [ -z "${OPENROUTER_API_KEY:-}" ] && [ -z "${OPENROUTER_API_KEY_FILE:-}" ]; then
  echo "openrouter-exec: configured OpenRouter key unavailable; return to Codex" >&2
  exit 77
fi

resolve_openrouter_root() {
  local cache root
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    root="$(ls -td "$cache"/openrouter/*/ 2>/dev/null | head -1)"
    [ -n "$root" ] || continue
    [ -x "$root/skills/openrouter-delegate/references/openrouter-wrapper.sh" ] &&
      [ -r "$root/skills/openrouter-delegate/references/delegation-security-policy.json" ] &&
      [ -x "$root/skills/openrouter-delegate/references/delegation-boundary.sh" ] &&
      [ -x "$root/skills/openrouter-delegate/references/payload-authorization.sh" ] || continue
    printf '%s' "${root%/}"
    return 0
  done
  return 1
}

OPENROUTER_ROOT="$(resolve_openrouter_root)" || {
  echo "openrouter-exec: coherent OpenRouter bundle unavailable; return to Codex" >&2
  exit 77
}
WRAPPER="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
POLICY="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"
AUTHORIZATION="$OPENROUTER_ROOT/skills/openrouter-delegate/references/payload-authorization.sh"

TASK_TMP_ROOT="${TMPDIR:-/tmp}"
SYSTEM="You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences."
PROMPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.prompt.XXXXXX")"
SYSTEM_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.system.XXXXXX")"
AUTHORIZATION_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.authorization.XXXXXX")"
ALLOWED_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.allowed.XXXXXX")"
PATCH_PATHS_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.paths.XXXXXX")"
RECEIPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.receipt.XXXXXX")"
PATCH_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.patch.XXXXXX")"
MSG_FILE=""
trap 'rm -f "$PROMPT_FILE" "$SYSTEM_FILE" "$AUTHORIZATION_FILE" "$ALLOWED_FILE" "$PATCH_PATHS_FILE" "$RECEIPT_FILE" "$PATCH_FILE" "$MSG_FILE"' EXIT

cat > "$PROMPT_FILE"
printf '%s' "$SYSTEM" > "$SYSTEM_FILE"
[ -s "$PROMPT_FILE" ] || { echo "openrouter-exec: empty prompt" >&2; exit 2; }
printf '%s\n' "$OPENROUTER_EXEC_ALLOWED_PATHS" > "$ALLOWED_FILE"

# Automatic disclosure boundary plus unchanged-byte proof. This happens before
# the wrapper can open a provider connection and requires no human interaction.
"$AUTHORIZATION" snapshot --output "$AUTHORIZATION_FILE" \
  --content-file "$SYSTEM_FILE" --content-file "$PROMPT_FILE" >/dev/null
if ! "$AUTHORIZATION" verify-trusted-boundary --manifest "$AUTHORIZATION_FILE" \
    --policy "$POLICY" --content-file "$SYSTEM_FILE" \
    --content-file "$PROMPT_FILE" >/dev/null; then
  echo "openrouter-exec: host_disclosure_declined; return to Codex" >&2
  exit 77
fi

set +e
env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$SYSTEM_FILE" \
  OPENROUTER_AUTHORIZATION_MODE=trusted-boundary \
  OPENROUTER_WORKLOAD=mechanical OPENROUTER_RECEIPT_FILE="$RECEIPT_FILE" \
  bash "$WRAPPER" "$MODEL" - "$TIMEOUT" "$FALLBACK_MODEL" \
  < "$PROMPT_FILE" > "$PATCH_FILE"
rc=$?
set -e
case "$rc" in
  0) ;;
  28|1)
    echo "openrouter-exec: provider unavailable or credentials invalid; return to Codex" >&2
    exit 77
    ;;
  2)
    echo "openrouter-exec: wrapper invocation rejected" >&2
    exit 2
    ;;
  *)
    echo "openrouter-exec: wrapper failed with status $rc" >&2
    exit 77
    ;;
esac

jq -e '
  .schemaVersion == 2 and .outcome == "success" and
  .requestedModel != null and .responseModel != null and
  (.authorization.mode == "trusted-boundary") and
  (.authorization.requestEnvelopeSha256 | test("^[0-9a-f]{64}$")) and
  (.generationId | type == "string" and length > 0) and
  (.usage == null or (.usage | type == "object")) and
  ([(.. | objects) | keys[] |
    select(test("^(prompt|response|content|api_?key|secret)$"; "i"))] | length) == 0
' "$RECEIPT_FILE" >/dev/null || {
  echo "openrouter-exec: wrapper receipt invalid" >&2
  exit 2
}

[ -s "$PATCH_FILE" ] || { echo "openrouter-exec: model returned no unified diff" >&2; exit 1; }
if "$BOUNDARY" --policy "$POLICY" --changed-files "$ALLOWED_FILE" \
    --diff-file "$PATCH_FILE" --output-paths "$PATCH_PATHS_FILE"; then
  :
else
  rc=$?
  if [ "$rc" -eq 2 ] || [ "$rc" -eq 3 ]; then
    echo "openrouter-exec: model patch exceeded chunk/security boundary; return to Codex" >&2
    exit 77
  fi
  echo "openrouter-exec: model patch could not be validated" >&2
  exit 2
fi

git apply --check "$PATCH_FILE"
git apply "$PATCH_FILE"
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
jq -n --arg commit "$(git rev-parse --short HEAD)" --arg files "$FILES_CHANGED" \
  --arg verification "$VERIFY_RESULT" --arg requested_model "$MODEL" \
  --arg actual_model "$(jq -r '.responseModel' "$RECEIPT_FILE")" \
  --arg provider "$(jq -r '.servingProvider // ""' "$RECEIPT_FILE")" \
  --arg provider_provenance "$(jq -r '.servingProviderProvenance' "$RECEIPT_FILE")" \
  --arg generation_id "$(jq -r '.generationId' "$RECEIPT_FILE")" \
  --arg request_digest "$(jq -r '.authorization.requestEnvelopeSha256' "$RECEIPT_FILE")" \
  --argjson usage "$(jq '.usage' "$RECEIPT_FILE")" \
  --argjson fallback "$(jq '.fallbackUsed' "$RECEIPT_FILE")" '
  {requestedProvider:"openrouter",attemptedProvider:"openrouter",actualImplementer:"openrouter",
   implementedBy:"openrouter",status:"committed",commit:$commit,filesChanged:$files,
   verification:$verification,requestedModel:$requested_model,actualModel:$actual_model,
   servingProvider:(if $provider == "" then null else $provider end),generationId:$generation_id,
   requestEnvelopeSha256:$request_digest,responseModelProvenance:"response",
   servingProviderProvenance:$provider_provenance,fallback:$fallback,
   fallbackReason:(if $fallback then "openrouter-native-fallback" else "none" end),
   nativeVendorOriginInvariant:"passed",usage:$usage}'
