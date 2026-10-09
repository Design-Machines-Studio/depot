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
