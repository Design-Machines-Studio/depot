#!/usr/bin/env bash
#
# gemini-wrapper.sh — Real fallback chain for the Gemini CLI.
#
# WHY THIS EXISTS:
#   The gemini-delegate skill documented a `pro → flash → flash-lite → skip`
#   automatic fallback chain on HTTP 429 errors. The Gemini CLI does NOT
#   auto-fall-back: on 2026-04-22, Pro was rate-limited across 10 retries
#   and exited with an error. Manual rerun with `-m flash` succeeded in 23s.
#
# WHAT THIS FIXES:
#   This wrapper catches 429-equivalent failures (exit code OR stderr match)
#   and retries with the next model in the chain. After flash-lite fails,
#   it exits 1 with a clear message (NOT a silent skip — surface the failure).
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default)
#   - gtimeout (from coreutils — `brew install coreutils`)
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

# nohup bash -c does not inherit the login shell PATH on macOS.
# Add /opt/homebrew/bin (Apple Silicon) and /usr/local/bin (Intel) explicitly.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# Verify gtimeout is available — required for run-time bounding.
if ! command -v gtimeout >/dev/null 2>&1; then
  echo "ERROR: gtimeout not found. Install with: brew install coreutils" >&2
  exit 127
fi

# The fallback chain. Order matters: most-capable first.
GEMINI_FALLBACK_CHAIN=("pro" "flash" "flash-lite")

# Patterns that indicate rate-limit / quota / capacity failures in stderr.
# Case-insensitive grep.
RATE_LIMIT_PATTERNS="exhausted your capacity|quota|rate limit|429|too many requests"

gemini_with_fallback() {
  local timeout_s="${GEMINI_TIMEOUT_S:-60}"
  local start_idx=0
  local args=()

  # If the caller passed -m <model>, find that model in the chain and start there.
  while [ $# -gt 0 ]; do
    case "$1" in
      -m)
        local requested_model="$2"
        local i=0
        for m in "${GEMINI_FALLBACK_CHAIN[@]}"; do
          if [ "$m" = "$requested_model" ]; then
            start_idx=$i
            break
          fi
          i=$((i+1))
        done
        shift 2
        ;;
      *)
        args+=("$1")
        shift
        ;;
    esac
  done

  local i=$start_idx
  while [ $i -lt ${#GEMINI_FALLBACK_CHAIN[@]} ]; do
    local model="${GEMINI_FALLBACK_CHAIN[$i]}"
    local err_log
    err_log=$(mktemp -t gemini-wrapper.XXXXXX)

    echo "[gemini-wrapper] trying model: $model" >&2
    if gtimeout "${timeout_s}s" gemini -m "$model" --yolo "${args[@]}" 2>"$err_log"; then
      rm -f "$err_log"
      return 0
    fi

    local exit_code=$?
    if grep -iE "$RATE_LIMIT_PATTERNS" "$err_log" >/dev/null 2>&1; then
      echo "[gemini-wrapper] $model rate-limited; trying next model" >&2
      cat "$err_log" >&2
      rm -f "$err_log"
      i=$((i+1))
      continue
    fi

    # Not a rate-limit failure — surface it and stop.
    echo "[gemini-wrapper] $model failed (exit $exit_code, not a 429); aborting" >&2
    cat "$err_log" >&2
    rm -f "$err_log"
    return $exit_code
  done

  echo "[gemini-wrapper] all models in fallback chain exhausted; try again later" >&2
  return 1
}

# If invoked directly (not sourced), call the function with all args.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  gemini_with_fallback "$@"
fi
