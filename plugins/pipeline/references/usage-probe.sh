#!/usr/bin/env bash
# usage-probe.sh -- gauge conservative remaining headroom per routing rail.
#
# Parser baselines probed 2026-08-08: Claude Code 2.1.220 statusLine
# rate_limits; Codex CLI 0.146.0 app-server account/rateLimits/read; curl
# 8.7.1 against OpenRouter /api/v1/credits. ccusage was not installed on the
# probe host; its fallback is pinned to the current `ccusage blocks --json`
# blocks/data shapes and explicit percent or used/limit fields.
#
# Subscription rails emit one conservative limiting-window object:
#   {"state":"ok|limited|unknown","remaining_pct":<number>,"window":"<name>"}
# OpenRouter is an API balance rail:
#   {"balance_usd":<number|null>}
#
# Known rails use built-in probes. Other subscriptions declared in the local
# operator profile run their profile command under the same reset PATH. A custom
# command must emit one common limiting-window object that conservatively
# represents every window declared by that entry. Non-zero, malformed, or unmappable output becomes unknown at
# the policy threshold.
set -uo pipefail

# Reset PATH before any command lookup, including profile-declared probes.
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Every emission path below builds JSON with jq. Without jq the script would
# print a blank line and exit 0, and the consumer would see an unrecognized
# shape rather than the mandated unknown object. Absent jq is exactly the
# "tool is absent" case, so answer it in jq-free literal form and stop.
if ! command -v jq >/dev/null 2>&1; then
  printf '%s\n' '{"codex":{"state":"unknown","remaining_pct":0,"window":"unknown"},"claude":{"state":"unknown","remaining_pct":0,"window":"unknown"},"openrouter":{"state":"unknown","remaining_pct":0,"balance_usd":null}}'
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
  # who controls the environment assert used_percentage 0 for both windows,
  # which also suppresses the ccusage fallback (it only runs when no five_hour
  # observation exists) and reports Claude "ok" while its real headroom is
  # unknown or exhausted. That is the optimistic direction this file exists to
  # prevent, so they are honoured only under an explicit test mode.
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
  local statusline="" observations='[]' cc_out="" cc_observation=""
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

  if ! printf '%s' "$observations" | jq -e 'any(.window == "five_hour")' >/dev/null 2>&1 \
     && command -v ccusage >/dev/null 2>&1; then
    cc_out="$(ccusage blocks --json 2>/dev/null)" || cc_out=""
    if [ -n "$cc_out" ]; then
      cc_observation="$(printf '%s' "$cc_out" | jq -c '
        (if (.data? | type) == "array" then .data
         elif (.blocks? | type) == "array" then .blocks
         else [] end
         | map(select(.isActive == true)) | first // empty) as $b
        | ($b.usagePercent // $b.percentUsed // $b.percent // empty) as $explicit
        | ($b.totalTokens // $b.tokenCounts.totalTokens // empty) as $used
        | ($b.tokenLimit // $b.limit // $b.maxTokens // empty) as $limit
        | (if ($explicit | type) == "number" then $explicit
           elif (($used | type) == "number" and ($limit | type) == "number" and $limit > 0)
             then ($used / $limit * 100)
           else empty end) as $used_pct
        | {window:"five_hour", remaining_pct:([0, (100 - $used_pct), 100] | sort | .[1])}
      ' 2>/dev/null)" || cc_observation=""
      if [ -n "$cc_observation" ]; then
        observations="$(printf '%s' "$observations" | jq -c --argjson item "$cc_observation" '. + [$item]')"
      fi
    fi
  fi

  aggregate_windows '["five_hour","weekly"]' "$observations"
}

codex_json() {
  local out="" rc=0 observations='[]'
  if command -v codex >/dev/null 2>&1; then
    out="$({
      printf '%s\n' \
        '{"method":"initialize","id":0,"params":{"clientInfo":{"name":"depot-usage-probe","title":"Depot usage probe","version":"1"},"capabilities":{"experimentalApi":true}}}' \
        '{"method":"initialized","params":{}}' \
        '{"method":"account/rateLimits/read","id":7,"params":{}}'
    } | run_bounded 20 codex app-server --stdio 2>/dev/null)" || rc=$?
    if [ "$rc" -eq 0 ] && [ -n "$out" ]; then
      observations="$(printf '%s\n' "$out" | jq -sc '
        (map(select(.id == 7 and .result.rateLimits != null)) | last
          | .result.rateLimits // {}) as $limits
        | [$limits.primary, $limits.secondary]
        | map(select(type == "object"
            and (.usedPercent | type) == "number"
            and (.windowDurationMins | type) == "number")
          | {window:(if .windowDurationMins == 300 then "five_hour"
                     elif .windowDurationMins >= 1440 then "weekly"
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
        | jq -r '(.data.total_credits - .data.total_usage) | numbers' 2>/dev/null)" || balance=""
    fi
  fi
  case "$balance" in ''|*[!0-9.+-]*) balance="" ;; esac
  # `state` is load-bearing and must not be dropped. cascade-dispatch.sh's
  # rail_has_headroom reads `.state` and `.remaining_pct`; it never reads
  # `balance_usd`. Emitting balance alone made a known-low account read as an
  # unconstrained rail, which is the optimistic direction this file exists to
  # prevent. Preserve the pre-existing low/ok/unknown semantics alongside the
  # balance.
  local state="unknown"
  if [ -n "$balance" ]; then
    if awk -v b="$balance" 'BEGIN{exit !(b < 5)}'; then state="low"; else state="ok"; fi
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
  local root="" candidate=""
  # An environment-selected profile path is a test fixture, not production
  # input: the profile supplies argv this script executes, so letting the
  # environment point it at any untracked file defeats the "developer-local
  # config" boundary the contract claims. In normal operation only the
  # canonical repository path is resolved.
  if [ "${USAGE_PROBE_TEST_MODE:-0}" = "1" ] && [ -n "${DM_OPERATOR_PROFILE_FILE:-}" ]; then
    candidate="$DM_OPERATOR_PROFILE_FILE"
  else
    root="$(git rev-parse --show-toplevel 2>/dev/null)" || root=""
    [ -n "$root" ] || return 0
    candidate="$root/.dm/operator-profile.local.json"
  fi
  # A profile supplies probe argv that this script executes, so the file itself
  # is a trust boundary. It is legitimate only as untracked developer-local
  # config.
  #
  # Refuse a symlink: it can redirect the read outside the checkout.
  [ -L "$candidate" ] && return 0
  [ -f "$candidate" ] || return 0
  # Refuse a git-TRACKED profile. This is the live vector, not a theoretical
  # one: .gitignore is routinely defeated by `git add -f` in this repository
  # (several plans/ subtrees are ignored and tracked anyway), so a branch could
  # ship .dm/operator-profile.local.json and have every later run execute its
  # probes. An ignored-but-committed file is not developer-local config.
  if git ls-files --error-unmatch -- "$candidate" >/dev/null 2>&1; then
    return 0
  fi
  printf '%s\n' "$candidate"
}

profile="$(operator_profile_path)"
result="$(jq -cn --argjson codex "$(codex_json)" \
  --argjson claude "$(claude_json)" --argjson openrouter "$(openrouter_json)" \
  '{codex:$codex,claude:$claude,openrouter:$openrouter}')"

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

    # `probe` is an ARGV ARRAY, never a shell string, and it is never passed to
    # `sh -c`. A profile is developer-local config, but it is still a file this
    # script executes from, so it gets no shell: no metacharacters, no word
    # splitting, no globbing, no chaining. Read the argv with a NUL-delimited
    # loop -- bash 3.2 has no mapfile.
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
      # An argv array blocks IMPLICIT shell parsing; it does not stop a profile
      # from naming a shell explicitly. Refuse interpreters outright, otherwise
      # ["/bin/sh","-c","..."] walks straight back through the door this
      # hardening closed.
      case "${probe_bin##*/}" in
        sh|bash|dash|zsh|ksh|csh|tcsh|fish|env|eval|xargs|perl|python|python3|ruby|node|osascript|awk|nohup|command|exec|su|sudo|doas)
          probe_ok=0 ;;
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
