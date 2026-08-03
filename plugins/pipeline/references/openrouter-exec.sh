#!/usr/bin/env bash
# openrouter-exec.sh -- bounded Pipeline adapter for workflow-authority dispatch.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="run"
MODEL="${OPENROUTER_EXEC_MODEL:-moonshotai/kimi-k3}"
FALLBACK_MODEL="${OPENROUTER_EXEC_FALLBACK_MODEL:-}"
TIMEOUT="${OPENROUTER_EXEC_TIMEOUT:-3600}"
DEFERRED_VERIFY_CMD="${OPENROUTER_EXEC_VERIFY_CMD:-}"
COMMIT_MSG="${OPENROUTER_EXEC_COMMIT_MSG:-pipeline: implement openrouter chunk}"
WORKFLOW_AUTHORITY_CLIENT="/usr/local/bin/workflow-authority"
ASSESSMENT_LANE="pipeline-assessment-artifact-delegation-v1"

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
  case "$(printf '%s' "$candidate" | tr '[:upper:]' '[:lower:]')" in
    openai/*|anthropic/*)
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
[ "${DM_PROVIDER_LANE:-}" = "$ASSESSMENT_LANE" ] || {
  echo "openrouter-exec: host_authority_unavailable" >&2
  exit 70
}
[ -n "${DM_PROVIDER_REPOSITORY:-}" ] && [ -n "${DM_PROVIDER_RUN_ID:-}" ] &&
  [ -n "${DM_PROVIDER_CANDIDATE:-}" ] && [ -n "${DM_PROVIDER_NONCE:-}" ] || {
  echo "openrouter-exec: host_authority_unavailable" >&2
  exit 70
}

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$DIR/../../openrouter/skills/openrouter-delegate/references/delegation-security-policy.json"
BOUNDARY="$DIR/../../openrouter/skills/openrouter-delegate/references/delegation-boundary.sh"
[ -r "$POLICY" ] && [ -x "$BOUNDARY" ] || {
  echo "openrouter-exec: output boundary unavailable" >&2
  exit 2
}

authority_client() {
  [ -x "$WORKFLOW_AUTHORITY_CLIENT" ] || return 1
  printf '%s' "$WORKFLOW_AUTHORITY_CLIENT"
}

authority_env() {
  env -i PATH="$PATH" LC_ALL=C "$@"
}

request_body_digest() {
  local model="$1" fallback="$2" system_file="$3" prompt_file="$4"
  /usr/bin/python3 - "$model" "$fallback" 4<"$system_file" 5<"$prompt_file" <<'PY'
import hashlib, json, os, sys
models = [sys.argv[1]] + ([sys.argv[2]] if sys.argv[2] else [])
body = {"messages": [{"content": os.read(4, 8388609).decode("utf-8"), "role": "system"},
                     {"content": os.read(5, 8388609).decode("utf-8"), "role": "user"}],
        "models": models, "temperature": None}
raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
print("sha256:" + hashlib.sha256(raw).hexdigest())
PY
}

response_metrics() {
  /usr/bin/python3 -c 'import hashlib,sys; b=sys.stdin.buffer.read(); print(len(b)); print("sha256:"+hashlib.sha256(b).hexdigest())'
}

CLIENT="$(authority_client)" || {
  echo "openrouter-exec: host_authority_unavailable" >&2
  exit 70
}
STATUS="$(authority_env "$CLIENT" provider-transport-status 2>/dev/null)" || {
  echo "openrouter-exec: host_authority_unavailable" >&2
  exit 70
}
printf '%s' "$STATUS" | jq -e '.production_ready == true and .m1_acceptance == true' >/dev/null || {
  echo "openrouter-exec: host_authority_unavailable" >&2; exit 70;
}

TASK_TMP_ROOT="${TMPDIR:-/tmp}"
SYSTEM="You are an agentic coding runner. Return only a unified diff that applies cleanly to the current git worktree. No prose. No markdown fences."
PROMPT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.prompt.XXXXXX")"
SYSTEM_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.system.XXXXXX")"
ALLOWED_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.allowed.XXXXXX")"
PATCH_PATHS_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.paths.XXXXXX")"
RESULT_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.result.XXXXXX")"
PATCH_FILE="$(mktemp "$TASK_TMP_ROOT/openrouter-exec.patch.XXXXXX")"
MSG_FILE=""
trap 'rm -f "$PROMPT_FILE" "$SYSTEM_FILE" "$ALLOWED_FILE" "$PATCH_PATHS_FILE" "$RESULT_FILE" "$PATCH_FILE" "$MSG_FILE"' EXIT
cat > "$PROMPT_FILE"
printf '%s' "$SYSTEM" > "$SYSTEM_FILE"
[ -s "$PROMPT_FILE" ] || { echo "openrouter-exec: empty prompt" >&2; exit 2; }
printf '%s\n' "$OPENROUTER_EXEC_ALLOWED_PATHS" > "$ALLOWED_FILE"

marker="$(printf '\001')"
set +e
RAW_OUT="$(
  authority_env "$CLIENT" dispatch-provider-request \
    --repository "$DM_PROVIDER_REPOSITORY" --run-id "$DM_PROVIDER_RUN_ID" \
    --lane "$DM_PROVIDER_LANE" --candidate "$DM_PROVIDER_CANDIDATE" \
    --workload "${DM_PROVIDER_WORKLOAD:-pipeline-assessment}" --nonce "$DM_PROVIDER_NONCE" \
    --model "$MODEL" --fallback-model "$FALLBACK_MODEL" \
    --system-fd 4 --user-fd 5 --response-fd 3 \
    4<"$SYSTEM_FILE" 5<"$PROMPT_FILE" 3>&1 >"$RESULT_FILE"
  rc=$?
  [ "$rc" -eq 0 ] && printf '\001'
  exit "$rc"
)"
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  case "$rc" in
    71) echo "openrouter-exec: host authorization declined" >&2; exit 77;;
    72) echo "openrouter-exec: host_disclosure_declined" >&2; exit 77;;
    70) echo "openrouter-exec: host_authority_unavailable" >&2; exit 70;;
    73) echo "openrouter-exec: provider failure" >&2; exit 1;;
    74) echo "openrouter-exec: provider outcome unknown" >&2; exit 1;;
    *) echo "openrouter-exec: broker result verification failed" >&2; exit 2;;
  esac
fi
RAW_OUT="${RAW_OUT%$marker}"
METRICS="$(printf '%s' "$RAW_OUT" | response_metrics)" || {
  echo "openrouter-exec: response digest failed" >&2; exit 2;
}
RESPONSE_LENGTH="$(printf '%s\n' "$METRICS" | sed -n '1p')"
RESPONSE_DIGEST="$(printf '%s\n' "$METRICS" | sed -n '2p')"
BODY_DIGEST="$(request_body_digest "$MODEL" "$FALLBACK_MODEL" "$SYSTEM_FILE" "$PROMPT_FILE")" || {
  echo "openrouter-exec: request body digest failed" >&2; exit 2;
}
MODELS_JSON="$(jq -nc --arg model "$MODEL" --arg fallback "$FALLBACK_MODEL" \
  'if $fallback == "" then [$model] else [$model,$fallback] end')"
jq -e --arg repository "$DM_PROVIDER_REPOSITORY" --arg run_id "$DM_PROVIDER_RUN_ID" \
  --arg lane "$DM_PROVIDER_LANE" --arg candidate "$DM_PROVIDER_CANDIDATE" \
  --arg workload "${DM_PROVIDER_WORKLOAD:-pipeline-assessment}" --arg nonce "$DM_PROVIDER_NONCE" \
  --arg body_digest "$BODY_DIGEST" --arg response_digest "$RESPONSE_DIGEST" \
  --argjson models "$MODELS_JSON" --argjson response_length "$RESPONSE_LENGTH" '
    .schema_version == 1 and .protocol == "workflow-authority-provider-dispatch-v1" and
    .operation_family == "external_provider_dispatch" and .substrate_authority == "not_asserted" and
    .outcome == "verified" and .exit_code == 0 and
    .scope.repository == $repository and .scope.run_id == $run_id and .scope.lane == $lane and
    .scope.candidate == $candidate and .scope.workload == $workload and
    .models == $models and (.selected_model as $selected | (.models | index($selected)) != null) and
    .provider == "openrouter" and .part_count == 2 and
    .request_body_sha256 == $body_digest and
    .response_sha256 == $response_digest and .response_length == $response_length and
    (.challenge_sha256 | test("^sha256:[0-9a-f]{64}$")) and
    (.authority_assertion_sha256 | test("^sha256:[0-9a-f]{64}$")) and
    (.result_signer_sha256 | test("^sha256:[0-9a-f]{64}$")) and
    (.prior_chain_digest | test("^sha256:[0-9a-f]{64}$")) and
    (.sequence | type == "number" and . >= 1) and
    .cleanup == {reservation:"consumed",connection:"closed",content_buffer:"discarded"} and
    .signature.kind == "es256" and
    (.signature.signature_der | test("^[A-Za-z0-9_-]{1,4096}$")) and
    ([keys[] | select(test("prompt|content|credential|api_key|secret"; "i"))] | length) == 0
  ' "$RESULT_FILE" >/dev/null || {
  echo "openrouter-exec: broker result scope mismatch" >&2
  exit 2
}

# The response is held in memory until its signed terminal is accepted. It is
# materialized only for the existing local diff parser/apply boundary and is
# removed by the EXIT trap; there is no broker retrieval or caller output path.
printf '%s' "$RAW_OUT" > "$PATCH_FILE"
[ -s "$PATCH_FILE" ] || { echo "openrouter-exec: model returned no unified diff" >&2; exit 1; }
if "$BOUNDARY" --policy "$POLICY" --changed-files "$ALLOWED_FILE" \
    --diff-file "$PATCH_FILE" --output-paths "$PATCH_PATHS_FILE"; then
  :
else
  rc=$?
  [ "$rc" -eq 3 ] && { echo "openrouter-exec: model patch exceeded chunk/security boundary; return to Codex" >&2; exit 77; }
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
  --arg actual_model "$(jq -r '.selected_model' "$RESULT_FILE")" \
  --arg provider "$(jq -r '.provider' "$RESULT_FILE")" \
  --argjson fallback "$([ "$(jq -r '.selected_model' "$RESULT_FILE")" != "$MODEL" ] && echo true || echo false)" '
  {requestedProvider:"openrouter",attemptedProvider:"openrouter",actualImplementer:"openrouter",
   implementedBy:"openrouter",status:"committed",commit:$commit,filesChanged:$files,
   verification:$verification,requestedModel:$requested_model,actualModel:$actual_model,
   servingProvider:$provider,responseModelProvenance:"broker-verified",
   servingProviderProvenance:"broker-verified",fallback:$fallback,
   fallbackReason:(if $fallback then "broker-routed-fallback" else "none" end),
   nativeVendorOriginInvariant:"passed",usage:null}'
