#!/usr/bin/env bash
# cascade-dispatch.sh -- World B usage-aware model-cascade decision engine.
# Harness-neutral (Claude Code / Codex / opencode / Pi). Generalizes the merged
# execution-orchestrator fallback into a Codex/OpenRouter coding ladder.
# usage-gauged ladder. Reads model-cascade.json (executor-intent classes ->
# role ladders) + routing-policy.json + harness-profile.json (role->rail per host) + usage-probe.sh
# (live headroom). Picks the best rung above the class quality_floor; on a cap
# error fires the Airlift Tier-1 checkpoint and descends.
#
# Usage:
#   cascade-dispatch.sh --class <codex|openrouter> --prompt <text|-> \
#       [--kind <ui|logic|integration|config>] [--phase <p>] [--host H] \
#       [--timeout N] [--dry-run] [--probe-file <json>] \
#       [--exhausted-rail <codex|openrouter>]
#   (--kind is an alternative to --class; mapped via cascade.class_from_kind)
#
# Exit codes:
#   0   a wrapper/codex_companion/openrouter_exec rung executed -- output on stdout
#   64  chosen rung is NATIVE -- directive JSON on stdout; the HOST orchestrator
#       runs that model in-process (Claude subagent / Codex). The only host-specific action.
#   75  provider terminal -- signed failure/unknown receipt or unverifiable post-dial outcome
#   76  ladder exhausted -- no rung had headroom above the floor
#   77  disclosure declined -- use the trusted native fallback
#   78  exact payload user approval required -- surface digest and retry unchanged
#   2   bad args
#
# Deps: bash, jq. Optional: airlift engine (guarded; no-op if absent), node + Codex plugin.
set -uo pipefail

# Fixed PATH reset -- prevent caller-controlled hijack of jq/node/ls/awk/grep/bash while
# this dispatcher shells out during autonomous execution. Depot shell-script convention.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CASCADE="${CASCADE_FILE:-$DIR/model-cascade.json}"
PROFILE="${PROFILE_FILE:-$DIR/harness-profile.json}"
PROBE="${PROBE_CMD:-$DIR/usage-probe.sh}"
# Automated provider dispatch has one installed client and one fixture-only seam.
WORKFLOW_AUTHORITY_CLIENT="/usr/local/bin/workflow-authority"
ASSESSMENT_LANE="pipeline-assessment-artifact-delegation-v1"

CLASS=""; KIND=""; PROMPT=""; PHASE="execute"; HOST=""; TIMEOUT="3600"; DRYRUN=0; PROBE_FILE=""
EXHAUSTED_RAILS="${CASCADE_EXHAUSTED_RAILS:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --class) CLASS="$2"; shift 2;;
    --kind) KIND="$2"; shift 2;;
    --prompt) PROMPT="$2"; shift 2;;
    --phase) PHASE="$2"; shift 2;;
    --host) HOST="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --dry-run) DRYRUN=1; shift;;
    --probe-file) PROBE_FILE="$2"; shift 2;;
    --exhausted-rail) EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 2;;
  esac
done
command -v jq >/dev/null 2>&1 || { echo "cascade-dispatch: jq required" >&2; exit 2; }
[ -z "$CLASS" ] && [ -n "$KIND" ] && CLASS="$(jq -r --arg k "$KIND" '.class_from_kind[$k] // empty' "$CASCADE")"
[ -z "$CLASS" ] || [ -z "$PROMPT" ] && { echo "usage: $0 --class <codex|openrouter>|--kind <k> --prompt <p|-> [opts]" >&2; exit 2; }
[ "$PROMPT" = "-" ] && PROMPT="$(cat)"

# --- host detection ----------------------------------------------------------
if [ -z "$HOST" ]; then
  HOST="$(jq -r '.active_host' "$PROFILE" 2>/dev/null)"
  { [ "$HOST" = "auto" ] || [ -z "$HOST" ]; } && HOST="${CASCADE_HOST:-}"
  if [ -z "$HOST" ]; then
    if   [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ]; then HOST="claude-code"
    elif [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ]; then HOST="codex"
    else HOST="generic"; fi
  fi
fi

# --- Airlift Tier-1 checkpoint (guarded resolve; no model budget; no-op if absent)
checkpoint() {
  local engine=""
  for cache in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
    engine="$(ls -t "$cache"/airlift/*/skills/airlift/references/airlift-engine.sh 2>/dev/null | head -1)"
    [ -n "$engine" ] && break
  done
  if [ -n "$engine" ] && [ -x "$engine" ]; then bash "$engine" write --phase "$PHASE" >/dev/null 2>&1 || true; fi
}

# --- Codex via codex-companion (matches execution-orchestrator.md 3d) ---------
resolve_codex_root() {
  local root=""
  for cache in "$HOME/.claude/plugins/cache/openai-codex/codex" "$HOME/.codex/plugins/cache/openai-codex/codex"; do
    root="$(ls -td "$cache"/*/ 2>/dev/null | head -1)"
    [ -n "$root" ] && break
  done
  printf '%s' "$root"
}
dispatch_codex() {
  local root; root="$(resolve_codex_root)"
  [ -z "$root" ] && return 127                       # Codex not installed -> unavailable
  node "${root}/scripts/codex-companion.mjs" task --write "$PROMPT" 2>&1
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
text = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
raw = text.replace("\u2028", "\\u2028").replace("\u2029", "\\u2029").encode()
print("sha256:" + hashlib.sha256(raw).hexdigest())
PY
}

response_metrics() {
  /usr/bin/python3 -c 'import hashlib,sys; b=sys.stdin.buffer.read(); print(len(b)); print("sha256:"+hashlib.sha256(b).hexdigest())'
}

validate_provider_result() {
  local receipt="$1" model="$2" fallback="$3" response_length="$4" response_digest="$5" body_digest="$6" models
  models="$(jq -nc --arg model "$model" --arg fallback "$fallback" 'if $fallback == "" then [$model] else [$model,$fallback] end')"
  jq -e --arg repository "${DM_PROVIDER_REPOSITORY:-}" \
    --arg run_id "${DM_PROVIDER_RUN_ID:-}" --arg lane "${DM_PROVIDER_LANE:-}" \
    --arg candidate "${DM_PROVIDER_CANDIDATE:-}" --arg workload "${DM_PROVIDER_WORKLOAD:-pipeline-assessment}" \
    --arg model "$model" --arg body_digest "$body_digest" --arg response_digest "$response_digest" \
    --argjson models "$models" --argjson response_length "$response_length" '
      .schema_version == 1 and .protocol == "workflow-authority-provider-dispatch-v1" and
      .operation_family == "external_provider_dispatch" and .substrate_authority == "not_asserted" and
      .outcome == "verified" and .exit_code == 0 and
      .scope.repository == $repository and .scope.run_id == $run_id and .scope.lane == $lane and
      .scope.candidate == $candidate and .scope.workload == $workload and
      .models == $models and (.selected_model as $selected | (.models | index($selected)) != null) and
      .provider == "openrouter" and .part_count == 2 and
      (.generation_id | test("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")) and
      (.serving_provider | test("^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")) and
      (.usage_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      (.fallback == (.selected_model != .models[0])) and
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
    ' "$receipt" >/dev/null 2>&1
}

validate_provider_failure() {
  local receipt="$1" model="$2" body_digest="$3" outcome="$4" exit_code="$5" models
  models="$(jq -nc --arg model "$model" '[$model]')"
  jq -e --arg repository "${DM_PROVIDER_REPOSITORY:-}" \
    --arg run_id "${DM_PROVIDER_RUN_ID:-}" --arg lane "${DM_PROVIDER_LANE:-}" \
    --arg candidate "${DM_PROVIDER_CANDIDATE:-}" --arg workload "${DM_PROVIDER_WORKLOAD:-pipeline-assessment}" \
    --arg body_digest "$body_digest" --arg outcome "$outcome" --argjson exit_code "$exit_code" \
    --argjson models "$models" '
      .schema_version == 1 and .protocol == "workflow-authority-provider-dispatch-v1" and
      .operation_family == "external_provider_dispatch" and .substrate_authority == "not_asserted" and
      .outcome == $outcome and .exit_code == $exit_code and
      .scope.repository == $repository and .scope.run_id == $run_id and .scope.lane == $lane and
      .scope.candidate == $candidate and .scope.workload == $workload and
      .models == $models and .selected_model == null and
      .provider == "openrouter" and .part_count == 2 and
      .generation_id == null and .serving_provider == null and
      .usage_sha256 == null and .fallback == null and
      .request_body_sha256 == $body_digest and
      .response_sha256 == "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" and
      .response_length == 0 and
      (.challenge_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      (.authority_assertion_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      (.result_signer_sha256 | test("^sha256:[0-9a-f]{64}$")) and
      (.prior_chain_digest | test("^sha256:[0-9a-f]{64}$")) and
      (.sequence | type == "number" and . >= 1 and . <= 9223372036854775807) and
      (.issued_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")) and
      (.completed_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")) and
      .cleanup == {reservation:"consumed",connection:"closed",content_buffer:"discarded"} and
      .signature.kind == "es256" and
      (.signature.signature_der | test("^[A-Za-z0-9_-]{1,4096}$")) and
      ([keys[] | select(test("prompt|content|credential|api_key|secret"; "i"))] | length) == 0
    ' "$receipt" >/dev/null 2>&1
}

dispatch_wrapper() {
  local model="$1" system task_tmp_root system_file prompt_file receipt_file client response marker rc metrics response_length response_digest body_digest outcome
  client="$(authority_client)" || return 1
  system="${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}"
  task_tmp_root="${TMPDIR:-/tmp}"
  system_file="$(mktemp "$task_tmp_root/cascade-wrapper.system.XXXXXX")" || return 1
  prompt_file="$(mktemp "$task_tmp_root/cascade-wrapper.prompt.XXXXXX")" || {
    rm -f "$system_file"; return 1;
  }
  receipt_file="$(mktemp "$task_tmp_root/cascade-wrapper.result.XXXXXX")" || {
    rm -f "$system_file" "$prompt_file"; return 1;
  }
  printf '%s' "$system" > "$system_file"
  printf '%s' "$PROMPT" > "$prompt_file"
  body_digest="$(request_body_digest "$model" "" "$system_file" "$prompt_file")" || {
    rm -f "$system_file" "$prompt_file" "$receipt_file"
    return 2
  }
  marker="$(printf '\001')"
  response="$(
    authority_env "$client" dispatch-provider-request \
      --repository "${DM_PROVIDER_REPOSITORY:-}" --run-id "${DM_PROVIDER_RUN_ID:-}" \
      --lane "${DM_PROVIDER_LANE:-}" --candidate "${DM_PROVIDER_CANDIDATE:-}" \
      --workload "${DM_PROVIDER_WORKLOAD:-pipeline-assessment}" --nonce "${DM_PROVIDER_NONCE:-}" \
      --model "$model" --fallback-model "" --system-fd 4 --user-fd 5 --response-fd 3 \
      4<"$system_file" 5<"$prompt_file" 3>&1 >"$receipt_file"
    rc=$?
    [ "$rc" -eq 0 ] && printf '\001'
    exit "$rc"
  )"; rc=$?
  if [ "$rc" -ne 0 ]; then
    case "$rc" in
      71|72) rm -f "$system_file" "$prompt_file" "$receipt_file"; return 77;;
      70) rm -f "$system_file" "$prompt_file" "$receipt_file"; return 1;;
      73|74)
        outcome="provider_failure"
        [ "$rc" -eq 74 ] && outcome="unknown"
        if [ -z "$response" ] && validate_provider_failure "$receipt_file" "$model" "$body_digest" "$outcome" "$rc"; then
          cat "$receipt_file"
        fi
        rm -f "$system_file" "$prompt_file" "$receipt_file"
        return 75
        ;;
      75) rm -f "$system_file" "$prompt_file" "$receipt_file"; return 75;;
      *) rm -f "$system_file" "$prompt_file" "$receipt_file"; return 2;;
    esac
  fi
  response="${response%"$marker"}"
  metrics="$(printf '%s' "$response" | response_metrics)" || {
    rm -f "$system_file" "$prompt_file" "$receipt_file"
    return 2
  }
  response_length="$(printf '%s\n' "$metrics" | sed -n '1p')"
  response_digest="$(printf '%s\n' "$metrics" | sed -n '2p')"
  if ! validate_provider_result "$receipt_file" "$model" "" "$response_length" "$response_digest" "$body_digest"; then
    rm -f "$system_file" "$prompt_file" "$receipt_file"
    return 2
  fi
  printf '%s' "$response"
  rm -f "$system_file" "$prompt_file" "$receipt_file"
}
resolve_openrouter_exec() {
  [ -x "$DIR/openrouter-exec.sh" ] && printf '%s' "$DIR/openrouter-exec.sh"
}
dispatch_openrouter_exec() {
  local runner; runner="$(resolve_openrouter_exec)"
  [ -z "$runner" ] && return 1
  printf '%s' "$PROMPT" | "$runner" --model "$1" --timeout "$TIMEOUT"
}

# Gate the prompt once before any OpenRouter execution or wrapper role. A
# missing/unverifiable boundary makes the entire OpenRouter rail unavailable;
# trusted Codex roles may still run.
OPENROUTER_GATE_STATE="unchecked"
openrouter_allowed() {
  [ "$DRYRUN" = "1" ] && return 0
  [ "$OPENROUTER_GATE_STATE" = "safe" ] && return 0
  [ "$OPENROUTER_GATE_STATE" = "denied" ] && return 1
  [ "${DM_PROVIDER_LANE:-}" = "$ASSESSMENT_LANE" ] || {
    OPENROUTER_GATE_STATE="denied"
    return 1
  }
  [ -n "${DM_PROVIDER_REPOSITORY:-}" ] && [ -n "${DM_PROVIDER_RUN_ID:-}" ] &&
    [ -n "${DM_PROVIDER_CANDIDATE:-}" ] && [ -n "${DM_PROVIDER_NONCE:-}" ] || {
    OPENROUTER_GATE_STATE="denied"
    return 1
  }
  local client="" status=""
  client="$(authority_client)" || {
    OPENROUTER_GATE_STATE="denied"
    return 1
  }
  status="$(authority_env "$client" provider-transport-status 2>/dev/null)" || {
    OPENROUTER_GATE_STATE="denied"; return 1;
  }
  if printf '%s' "$status" | jq -e \
      '.production_ready == true and .m1_acceptance == true' >/dev/null; then
    OPENROUTER_GATE_STATE="safe"
    return 0
  fi
  OPENROUTER_GATE_STATE="denied"
  return 1
}

# native_judgment exists because the 2026-08-08 capped-Codex and fail-closed
# OpenRouter state produced a zero-chunk execution deadlock. It is gated because
# silently spending Claude quota on coding work is a policy violation; an honest
# deadlock report is better than a silent reroute.
#
# DM_NATIVE_JUDGMENT_AUTHORIZATION represents an explicit human grant. It is NOT
# a self-service escape hatch: a caller-invented value is a policy violation, not
# an authorization. The gate validates its shape, repository/run scope, and live
# epoch-seconds expiry, and fails closed on every error.
NATIVE_JUDGMENT_AUTHORIZATION_ID=""
NATIVE_JUDGMENT_AUTHORIZATION_EXPIRES_AT_EPOCH=""
native_judgment_allowed() {
  local authorization="${DM_NATIVE_JUDGMENT_AUTHORIZATION:-}" now=""
  NATIVE_JUDGMENT_AUTHORIZATION_ID=""
  NATIVE_JUDGMENT_AUTHORIZATION_EXPIRES_AT_EPOCH=""
  [ -n "$authorization" ] || return 1
  [ -n "${DM_PROVIDER_REPOSITORY:-}" ] && [ -n "${DM_PROVIDER_RUN_ID:-}" ] || return 1
  now="$(date -u +%s 2>/dev/null)" || return 1
  case "$now" in ''|*[!0-9]*) return 1;; esac
  printf '%s' "$authorization" | jq -e \
    --arg repository "$DM_PROVIDER_REPOSITORY" --arg run_id "$DM_PROVIDER_RUN_ID" \
    --argjson now "$now" '
      type == "object" and
      .humanGranted == true and
      (.authorizationId | type == "string" and test("^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")) and
      (.repository | type == "string") and .repository == $repository and
      (.runId | type == "string") and .runId == $run_id and
      (.expiresAtEpoch | type == "number" and . == floor and . > $now and . <= 9223372036854775807)
    ' >/dev/null 2>&1 || return 1
  NATIVE_JUDGMENT_AUTHORIZATION_ID="$(printf '%s' "$authorization" | jq -r '.authorizationId')" || return 1
  NATIVE_JUDGMENT_AUTHORIZATION_EXPIRES_AT_EPOCH="$(printf '%s' "$authorization" | jq -r '.expiresAtEpoch')" || return 1
  return 0
}

probe_json() { [ -n "$PROBE_FILE" ] && cat "$PROBE_FILE" || { [ -x "$PROBE" ] && "$PROBE" || echo '{}'; }; }
PROBES="$(probe_json)"
FLOOR="$(jq -r --arg c "$CLASS" '.cascades[$c].quality_floor // 0' "$CASCADE")"
LADDER="$(jq -r --arg c "$CLASS" '.cascades[$c].ladder[]?' "$CASCADE")"
[ -z "$LADDER" ] && { echo "cascade-dispatch: unknown class '$CLASS'" >&2; exit 2; }
REQUESTED_ROLE="$(printf '%s\n' "$LADDER" | sed -n '1p')"
REQUESTED_MODEL="$(jq -r --arg h "$HOST" --arg r "$REQUESTED_ROLE" \
  '.hosts[$h].roles[$r].models[0] // empty' "$PROFILE")"
THRESH="$(jq -r '.policy.headroom_threshold_pct // 8' "$CASCADE")"

rail_is_exhausted() {
  # bash 3.2 safe: avoid read -a + "${arr[@]}" (empty array + set -u is fatal on 3.2).
  # Comma-wrap both sides so a substring match is an exact rail match.
  [ -z "$EXHAUSTED_RAILS" ] && return 1
  case ",$EXHAUSTED_RAILS," in *",$1,"*) return 0 ;; esac
  return 1
}

rail_has_headroom() {
  local rail="$1" state pct
  [ "$rail" = "none" ] && return 0
  rail_is_exhausted "$rail" && return 1
  state="$(printf '%s' "$PROBES" | jq -r --arg r "$rail" '.[$r].state // "unknown"')"
  case "$state" in limited|low) return 1;; esac
  pct="$(printf '%s' "$PROBES" | jq -r --arg r "$rail" '.[$r].remaining_pct // empty')"
  [ -n "$pct" ] && [ "$pct" -lt "$THRESH" ] 2>/dev/null && return 1
  return 0
}

# --- walk the ladder ---------------------------------------------------------
for role in $LADDER; do
  kind="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].kind // "none"' "$PROFILE")"
  [ "$kind" = "none" ] && continue
  [ "$role" = "native_judgment" ] && ! native_judgment_allowed && continue
  prail="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].probe // "none"' "$PROFILE")"
  rail_has_headroom "$prail" || continue
  if [ "$prail" = "openrouter" ] && ! openrouter_allowed; then
    EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
    continue
  fi
  models="$(jq -r --arg h "$HOST" --arg r "$role" '.hosts[$h].roles[$r].models[]?' "$PROFILE")"
  for model in $models; do
    model_origin="$(printf '%s' "$model" | tr '[:upper:]' '[:lower:]')"
    case "$kind:$model_origin" in
      wrapper:anthropic/*|openrouter_exec:anthropic/*)
        echo "cascade-dispatch: native-vendor-origin invariant rejected OpenRouter model '$model'" >&2
        exit 2
        ;;
    esac
    q="$(jq -r --arg m "$model" '.quality_rank[$m] // 0' "$CASCADE")"
    [ "$q" -lt "$FLOOR" ] 2>/dev/null && continue
    if [ "$DRYRUN" = "1" ]; then
      fallback=false
      fallback_reason="none"
      if [ "$CLASS" != "$prail" ]; then
        fallback=true
        fallback_reason="${CLASS}-unavailable-or-below-floor"
      fi
      if [ "$role" = "native_judgment" ]; then
        jq -n --arg c "$CLASS" --arg h "$HOST" --arg role "$role" --arg k "$kind" \
              --arg m "$model" --arg q "$q" --arg pr "$prail" \
              --arg requested_model "$REQUESTED_MODEL" \
              --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
              --arg authorization_id "$NATIVE_JUDGMENT_AUTHORIZATION_ID" \
              --argjson authorization_expiry "$NATIVE_JUDGMENT_AUTHORIZATION_EXPIRES_AT_EPOCH" \
              '{class:$c,host:$h,role:$role,kind:$k,model:$m,quality:($q|tonumber),probe_rail:$pr,
                requestedProvider:$c,requestedModel:$requested_model,
                attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
                fallback:$fallback,fallbackReason:$fallback_reason,native_vendor_origin_invariant:"passed",
                nativeAuthorization:{authorizationId:$authorization_id,expiresAtEpoch:$authorization_expiry},
                targetVariance:true,varianceReceiptRequired:true}'
      else
        jq -n --arg c "$CLASS" --arg h "$HOST" --arg role "$role" --arg k "$kind" \
              --arg m "$model" --arg q "$q" --arg pr "$prail" \
              --arg requested_model "$REQUESTED_MODEL" \
              --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
              '{class:$c,host:$h,role:$role,kind:$k,model:$m,quality:($q|tonumber),probe_rail:$pr,
                requestedProvider:$c,requestedModel:$requested_model,
                attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
                fallback:$fallback,fallbackReason:$fallback_reason,native_vendor_origin_invariant:"passed"}'
      fi
      exit 0
    fi
    # Traversal intent per rung kind: codex_companion is single-attempt per role
    # -> `break` to the next ROLE on any failure; native emits a directive and
    # `exit 64`s on the first qualifying model (the orchestrator owns the in-process
    # model descent, e.g. opus->sonnet); wrapper roles iterate their model list
    # -> `continue` to the next MODEL on a per-model error.
    case "$kind" in
      native)
        fallback=false
        fallback_reason="none"
        if [ "$CLASS" != "$prail" ]; then
          fallback=true
          fallback_reason="${CLASS}-unavailable-or-below-floor"
        fi
        if [ "$role" = "native_judgment" ]; then
          jq -n --arg m "$model" --arg role "$role" --arg pr "$prail" \
                --arg requested_provider "$CLASS" --arg requested_model "$REQUESTED_MODEL" \
                --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
                --arg authorization_id "$NATIVE_JUDGMENT_AUTHORIZATION_ID" \
                --argjson authorization_expiry "$NATIVE_JUDGMENT_AUTHORIZATION_EXPIRES_AT_EPOCH" \
                '{dispatch:"native",model:$m,role:$role,probe_rail:$pr,
                  requestedProvider:$requested_provider,requestedModel:$requested_model,
                  attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
                  fallback:$fallback,fallbackReason:$fallback_reason,nativeVendorOriginInvariant:"passed",
                  nativeAuthorization:{authorizationId:$authorization_id,expiresAtEpoch:$authorization_expiry},
                  targetVariance:true,varianceReceiptRequired:true}'
        else
          jq -n --arg m "$model" --arg role "$role" --arg pr "$prail" \
                --arg requested_provider "$CLASS" --arg requested_model "$REQUESTED_MODEL" \
                --arg fallback_reason "$fallback_reason" --argjson fallback "$fallback" \
                '{dispatch:"native",model:$m,role:$role,probe_rail:$pr,
                  requestedProvider:$requested_provider,requestedModel:$requested_model,
                  attemptedProvider:$pr,attemptedModel:$m,actualImplementer:$pr,actualModel:$m,
                  fallback:$fallback,fallbackReason:$fallback_reason,nativeVendorOriginInvariant:"passed"}'
        fi
        exit 64;;
      codex_companion)
        out="$(dispatch_codex)"; rc=$?
        [ $rc -eq 127 ] && break                       # Codex absent -> next role
        if printf '%s' "$out" | grep -qiE 'usage limit|rate.?limit|quota'; then
          checkpoint; break                            # CAP -> handoff, next role
        fi
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        break;;                                        # other Codex failure -> next OpenRouter role
      wrapper)
        dispatch_wrapper "$model"; rc=$?
        [ $rc -eq 0 ] && exit 0
        [ $rc -eq 75 ] && { echo "cascade-dispatch: terminal provider outcome; external dispatch rail stopped" >&2; exit 75; }
        if [ $rc -eq 77 ]; then
          OPENROUTER_GATE_STATE="denied"
          EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
          break
        fi
        [ $rc -eq 2 ] && exit 2
        continue;;                                     # wrapper error -> next model
      openrouter_exec)
        out="$(dispatch_openrouter_exec "$model")"; rc=$?
        [ $rc -eq 0 ] && { printf '%s\n' "$out"; exit 0; }
        [ $rc -eq 75 ] && { [ -z "$out" ] || printf '%s\n' "$out"; echo "cascade-dispatch: terminal provider outcome; external dispatch rail stopped" >&2; exit 75; }
        [ $rc -eq 78 ] && { printf '%s\n' "$out"; exit 78; }
        if [ $rc -eq 77 ]; then
          OPENROUTER_GATE_STATE="denied"
          EXHAUSTED_RAILS="${EXHAUSTED_RAILS}${EXHAUSTED_RAILS:+,}openrouter"
          break                                    # skip every later OpenRouter role
        fi
        [ $rc -eq 2 ] && exit 2
        continue;;
      *)
        echo "cascade-dispatch: unknown rail kind '$kind'" >&2
        exit 2;;
    esac
  done
done

echo "cascade-dispatch: ladder exhausted for class '$CLASS' on host '$HOST' (floor $FLOOR)" >&2
exit 76
