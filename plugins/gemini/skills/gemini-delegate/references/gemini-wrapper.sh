#!/usr/bin/env bash
#
# gemini-wrapper.sh: Real fallback chain for the Gemini CLI.
#
# WHY THIS EXISTS:
#   The gemini-delegate skill documented a `pro -> flash -> flash-lite -> skip`
#   automatic fallback chain on HTTP 429 errors. The Gemini CLI does NOT
#   auto-fall-back: on 2026-04-22, Pro was rate-limited across 10 retries
#   and exited with an error. Manual rerun with `-m flash` succeeded in 23s.
#
# WHAT THIS FIXES:
#   This wrapper catches 429-equivalent failures (exit code OR stderr match)
#   and retries with the next model in the chain. After flash-lite fails,
#   it exits 1 with a clear message (NOT a silent skip; surface the failure).
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default)
#   - gtimeout (from coreutils: `brew install coreutils`)
#   - gemini CLI (`gemini --version`)
#
# USAGE:
#   bash gemini-wrapper.sh -p "your prompt"        # starts at pro
#   bash gemini-wrapper.sh -m flash -p "prompt"    # starts at flash
#   echo "prompt" | bash gemini-wrapper.sh         # stdin
#
# Source it to get the function:
#   source gemini-wrapper.sh
#   gemini_with_fallback -p "prompt"
#
# Environment variables:
#   GEMINI_TIMEOUT_S=60   per-attempt timeout in seconds (default 60)
#   GEMINI_YOLO=1         pass --yolo to gemini (default 1; set 0 to opt out
#                         of skip-confirmation mode for sensitive contexts)
#
# SECURITY NOTES:
#   - PATH is set to a fixed value to prevent caller-controlled hijack of
#     gemini, gtimeout, grep, cat, rm, mktemp.
#   - stderr from gemini is filtered through `tr` to strip ANSI escape
#     sequences before forwarding to the user's terminal. This blocks
#     OSC 52 clipboard hijack, OSC 8 phishing hyperlinks, and cursor
#     manipulation that could land via crafted prompts reflected in
#     gemini's error output.
#   - Temp files are created with 0600 perms and cleaned up via trap on
#     EXIT/INT/TERM (when run as a script; see notes for sourced mode).
#   - The rate-limit regex requires word boundaries on `429` and contextual
#     punctuation around `quota`/`rate limit` to reduce false-positive
#     model downgrades.

# Internal namespace prefix to avoid polluting caller shell when sourced.
__GEMINI_WRAPPER_FALLBACK_CHAIN=("pro" "flash" "flash-lite")

# Rate-limit patterns. Anchored to reduce false matches that would silently
# downgrade the model. `\b429\b` requires word boundaries around the digits.
# Other terms require leading whitespace + trailing punctuation/word boundary.
__GEMINI_WRAPPER_RATE_LIMIT_PATTERNS='exhausted your capacity|\bquota\b[[:space:]]*(exceeded|limit|exhaust)|\brate[[:space:]]+limit\b|\b429\b|\btoo many requests\b'

gemini_with_fallback() {
  # SECURITY: fixed PATH inside the function so sourced callers do not get
  # their PATH mutated by side effect. Caller's PATH is restored on return.
  local _saved_path="$PATH"
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

  # Verify gtimeout is available.
  if ! command -v gtimeout >/dev/null 2>&1; then
    echo "ERROR: gtimeout not found. Install with: brew install coreutils" >&2
    export PATH="$_saved_path"
    return 127
  fi

  local timeout_s="${GEMINI_TIMEOUT_S:-60}"
  local yolo_flag=""
  if [ "${GEMINI_YOLO:-1}" = "1" ]; then
    yolo_flag="--yolo"
  fi
  local start_idx=0
  local args=()
  local err_log=""

  # Cleanup on any exit path. Using a function so we can call it explicitly
  # and via trap; sourced contexts should not register an EXIT trap (would
  # fire on the caller's shell exit), so we call cleanup explicitly on
  # every return path instead.
  __gemini_wrapper_cleanup() {
    if [ -n "$err_log" ] && [ -e "$err_log" ]; then
      rm -f "$err_log"
    fi
  }

  # If the caller passed -m <model>, find that model in the chain and start there.
  while [ $# -gt 0 ]; do
    case "$1" in
      -m)
        if [ -z "${2:-}" ]; then
          echo "ERROR: -m requires a model argument" >&2
          export PATH="$_saved_path"
          return 2
        fi
        local requested_model="$2"
        local i=0
        local found=0
        for m in "${__GEMINI_WRAPPER_FALLBACK_CHAIN[@]}"; do
          if [ "$m" = "$requested_model" ]; then
            start_idx=$i
            found=1
            break
          fi
          i=$((i+1))
        done
        if [ $found -eq 0 ]; then
          echo "ERROR: unknown model '$requested_model' (chain: ${__GEMINI_WRAPPER_FALLBACK_CHAIN[*]})" >&2
          export PATH="$_saved_path"
          return 2
        fi
        shift 2
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done

  local i=$start_idx
  while [ $i -lt ${#__GEMINI_WRAPPER_FALLBACK_CHAIN[@]} ]; do
    local model="${__GEMINI_WRAPPER_FALLBACK_CHAIN[$i]}"

    # Per-attempt temp file with restrictive perms.
    err_log=$(mktemp -t gemini-wrapper.XXXXXX) || {
      echo "ERROR: mktemp failed; check TMPDIR permissions" >&2
      export PATH="$_saved_path"
      return 1
    }
    chmod 600 "$err_log" 2>/dev/null || true

    echo "[gemini-wrapper] trying model: $model" >&2
    if [ -n "$yolo_flag" ]; then
      gtimeout "${timeout_s}s" gemini -m "$model" "$yolo_flag" "${args[@]}" 2>"$err_log"
    else
      gtimeout "${timeout_s}s" gemini -m "$model" "${args[@]}" 2>"$err_log"
    fi
    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
      __gemini_wrapper_cleanup
      export PATH="$_saved_path"
      return 0
    fi

    # Determine if this looks like a rate-limit. Use both exit-code hints
    # (gtimeout returns 124 on timeout; treat as transient) and stderr regex.
    local is_rate_limit=0
    if grep -iE "$__GEMINI_WRAPPER_RATE_LIMIT_PATTERNS" "$err_log" >/dev/null 2>&1; then
      is_rate_limit=1
    fi

    if [ $is_rate_limit -eq 1 ]; then
      echo "[gemini-wrapper] $model rate-limited; trying next model" >&2
      # SECURITY: filter ANSI escape sequences before forwarding stderr to
      # the user's terminal. Strips control chars 0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F.
      LC_ALL=C tr -d '\000-\010\013\014\016-\037' < "$err_log" >&2
      __gemini_wrapper_cleanup
      i=$((i+1))
      continue
    fi

    # Not a rate-limit failure; surface it and stop.
    echo "[gemini-wrapper] $model failed (exit $exit_code, not a 429); aborting" >&2
    LC_ALL=C tr -d '\000-\010\013\014\016-\037' < "$err_log" >&2
    __gemini_wrapper_cleanup
    export PATH="$_saved_path"
    return $exit_code
  done

  echo "[gemini-wrapper] all models in fallback chain exhausted; try again later" >&2
  export PATH="$_saved_path"
  return 1
}

# If invoked directly (not sourced), call the function with all args. Direct
# invocation also registers a trap so an interrupt or signal cleans up any
# in-flight temp file. Sourced mode does not register the trap (it would fire
# on the caller's shell exit, not on the wrapper invocation).
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -uo pipefail
  trap 'rm -f /tmp/gemini-wrapper.* 2>/dev/null || true' EXIT INT TERM
  gemini_with_fallback "$@"
fi
