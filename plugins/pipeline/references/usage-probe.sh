#!/usr/bin/env bash
# usage-probe.sh -- gauge conservative remaining headroom per routing rail.
#
# Parser baselines probed 2026-08-08: Claude Code 2.1.220 statusLine
# rate_limits; Codex CLI 0.146.0 app-server account/rateLimits/read; curl
# 8.7.1 against OpenRouter /api/v1/credits. ccusage is deliberately not a live
# source because its block output does not provide both required limiting
# windows; Claude therefore remains unknown outside explicit statusLine tests.
#
# Subscription rails emit one conservative limiting-window object:
#   {"state":"ok|limited|unknown","remaining_pct":<number>,"window":"<name>"}
# OpenRouter is an auto-reloading API balance rail:
#   {"state":"ok|unknown","balance_usd":<number|null>}
#
# Known rails use built-in probes. Other subscriptions declared in the local
# operator profile run their trusted profile command under the same reset PATH. A custom
# command must emit one common limiting-window object that conservatively
# represents every window declared by that entry. Non-zero, malformed, or unmappable output becomes unknown at
# the policy threshold.
set -uo pipefail

# Reset PATH before any command lookup, including profile-declared probes.
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROBE_SOURCE="live"
if [ "${USAGE_PROBE_TEST_MODE:-0}" = "1" ]; then
  PROBE_SOURCE="fixture"
  echo "usage-probe: TEST FIXTURE MODE active; headroom is not live capacity evidence" >&2
fi

# Every emission path below builds JSON with jq. Without jq the script would
# print a blank line and exit 0, and the consumer would see an unrecognized
# shape rather than the mandated unknown object. Absent jq is exactly the
# "tool is absent" case, so answer it in jq-free literal form and stop.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' "{\"probe_source\":\"$PROBE_SOURCE\",\"codex\":{\"state\":\"unknown\",\"remaining_pct\":0,\"window\":\"unknown\"},\"claude\":{\"state\":\"unknown\",\"remaining_pct\":0,\"window\":\"unknown\"},\"openrouter\":{\"state\":\"unknown\",\"balance_usd\":null}}"
  exit 0
fi

THRESHOLD="$(jq -r '.policy.headroom_threshold_pct // 8' "$SCRIPT_DIR/model-cascade.json" 2>/dev/null)"
case "$THRESHOLD" in ''|*[!0-9]*) THRESHOLD=8 ;; esac

# Portable bash 3.2 watchdog. A wedged CLI must resolve to unknown, not hang
# the caller forever. No `timeout(1)` on stock macOS, so background + poll.
run_bounded() {
  local limit="$1"; shift
  local tmp rc waited
  tmp="$(mktemp "${TMPDIR:-/tmp}/usage-probe.XXXXXX")" || return 1
  ( "$@" >"$tmp" 2>/dev/null ) &
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

unknown_json() {
  jq -cn --argjson threshold "$THRESHOLD" --arg window "${1:-unknown}" \
    '{state:"unknown",remaining_pct:0,window:$window}'
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

claude_statusline_input() {
  # These three inputs are CALLER-SUPPLIED usage numbers, so they are test
  # fixtures, not evidence. Accepting them in normal operation would let anyone
  # who controls the environment assert used_percentage 0 for both required
  # windows and report Claude "ok" while its real headroom is unknown or
  # exhausted. That is the optimistic direction this file exists to prevent,
  # so they are honoured only under an explicit test mode.
  #
  # Outside test mode this probe has no live Claude source: it is not a
  # statusLine command and cannot see the runtime's rate_limits payload. It
  # therefore reports Claude as unknown, which resolves to no headroom. That is
  # the truthful answer, not a degradation.
  [ "${USAGE_PROBE_TEST_MODE:-0}" = "1" ] || return 0
  if [ -n "${USAGE_PROBE_CLAUDE_STATUSLINE_JSON:-}" ]; then
    printf '%s' "$USAGE_PROBE_CLAUDE_STATUSLINE_JSON"
  elif [ -n "${USAGE_PROBE_CLAUDE_STATUSLINE_FILE:-}" ] \
       && [ -r "$USAGE_PROBE_CLAUDE_STATUSLINE_FILE" ]; then
    command cat "$USAGE_PROBE_CLAUDE_STATUSLINE_FILE" 2>/dev/null || true
  elif [ "${USAGE_PROBE_CLAUDE_STATUSLINE_STDIN:-0}" = "1" ] && [ ! -t 0 ]; then
    # Only read stdin when the caller explicitly asks. Orchestrators routinely
    # spawn scripts with an open-but-idle pipe on fd 0, and a bare `cat` there
    # blocks until the writer closes -- hanging the probe rather than
    # reporting unknown.
    command cat 2>/dev/null || true
  fi
}

claude_json() {
  local statusline="" observations='[]'
  statusline="$(claude_statusline_input)"
  if [ -n "$statusline" ]; then
    observations="$(printf '%s' "$statusline" | jq -c '
      [ {window:"five_hour", value:(.rate_limits.five_hour // null)},
        {window:"weekly", value:(.rate_limits.weekly // .rate_limits.seven_day // null)} ]
      | map(select(.value != null and (.value.used_percentage | type) == "number")
        | {window:.window, remaining_pct:([0, (100 - .value.used_percentage), 100] | sort | .[1])})
    ' 2>/dev/null)" || observations='[]'
  fi
  [ -n "$observations" ] || observations='[]'

  aggregate_windows '["five_hour","weekly"]' "$observations"
}

codex_app_server_output() {
  # The injected response is a deterministic parser fixture only. Production
  # always obtains these bytes from the Codex app server itself.
  if [ "${USAGE_PROBE_TEST_MODE:-0}" = "1" ] \
     && [ -n "${USAGE_PROBE_CODEX_APP_SERVER_JSON:-}" ]; then
    printf '%s\n' "$USAGE_PROBE_CODEX_APP_SERVER_JSON"
    return 0
  fi

  command -v codex >/dev/null 2>&1 || return 1
  {
    printf '%s\n' \
      '{"method":"initialize","id":0,"params":{"clientInfo":{"name":"depot-usage-probe","title":"Depot usage probe","version":"1"},"capabilities":{"experimentalApi":true}}}' \
      '{"method":"initialized","params":{}}' \
      '{"method":"account/rateLimits/read","id":7,"params":{}}'
  } | run_bounded 20 codex app-server --stdio 2>/dev/null
}

codex_json() {
  local out="" observations='[]'
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
  aggregate_windows '["five_hour","weekly"]' "$observations"
}

openrouter_json() {
  local response="" rc=0 balance=""
  if [ -n "${OPENROUTER_API_KEY:-}" ] && command -v curl >/dev/null 2>&1; then
    response="$(curl -sS --max-time 10 https://openrouter.ai/api/v1/credits \
      -H "Authorization: Bearer $OPENROUTER_API_KEY" 2>/dev/null)" || rc=$?
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
  # remain unknown and fail closed in cascade-dispatch.sh.
  local state="unknown"
  if [ -n "$balance" ]; then
    if awk -v b="$balance" 'BEGIN{exit !(b >= 0)}'; then state="ok"; fi
  fi
  jq -cn --arg balance "$balance" --arg state "$state" \
    '{state:$state,
      balance_usd:(if $balance == "" then null else ($balance | tonumber) end)}'
}

normalize_profile_probe() {
  local output="$1" windows="$2" first_window
  first_window="$(printf '%s' "$windows" | jq -r '.[0] // "unknown"')"
  printf '%s' "$output" | jq -sce --argjson windows "$windows" \
    --argjson threshold "$THRESHOLD" '
      select(length == 1) | .[0]
      | select(type == "object")
      | .window as $window
      | select((.state == "ok" or .state == "limited" or .state == "unknown")
          and ($window | type) == "string"
          and ($windows | index($window)) != null)
      | if .state == "unknown" then
          {state:"unknown", remaining_pct:0, window:.window}
        elif ((.remaining_pct | type) == "number"
          and .remaining_pct >= 0 and .remaining_pct <= 100) then
          # An explicit "limited" is never upgraded to "ok". A provider hard
          # cap or account hold is not percentage-shaped, so a probe may report
          # limited alongside a healthy-looking remaining_pct; discarding that
          # signal would move in the optimistic direction, which this
          # invariant exists to prevent.
          {state:(if .state == "limited" or .remaining_pct <= $threshold
                  then "limited" else "ok" end),
           remaining_pct:.remaining_pct, window:.window}
        else empty end
    ' 2>/dev/null || unknown_json "$first_window"
}

operator_profile_path() {
  local root="" common_dir="" root_physical="" candidate="" candidate_parent=""
  local resolved_parent="" expected_parent="" test_override=0
  # An environment-selected profile path is a test fixture, not production
  # input: the profile supplies argv this script executes, so letting the
  # environment point it at any untracked file defeats the "developer-local
  # config" boundary the contract claims. In normal operation only the
  # canonical repository path is resolved.
  if [ "${USAGE_PROBE_TEST_MODE:-0}" = "1" ] && [ -n "${DM_OPERATOR_PROFILE_FILE:-}" ]; then
    candidate="$DM_OPERATOR_PROFILE_FILE"
    test_override=1
  else
    # Resolve host-owned local configuration from the COMMON checkout, never
    # from the ambient linked worktree. Pipeline chunk output lives in linked
    # worktrees and must not be able to plant executable local configuration
    # merely by writing an ignored `.dm` file there.
    common_dir="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)" \
      || common_dir=""
    [ -n "$common_dir" ] && [ -d "$common_dir" ] || return 0
    common_dir="$(cd "$common_dir" 2>/dev/null && pwd -P)" || return 0
    [ "${common_dir##*/}" = ".git" ] || return 0
    root="${common_dir%/.git}"
    candidate="$root/.dm/operator-profile.local.json"
  fi
  # A profile supplies probe argv that this script executes, so the file itself
  # is a trust boundary. It is legitimate only as untracked developer-local
  # config.
  #
  # Refuse a symlink: it can redirect the read outside the checkout.
  [ -L "$candidate" ] && return 0
  [ -f "$candidate" ] || return 0
  if [ "$test_override" -eq 0 ]; then
    # `-L "$candidate"` checks only the final component. A tracked `.dm`
    # symlink can otherwise redirect the regular profile file to a different
    # repository path while the literal `.dm/operator-profile.local.json`
    # path remains absent from the index. Compare physical parents so every
    # intermediate component is covered without trusting `realpath(1)` to be
    # present on stock macOS.
    root_physical="$(cd "$root" 2>/dev/null && pwd -P)" || return 0
    candidate_parent="$(dirname "$candidate")"
    resolved_parent="$(cd "$candidate_parent" 2>/dev/null && pwd -P)" || return 0
    expected_parent="$root_physical/.dm"
    [ "$resolved_parent" = "$expected_parent" ] || return 0
    candidate="$resolved_parent/operator-profile.local.json"
  fi
  # Refuse a git-TRACKED profile. This is the live vector, not a theoretical
  # one: .gitignore is routinely defeated by `git add -f` in this repository
  # (several plans/ subtrees are ignored and tracked anyway), so a branch could
  # ship .dm/operator-profile.local.json and have every later run execute its
  # probes. An ignored-but-committed file is not developer-local config.
  if [ "$test_override" -eq 0 ]; then
    git -C "$root" ls-files --error-unmatch -- \
      .dm/operator-profile.local.json >/dev/null 2>&1 && return 0
  elif git ls-files --error-unmatch -- "$candidate" >/dev/null 2>&1; then
    return 0
  fi
  printf '%s\n' "$candidate"
}

profile="$(operator_profile_path)"
result="$(jq -cn --arg source "$PROBE_SOURCE" --argjson codex "$(codex_json)" \
  --argjson claude "$(claude_json)" --argjson openrouter "$(openrouter_json)" \
  '{probe_source:$source,codex:$codex,claude:$claude,openrouter:$openrouter}')"

if [ -n "$profile" ] && [ -r "$profile" ] \
   && jq -e 'type == "object"
     and (.operator | type) == "string" and (.operator | length) > 0
     and (.updated | type) == "string" and (.updated | length) > 0
     and (.familyPreferenceOrder | type) == "array"
     and all(.familyPreferenceOrder[]; type == "string" and length > 0)
     and (.neverUse | type) == "array"
     and all(.neverUse[]; type == "string" and length > 0)
     and (.subscriptions | type) == "array"
     and all(.subscriptions[];
       type == "object" and (.rail | type) == "string" and (.rail | length) > 0
       and ((.probe == "none")
            or ((.probe | type) == "array" and (.probe | length) > 0
                and all(.probe[]; type == "string" and length > 0)))
       and (.windows | type) == "array" and (.windows | length) > 0
       and all(.windows[]; type == "string" and length > 0))
     and ([.subscriptions[].rail] | length == (unique | length))' "$profile" >/dev/null 2>&1; then
  while IFS= read -r subscription; do
    rail="$(printf '%s' "$subscription" | jq -r '.rail // empty')"
    windows="$(printf '%s' "$subscription" | jq -c '.windows // []')"
    [ -n "$rail" ] || continue
    case "$rail" in codex|claude|openrouter) continue ;; esac

    first_window="$(printf '%s' "$windows" | jq -r '.[0] // "unknown"')"
    value="$(unknown_json "$first_window")"

    # `probe` is an ARGV ARRAY, never implicitly parsed by a shell. The profile
    # is nevertheless TRUSTED EXECUTABLE developer configuration: a named
    # program may implement its own command language. The security boundary is
    # therefore the host-owned common-checkout path above, not a partial
    # executable-name blocklist. Read argv with a NUL-delimited loop -- bash
    # 3.2 has no mapfile.
    probe_argv=()
    probe_is_none=1
    if printf '%s' "$subscription" | jq -e '.probe != "none"' >/dev/null 2>&1; then
      probe_is_none=0
      while IFS= read -r -d '' probe_word; do
        probe_argv[${#probe_argv[@]}]="$probe_word"
      done < <(printf '%s' "$subscription" | jq -j '.probe[] | (. + "\u0000")' 2>/dev/null)
    fi
    if [ "$probe_is_none" -eq 0 ] && [ "${#probe_argv[@]}" -gt 0 ]; then
      # The executable must resolve on the reset PATH, or be an absolute path
      # to an existing regular file. Anything else stays unknown.
      probe_bin="${probe_argv[0]}"
      probe_ok=0
      case "$probe_bin" in
        /*) [ -f "$probe_bin" ] && [ -x "$probe_bin" ] && probe_ok=1 ;;
        */*) probe_ok=0 ;;
        *) command -v "$probe_bin" >/dev/null 2>&1 && probe_ok=1 ;;
      esac
      if [ "$probe_ok" -eq 1 ]; then
        # Bounded: a hanging profile probe must resolve to unknown, not block.
        probe_output="$(run_bounded 20 "${probe_argv[@]}" 2>/dev/null)" || probe_output=""
        [ -n "$probe_output" ] \
          && value="$(normalize_profile_probe "$probe_output" "$windows")"
      fi
    fi
    result="$(printf '%s' "$result" \
      | jq -c --arg rail "$rail" --argjson value "$value" '. + {($rail):$value}')"
  done < <(jq -c '.subscriptions[] | select(type == "object")' "$profile")
fi

printf '%s\n' "$result"
