#!/usr/bin/env bash
# availability-probe.sh -- private live availability evidence for model-router.
#
# Parser baselines probed 2026-08-08: Claude Code 2.1.220 statusLine
# rate_limits; Codex CLI 0.146.0 app-server account/rateLimits/read; curl
# 8.7.1 against OpenRouter /api/v1/credits. Claude subscription telemetry is
# session-scoped and may be absent before the first response; absence remains
# distinct from exhaustion.
#
# Subscription rails emit one conservative limiting-window object:
#   {"state":"ok|limited|unknown","remaining_pct":<number>,"window":"<name>"}
# OpenRouter is an auto-reloading API balance rail:
#   {"state":"ok|unknown","balance_usd":<number|null>}
#
# No operator identity, email, plan, quota, or billing preference is persisted.
set -uo pipefail

# Resolve supported CLIs from the operator's incoming PATH, then reset PATH
# before every other lookup. Exact machine paths are process-local evidence.
CODEX_CLI="$(command -v codex 2>/dev/null || true)"
CLAUDE_CLI="$(command -v claude 2>/dev/null || true)"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Every emission path below builds JSON with jq. Without jq the script would
# print a blank line and exit 0, and the consumer would see an unrecognized
# shape rather than the mandated unknown object. Absent jq is exactly the
# "tool is absent" case, so answer it in jq-free literal form and stop.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' '{"probe_source":"live","codex":{"state":"unknown","authMode":"unknown"},"claude":{"state":"unknown","authMode":"unknown","plan":"unknown","rateLimitsObserved":false,"agentSdkRateLimitsObserved":false,"fable":"unknown"},"openrouter":{"state":"unknown","balance_usd":null}}'
  exit 0
fi

THRESHOLD="$(jq -r '.availability.headroomThresholdPct // 8' "$SCRIPT_DIR/role-policy.json" 2>/dev/null)"
case "$THRESHOLD" in ''|*[!0-9]*) THRESHOLD=8 ;; esac
# Portable bash 3.2 watchdog. A wedged CLI must resolve to unknown, not hang
# the caller forever. No `timeout(1)` on stock macOS, so background + poll.
run_bounded() {
  local limit="$1"; shift
  local tmp rc waited
  tmp="$(mktemp "${TMPDIR:-/tmp}/usage-probe.XXXXXX")" || return 1
  ( "$@" >"$tmp" 2>&1 ) &
  local pid=$!
  waited=0
  while [ "$waited" -lt "$limit" ]; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
    waited=$((waited + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null
    sleep 1
    kill -KILL "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    rm -f "$tmp"
    return 124
  fi
  wait "$pid" 2>/dev/null; rc=$?
  cat "$tmp" 2>/dev/null
  rm -f "$tmp"
  return "$rc"
}

aggregate_windows() {
  local required="$1" observations="$2"
  jq -cn --argjson required "$required" --argjson observations "$observations" \
    --argjson threshold "$THRESHOLD" '
      [ $required[] as $window
        | (($observations | map(select(.window == $window)) | first) // null) as $seen
        | if $seen == null then
            {state:"unknown", remaining_pct:0, window:$window}
          elif (($seen.remaining_pct | type) != "number")
            or $seen.remaining_pct < 0 or $seen.remaining_pct > 100 then
            {state:"unknown", remaining_pct:0, window:$window}
          else
            {state:(if $seen.remaining_pct <= $threshold then "limited" else "ok" end),
             remaining_pct:$seen.remaining_pct, window:$window}
          end
      ] as $normalized
      | (($normalized | map(select(.state == "unknown")) | first)
         // ($normalized | min_by(.remaining_pct))) as $limiting
      | $limiting + {windows: ($normalized | map({key:.window, value:.}) | from_entries)}
    '
}

normalize_claude_plan() {
  local raw
  raw="$(printf '%s' "${1:-unknown}" | tr '[:upper:]_' '[:lower:]-')"
  case "$raw" in
    max|max-*|*-max) printf '%s\n' max ;;
    pro|pro-*|*-pro) printf '%s\n' pro ;;
    premium-team|team-premium) printf '%s\n' team-premium ;;
    premium-enterprise|enterprise-premium) printf '%s\n' enterprise-premium ;;
    credits-only) printf '%s\n' credits-only ;;
    included) printf '%s\n' included ;;
    *) printf '%s\n' unknown ;;
  esac
}

claude_json() {
  local auth='{}' auth_method="unknown" auth_mode="unknown" state="unavailable"
  local telemetry='{}' observations='[]' sdk_observations='[]' plan="unknown" telemetry_plan="" fable="unknown"
  local observed=false sdk_observed=false windows sdk_windows window_state sdk_state
  if [ -n "$CLAUDE_CLI" ] && [ -x "$CLAUDE_CLI" ]; then
    auth="$(run_bounded 10 "$CLAUDE_CLI" auth status --json 2>/dev/null)" || auth='{}'
    auth_method="$(printf '%s' "$auth" | jq -r '.authMethod // "unknown"' 2>/dev/null)"
    plan="$(normalize_claude_plan "$(printf '%s' "$auth" | jq -r '.subscriptionType // .subscription_type // .plan // "unknown"' 2>/dev/null)")"
    if printf '%s' "$auth" | jq -e '.loggedIn == true' >/dev/null 2>&1; then
      case "$(printf '%s' "$auth_method" | tr '[:upper:]' '[:lower:]')" in
        *api*|*key*|*console*) auth_mode="api" ;;
        *claude.ai*|*oauth*|*subscription*|*max*|*team*|*enterprise*) auth_mode="subscription" ;;
        *) auth_mode="unknown" ;;
      esac
      state="unknown"
    fi
  fi
  # A host may provide its fresh session statusLine rate_limits object in a
  # private file. The file is observation input, never tracked routing policy.
  if [ -n "${MODEL_ROUTER_CLAUDE_RATE_LIMITS_FILE:-}" ] &&
     [ -f "$MODEL_ROUTER_CLAUDE_RATE_LIMITS_FILE" ] &&
     [ ! -L "$MODEL_ROUTER_CLAUDE_RATE_LIMITS_FILE" ]; then
    telemetry="$(jq -c '.' "$MODEL_ROUTER_CLAUDE_RATE_LIMITS_FILE" 2>/dev/null)" || telemetry='{}'
    telemetry_plan="$(printf '%s' "$telemetry" | jq -r '.plan // empty')"
    [ -z "$telemetry_plan" ] || plan="$(normalize_claude_plan "$telemetry_plan")"
    fable="$(printf '%s' "$telemetry" | jq -r '.fable // "unknown"')"
    observations="$(printf '%s' "$telemetry" | jq -c '[
      ((.rate_limits.five_hour // empty) | select(.used_percentage | type == "number") | {window:"five_hour",remaining_pct:(100-.used_percentage)}),
      ((.rate_limits.seven_day // empty) | select(.used_percentage | type == "number") | {window:"weekly",remaining_pct:(100-.used_percentage)})
    ]')"
    sdk_observations="$(printf '%s' "$telemetry" | jq -c '
      (.agent_sdk_rate_limits // .rate_limits.agent_sdk // {}) as $sdk
      | [
        (($sdk.five_hour // empty) | select(.used_percentage | type == "number") | {window:"five_hour",remaining_pct:(100-.used_percentage)}),
        (($sdk.seven_day // empty) | select(.used_percentage | type == "number") | {window:"weekly",remaining_pct:(100-.used_percentage)})
      ]')"
    [ "$(printf '%s' "$observations" | jq 'length')" -gt 0 ] && observed=true
    [ "$(printf '%s' "$sdk_observations" | jq 'length')" -gt 0 ] && sdk_observed=true
  fi
  windows="$(aggregate_windows '["five_hour","weekly"]' "$observations")"
  sdk_windows="$(aggregate_windows '["five_hour","weekly"]' "$sdk_observations")"
  window_state="$(printf '%s' "$windows" | jq -r '.state')"
  sdk_state="$(printf '%s' "$sdk_windows" | jq -r '.state')"
  if [ "$auth_mode" = subscription ]; then
    if { [ "$observed" = true ] && [ "$window_state" = ok ]; } ||
       { [ "$sdk_observed" = true ] && [ "$sdk_state" = ok ]; }; then
      state=ok
    elif { [ "$observed" = true ] && [ "$window_state" = limited ]; } ||
         { [ "$sdk_observed" = true ] && [ "$sdk_state" = limited ]; }; then
      state=limited
    fi
  fi
  printf '%s' "$windows" | jq -c --arg state "$state" --arg auth_mode "$auth_mode" \
    --arg plan "$plan" --arg fable "$fable" --argjson observed "$observed" \
    --argjson sdk_observed "$sdk_observed" --argjson sdk_windows "$sdk_windows" \
    '. + {state:$state,authMode:$auth_mode,plan:$plan,fable:$fable,
      rateLimitsObserved:$observed,agentSdkRateLimitsObserved:$sdk_observed,
      allowances:{interactive:.,agent_sdk:$sdk_windows}}'
}

codex_app_server_output() {
  [ -n "$CODEX_CLI" ] && [ -x "$CODEX_CLI" ] || return 1
  {
    printf '%s\n' \
      '{"method":"initialize","id":0,"params":{"clientInfo":{"name":"depot-usage-probe","title":"Depot usage probe","version":"1"},"capabilities":{"experimentalApi":true}}}' \
      '{"method":"initialized","params":{}}' \
      '{"method":"account/rateLimits/read","id":7,"params":{}}'
  } | run_bounded 20 "$CODEX_CLI" app-server --stdio 2>/dev/null
}

codex_json() {
  local out="" observations='[]' auth_mode="unknown" state="unknown" windows
  if [ -n "$CODEX_CLI" ] && [ -x "$CODEX_CLI" ]; then
    login="$(run_bounded 10 "$CODEX_CLI" login status 2>/dev/null)" || login=""
    case "$login" in *'Logged in using ChatGPT'*) auth_mode="subscription" ;; *'API key'*) auth_mode="api" ;; esac
  fi
  if out="$(codex_app_server_output)"; then
    if [ -n "$out" ]; then
      observations="$(printf '%s\n' "$out" | jq -sc '
        (map(select(.id == 7 and .result.rateLimits != null)) | last
          | .result.rateLimits // {}) as $limits
        | [$limits.primary, $limits.secondary]
        | map(select(type == "object"
            and (.usedPercent | type) == "number"
            and (.windowDurationMins | type) == "number")
          | {window:(if .windowDurationMins == 300 then "five_hour"
                     elif .windowDurationMins == 10080 then "weekly"
                     else ("window_" + (.windowDurationMins | tostring) + "m") end),
             remaining_pct:([0, (100 - .usedPercent), 100] | sort | .[1])})
      ' 2>/dev/null)" || observations='[]'
    fi
  fi
  [ -n "$observations" ] || observations='[]'
  windows="$(aggregate_windows '["five_hour","weekly"]' "$observations")"
  [ "$auth_mode" = subscription ] && [ "$(printf '%s' "$windows" | jq -r '.state')" = ok ] && state=ok
  printf '%s' "$windows" | jq -c --arg state "$state" --arg auth_mode "$auth_mode" \
    '. + {state:$state,authMode:$auth_mode}'
}

openrouter_json() {
  local response="" rc=0 balance="" credential_loader="" active_host="" bundle_json="" bundle_ref="" header_file="" probe_key=""
  if [ -n "${OPENROUTER_API_KEY_FILE:-}" ] && [ -z "${OPENROUTER_API_KEY:-}" ]; then
    case "${OPENROUTER_BUNDLE_RESOLVED:-0}:${OPENROUTER_BUNDLE_REF:-}" in
      "1:~/"*) credential_loader="$HOME/${OPENROUTER_BUNDLE_REF#\~/}/skills/openrouter-delegate/references/openrouter-credential.sh" ;;
    esac
    # Standalone probes may resolve once for themselves. Cascade callers always
    # supply the complete process-local binding above, preventing mixed roots.
    if [ -z "$credential_loader" ] && [ -n "${WORKFLOW_KERNEL:-}" ] && [ -x "$WORKFLOW_KERNEL" ]; then
      [ -n "${CLAUDE_CODE:-}${CLAUDECODE:-}" ] && active_host="claude"
      [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ] && active_host="codex"
      if [ -n "$active_host" ]; then
        bundle_json=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
          --minimum-version 1.19.0 --active-host "$active_host" \
          --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
          --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
          --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
          --required-executable skills/openrouter-delegate/references/delegation-boundary.sh) || bundle_json=""
      else
        bundle_json=$("$WORKFLOW_KERNEL" resolve-plugin-bundle --plugin openrouter \
          --minimum-version 1.19.0 \
          --required-executable skills/openrouter-delegate/references/openrouter-wrapper.sh \
          --required-asset skills/openrouter-delegate/references/openrouter-credential.sh \
          --required-asset skills/openrouter-delegate/references/delegation-security-policy.json \
          --required-executable skills/openrouter-delegate/references/delegation-boundary.sh) || bundle_json=""
      fi
      bundle_ref=$(printf '%s' "$bundle_json" | jq -r '.selected_root // empty')
      case "$bundle_ref" in
        "~/"*) credential_loader="$HOME/${bundle_ref#\~/}/skills/openrouter-delegate/references/openrouter-credential.sh" ;;
      esac
    fi
    if [ -r "$credential_loader" ]; then
      # shellcheck source=/dev/null
      . "$credential_loader"
      load_openrouter_api_key || OPENROUTER_API_KEY=""
    fi
  fi
  if [ -n "${OPENROUTER_API_KEY:-}" ] && command -v curl >/dev/null 2>&1; then
    header_file="$(mktemp "${TMPDIR:-/tmp}/openrouter-probe.header.XXXXXX")" || header_file=""
    [ -z "$header_file" ] || chmod 600 "$header_file"
    if [ -n "$header_file" ]; then
      trap 'rm -f "$header_file"' EXIT
      trap 'exit 130' HUP INT TERM
    fi
    probe_key="$OPENROUTER_API_KEY"
    [ -z "$header_file" ] || printf 'Authorization: Bearer %s\n' "$probe_key" > "$header_file"
    unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE
    if [ -z "$header_file" ]; then
      rc=1
    else
    response="$(curl -sS --max-time 10 https://openrouter.ai/api/v1/credits \
      -H "@$header_file" 2>/dev/null)" || rc=$?
    fi
    [ -z "$header_file" ] || rm -f "$header_file"
    trap - EXIT HUP INT TERM
    if [ "$rc" -eq 0 ] && [ -n "$response" ]; then
      balance="$(printf '%s' "$response" \
        | jq -r '.data as $data
            | select($data | type == "object")
            | select($data.total_credits | type == "number")
            | select($data.total_usage | type == "number")
            | ($data.total_credits - $data.total_usage)' 2>/dev/null)" || balance=""
    fi
  fi
  case "$balance" in ''|*[!0-9.+-]*) balance="" ;; esac
  # This account auto-reloads, so the retired $5 low-balance cutoff is not an
  # availability boundary. A finite non-negative balance is positive evidence
  # that the API balance probe worked; missing, malformed, or negative values
  # remain unknown and fail closed at role dispatch.
  local state="unknown"
  if [ -n "$balance" ]; then
    if awk -v b="$balance" 'BEGIN{exit !(b >= 0)}'; then state="ok"; fi
  fi
  jq -cn --arg balance "$balance" --arg state "$state" \
    '{state:$state,
      balance_usd:(if $balance == "" then null else ($balance | tonumber) end)}'
}

result="$(jq -cn --argjson codex "$(codex_json)" \
  --argjson claude "$(claude_json)" --argjson openrouter "$(openrouter_json)" \
  '{probe_source:"live",codex:$codex,claude:$claude,openrouter:$openrouter}')"

printf '%s\n' "$result"
