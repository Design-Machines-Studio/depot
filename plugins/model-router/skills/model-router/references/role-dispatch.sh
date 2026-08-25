#!/usr/bin/env bash
# role-dispatch.sh -- deterministic, provider-neutral, one-shot role dispatcher.
set -uo pipefail

ROUTER_CODEX_CLI="$(command -v codex 2>/dev/null || true)"
ROUTER_CLAUDE_CLI="$(command -v claude 2>/dev/null || true)"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
umask 077

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$DIR/role-policy.json"
ROLE=""
EFFORT=""
PROMPT_FILE=""
OUTPUT_FILE=""
RECEIPT_FILE=""
CAPABILITIES=()
INDEPENDENCE_RECEIPT_IDS=()

usage() {
  printf '%s\n' 'usage: role-dispatch --role ROLE --capability CAP [--capability CAP ...] --effort EFFORT --prompt-file PATH --output-file PATH --receipt-file PATH [--independence-receipt-id ID ...]' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --role) [ "$#" -ge 2 ] || usage; ROLE="$2"; shift 2 ;;
    --capability) [ "$#" -ge 2 ] || usage; CAPABILITIES+=("$2"); shift 2 ;;
    --effort) [ "$#" -ge 2 ] || usage; EFFORT="$2"; shift 2 ;;
    --prompt-file) [ "$#" -ge 2 ] || usage; PROMPT_FILE="$2"; shift 2 ;;
    --output-file) [ "$#" -ge 2 ] || usage; OUTPUT_FILE="$2"; shift 2 ;;
    --receipt-file) [ "$#" -ge 2 ] || usage; RECEIPT_FILE="$2"; shift 2 ;;
    --independence-receipt-id) [ "$#" -ge 2 ] || usage; INDEPENDENCE_RECEIPT_IDS+=("$2"); shift 2 ;;
    *) usage ;;
  esac
done

command -v jq >/dev/null 2>&1 || { printf '%s\n' 'role-dispatch: unavailable (missing runtime dependency)' >&2; exit 76; }
[ -r "$POLICY" ] && jq -e '.schemaVersion == 1' "$POLICY" >/dev/null 2>&1 || {
  printf '%s\n' 'role-dispatch: unavailable (invalid role policy)' >&2
  exit 76
}
case "$ROLE" in
  architect|plan-critic|builder-fast|builder-deep|review-fast|review-deep|security-review|research-fast|editorial) ;;
  *) usage ;;
esac
case "$EFFORT" in low|medium|high|max) ;; *) usage ;; esac
[ -f "$PROMPT_FILE" ] && [ -r "$PROMPT_FILE" ] && [ ! -L "$PROMPT_FILE" ] || usage
[ -n "$OUTPUT_FILE" ] && [ -n "$RECEIPT_FILE" ] || usage
[ "$OUTPUT_FILE" != "$RECEIPT_FILE" ] || usage
[ -d "$(dirname "$OUTPUT_FILE")" ] && [ -d "$(dirname "$RECEIPT_FILE")" ] || usage
[ ! -e "$OUTPUT_FILE" ] && [ ! -L "$OUTPUT_FILE" ] || usage
[ ! -e "$RECEIPT_FILE" ] && [ ! -L "$RECEIPT_FILE" ] || usage

VALID_CAPABILITIES='["read-repository","write-repository","tool-use","browser","long-context","structured-output","independent-family"]'
CAPABILITIES_JSON='[]'
for capability in "${CAPABILITIES[@]}"; do
  printf '%s' "$VALID_CAPABILITIES" | jq -e --arg capability "$capability" 'index($capability) != null' >/dev/null || usage
  CAPABILITIES_JSON="$(printf '%s' "$CAPABILITIES_JSON" | jq -c --arg capability "$capability" '. + [$capability] | unique | sort')"
done
if printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("independent-family") != null' >/dev/null &&
   [ "${#INDEPENDENCE_RECEIPT_IDS[@]}" -eq 0 ]; then
  printf '%s\n' 'role-dispatch: invalid independent-family request' >&2
  exit 2
fi

case "$ROLE" in
  architect|plan-critic) PARTICIPANT_PREFIX="planner" ;;
  review-fast|review-deep|security-review) PARTICIPANT_PREFIX="reviewer" ;;
  *) PARTICIPANT_PREFIX="participant" ;;
esac

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'
  fi
}

sha256_text() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | awk '{print $1}'
  else shasum -a 256 | awk '{print $1}'
  fi
}

PROMPT_DIGEST="$(sha256_file "$PROMPT_FILE")"
RECEIPT_ID="dispatch-$(printf '%s' "$ROLE|$PROMPT_DIGEST|$RECEIPT_FILE|$$" | sha256_text | cut -c1-24)"
PARTICIPANT_ID="$PARTICIPANT_PREFIX-${RECEIPT_ID#dispatch-}"
PARTICIPANT_ID="${PARTICIPANT_ID%????????????????}"
MATRIX_SNAPSHOT="$(jq -r '.matrixSnapshot' "$POLICY")"
THRESHOLD="$(jq -r '.availability.headroomThresholdPct' "$POLICY")"
EXCLUDED_FAMILIES='[]'
INDEPENDENCE_IDS_JSON='[]'

for prior_id in "${INDEPENDENCE_RECEIPT_IDS[@]}"; do
  case "$prior_id" in *[!a-z0-9-]*|'') usage ;; esac
  match=""
  for candidate_receipt in "$(dirname "$RECEIPT_FILE")"/*; do
    [ -f "$candidate_receipt" ] && [ ! -L "$candidate_receipt" ] || continue
    if jq -e --arg receipt_id "$prior_id" '.receiptId == $receipt_id and (.served.family | type == "string")' "$candidate_receipt" >/dev/null 2>&1; then
      match="$candidate_receipt"
      break
    fi
  done
  [ -n "$match" ] || { printf '%s\n' 'role-dispatch: invalid independence evidence' >&2; exit 2; }
  family="$(jq -r '.served.family' "$match")"
  EXCLUDED_FAMILIES="$(printf '%s' "$EXCLUDED_FAMILIES" | jq -c --arg family "$family" '. + [$family] | unique | sort')"
  INDEPENDENCE_IDS_JSON="$(printf '%s' "$INDEPENDENCE_IDS_JSON" | jq -c --arg receipt_id "$prior_id" '. + [$receipt_id] | unique | sort')"
done

local_profile_path() {
  local common root candidate parent physical_root physical_parent
  common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" || return 0
  common="$(cd "$common" 2>/dev/null && pwd -P)" || return 0
  [ "${common##*/}" = '.git' ] || return 0
  root="${common%/.git}"
  candidate="$root/.dm/model-router.local.json"
  [ -f "$candidate" ] && [ ! -L "$candidate" ] || return 0
  physical_root="$(cd "$root" && pwd -P)" || return 0
  parent="$(dirname "$candidate")"
  physical_parent="$(cd "$parent" && pwd -P)" || return 0
  [ "$physical_parent" = "$physical_root/.dm" ] || return 0
  git -C "$root" ls-files --error-unmatch -- .dm/model-router.local.json >/dev/null 2>&1 && return 0
  jq -e 'type == "object" and ((keys - ["allowPaidClaudeCredits"]) | length == 0) and (.allowPaidClaudeCredits == null or (.allowPaidClaudeCredits | type) == "boolean")' "$candidate" >/dev/null 2>&1 || return 0
  printf '%s\n' "$candidate"
}

PAID_CLAUDE_CREDITS=false
PROFILE="$(local_profile_path)"
if [ -n "$PROFILE" ]; then
  PAID_CLAUDE_CREDITS="$(jq -r '.allowPaidClaudeCredits // false' "$PROFILE")"
fi

if [ -n "${MODEL_ROUTER_AVAILABILITY_FILE:-}" ]; then
  [ -r "$MODEL_ROUTER_AVAILABILITY_FILE" ] && [ ! -L "$MODEL_ROUTER_AVAILABILITY_FILE" ] || usage
  AVAILABILITY="$(jq -c '. + {probeSource:"fixture"}' "$MODEL_ROUTER_AVAILABILITY_FILE")" || usage
else
  AVAILABILITY="$("$DIR/availability-probe.sh" | jq -c '. + {probeSource:"live"}')" || AVAILABILITY='{"probeSource":"live"}'
fi

ATTEMPTS='[]'
LAST_REASON="none"
ATTEMPT_INDEX=0
EXHAUSTED_TRANSPORTS='[]'
EXHAUSTED_MODELS='[]'
PRIVATE_LOG="$(mktemp "${TMPDIR:-/tmp}/model-router.log.XXXXXX")" || exit 76
TRANSPORT_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/model-router.output.XXXXXX")" || { rm -f "$PRIVATE_LOG"; exit 76; }
PROVIDER_RECEIPT="$(mktemp "${TMPDIR:-/tmp}/model-router.provider.XXXXXX")" || { rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT"; exit 76; }
cleanup() { rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT" "$PROVIDER_RECEIPT"; }
trap cleanup EXIT

candidate_has_capabilities() {
  local candidate="$1"
  jq -en --argjson requested "$CAPABILITIES_JSON" --argjson candidate "$candidate" '
    ($requested - ["independent-family"]) as $needed
    | all($needed[]; . as $cap | $candidate.capabilities | index($cap) != null)'
}

transport_eligibility() {
  local transport="$1" model="$2" state auth_mode plan fable_state observed sdk_observed five weekly paid
  BILLING_MODE="unavailable"
  ALLOWANCE_WINDOW="unavailable"
  case "$transport" in
    codex-cli)
      state="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.state // "unknown"')"
      auth_mode="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.authMode // .codex.auth_mode // "unknown"')"
      five="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.windows.five_hour.remaining_pct // .codex.fiveHourRemainingPct // 0')"
      weekly="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.windows.weekly.remaining_pct // .codex.weeklyRemainingPct // 0')"
      [ "$state" = ok ] && [ "$auth_mode" = subscription ] && awk -v a="$five" -v b="$weekly" -v t="$THRESHOLD" 'BEGIN{exit !(a>t && b>t)}' || return 1
      BILLING_MODE="included-subscription"
      ALLOWANCE_WINDOW="subscription"
      ;;
    claude-cli)
      state="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.state // "unknown"')"
      auth_mode="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.authMode // .claude.auth_mode // "unknown"')"
      plan="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.plan // "unknown"')"
      fable_state="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.fable // .claude.fableAvailability // "unknown"')"
      observed="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.rateLimitsObserved // false')"
      sdk_observed="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.agentSdkRateLimitsObserved // false')"
      paid="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.paidCreditsEnabled // empty')"
      [ -n "$paid" ] || paid="$PAID_CLAUDE_CREDITS"
      [ "$state" != unavailable ] && [ "$auth_mode" = subscription ] || return 1
      [ "$fable_state" != exhausted ] || return 1
      case "$plan" in
        max|team-premium|enterprise-premium|included)
          if [ "$sdk_observed" = true ] &&
             [ "$(printf '%s' "$AVAILABILITY" | jq -r '.claude.allowances.agent_sdk.state // "unknown"')" = ok ]; then
            five="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.allowances.agent_sdk.windows.five_hour.remaining_pct // 0')"
            weekly="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.allowances.agent_sdk.windows.weekly.remaining_pct // 0')"
            awk -v a="$five" -v b="$weekly" -v t="$THRESHOLD" 'BEGIN{exit !(a>t && b>t)}' || return 1
            BILLING_MODE="included-subscription"
            ALLOWANCE_WINDOW="agent-sdk"
          elif [ "$observed" = true ]; then
            five="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.windows.five_hour.remaining_pct // .claude.fiveHourRemainingPct // 0')"
            weekly="$(printf '%s' "$AVAILABILITY" | jq -r '.claude.windows.weekly.remaining_pct // .claude.weeklyRemainingPct // 0')"
            awk -v a="$five" -v b="$weekly" -v t="$THRESHOLD" 'BEGIN{exit !(a>t && b>t)}' || return 1
            BILLING_MODE="included-subscription"
            ALLOWANCE_WINDOW="interactive"
          else
            BILLING_MODE="subscription-headroom-unknown"
            ALLOWANCE_WINDOW="unknown"
          fi
          ;;
        credits-only)
          [ "$paid" = true ] || return 1
          BILLING_MODE="paid-credits"
          ALLOWANCE_WINDOW="paid-credits"
          ;;
        *) return 1 ;;
      esac
      ;;
    openrouter)
      state="$(printf '%s' "$AVAILABILITY" | jq -r '.openrouter.state // "unknown"')"
      [ "$state" = ok ] || return 1
      BILLING_MODE="api"
      ALLOWANCE_WINDOW="api"
      ;;
    *) return 1 ;;
  esac
}

resolve_openrouter_root() {
  local active_host="" bundle_json bundle_ref
  [ -n "${WORKFLOW_KERNEL:-}" ] && [ -x "$WORKFLOW_KERNEL" ] || return 1
  [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && active_host=claude
  [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && active_host=codex
  args=(resolve-plugin-bundle --plugin openrouter --minimum-version 1.19.0
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh
    --required-asset skills/openrouter-delegate/references/openrouter-credential.sh
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh)
  [ -n "$active_host" ] && args+=(--active-host "$active_host")
  bundle_json="$("$WORKFLOW_KERNEL" "${args[@]}" 2>>"$PRIVATE_LOG")" || return 1
  bundle_ref="$(printf '%s' "$bundle_json" | jq -r '.selected_root // empty')"
  case "$bundle_ref" in '~/'*) printf '%s\n' "$HOME/${bundle_ref#\~/}" ;; *) return 1 ;; esac
}

invoke_candidate() {
  local transport="$1" model="$2" effective="$3" rc=0 root system_file prompt_copy result_json sandbox web_search=0
  : > "$TRANSPORT_OUTPUT"
  : > "$PROVIDER_RECEIPT"
  if [ -n "${MODEL_ROUTER_TRANSPORT_STUB:-}" ]; then
    argv=("$MODEL_ROUTER_TRANSPORT_STUB" --transport "$transport" --model "$model" --effort "$effective" --prompt-file "$PROMPT_FILE" --output-file "$TRANSPORT_OUTPUT")
    "${argv[@]}" 2>>"$PRIVATE_LOG"
    return $?
  fi
  case "$transport" in
    codex-cli)
      [ -n "$ROUTER_CODEX_CLI" ] && [ -x "$ROUTER_CODEX_CLI" ] || return 77
      sandbox=read-only
      printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("write-repository") != null' >/dev/null && sandbox=workspace-write
      argv=("$ROUTER_CODEX_CLI" exec --model "$model" --config "model_reasoning_effort=\"$effective\"" --sandbox "$sandbox" --ephemeral --output-last-message "$TRANSPORT_OUTPUT")
      git_root="$(git rev-parse --show-toplevel 2>/dev/null)" && argv+=(--cd "$git_root")
      "${argv[@]}" < "$PROMPT_FILE" >>"$PRIVATE_LOG" 2>&1
      ;;
    claude-cli)
      [ -n "$ROUTER_CLAUDE_CLI" ] && [ -x "$ROUTER_CLAUDE_CLI" ] || return 77
      argv=("$ROUTER_CLAUDE_CLI" -p --model "$model" --effort "$effective" --tools "" --no-session-persistence --output-format json)
      result_json="$("${argv[@]}" < "$PROMPT_FILE" 2>>"$PRIVATE_LOG")" || return $?
      printf '%s' "$result_json" | jq -r '.result // empty' > "$TRANSPORT_OUTPUT" || return 1
      printf '%s' "$result_json" > "$PROVIDER_RECEIPT"
      ;;
    openrouter)
      if printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("write-repository") != null' >/dev/null; then
        [ -n "${OPENROUTER_EXEC_ALLOWED_PATHS:-}" ] || return 77
        argv=("$DIR/openrouter-write-adapter.sh" --model "$model")
        "${argv[@]}" < "$PROMPT_FILE" > "$PROVIDER_RECEIPT" 2>>"$PRIVATE_LOG" || return $?
        printf '%s\n' '{"status":"committed","verification":"required"}' > "$TRANSPORT_OUTPUT"
      else
        root="$(resolve_openrouter_root)" || return 77
        system_file="$(mktemp "${TMPDIR:-/tmp}/model-router.system.XXXXXX")" || return 1
        prompt_copy="$(mktemp "${TMPDIR:-/tmp}/model-router.prompt.XXXXXX")" || { rm -f "$system_file"; return 1; }
        printf '%s' 'Return only the requested analysis. You have no command authority.' > "$system_file"
        cp "$PROMPT_FILE" "$prompt_copy"
        argv=("$root/skills/openrouter-delegate/references/delegation-boundary.sh" --mode artifact-delegation --policy "$root/skills/openrouter-delegate/references/delegation-security-policy.json" --content-file "$system_file" --content-file "$prompt_copy")
        "${argv[@]}" >>"$PRIVATE_LOG" 2>&1 || { rm -f "$system_file" "$prompt_copy"; return 77; }
        argv=(bash "$root/skills/openrouter-delegate/references/openrouter-wrapper.sh" "$model" - 3600)
        printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("browser") != null' >/dev/null && web_search=1
        env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$system_file" \
          OPENROUTER_WORKLOAD=mechanical OPENROUTER_WEB_SEARCH="$web_search" \
          OPENROUTER_RECEIPT_FILE="$PROVIDER_RECEIPT" "${argv[@]}" \
          < "$prompt_copy" > "$TRANSPORT_OUTPUT" 2>>"$PRIVATE_LOG"
        rc=$?
        rm -f "$system_file" "$prompt_copy"
        return "$rc"
      fi
      ;;
  esac
}

CANDIDATES="$(jq -c --arg role "$ROLE" '.roles[$role][]' "$POLICY")"
REQUESTED_CANDIDATE="$(printf '%s\n' "$CANDIDATES" | sed -n '1p')"
while IFS= read -r candidate; do
  [ -n "$candidate" ] || continue
  candidate_has_capabilities "$candidate" >/dev/null || continue
  family="$(printf '%s' "$candidate" | jq -r '.family')"
  if printf '%s' "$EXCLUDED_FAMILIES" | jq -e --arg family "$family" 'index($family) != null' >/dev/null; then
    continue
  fi
  transport="$(printf '%s' "$candidate" | jq -r '.transport')"
  model="$(printf '%s' "$candidate" | jq -r '.model')"
  provider="$(printf '%s' "$candidate" | jq -r '.provider')"
  if printf '%s' "$EXHAUSTED_TRANSPORTS" | jq -e --arg value "$transport" 'index($value) != null' >/dev/null ||
     printf '%s' "$EXHAUSTED_MODELS" | jq -e --arg value "$model" 'index($value) != null' >/dev/null; then
    continue
  fi
  ATTEMPT_INDEX=$((ATTEMPT_INDEX + 1))
  if ! transport_eligibility "$transport" "$model"; then
    reason="unavailable"
    ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg reason "$reason" '. + [{model:$model,provider:$provider,transport:$transport,outcome:"skipped",reason:$reason}]')"
    LAST_REASON="$reason"
    continue
  fi
  EFFECTIVE_EFFORT="$(jq -r --arg transport "$transport" --arg effort "$EFFORT" '.effort.transports[$transport][$effort]' "$POLICY")"
  STARTED="$(date +%s)"
  fixture_outcome="$(printf '%s' "$AVAILABILITY" | jq -r --arg model "$model" '.candidateResults[$model].outcome // ""')"
  if [ "$(printf '%s' "$AVAILABILITY" | jq -r '.probeSource')" = fixture ] &&
     [ -z "${MODEL_ROUTER_TRANSPORT_STUB:-}" ]; then
    [ -n "$fixture_outcome" ] || fixture_outcome=success
    if [ "$fixture_outcome" = success ]; then
      printf '%s' "$AVAILABILITY" | jq -r --arg model "$model" '.candidateResults[$model].output // "fixture output"' > "$TRANSPORT_OUTPUT"
      rc=0
    else
      printf '%s\n' "$fixture_outcome" > "$PRIVATE_LOG"
      rc=77
    fi
  else
    invoke_candidate "$transport" "$model" "$EFFECTIVE_EFFORT"
    rc=$?
  fi
  DURATION_SECONDS=$(( $(date +%s) - STARTED ))
  if [ "$rc" -eq 0 ] && [ -s "$TRANSPORT_OUTPUT" ]; then
    cp "$TRANSPORT_OUTPUT" "$OUTPUT_FILE"
    usage_json=null
    cost_json=null
    token_provenance=unavailable
    cost_provenance=unavailable
    if jq -e . "$PROVIDER_RECEIPT" >/dev/null 2>&1; then
      usage_json="$(jq -c '.usage // null' "$PROVIDER_RECEIPT")"
      cost_json="$(jq -c '.costUsd // .cost_usd // null' "$PROVIDER_RECEIPT")"
      [ "$usage_json" = null ] || token_provenance=provider-receipt
      [ "$cost_json" = null ] || cost_provenance=provider-receipt
    fi
    ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg billing "$BILLING_MODE" --argjson duration "$DURATION_SECONDS" '. + [{model:$model,provider:$provider,transport:$transport,billingMode:$billing,outcome:"served",durationSeconds:$duration}]')"
    fallback=false
    fallback_reason=none
    [ "$ATTEMPT_INDEX" -gt 1 ] && { fallback=true; fallback_reason="$LAST_REASON"; }
    jq -n --arg receipt_id "$RECEIPT_ID" --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg requested_effort "$EFFORT" --arg effective_effort "$EFFECTIVE_EFFORT" --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg family "$family" --arg billing "$BILLING_MODE" --arg allowance_window "$ALLOWANCE_WINDOW" --arg matrix "$MATRIX_SNAPSHOT" --arg fallback_reason "$fallback_reason" --arg token_provenance "$token_provenance" --arg cost_provenance "$cost_provenance" --argjson requested_candidate "$REQUESTED_CANDIDATE" --argjson capabilities "$CAPABILITIES_JSON" --argjson attempts "$ATTEMPTS" --argjson independence_ids "$INDEPENDENCE_IDS_JSON" --argjson excluded_families "$EXCLUDED_FAMILIES" --argjson fallback "$fallback" --argjson duration "$DURATION_SECONDS" --argjson usage "$usage_json" --argjson cost "$cost_json" '{schemaVersion:1,receiptId:$receipt_id,requested:{role:$role,capabilities:$capabilities,effort:$requested_effort,independenceReceiptIds:$independence_ids,candidate:{model:$requested_candidate.model,provider:$requested_candidate.provider,transport:$requested_candidate.transport}},participantId:$participant,attempts:$attempts,served:{model:$model,provider:$provider,transport:$transport,family:$family,billingMode:$billing,allowanceWindow:$allowance_window,durationSeconds:$duration,tokens:$usage,tokenProvenance:$token_provenance,billedCostUsd:$cost,costProvenance:$cost_provenance},effectiveEffort:$effective_effort,effortNormalized:($requested_effort != $effective_effort),fallback:$fallback,fallbackReason:$fallback_reason,matrixSnapshot:$matrix,familyIndependence:{required:($independence_ids|length>0),excludedFamilies:$excluded_families,passed:true}}' > "$RECEIPT_FILE"
    jq -n --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg requested_effort "$EFFORT" --arg effective_effort "$EFFECTIVE_EFFORT" --arg output "$OUTPUT_FILE" --argjson capabilities "$CAPABILITIES_JSON" --argjson fallback "$fallback" '{role:$role,capabilities:$capabilities,requestedEffort:$requested_effort,effectiveEffort:$effective_effort,participantId:$participant,disposition:"completed",fallback:$fallback,output:$output}'
    exit 0
  fi
  if grep -qiE 'usage.?limit|rate.?limit|quota|exhausted' "$PRIVATE_LOG"; then reason=quota-exhausted
  elif grep -qiE 'declin|disclosure' "$PRIVATE_LOG"; then reason=disclosure-declined
  else reason=transport-unavailable
  fi
  ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg billing "$BILLING_MODE" --arg reason "$reason" --argjson duration "$DURATION_SECONDS" '. + [{model:$model,provider:$provider,transport:$transport,billingMode:$billing,outcome:"failed",reason:$reason,durationSeconds:$duration}]')"
  if [ "$reason" = quota-exhausted ]; then
    if [ "$transport" = codex-cli ]; then
      EXHAUSTED_TRANSPORTS="$(printf '%s' "$EXHAUSTED_TRANSPORTS" | jq -c --arg value "$transport" '. + [$value] | unique')"
    else
      EXHAUSTED_MODELS="$(printf '%s' "$EXHAUSTED_MODELS" | jq -c --arg value "$model" '. + [$value] | unique')"
    fi
  fi
  LAST_REASON="$reason"
done <<< "$CANDIDATES"

jq -n --arg receipt_id "$RECEIPT_ID" --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg effort "$EFFORT" --arg matrix "$MATRIX_SNAPSHOT" --arg reason "$LAST_REASON" --argjson requested_candidate "$REQUESTED_CANDIDATE" --argjson capabilities "$CAPABILITIES_JSON" --argjson attempts "$ATTEMPTS" --argjson independence_ids "$INDEPENDENCE_IDS_JSON" --argjson excluded_families "$EXCLUDED_FAMILIES" '{schemaVersion:1,receiptId:$receipt_id,requested:{role:$role,capabilities:$capabilities,effort:$effort,independenceReceiptIds:$independence_ids,candidate:{model:$requested_candidate.model,provider:$requested_candidate.provider,transport:$requested_candidate.transport}},participantId:$participant,attempts:$attempts,served:null,effectiveEffort:$effort,effortNormalized:false,fallback:true,fallbackReason:$reason,matrixSnapshot:$matrix,familyIndependence:{required:($independence_ids|length>0),excludedFamilies:$excluded_families,passed:false}}' > "$RECEIPT_FILE"
jq -n --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg effort "$EFFORT" --argjson capabilities "$CAPABILITIES_JSON" '{role:$role,capabilities:$capabilities,requestedEffort:$effort,effectiveEffort:$effort,participantId:$participant,disposition:"unavailable",fallback:true,output:null}'
exit 76
