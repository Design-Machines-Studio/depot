#!/usr/bin/env bash
# openrouter-exec.sh -- bounded configured-key OpenRouter Pipeline adapter.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="run"
MODEL="${OPENROUTER_EXEC_MODEL:-deepseek/deepseek-v4-flash-0731}"
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

resolve_openrouter_bundle() {
  local active_host=""
  [ -n "${WORKFLOW_KERNEL:-}" ] && [ -x "$WORKFLOW_KERNEL" ] || return 1
  [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && active_host="claude"
  [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && active_host="codex"
  if [ -n "$active_host" ]; then
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 --active-host "$active_host" \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  else
    "$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
      --minimum-version 1.14.0 \
      --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
      --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
      --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
      --required-executable skills/openrouter-delegate/references/delegation-boundary.sh
  fi
}

RESOLVED_BUNDLE_JSON="$(resolve_openrouter_bundle)" || {
  echo "openrouter-exec: coherent OpenRouter bundle unavailable; return to Codex" >&2
  exit 77
}
RESOLVED_BUNDLE_REF="$(printf '%s' "$RESOLVED_BUNDLE_JSON" | jq -r '.selected_root // empty')"
RESOLVED_BUNDLE_VERSION="$(printf '%s' "$RESOLVED_BUNDLE_JSON" | jq -r '.version // empty')"
RESOLVED_BUNDLE_CACHE_CLASS="$(printf '%s' "$RESOLVED_BUNDLE_JSON" | jq -r '.cache_class // empty')"
RESOLVED_BUNDLE_REASON="$(printf '%s' "$RESOLVED_BUNDLE_JSON" | jq -r '.reason // empty')"
if [ -n "${OPENROUTER_BUNDLE_REF:-}" ] &&
   { [ "$RESOLVED_BUNDLE_REF" != "$OPENROUTER_BUNDLE_REF" ] ||
     [ "$RESOLVED_BUNDLE_VERSION" != "${OPENROUTER_BUNDLE_VERSION:-}" ] ||
     [ "$RESOLVED_BUNDLE_CACHE_CLASS" != "${OPENROUTER_BUNDLE_CACHE_CLASS:-}" ] ||
     [ "$RESOLVED_BUNDLE_REASON" != "${OPENROUTER_BUNDLE_REASON:-}" ]; }; then
  echo "openrouter-exec: OpenRouter bundle binding changed before transport; return to Codex" >&2
  exit 77
fi
case "$RESOLVED_BUNDLE_REF" in
  "~/"*) OPENROUTER_ROOT="$HOME/${RESOLVED_BUNDLE_REF#\~/}" ;;
  *) echo "openrouter-exec: invalid OpenRouter bundle binding; return to Codex" >&2; exit 77 ;;
esac
WRAPPER="$OPENROUTER_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh"
POLICY="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY="$OPENROUTER_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh"

TASK_TMP_ROOT="${TMPDIR:-/tmp}"
SYSTEM="You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences."
PROMPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.prompt.XXXXXX")"
SYSTEM_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.system.XXXXXX")"
ALLOWED_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.allowed.XXXXXX")"
PATCH_PATHS_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.paths.XXXXXX")"
CACHED_PATHS_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.cached.XXXXXX")"
RECEIPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.receipt.XXXXXX")"
PATCH_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.patch.XXXXXX")"
MSG_FILE=""
MUTATION_ACTIVE=0
cleanup() {
  local original_rc=$?
  if [ "$MUTATION_ACTIVE" = "1" ]; then
    git apply -R --index "$PATCH_FILE" >/dev/null 2>&1 || {
      echo "openrouter-exec: failed to roll back rejected patch transaction" >&2
      original_rc=2
    }
  fi
  rm -f "$PROMPT_FILE" "$SYSTEM_FILE" "$ALLOWED_FILE" "$PATCH_PATHS_FILE" \
    "$CACHED_PATHS_FILE" "$RECEIPT_FILE" "$PATCH_FILE" "$MSG_FILE"
  exit "$original_rc"
}
trap cleanup EXIT

cat > "$PROMPT_FILE"
printf '%s' "$SYSTEM" > "$SYSTEM_FILE"
[ -s "$PROMPT_FILE" ] || { echo "openrouter-exec: empty prompt" >&2; exit 2; }
printf '%s\n' "$OPENROUTER_EXEC_ALLOWED_PATHS" > "$ALLOWED_FILE"

# This adapter owns the complete index transaction. Refuse an existing staged
# set before any provider contact so unrelated caller state cannot enter the
# generated commit.
if ! git diff --cached --quiet; then
  echo "openrouter-exec: staged changes already exist; return to Codex" >&2
  exit 77
fi

# Scan the private outbound files immediately before the wrapper reads those
# same files. This requires no human interaction.
if ! "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" \
    --content-file "$SYSTEM_FILE" \
    --content-file "$PROMPT_FILE" >/dev/null; then
  echo "openrouter-exec: host_disclosure_declined; return to Codex" >&2
  exit 77
fi

set +e
env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$SYSTEM_FILE" \
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

# Apply and stage as one index-bound transaction. Unlike a later `git add`,
# `--index` refuses an approved file whose worktree already differs from the
# index, so a disjoint caller edit in that file cannot hitchhike into the
# model-authored commit.
git apply --check --index "$PATCH_FILE"
git apply --index "$PATCH_FILE"
MUTATION_ACTIVE=1
if git diff --cached --quiet; then
  echo "openrouter-exec: patch produced no staged changes" >&2
  exit 1
fi

# Confirm the staged set is exactly the boundary-approved patch set. The
# nested NUL readers preserve every legal Git pathname except NUL itself.
git diff --cached --name-only -z > "$CACHED_PATHS_FILE"
path_in_nul_file() {
  local wanted="$1" file="$2" candidate
  while IFS= read -r -d '' candidate; do
    [ "$candidate" = "$wanted" ] && return 0
  done < "$file"
  return 1
}
while IFS= read -r -d '' staged_path; do
  path_in_nul_file "$staged_path" "$PATCH_PATHS_FILE" || {
    echo "openrouter-exec: staged path escaped approved patch set; return to Codex" >&2
    exit 77
  }
done < "$CACHED_PATHS_FILE"
while IFS= read -r -d '' approved_path; do
  path_in_nul_file "$approved_path" "$CACHED_PATHS_FILE" || {
    echo "openrouter-exec: approved patch path was not staged; return to Codex" >&2
    exit 77
  }
done < "$PATCH_PATHS_FILE"
git diff --check --cached

if [ -n "$DEFERRED_VERIFY_CMD" ]; then
  VERIFY_RESULT="deferred_to_native_reviewer: requested command not executed"
else
  VERIFY_RESULT="deferred_to_native_reviewer: no command supplied"
fi
MSG_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.msg.XXXXXX")"
printf '%s\n\nImplementedBy: openrouter\nStructuralValidation: git diff --check --cached\nVerification: %s\n' \
  "$COMMIT_MSG" "$VERIFY_RESULT" > "$MSG_FILE"
PARENT_COMMIT="$(git rev-parse HEAD)"
COMMIT_TREE="$(git write-tree)"
NEW_COMMIT="$(git commit-tree "$COMMIT_TREE" -p "$PARENT_COMMIT" -F "$MSG_FILE")"
git update-ref HEAD "$NEW_COMMIT" "$PARENT_COMMIT"
MUTATION_ACTIVE=0

FILES_CHANGED="$(git diff --name-only HEAD~1..HEAD | tr '\n' ',' | sed 's/,$//')"
jq -n --arg commit "$(git rev-parse --short HEAD)" --arg files "$FILES_CHANGED" \
  --arg verification "$VERIFY_RESULT" --arg requested_model "$MODEL" \
  --arg actual_model "$(jq -r '.responseModel' "$RECEIPT_FILE")" \
  --arg provider "$(jq -r '.servingProvider // ""' "$RECEIPT_FILE")" \
  --arg provider_provenance "$(jq -r '.servingProviderProvenance' "$RECEIPT_FILE")" \
  --arg generation_id "$(jq -r '.generationId' "$RECEIPT_FILE")" \
  --arg bundle_version "$RESOLVED_BUNDLE_VERSION" \
  --arg bundle_cache_class "$RESOLVED_BUNDLE_CACHE_CLASS" \
  --arg bundle_reason "$RESOLVED_BUNDLE_REASON" \
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
   openrouterBundle:{version:$bundle_version,cacheClass:$bundle_cache_class,reason:$bundle_reason},
   nativeVendorOriginInvariant:"passed",usage:$usage}'
