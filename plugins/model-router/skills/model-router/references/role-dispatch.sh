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
REPOSITORY_EVIDENCE_FILE=""
INDEPENDENCE_RECEIPT_DIR=""
HUMAN_AUTHORED=0
CONTRACT_DIGEST=""
CONTRACT_REVISION=""
CONTRACT_REVISION_JSON=null
WORKFLOW_KERNEL_LAUNCHER=""
CAPABILITIES=()
INDEPENDENCE_RECEIPT_IDS=()
CAPABILITY_COUNT=0
INDEPENDENCE_RECEIPT_COUNT=0

usage() {
  printf '%s\n' 'usage: role-dispatch --role ROLE --capability CAP [--capability CAP ...] --effort EFFORT --workflow-kernel PATH --prompt-file PATH --output-file PATH --receipt-file PATH [--repository-evidence-file PATH] [--independence-receipt-dir DIR --independence-receipt-id ID ... | --human-authored] [--contract-digest SHA256 --contract-revision N]' >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --role) [ "$#" -ge 2 ] || usage; ROLE="$2"; shift 2 ;;
    --capability) [ "$#" -ge 2 ] || usage; CAPABILITIES+=("$2"); CAPABILITY_COUNT=$((CAPABILITY_COUNT + 1)); shift 2 ;;
    --effort) [ "$#" -ge 2 ] || usage; EFFORT="$2"; shift 2 ;;
    --prompt-file) [ "$#" -ge 2 ] || usage; PROMPT_FILE="$2"; shift 2 ;;
    --output-file) [ "$#" -ge 2 ] || usage; OUTPUT_FILE="$2"; shift 2 ;;
    --receipt-file) [ "$#" -ge 2 ] || usage; RECEIPT_FILE="$2"; shift 2 ;;
    --repository-evidence-file) [ "$#" -ge 2 ] || usage; REPOSITORY_EVIDENCE_FILE="$2"; shift 2 ;;
    --independence-receipt-dir) [ "$#" -ge 2 ] || usage; INDEPENDENCE_RECEIPT_DIR="$2"; shift 2 ;;
    --independence-receipt-id) [ "$#" -ge 2 ] || usage; INDEPENDENCE_RECEIPT_IDS+=("$2"); INDEPENDENCE_RECEIPT_COUNT=$((INDEPENDENCE_RECEIPT_COUNT + 1)); shift 2 ;;
    --human-authored) HUMAN_AUTHORED=1; shift ;;
    --contract-digest) [ "$#" -ge 2 ] || usage; CONTRACT_DIGEST="$2"; shift 2 ;;
    --contract-revision) [ "$#" -ge 2 ] || usage; CONTRACT_REVISION="$2"; shift 2 ;;
    --workflow-kernel) [ "$#" -ge 2 ] || usage; WORKFLOW_KERNEL_LAUNCHER="$2"; shift 2 ;;
    *) usage ;;
  esac
done

command -v jq >/dev/null 2>&1 || { printf '%s\n' 'role-dispatch: unavailable (missing runtime dependency)' >&2; exit 76; }
[ -r "$POLICY" ] && jq -e '.schemaVersion == 1' "$POLICY" >/dev/null 2>&1 || {
  printf '%s\n' 'role-dispatch: unavailable (invalid role policy)' >&2
  exit 76
}
MODEL_ROUTER_TEST_MODE="${MODEL_ROUTER_TEST_MODE:-0}"
case "$MODEL_ROUTER_TEST_MODE" in 0|1) ;; *) usage ;; esac
if [ "$MODEL_ROUTER_TEST_MODE" != 1 ] &&
   [ -n "${MODEL_ROUTER_AVAILABILITY_FILE:-}${MODEL_ROUTER_TRANSPORT_STUB:-}${MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS:-}" ]; then
  printf '%s\n' 'role-dispatch: test fixture hooks require MODEL_ROUTER_TEST_MODE=1' >&2
  exit 2
fi
case "$ROLE" in
  architect|plan-critic|builder-fast|builder-deep|review-fast|review-deep|security-review|research-fast|editorial) ;;
  *) usage ;;
esac
case "$EFFORT" in low|medium|high|max) ;; *) usage ;; esac
[ -f "$PROMPT_FILE" ] && [ -r "$PROMPT_FILE" ] && [ ! -L "$PROMPT_FILE" ] || usage
[ -z "$REPOSITORY_EVIDENCE_FILE" ] || {
  [ -f "$REPOSITORY_EVIDENCE_FILE" ] && [ -r "$REPOSITORY_EVIDENCE_FILE" ] && [ ! -L "$REPOSITORY_EVIDENCE_FILE" ] || usage
  [ "$REPOSITORY_EVIDENCE_FILE" != "$PROMPT_FILE" ] || usage
  [ ! "$REPOSITORY_EVIDENCE_FILE" -ef "$PROMPT_FILE" ] || usage
}
[ -n "$OUTPUT_FILE" ] && [ -n "$RECEIPT_FILE" ] || usage
[ "$OUTPUT_FILE" != "$RECEIPT_FILE" ] || usage
[ -d "$(dirname "$OUTPUT_FILE")" ] && [ -d "$(dirname "$RECEIPT_FILE")" ] || usage
[ ! -e "$OUTPUT_FILE" ] && [ ! -L "$OUTPUT_FILE" ] || usage
[ ! -e "$RECEIPT_FILE" ] && [ ! -L "$RECEIPT_FILE" ] || usage

VALID_CAPABILITIES='["read-repository","write-repository","tool-use","browser","long-context","structured-output","independent-family"]'
CAPABILITIES_JSON='[]'
if [ "$CAPABILITY_COUNT" -gt 0 ]; then
  for capability in "${CAPABILITIES[@]}"; do
    printf '%s' "$VALID_CAPABILITIES" | jq -e --arg capability "$capability" 'index($capability) != null' >/dev/null || usage
    CAPABILITIES_JSON="$(printf '%s' "$CAPABILITIES_JSON" | jq -c --arg capability "$capability" '. + [$capability] | unique | sort')"
  done
fi
if printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("independent-family") != null' >/dev/null &&
   [ "$INDEPENDENCE_RECEIPT_COUNT" -eq 0 ] && [ "$HUMAN_AUTHORED" -ne 1 ]; then
  printf '%s\n' 'role-dispatch: invalid independent-family request' >&2
  exit 2
fi
[ "$HUMAN_AUTHORED" -eq 0 ] || [ "$INDEPENDENCE_RECEIPT_COUNT" -eq 0 ] || usage
if ! printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("independent-family") != null' >/dev/null; then
  [ "$HUMAN_AUTHORED" -eq 0 ] && [ "$INDEPENDENCE_RECEIPT_COUNT" -eq 0 ] && [ -z "$INDEPENDENCE_RECEIPT_DIR" ] || usage
fi
if [ "$INDEPENDENCE_RECEIPT_COUNT" -gt 0 ]; then
  [ -n "$INDEPENDENCE_RECEIPT_DIR" ] && [ -d "$INDEPENDENCE_RECEIPT_DIR" ] && [ ! -L "$INDEPENDENCE_RECEIPT_DIR" ] || usage
fi
WRITE_REQUEST=0
if printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("write-repository") != null' >/dev/null; then
  WRITE_REQUEST=1
  [[ "$CONTRACT_DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || usage
  [[ "$CONTRACT_REVISION" =~ ^[1-9][0-9]*$ ]] || usage
fi
[ -z "$CONTRACT_REVISION" ] || CONTRACT_REVISION_JSON="$CONTRACT_REVISION"

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

if [ "$INDEPENDENCE_RECEIPT_COUNT" -gt 0 ]; then
  for prior_id in "${INDEPENDENCE_RECEIPT_IDS[@]}"; do
    case "$prior_id" in *[!a-z0-9-]*|'') usage ;; esac
    match=""
    for candidate_receipt in "$INDEPENDENCE_RECEIPT_DIR"/*; do
      [ -f "$candidate_receipt" ] && [ ! -L "$candidate_receipt" ] || continue
      if jq -e --arg receipt_id "$prior_id" '
        .receiptId == $receipt_id and
        .probeSource == "live" and
        .transportStub == false and
        (.served.family | type == "string")
      ' "$candidate_receipt" >/dev/null 2>&1; then
        match="$candidate_receipt"
        break
      fi
    done
    [ -n "$match" ] || { printf '%s\n' 'role-dispatch: invalid independence evidence' >&2; exit 2; }
    family="$(jq -r '.served.family' "$match")"
    EXCLUDED_FAMILIES="$(printf '%s' "$EXCLUDED_FAMILIES" | jq -c --arg family "$family" '. + [$family] | unique | sort')"
    INDEPENDENCE_IDS_JSON="$(printf '%s' "$INDEPENDENCE_IDS_JSON" | jq -c --arg receipt_id "$prior_id" '. + [$receipt_id] | unique | sort')"
  done
fi

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

OPENROUTER_BUNDLE_STATE="workflow_kernel_unavailable"
OPENROUTER_BUNDLE_REF=""
OPENROUTER_BUNDLE_ROOT=""
OPENROUTER_BUNDLE_VERSION=""
OPENROUTER_BUNDLE_CACHE_CLASS=""
OPENROUTER_BUNDLE_REASON=""
resolve_openrouter_bundle() {
  local active_host="" bundle_json bundle_ref
  case "$WORKFLOW_KERNEL_LAUNCHER" in /*/workflow-kernel-launcher.sh) ;; *) return 1 ;; esac
  [ -f "$WORKFLOW_KERNEL_LAUNCHER" ] && [ -x "$WORKFLOW_KERNEL_LAUNCHER" ] &&
    [ ! -L "$WORKFLOW_KERNEL_LAUNCHER" ] || return 1
  OPENROUTER_BUNDLE_STATE="provider_bundle_unavailable"
  [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && active_host=claude
  [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && active_host=codex
  args=(resolve-plugin-bundle --plugin openrouter --minimum-version 1.19.0
    --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh
    --required-asset skills/openrouter-delegate/references/openrouter-credential.sh
    --required-asset skills/openrouter-delegate/references/delegation-security-policy.json
    --required-executable skills/openrouter-delegate/references/delegation-boundary.sh)
  [ -n "$active_host" ] && args+=(--active-host "$active_host")
  bundle_json="$("$WORKFLOW_KERNEL_LAUNCHER" "${args[@]}" 2>/dev/null)" || return 1
  bundle_ref="$(printf '%s' "$bundle_json" | jq -r '.selected_root // empty')"
  case "$bundle_ref" in '~/'*) ;; *) return 1 ;; esac
  OPENROUTER_BUNDLE_REF="$bundle_ref"
  OPENROUTER_BUNDLE_ROOT="$HOME/${bundle_ref#\~/}"
  OPENROUTER_BUNDLE_VERSION="$(printf '%s' "$bundle_json" | jq -r '.version // empty')"
  OPENROUTER_BUNDLE_CACHE_CLASS="$(printf '%s' "$bundle_json" | jq -r '.cache_class // empty')"
  OPENROUTER_BUNDLE_REASON="$(printf '%s' "$bundle_json" | jq -r '.reason // empty')"
  [ -x "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/openrouter-wrapper.sh" ] &&
    [ -r "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/openrouter-credential.sh" ] &&
    [ -r "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-security-policy.json" ] &&
    [ -x "$OPENROUTER_BUNDLE_ROOT/skills/openrouter-delegate/references/delegation-boundary.sh" ] || return 1
  OPENROUTER_BUNDLE_STATE="resolved"
}
resolve_openrouter_bundle || true

if [ -n "${MODEL_ROUTER_AVAILABILITY_FILE:-}" ]; then
  [ -r "$MODEL_ROUTER_AVAILABILITY_FILE" ] && [ ! -L "$MODEL_ROUTER_AVAILABILITY_FILE" ] || usage
  AVAILABILITY="$(jq -c '. + {probeSource:"fixture"}' "$MODEL_ROUTER_AVAILABILITY_FILE")" || usage
else
  AVAILABILITY="$(OPENROUTER_BUNDLE_RESOLVED="$([ "$OPENROUTER_BUNDLE_STATE" = resolved ] && printf 1 || printf 0)" \
    OPENROUTER_BUNDLE_REF="$OPENROUTER_BUNDLE_REF" \
    OPENROUTER_BUNDLE_VERSION="$OPENROUTER_BUNDLE_VERSION" \
    OPENROUTER_BUNDLE_CACHE_CLASS="$OPENROUTER_BUNDLE_CACHE_CLASS" \
    OPENROUTER_BUNDLE_REASON="$OPENROUTER_BUNDLE_REASON" \
    MODEL_ROUTER_CODEX_CLI_PATH="$ROUTER_CODEX_CLI" \
    MODEL_ROUTER_CLAUDE_CLI_PATH="$ROUTER_CLAUDE_CLI" \
    "$DIR/availability-probe.sh" | jq -c '. + {probeSource:"live"}')" || AVAILABILITY='{"probeSource":"live"}'
fi
PROBE_SOURCE="$(printf '%s' "$AVAILABILITY" | jq -r '.probeSource')"
TRANSPORT_STUB=false
[ -z "${MODEL_ROUTER_TRANSPORT_STUB:-}" ] || TRANSPORT_STUB=true

ATTEMPTS='[]'
LAST_REASON="none"
if printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("browser") != null' >/dev/null; then
  # No current one-shot transport can prove access to the caller's local
  # interactive browser. Browser interaction remains host-owned.
  LAST_REASON="browser_transport_unavailable"
fi
ATTEMPT_INDEX=0
EXHAUSTED_TRANSPORTS='[]'
EXHAUSTED_MODELS='[]'
PRIVATE_LOG="$(mktemp "${TMPDIR:-/tmp}/model-router.log.XXXXXX")" || exit 76
TRANSPORT_OUTPUT="$(mktemp "${TMPDIR:-/tmp}/model-router.output.XXXXXX")" || { rm -f "$PRIVATE_LOG"; exit 76; }
PROVIDER_RECEIPT="$(mktemp "${TMPDIR:-/tmp}/model-router.provider.XXXXXX")" || { rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT"; exit 76; }
EMERGENCY_RECEIPT="$(mktemp "${TMPDIR:-/tmp}/model-router.mutation-receipt.XXXXXX")" || { rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT" "$PROVIDER_RECEIPT"; exit 76; }
PUBLIC_OUTPUT_TMP="$(mktemp "$(dirname "$OUTPUT_FILE")/.model-router-output.XXXXXX")" || { rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT" "$PROVIDER_RECEIPT" "$EMERGENCY_RECEIPT"; exit 76; }
PUBLIC_RECEIPT_TMP="$(mktemp "$(dirname "$RECEIPT_FILE")/.model-router-receipt.XXXXXX")" || { rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT" "$PROVIDER_RECEIPT" "$EMERGENCY_RECEIPT" "$PUBLIC_OUTPUT_TMP"; exit 76; }
PRESERVE_EMERGENCY_RECEIPT=0
cleanup() {
  rm -f "$PRIVATE_LOG" "$TRANSPORT_OUTPUT" "$PROVIDER_RECEIPT" "$PUBLIC_OUTPUT_TMP" "$PUBLIC_RECEIPT_TMP"
  [ "$PRESERVE_EMERGENCY_RECEIPT" -eq 1 ] || rm -f "$EMERGENCY_RECEIPT"
}
trap cleanup EXIT

publication_failed() {
  local reason="$1"
  PRESERVE_EMERGENCY_RECEIPT=1
  jq -n --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" \
    --arg reason "$reason" --arg receipt "$EMERGENCY_RECEIPT" \
    --argjson commit "${commit_json:-null}" \
    '{role:$role,participantId:$participant,disposition:"completed-publication-failed",fallback:false,fallbackReason:$reason,commit:$commit,privateReceipt:$receipt,output:null}'
  exit 76
}

candidate_has_capabilities() {
  local candidate="$1"
  jq -en --arg evidence "$REPOSITORY_EVIDENCE_FILE" --argjson requested "$CAPABILITIES_JSON" --argjson candidate "$candidate" '
    ($requested - ["independent-family"]) as $needed
    | all($needed[]; . as $cap | $candidate.capabilities | index($cap) != null)
    and (($requested | index("read-repository") | not)
      or $candidate.transport == "codex-cli" or $evidence != "")'
}

closed_openrouter_failure_reason() {
  local receipt="$1" failure_kind failure_reason http_status
  if ! jq -e 'type == "object"' "$receipt" >/dev/null 2>&1; then
    printf '%s\n' provider_transport_failed
    return
  fi
  failure_kind="$(jq -r '.failureKind // empty' "$receipt")"
  failure_reason="$(jq -r '.failureReason // empty' "$receipt")"
  http_status="$(jq -r '.httpStatus // empty' "$receipt")"
  if [ "$http_status" = 404 ]; then
    printf '%s\n' provider_model_unavailable
    return
  fi
  case "$failure_reason" in
    key_permission_denied) printf '%s\n' provider_credential_unavailable ;;
    guardrail_blocked) printf '%s\n' provider_boundary_declined ;;
    organization_monthly_budget_exceeded) printf '%s\n' organization_monthly_budget_exceeded ;;
    insufficient_credits) printf '%s\n' insufficient_credits ;;
    rate_limited) printf '%s\n' rate_limited ;;
    model_not_found|no_available_provider) printf '%s\n' provider_model_unavailable ;;
    unknown_http_error) printf '%s\n' unknown_provider_failure ;;
    "")
      case "$failure_kind" in
        transport_error|curl_timeout|stream_timeout|incomplete_stream|stream_error|malformed_stream)
          printf '%s\n' provider_transport_failed
          ;;
        *) printf '%s\n' unknown_provider_failure ;;
      esac
      ;;
    *) printf '%s\n' unknown_provider_failure ;;
  esac
}

transport_eligibility() {
  local transport="$1" model="$2" rate_limit_id="${3:-}" state auth_mode plan fable_state observed sdk_observed five weekly paid allowance_reason healthy_count allowance_count
  BILLING_MODE="unavailable"
  ALLOWANCE_WINDOW="unavailable"
  ELIGIBILITY_REASON="model_participant_unavailable"
  case "$transport" in
    codex-cli)
      if [ -z "$rate_limit_id" ]; then
        rate_limit_id="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.defaultAllowanceId // empty')"
        # Pre-0.3 fixture/observation files had one implicit legacy Codex
        # bucket and no allowances object. Preserve that closed single-bucket
        # interpretation without applying it to a 0.147 multi-bucket result.
        if [ -z "$rate_limit_id" ] &&
           [ "$(printf '%s' "$AVAILABILITY" | jq -r '.codex.allowances? | type')" != object ]; then
          rate_limit_id="codex"
        fi
      fi
      if [ -z "$rate_limit_id" ] &&
         [ "$(printf '%s' "$AVAILABILITY" | jq -r '.codex.allowances? | type')" = object ]; then
        allowance_count="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.allowances | length')"
        healthy_count="$(printf '%s' "$AVAILABILITY" | jq -r '[.codex.allowances[] | select(.state == "ok")] | length')"
        if [ "$allowance_count" -gt 0 ] && [ "$healthy_count" -gt 0 ]; then
          auth_mode="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.authMode // .codex.auth_mode // "unknown"')"
          [ "$auth_mode" = subscription ] || {
            ELIGIBILITY_REASON="model_participant_unavailable"
            return 1
          }
          BILLING_MODE="included-subscription"
          ALLOWANCE_WINDOW="mapping-unknown"
          ELIGIBILITY_REASON="attemptable"
          return 0
        fi
        if [ "$allowance_count" -gt 0 ] &&
           printf '%s' "$AVAILABILITY" | jq -e 'all(.codex.allowances[]; .state == "limited")' >/dev/null; then
          ELIGIBILITY_REASON="rate_limit_exhausted"
          return 1
        fi
        ELIGIBILITY_REASON="rate_limit_mapping_unknown"
        return 1
      fi
      [ -n "$rate_limit_id" ] || { ELIGIBILITY_REASON="rate_limit_mapping_unknown"; return 1; }
      if [ "$(printf '%s' "$AVAILABILITY" | jq -r '.codex.allowances? | type')" = object ]; then
        if ! printf '%s' "$AVAILABILITY" | jq -e --arg limit_id "$rate_limit_id" \
          '.codex.allowances | has($limit_id)' >/dev/null 2>&1; then
          ELIGIBILITY_REASON="rate_limit_mapping_unknown"
          return 1
        fi
        state="$(printf '%s' "$AVAILABILITY" | jq -r --arg limit_id "$rate_limit_id" '.codex.allowances[$limit_id].state')"
        allowance_reason="$(printf '%s' "$AVAILABILITY" | jq -r --arg limit_id "$rate_limit_id" '.codex.allowances[$limit_id].reason')"
      else
        [ "$rate_limit_id" = codex ] || {
          ELIGIBILITY_REASON="rate_limit_mapping_unknown"
          return 1
        }
        state="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.state // "unknown"')"
        allowance_reason="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.reason // "rate_limit_mapping_unknown"')"
      fi
      auth_mode="$(printf '%s' "$AVAILABILITY" | jq -r '.codex.authMode // .codex.auth_mode // "unknown"')"
      if [ "$state" != ok ] || [ "$auth_mode" != subscription ]; then
        [ "$state" != limited ] || allowance_reason="rate_limit_exhausted"
        case "$allowance_reason" in
          rate_limit_probe_no_response|rate_limit_response_malformed|rate_limit_shape_unsupported|rate_limit_mapping_unknown|required_window_missing|rate_limit_exhausted)
            ELIGIBILITY_REASON="$allowance_reason"
            ;;
          *) ELIGIBILITY_REASON="model_participant_unavailable" ;;
        esac
        return 1
      fi
      BILLING_MODE="included-subscription"
      ALLOWANCE_WINDOW="$rate_limit_id"
      ELIGIBILITY_REASON="available"
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
      if [ "$model" = fable ] && [ "$fable_state" = exhausted ]; then return 1; fi
      case "$plan" in
        max|pro|team-premium|enterprise-premium|included|unknown)
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
      if [ "$OPENROUTER_BUNDLE_STATE" != resolved ]; then
        ELIGIBILITY_REASON="$OPENROUTER_BUNDLE_STATE"
        return 1
      fi
      state="$(printf '%s' "$AVAILABILITY" | jq -r '.openrouter.state // "unknown"')"
      if [ "$state" != ok ]; then
        allowance_reason="$(printf '%s' "$AVAILABILITY" | jq -r '.openrouter.reason // "provider_availability_unknown"')"
        case "$allowance_reason" in
          provider_credential_unavailable|provider_availability_unknown) ELIGIBILITY_REASON="$allowance_reason" ;;
          *) ELIGIBILITY_REASON="provider_availability_unknown" ;;
        esac
        return 1
      fi
      BILLING_MODE="api"
      ALLOWANCE_WINDOW="api"
      ;;
    *) return 1 ;;
  esac
}

invoke_candidate() {
  local transport="$1" model="$2" effective="$3" rc=0 root system_file prompt_copy result_json sandbox
  INVOKE_REASON=""
  : > "$TRANSPORT_OUTPUT"
  : > "$PROVIDER_RECEIPT"
  if [ -n "${MODEL_ROUTER_TRANSPORT_STUB:-}" ]; then
    argv=("$MODEL_ROUTER_TRANSPORT_STUB" --transport "$transport" --model "$model" --effort "$effective" --prompt-file "$PROMPT_FILE" --output-file "$TRANSPORT_OUTPUT" --provider-receipt-file "$PROVIDER_RECEIPT")
    "${argv[@]}" 2>>"$PRIVATE_LOG"
    return $?
  fi
  case "$transport" in
    codex-cli)
      [ -n "$ROUTER_CODEX_CLI" ] && [ -x "$ROUTER_CODEX_CLI" ] || return 77
      sandbox=read-only
      printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("write-repository") != null' >/dev/null && sandbox=workspace-write
      prompt_copy="$(mktemp "${TMPDIR:-/tmp}/model-router.prompt.XXXXXX")" || return 1
      cp "$PROMPT_FILE" "$prompt_copy" || { rm -f "$prompt_copy"; return 1; }
      if [ "$WRITE_REQUEST" -eq 1 ]; then
        printf '\n\n--- bound behavioral contract ---\ncontract_digest: %s\ncontract_revision: %s\n' \
          "$CONTRACT_DIGEST" "$CONTRACT_REVISION" >> "$prompt_copy"
      fi
      argv=("$ROUTER_CODEX_CLI" exec --model "$model" --config "model_reasoning_effort=\"$effective\"" --sandbox "$sandbox" --ephemeral --output-last-message "$TRANSPORT_OUTPUT")
      git_root="$(git rev-parse --show-toplevel 2>/dev/null)" && argv+=(--cd "$git_root")
      invoke_native_sanitized "${argv[@]}" < "$prompt_copy" >>"$PRIVATE_LOG" 2>&1
      rc=$?
      rm -f "$prompt_copy"
      return "$rc"
      ;;
    claude-cli)
      [ -n "$ROUTER_CLAUDE_CLI" ] && [ -x "$ROUTER_CLAUDE_CLI" ] || return 77
      prompt_copy="$(mktemp "${TMPDIR:-/tmp}/model-router.prompt.XXXXXX")" || return 1
      cp "$PROMPT_FILE" "$prompt_copy" || { rm -f "$prompt_copy"; return 1; }
      if [ -n "$REPOSITORY_EVIDENCE_FILE" ] && [ "$REPOSITORY_EVIDENCE_FILE" != "$PROMPT_FILE" ]; then
        printf '\n\n--- complete repository evidence ---\n' >> "$prompt_copy"
        cat "$REPOSITORY_EVIDENCE_FILE" >> "$prompt_copy"
      fi
      if [ "$WRITE_REQUEST" -eq 1 ]; then
        printf '\n\n--- bound behavioral contract ---\ncontract_digest: %s\ncontract_revision: %s\n' \
          "$CONTRACT_DIGEST" "$CONTRACT_REVISION" >> "$prompt_copy"
      fi
      argv=("$ROUTER_CLAUDE_CLI" -p --model "$model" --effort "$effective" --tools "" --no-session-persistence --output-format json)
      result_json="$(invoke_native_sanitized "${argv[@]}" < "$prompt_copy" 2>>"$PRIVATE_LOG")" || { rc=$?; rm -f "$prompt_copy"; return "$rc"; }
      rm -f "$prompt_copy"
      printf '%s' "$result_json" | jq -r '.result // empty' > "$TRANSPORT_OUTPUT" || return 1
      printf '%s' "$result_json" > "$PROVIDER_RECEIPT"
      ;;
    openrouter)
      root="$OPENROUTER_BUNDLE_ROOT"
      [ "$OPENROUTER_BUNDLE_STATE" = resolved ] || { INVOKE_REASON="$OPENROUTER_BUNDLE_STATE"; return 77; }
      if printf '%s' "$CAPABILITIES_JSON" | jq -e 'index("write-repository") != null' >/dev/null; then
        [ -n "${OPENROUTER_EXEC_ALLOWED_PATHS:-}" ] || return 77
        argv=("$DIR/openrouter-write-adapter.sh" --model "$model")
        MODEL_ROUTER_CONTRACT_DIGEST="$CONTRACT_DIGEST" \
          MODEL_ROUTER_CONTRACT_REVISION="$CONTRACT_REVISION" \
          OPENROUTER_BUNDLE_RESOLVED=1 OPENROUTER_BUNDLE_REF="$OPENROUTER_BUNDLE_REF" \
          OPENROUTER_BUNDLE_VERSION="$OPENROUTER_BUNDLE_VERSION" \
          OPENROUTER_BUNDLE_CACHE_CLASS="$OPENROUTER_BUNDLE_CACHE_CLASS" \
          OPENROUTER_BUNDLE_REASON="$OPENROUTER_BUNDLE_REASON" \
          "${argv[@]}" < "$PROMPT_FILE" > "$PROVIDER_RECEIPT" 2>>"$PRIVATE_LOG" || return $?
        jq -n --arg digest "$CONTRACT_DIGEST" --argjson revision "$CONTRACT_REVISION" \
          '{status:"committed",verification:"required",contract_digest:$digest,revision:$revision}' > "$TRANSPORT_OUTPUT"
      else
        system_file="$(mktemp "${TMPDIR:-/tmp}/model-router.system.XXXXXX")" || return 1
        prompt_copy="$(mktemp "${TMPDIR:-/tmp}/model-router.prompt.XXXXXX")" || { rm -f "$system_file"; return 1; }
        printf '%s' 'Return only the requested analysis. You have no command authority.' > "$system_file"
        cp "$PROMPT_FILE" "$prompt_copy"
        if [ -n "$REPOSITORY_EVIDENCE_FILE" ] && [ "$REPOSITORY_EVIDENCE_FILE" != "$PROMPT_FILE" ]; then
          printf '\n\n--- complete repository evidence ---\n' >> "$prompt_copy"
          cat "$REPOSITORY_EVIDENCE_FILE" >> "$prompt_copy"
        fi
        argv=("$root/skills/openrouter-delegate/references/delegation-boundary.sh" --mode artifact-delegation --policy "$root/skills/openrouter-delegate/references/delegation-security-policy.json" --content-file "$system_file" --content-file "$prompt_copy")
        "${argv[@]}" >>"$PRIVATE_LOG" 2>&1 || { INVOKE_REASON="provider_boundary_declined"; rm -f "$system_file" "$prompt_copy"; return 77; }
        argv=(bash "$root/skills/openrouter-delegate/references/openrouter-wrapper.sh" "$model" - 3600)
        env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$system_file" \
          OPENROUTER_WORKLOAD=mechanical OPENROUTER_WEB_SEARCH=0 \
          OPENROUTER_RECEIPT_FILE="$PROVIDER_RECEIPT" "${argv[@]}" \
          < "$prompt_copy" > "$TRANSPORT_OUTPUT" 2>>"$PRIVATE_LOG"
        rc=$?
        if [ "$rc" -ne 0 ]; then
          INVOKE_REASON="$(closed_openrouter_failure_reason "$PROVIDER_RECEIPT")"
        fi
        rm -f "$system_file" "$prompt_copy"
        return "$rc"
      fi
      ;;
  esac
}

invoke_native_sanitized() {
  env -u OPENROUTER_API_KEY -u OPENROUTER_API_KEY_FILE \
    -u OPENROUTER_BUNDLE_REF -u OPENROUTER_BUNDLE_VERSION \
    -u OPENROUTER_BUNDLE_CACHE_CLASS -u OPENROUTER_BUNDLE_REASON \
    -u OPENROUTER_BUNDLE_RESOLVED "$@"
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
  rate_limit_id="$(printf '%s' "$candidate" | jq -r '.rateLimitId // empty')"
  if printf '%s' "$EXHAUSTED_TRANSPORTS" | jq -e --arg value "$transport" 'index($value) != null' >/dev/null ||
     printf '%s' "$EXHAUSTED_MODELS" | jq -e --arg value "$model" 'index($value) != null' >/dev/null; then
    continue
  fi
  ATTEMPT_INDEX=$((ATTEMPT_INDEX + 1))
  if ! transport_eligibility "$transport" "$model" "$rate_limit_id"; then
    reason="$ELIGIBILITY_REASON"
    ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg reason "$reason" '. + [{model:$model,provider:$provider,transport:$transport,outcome:"skipped",reason:$reason}]')"
    LAST_REASON="$reason"
    continue
  fi
  EFFECTIVE_EFFORT="$(jq -r --arg transport "$transport" --arg effort "$EFFORT" '.effort.transports[$transport][$effort]' "$POLICY")"
  ATTEMPT_HEAD=""
  ATTEMPT_STATUS=""
  if [ "$WRITE_REQUEST" -eq 1 ]; then
    ATTEMPT_HEAD="$(git rev-parse --verify HEAD 2>/dev/null)" || exit 76
    ATTEMPT_STATUS="$(git status --porcelain=v1 --untracked-files=all 2>/dev/null)" || exit 76
  fi
  STARTED="$(date +%s)"
  : > "$PRIVATE_LOG"
  fixture_outcome="$(printf '%s' "$AVAILABILITY" | jq -r --arg model "$model" '.candidateResults[$model].outcome // ""')"
  if [ "$WRITE_REQUEST" -eq 1 ] && [ "$PROBE_SOURCE" = live ] &&
     [ "$TRANSPORT_STUB" = false ] && [ -n "$ATTEMPT_STATUS" ]; then
    printf '%s\n' 'repository-not-clean' > "$PRIVATE_LOG"
    rc=79
  elif [ "$PROBE_SOURCE" = fixture ] &&
     [ -z "${MODEL_ROUTER_TRANSPORT_STUB:-}" ] &&
     [ "${MODEL_ROUTER_INVOKE_FIXTURE_TRANSPORTS:-0}" != 1 ]; then
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
  if [ "$WRITE_REQUEST" -eq 1 ] && [ "$PROBE_SOURCE" = live ] &&
     [ "$TRANSPORT_STUB" = false ] && [ "$rc" -eq 0 ] && [ -s "$TRANSPORT_OUTPUT" ]; then
    CURRENT_HEAD="$(git rev-parse --verify HEAD 2>/dev/null)" || exit 76
    CURRENT_STATUS="$(git status --porcelain=v1 --untracked-files=all 2>/dev/null)" || exit 76
    if [ "$CURRENT_HEAD" = "$ATTEMPT_HEAD" ]; then
      printf '%s\n' 'write-completion-without-commit' > "$PRIVATE_LOG"
      rc=79
    elif [ "$CURRENT_STATUS" != "$ATTEMPT_STATUS" ]; then
      printf '%s\n' 'write-completion-dirty' > "$PRIVATE_LOG"
      rc=79
    fi
  fi
  DURATION_SECONDS=$(( $(date +%s) - STARTED ))
  if [ "$rc" -eq 0 ] && [ -s "$TRANSPORT_OUTPUT" ]; then
    usage_json=null
    cost_json=null
    commit_json=null
    files_changed_json=null
    token_provenance=unavailable
    cost_provenance=unavailable
    if jq -e . "$PROVIDER_RECEIPT" >/dev/null 2>&1; then
      usage_json="$(jq -c '.usage // null' "$PROVIDER_RECEIPT")"
      cost_json="$(jq -c 'if has("costUsd") then .costUsd elif has("cost_usd") then .cost_usd elif (.usage | type) == "object" and (.usage | has("cost")) then .usage.cost else null end' "$PROVIDER_RECEIPT")"
      [ "$usage_json" = null ] || token_provenance=provider-receipt
      [ "$cost_json" = null ] || cost_provenance=provider-receipt
      commit_json="$(jq -c 'if (.commit | type) == "string" and (.commit | length) > 0 then .commit else null end' "$PROVIDER_RECEIPT")"
      files_changed_json="$(jq -c 'if (.filesChanged | type) == "string" then .filesChanged else null end' "$PROVIDER_RECEIPT")"
    fi
    if [ "$WRITE_REQUEST" -eq 1 ] && [ "$commit_json" = null ]; then
      commit_json="$(jq -Rn --arg commit "${CURRENT_HEAD:-}" '$commit')"
    fi
    ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg billing "$BILLING_MODE" --argjson duration "$DURATION_SECONDS" '. + [{model:$model,provider:$provider,transport:$transport,billingMode:$billing,outcome:"served",durationSeconds:$duration}]')"
    fallback=false
    fallback_reason=none
    [ "$ATTEMPT_INDEX" -gt 1 ] && { fallback=true; fallback_reason="$LAST_REASON"; }
    jq -n --arg receipt_id "$RECEIPT_ID" --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg requested_effort "$EFFORT" --arg effective_effort "$EFFECTIVE_EFFORT" --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg family "$family" --arg billing "$BILLING_MODE" --arg allowance_window "$ALLOWANCE_WINDOW" --arg matrix "$MATRIX_SNAPSHOT" --arg fallback_reason "$fallback_reason" --arg token_provenance "$token_provenance" --arg cost_provenance "$cost_provenance" --arg contract_digest "$CONTRACT_DIGEST" --arg probe_source "$PROBE_SOURCE" --argjson transport_stub "$TRANSPORT_STUB" --argjson contract_revision "$CONTRACT_REVISION_JSON" --argjson requested_candidate "$REQUESTED_CANDIDATE" --argjson capabilities "$CAPABILITIES_JSON" --argjson attempts "$ATTEMPTS" --argjson independence_ids "$INDEPENDENCE_IDS_JSON" --argjson excluded_families "$EXCLUDED_FAMILIES" --argjson fallback "$fallback" --argjson human_authored "$([ "$HUMAN_AUTHORED" -eq 1 ] && printf true || printf false)" --argjson duration "$DURATION_SECONDS" --argjson usage "$usage_json" --argjson cost "$cost_json" --argjson commit "$commit_json" --argjson files_changed "$files_changed_json" '{schemaVersion:1,receiptId:$receipt_id,probeSource:$probe_source,transportStub:$transport_stub,requested:{role:$role,capabilities:$capabilities,effort:$requested_effort,independenceReceiptIds:$independence_ids,humanAuthored:$human_authored,candidate:{model:$requested_candidate.model,provider:$requested_candidate.provider,transport:$requested_candidate.transport}},contract_digest:(if $contract_digest == "" then null else $contract_digest end),revision:$contract_revision,participantId:$participant,attempts:$attempts,served:{model:$model,provider:$provider,transport:$transport,family:$family,billingMode:$billing,allowanceWindow:$allowance_window,durationSeconds:$duration,tokens:$usage,tokenProvenance:$token_provenance,billedCostUsd:$cost,costProvenance:$cost_provenance,commit:$commit,filesChanged:$files_changed},effectiveEffort:$effective_effort,effortNormalized:($requested_effort != $effective_effort),fallback:$fallback,fallbackReason:$fallback_reason,matrixSnapshot:$matrix,publication:{output:"pending"},familyIndependence:{required:(($independence_ids|length>0) or $human_authored),humanAuthored:$human_authored,excludedFamilies:$excluded_families,passed:true}}' > "$EMERGENCY_RECEIPT" || exit 76
    cp "$TRANSPORT_OUTPUT" "$PUBLIC_OUTPUT_TMP" 2>/dev/null || publication_failed output-preparation-failed
    jq '.publication.output="published"' "$EMERGENCY_RECEIPT" > "$PUBLIC_RECEIPT_TMP" || publication_failed receipt-preparation-failed
    mv "$PUBLIC_OUTPUT_TMP" "$OUTPUT_FILE" 2>/dev/null || publication_failed output-publication-failed
    mv "$PUBLIC_RECEIPT_TMP" "$RECEIPT_FILE" 2>/dev/null || publication_failed receipt-publication-failed
    jq -n --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg requested_effort "$EFFORT" --arg effective_effort "$EFFECTIVE_EFFORT" --arg output "$OUTPUT_FILE" --arg probe_source "$PROBE_SOURCE" --argjson transport_stub "$TRANSPORT_STUB" --argjson capabilities "$CAPABILITIES_JSON" --argjson fallback "$fallback" --argjson human_authored "$([ "$HUMAN_AUTHORED" -eq 1 ] && printf true || printf false)" --argjson excluded_family_count "$(printf '%s' "$EXCLUDED_FAMILIES" | jq 'length')" '{role:$role,capabilities:$capabilities,requestedEffort:$requested_effort,effectiveEffort:$effective_effort,participantId:$participant,disposition:"completed",fallback:$fallback,evidenceSource:$probe_source,transportStub:$transport_stub,familyIndependence:{humanAuthored:$human_authored,excludedFamilyCount:$excluded_family_count},output:$output}'
    exit 0
  fi
  if [ -n "${INVOKE_REASON:-}" ]; then reason="$INVOKE_REASON"
  elif grep -Fqi 'repository-not-clean' "$PRIVATE_LOG"; then reason=repository-not-clean
  elif grep -Fqi 'write-completion-without-commit' "$PRIVATE_LOG"; then reason=write-completion-without-commit
  elif grep -Fqi 'write-completion-dirty' "$PRIVATE_LOG"; then reason=write-completion-dirty
  elif grep -qiE 'usage.?limit|rate.?limit|quota|exhausted' "$PRIVATE_LOG"; then
    if [ "$transport" = codex-cli ]; then reason=rate_limit_exhausted; else reason=quota-exhausted; fi
  elif grep -qiE 'declin|refus' "$PRIVATE_LOG"; then reason=content-refusal
  else reason=transport-unavailable
  fi
  ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg model "$model" --arg provider "$provider" --arg transport "$transport" --arg billing "$BILLING_MODE" --arg reason "$reason" --argjson duration "$DURATION_SECONDS" '. + [{model:$model,provider:$provider,transport:$transport,billingMode:$billing,outcome:"failed",reason:$reason,durationSeconds:$duration}]')"
  if [ "$WRITE_REQUEST" -eq 1 ]; then
    CURRENT_HEAD="$(git rev-parse --verify HEAD 2>/dev/null)" || exit 76
    CURRENT_STATUS="$(git status --porcelain=v1 --untracked-files=all 2>/dev/null)" || exit 76
    if [ "$CURRENT_HEAD" != "$ATTEMPT_HEAD" ] || [ "$CURRENT_STATUS" != "$ATTEMPT_STATUS" ]; then
      reason=repository-mutated-on-failed-attempt
      ATTEMPTS="$(printf '%s' "$ATTEMPTS" | jq -c --arg reason "$reason" '.[-1].reason=$reason')"
      LAST_REASON="$reason"
      break
    fi
  fi
  if [ "$reason" = quota-exhausted ] || [ "$reason" = rate_limit_exhausted ]; then
    if [ "$transport" = codex-cli ]; then
      EXHAUSTED_TRANSPORTS="$(printf '%s' "$EXHAUSTED_TRANSPORTS" | jq -c --arg value "$transport" '. + [$value] | unique')"
    else
      EXHAUSTED_MODELS="$(printf '%s' "$EXHAUSTED_MODELS" | jq -c --arg value "$model" '. + [$value] | unique')"
    fi
  fi
  LAST_REASON="$reason"
done <<< "$CANDIDATES"

jq -n --arg receipt_id "$RECEIPT_ID" --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg effort "$EFFORT" --arg matrix "$MATRIX_SNAPSHOT" --arg reason "$LAST_REASON" --arg probe_source "$PROBE_SOURCE" --argjson transport_stub "$TRANSPORT_STUB" --argjson requested_candidate "$REQUESTED_CANDIDATE" --argjson capabilities "$CAPABILITIES_JSON" --argjson attempts "$ATTEMPTS" --argjson independence_ids "$INDEPENDENCE_IDS_JSON" --argjson excluded_families "$EXCLUDED_FAMILIES" --argjson human_authored "$([ "$HUMAN_AUTHORED" -eq 1 ] && printf true || printf false)" '{schemaVersion:1,receiptId:$receipt_id,probeSource:$probe_source,transportStub:$transport_stub,requested:{role:$role,capabilities:$capabilities,effort:$effort,independenceReceiptIds:$independence_ids,humanAuthored:$human_authored,candidate:{model:$requested_candidate.model,provider:$requested_candidate.provider,transport:$requested_candidate.transport}},participantId:$participant,attempts:$attempts,served:null,effectiveEffort:$effort,effortNormalized:false,fallback:true,fallbackReason:$reason,matrixSnapshot:$matrix,familyIndependence:{required:(($independence_ids|length>0) or $human_authored),humanAuthored:$human_authored,excludedFamilies:$excluded_families,passed:false}}' > "$RECEIPT_FILE"
jq -n --arg role "$ROLE" --arg participant "$PARTICIPANT_ID" --arg effort "$EFFORT" --arg probe_source "$PROBE_SOURCE" --argjson transport_stub "$TRANSPORT_STUB" --argjson capabilities "$CAPABILITIES_JSON" --argjson human_authored "$([ "$HUMAN_AUTHORED" -eq 1 ] && printf true || printf false)" --argjson excluded_family_count "$(printf '%s' "$EXCLUDED_FAMILIES" | jq 'length')" '{role:$role,capabilities:$capabilities,requestedEffort:$effort,effectiveEffort:$effort,participantId:$participant,disposition:"unavailable",fallback:true,evidenceSource:$probe_source,transportStub:$transport_stub,familyIndependence:{humanAuthored:$human_authored,excludedFamilyCount:$excluded_family_count},output:null}'
exit 76
