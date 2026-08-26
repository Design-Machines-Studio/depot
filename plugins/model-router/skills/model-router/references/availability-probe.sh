#!/usr/bin/env bash
# availability-probe.sh -- private live availability evidence for model-router.
#
# Parser baselines: Claude Code 2.1.220 statusLine rate_limits; Codex CLI
# 0.146.0 and 0.147.0 app-server account/rateLimits/read; curl 8.7.1 against
# OpenRouter /api/v1/credits. Claude subscription telemetry is session-scoped
# and may be absent before the first response; absence remains distinct from
# exhaustion.
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

wait_for_rpc_response() {
  local response_file="$1" response_id="$2" server_pid="$3" limit="$4" waited=0
  while [ "$waited" -lt "$limit" ]; do
    if jq -s -e --argjson response_id "$response_id" \
      'any(.[]; .id? == $response_id)' "$response_file" >/dev/null 2>&1; then
      return 0
    fi
    kill -0 "$server_pid" 2>/dev/null || return 1
    sleep 1
    waited=$((waited + 1))
  done
  return 1
}

# Current consumer: codex_json below. This bounded FIFO exchange prevents the
# 0.147 app-server from receiving account requests before initialization has
# completed, replacing the former fire-and-forget three-line pipe.
codex_app_server_exchange() (
  local rpc_dir request_fifo response_file error_file server_pid="" rpc_timeout response
  [ -n "$CODEX_CLI" ] && [ -x "$CODEX_CLI" ] || {
    jq -cn '{state:"closed",reason:"rate_limit_probe_no_response"}'
    exit 0
  }
  rpc_timeout="${MODEL_ROUTER_CODEX_RPC_TIMEOUT:-15}"
  case "$rpc_timeout" in ''|*[!0-9]*|0) rpc_timeout=15 ;; esac
  [ "$rpc_timeout" -le 30 ] || rpc_timeout=30
  rpc_dir="$(mktemp -d "${TMPDIR:-/tmp}/codex-rate-limit-rpc.XXXXXX")" || {
    jq -cn '{state:"closed",reason:"rate_limit_probe_no_response"}'
    exit 0
  }
  request_fifo="$rpc_dir/request"
  response_file="$rpc_dir/response"
  error_file="$rpc_dir/error"
  : > "$response_file"
  : > "$error_file"
  mkfifo "$request_fifo" || {
    rm -rf "$rpc_dir"
    jq -cn '{state:"closed",reason:"rate_limit_probe_no_response"}'
    exit 0
  }
  cleanup_codex_rpc() {
    exec 3>&- 2>/dev/null || true
    if [ -n "$server_pid" ] && kill -0 "$server_pid" 2>/dev/null; then
      kill -TERM "$server_pid" 2>/dev/null || true
      sleep 1
      kill -KILL "$server_pid" 2>/dev/null || true
    fi
    [ -z "$server_pid" ] || wait "$server_pid" 2>/dev/null || true
    rm -rf "$rpc_dir"
  }
  trap cleanup_codex_rpc EXIT
  trap 'exit 130' HUP INT TERM

  "$CODEX_CLI" app-server --stdio < "$request_fifo" > "$response_file" 2> "$error_file" &
  server_pid=$!
  exec 3> "$request_fifo" || {
    jq -cn '{state:"closed",reason:"rate_limit_probe_no_response"}'
    exit 0
  }
  printf '%s\n' '{"method":"initialize","id":0,"params":{"clientInfo":{"name":"depot-usage-probe","title":"Depot usage probe","version":"1"},"capabilities":{"experimentalApi":true}}}' >&3
  if ! wait_for_rpc_response "$response_file" 0 "$server_pid" "$rpc_timeout"; then
    jq -cn '{state:"closed",reason:"rate_limit_probe_no_response"}'
    exit 0
  fi
  response="$(jq -sc 'map(select(.id? == 0)) | last' "$response_file" 2>/dev/null)" || response=""
  if ! printf '%s' "$response" | jq -e \
    'type == "object" and .id == 0 and (.result | type) == "object" and (.error? == null)' >/dev/null 2>&1; then
    jq -cn '{state:"closed",reason:"rate_limit_response_malformed"}'
    exit 0
  fi

  printf '%s\n' \
    '{"method":"initialized","params":{}}' \
    '{"method":"account/rateLimits/read","id":7,"params":{}}' >&3
  if ! wait_for_rpc_response "$response_file" 7 "$server_pid" "$rpc_timeout"; then
    jq -cn '{state:"closed",reason:"rate_limit_probe_no_response"}'
    exit 0
  fi
  response="$(jq -sc 'map(select(.id? == 7)) | last' "$response_file" 2>/dev/null)" || response=""
  if ! printf '%s' "$response" | jq -e \
    'type == "object" and .id == 7 and (.result | type) == "object" and (.error? == null)' >/dev/null 2>&1; then
    jq -cn '{state:"closed",reason:"rate_limit_response_malformed"}'
    exit 0
  fi
  jq -cn --argjson response "$response" '{state:"response",response:$response}'
)

normalize_codex_snapshot() {
  local snapshot="$1"
  printf '%s' "$snapshot" | jq -c --argjson threshold "$THRESHOLD" '
    def closed($reason): {state:"unknown",reason:$reason};
    if type != "object" then closed("rate_limit_response_malformed")
    else
      [.primary?, .secondary?]
      | map(select(. != null)) as $raw
      | if any($raw[]; type != "object"
          or (.usedPercent | type) != "number"
          or .usedPercent < 0 or .usedPercent > 100
          or (.windowDurationMins | type) != "number") then
          closed("rate_limit_response_malformed")
        else
          [$raw[] | {
            window:(if .windowDurationMins == 300 then "five_hour"
                    elif .windowDurationMins == 10080 then "weekly"
                    else "unsupported" end),
            remaining:(100 - .usedPercent)
          }] as $windows
          | if any($windows[]; .window == "unsupported")
              or ([$windows[] | select(.window == "five_hour")] | length) != 1
              or ([$windows[] | select(.window == "weekly")] | length) != 1 then
              closed("required_window_missing")
            elif any($windows[]; .remaining <= $threshold) then
              {state:"limited",reason:"rate_limit_exhausted"}
            else
              {state:"ok",reason:"available"}
            end
        end
    end'
}

codex_json() {
  local exchange='{}' response='{}' result='{}' auth_mode="unknown" state="unknown"
  local reason="rate_limit_probe_no_response" allowances='{}' map_type="" entry key normalized
  local default_allowance_id=""
  if [ -n "$CODEX_CLI" ] && [ -x "$CODEX_CLI" ]; then
    login="$(run_bounded 10 "$CODEX_CLI" login status 2>/dev/null)" || login=""
    case "$login" in *'Logged in using ChatGPT'*) auth_mode="subscription" ;; *'API key'*) auth_mode="api" ;; esac
  fi
  exchange="$(codex_app_server_exchange)" || exchange='{"state":"closed","reason":"rate_limit_probe_no_response"}'
  if [ "$(printf '%s' "$exchange" | jq -r '.state // "closed"')" != response ]; then
    reason="$(printf '%s' "$exchange" | jq -r '.reason // "rate_limit_probe_no_response"')"
  else
    response="$(printf '%s' "$exchange" | jq -c '.response')"
    result="$(printf '%s' "$response" | jq -c '.result')"
    map_type="$(printf '%s' "$result" | jq -r 'if has("rateLimitsByLimitId") then (.rateLimitsByLimitId | type) else "absent" end')"
    if [ "$map_type" = object ]; then
      if [ "$(printf '%s' "$result" | jq '.rateLimitsByLimitId | length')" -eq 0 ] ||
         ! printf '%s' "$result" | jq -e '
           .rateLimitsByLimitId
           | all(to_entries[]; (.value | type) == "object"
               and (.value.limitId | type) == "string"
               and .value.limitId == .key)' >/dev/null 2>&1; then
        reason="rate_limit_response_malformed"
      else
        while IFS= read -r entry; do
          key="$(printf '%s' "$entry" | jq -r '.key')"
          normalized="$(normalize_codex_snapshot "$(printf '%s' "$entry" | jq -c '.value')")"
          allowances="$(printf '%s' "$allowances" | jq -c --arg key "$key" --argjson value "$normalized" '. + {($key):$value}')"
        done <<EOF
$(printf '%s' "$result" | jq -c '.rateLimitsByLimitId | to_entries[]')
EOF
        if printf '%s' "$allowances" | jq -e 'any(to_entries[]; .value.reason == "rate_limit_response_malformed")' >/dev/null; then
          reason="rate_limit_response_malformed"
        elif [ "$(printf '%s' "$allowances" | jq 'length')" -eq 1 ]; then
          # A single returned bucket is unambiguous. Multiple 0.147 buckets
          # require an authoritative candidate mapping at dispatch time; the
          # app-server does not currently expose that join.
          default_allowance_id="$(printf '%s' "$allowances" | jq -r 'keys[0]')"
          state="$(printf '%s' "$allowances" | jq -r --arg key "$default_allowance_id" '.[$key].state')"
          reason="$(printf '%s' "$allowances" | jq -r --arg key "$default_allowance_id" '.[$key].reason')"
        else
          if printf '%s' "$allowances" | jq -e 'all(.[]; .state == "limited")' >/dev/null; then
            state="limited"
            reason="rate_limit_exhausted"
          else
            # Bucket ownership remains unknown, but a healthy allowance makes
            # an authenticated candidate attemptable at dispatch time. Do not
            # select or attribute a bucket here.
            state="unknown"
            reason="rate_limit_mapping_unknown"
          fi
        fi
      fi
    elif [ "$map_type" != absent ] && [ "$map_type" != null ]; then
      reason="rate_limit_response_malformed"
    elif printf '%s' "$result" | jq -e '(.rateLimits | type) == "object"' >/dev/null 2>&1; then
      normalized="$(normalize_codex_snapshot "$(printf '%s' "$result" | jq -c '.rateLimits')")"
      allowances="$(jq -cn --argjson normalized "$normalized" '{codex:$normalized}')"
      default_allowance_id="codex"
      state="$(printf '%s' "$normalized" | jq -r '.state')"
      reason="$(printf '%s' "$normalized" | jq -r '.reason')"
    else
      reason="rate_limit_shape_unsupported"
    fi
  fi
  [ "$auth_mode" = subscription ] || state=unknown
  jq -cn --arg state "$state" --arg auth_mode "$auth_mode" --arg reason "$reason" \
    --arg default_allowance_id "$default_allowance_id" --argjson allowances "$allowances" \
    '{state:$state,authMode:$auth_mode,reason:$reason,allowances:$allowances,
      allowanceCount:($allowances | length)}
      + if $default_allowance_id == "" then {} else {defaultAllowanceId:$default_allowance_id} end'
}

openrouter_json() {
  local response="" rc=0 balance="" credential_loader="" active_host="" bundle_json="" bundle_ref="" header_file="" probe_key="" credential_state="missing"
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
  if [ -n "${OPENROUTER_API_KEY:-}" ]; then
    credential_state="available"
  fi
  if [ "$credential_state" = available ] && command -v curl >/dev/null 2>&1; then
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
  local state="unknown" reason="provider_availability_unknown"
  if [ -n "$balance" ]; then
    if awk -v b="$balance" 'BEGIN{exit !(b >= 0)}'; then state="ok"; reason="available"; fi
  fi
  [ "$credential_state" = available ] || reason="provider_credential_unavailable"
  jq -cn --arg balance "$balance" --arg state "$state" --arg reason "$reason" \
    '{state:$state,reason:$reason,
      balance_usd:(if $balance == "" then null else ($balance | tonumber) end)}'
}

result="$(jq -cn --argjson codex "$(codex_json)" \
  --argjson claude "$(claude_json)" --argjson openrouter "$(openrouter_json)" \
  '{probe_source:"live",codex:$codex,claude:$claude,openrouter:$openrouter}')"

printf '%s\n' "$result"
