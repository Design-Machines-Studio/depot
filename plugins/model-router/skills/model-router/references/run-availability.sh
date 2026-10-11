#!/usr/bin/env bash
# Read only this owner's ordered receipt index. No global cache or new state.
load_run_failures() {
  RUN_FAILURES='[]'
  [ -n "${RUN_RECEIPT_INDEX:-}" ] || return 0
  [ -f "$RUN_RECEIPT_INDEX" ] && [ ! -L "$RUN_RECEIPT_INDEX" ] || return 2
  local parent name receipt
  parent="$(cd "$(dirname "$RUN_RECEIPT_INDEX")" && pwd -P)" || return 2
  [ "$parent" = "$(cd "$(dirname "$RUN_RECEIPT_INDEX")" && pwd -L)" ] || return 2
  jq -e 'type == "object" and (keys | sort) == ["receiptFiles","schemaVersion"] and
    .schemaVersion == 1 and (.receiptFiles | type == "array" and length <= 256) and
    all(.receiptFiles[]; type == "string" and
      test("^[A-Za-z0-9][A-Za-z0-9._-]{0,126}\\.json$") and
      . != "terminal-receipt-index.json")' "$RUN_RECEIPT_INDEX" >/dev/null || return 2
  while IFS= read -r name; do
    receipt="$parent/$name"
    # Missing in-flight entries have no evidence. Unsafe existing entries fail closed.
    [ ! -L "$receipt" ] || return 2
    [ -e "$receipt" ] || continue
    [ -f "$receipt" ] && [ -r "$receipt" ] || return 2
    local failures
    failures="$(jq -c '
      if .schemaVersion == 1 and .probeSource == "live" and .transportStub == false
      then [.attempts[]? | select(.failureConfirmed == true and .outcome != "served") |
        select((.failureScope == "rail" and
          (.reason | IN("rate_limit_exhausted","quota-exhausted","provider_credential_unavailable","authentication-unavailable","insufficient_credits","organization_monthly_budget_exceeded"))) or
          (.failureScope == "model" and
          (.reason | IN("provider_model_unavailable","fast_mode_unavailable","fast_mode_unsupported")))) |
        select(.transport | IN("codex-cli","claude-cli","openrouter")) |
        {transport,model,scope:.failureScope,reason}]
      else [] end' "$receipt")" || return 2
    RUN_FAILURES="$(jq -cn --argjson prior "$RUN_FAILURES" --argjson next "$failures" '$prior + $next | unique')" || return 2
  done < <(jq -r '.receiptFiles[]' "$RUN_RECEIPT_INDEX")
}

run_failure_reason() {
  jq -r --arg transport "$1" --arg model "$2" '
    [.[] | select(.transport == $transport and (.scope == "rail" or .model == $model))][0].reason // empty
  ' <<< "$RUN_FAILURES"
}

# One Claude eligibility contract for recommendation and dispatch. Unknown
# subscription quota permits a bounded attempt; confirmed limits close it.
claude_candidate_eligibility() {
  local model="$1" billing="$2" state auth plan paid observed sdk five="" weekly="" window remaining window_limited=false window_exhausted=false
  local THRESHOLD
  THRESHOLD="$(jq -r '.availability.headroomThresholdPct' "$POLICY")"
  BILLING_MODE=unavailable
  ALLOWANCE_WINDOW=unavailable
  ELIGIBILITY_REASON=model_participant_unavailable
  state="$(jq -r '.claude.state // "unknown"' <<< "$AVAILABILITY")"
  auth="$(jq -r '.claude.authMode // .claude.auth_mode // "unknown"' <<< "$AVAILABILITY")"
  plan="$(jq -r '.claude.plan // "unknown"' <<< "$AVAILABILITY")"
  paid="$(jq -r '.claude.paidCreditsEnabled // empty' <<< "$AVAILABILITY")"
  [ -n "$paid" ] || paid="$PAID_CLAUDE_CREDITS"
  [ "$auth" = subscription ] && [ "$state" != unavailable ] || return 1
  if [ "$model" = fable ] && jq -e '(.claude.fable // .claude.fableAvailability) | IN("exhausted","unavailable")' <<< "$AVAILABILITY" >/dev/null; then
    return 1
  fi
  if [ "$plan" = credits-only ]; then
    [ "$billing" != included-subscription ] && [ "$paid" = true ] || return 1
    BILLING_MODE=paid-credits; ALLOWANCE_WINDOW=paid-credits; ELIGIBILITY_REASON=attemptable
    return 0
  fi
  case "$plan" in max|pro|team-premium|enterprise-premium|included|unknown) ;; *) return 1 ;; esac
  # The SDK bucket applies to noninteractive calls when it is observed.
  sdk="$(jq -r '.claude.agentSdkRateLimitsObserved // false' <<< "$AVAILABILITY")"
  observed="$(jq -r '.claude.rateLimitsObserved // false' <<< "$AVAILABILITY")"
  window=unknown
  if [ "$sdk" = true ]; then
    state="$(jq -r '.claude.allowances.agent_sdk.state // "unknown"' <<< "$AVAILABILITY")"
    five="$(jq -r '.claude.allowances.agent_sdk.windows.five_hour.remaining_pct // empty' <<< "$AVAILABILITY")"
    weekly="$(jq -r '.claude.allowances.agent_sdk.windows.weekly.remaining_pct // empty' <<< "$AVAILABILITY")"
    window=agent-sdk
  elif [ "$observed" = true ]; then
    five="$(jq -r '.claude.windows.five_hour.remaining_pct // .claude.fiveHourRemainingPct // empty' <<< "$AVAILABILITY")"
    weekly="$(jq -r '.claude.windows.weekly.remaining_pct // .claude.weeklyRemainingPct // empty' <<< "$AVAILABILITY")"
    window=interactive
  fi
  # Inspect every observed window before classifying the account. A numeric
  # zero takes precedence over reserved positive headroom in a sibling window.
  for remaining in "$five" "$weekly"; do
    [ -n "$remaining" ] || continue
    if jq -en --arg value "$remaining" '$value | tonumber? | . >= 0 and . <= 100' >/dev/null; then
      if awk -v value="$remaining" 'BEGIN{exit !(value==0)}'; then window_exhausted=true; fi
      if ! awk -v value="$remaining" -v t="$THRESHOLD" 'BEGIN{exit !(value>t)}'; then window_limited=true; fi
    fi
  done
  if [ "$state" = exhausted ] || [ "$window_exhausted" = true ]; then
    ELIGIBILITY_REASON=rate_limit_exhausted
    return 1
  fi
  if [ "$state" = limited ] || [ "$window_limited" = true ]; then
    ELIGIBILITY_REASON=reserve_threshold_reached
    return 1
  fi
  if [ "$window" != unknown ] && jq -en --arg a "$five" --arg b "$weekly" '
    [$a,$b] | all(.[]; (tonumber? // -1) >= 0 and (tonumber? // -1) <= 100)' >/dev/null; then
    BILLING_MODE=included-subscription; ALLOWANCE_WINDOW="$window"; ELIGIBILITY_REASON=available
  else
    BILLING_MODE=subscription-headroom-unknown; ALLOWANCE_WINDOW=unknown; ELIGIBILITY_REASON=attemptable
  fi
  return 0
}
