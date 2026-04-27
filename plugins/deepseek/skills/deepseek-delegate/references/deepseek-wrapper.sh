#!/usr/bin/env bash
#
# deepseek-wrapper.sh: Fallback chain for DeepSeek V4 API via curl.
#
# WHY THIS EXISTS:
#   The deepseek-delegate skill needs a reliable way to invoke DeepSeek V4
#   models from Claude Code subagents. Unlike Gemini (which has a CLI),
#   DeepSeek is invoked via curl against the OpenAI-compatible API. This
#   wrapper adds rate-limit detection, model fallback (v4-pro -> v4-flash),
#   timeout enforcement, and structured JSON output.
#
# WHAT THIS FIXES:
#   Without this wrapper, each caller must handle rate-limit retries, JSON
#   parsing, and error classification independently. The wrapper centralizes
#   these concerns following the same pattern as gemini-wrapper.sh.
#
# DEPENDENCIES:
#   - bash 3.2+ (macOS default)
#   - curl (standard on macOS/Linux)
#   - DEEPSEEK_API_KEY environment variable must be set
#
# USAGE:
#   bash deepseek-wrapper.sh -p "your prompt"                  # starts at v4-pro
#   bash deepseek-wrapper.sh -m v4-flash -p "prompt"           # starts at v4-flash
#   echo "prompt" | bash deepseek-wrapper.sh                   # stdin
#   bash deepseek-wrapper.sh -m v4-pro -s "system prompt" -p "user prompt"
#
# Source it to get the function:
#   source deepseek-wrapper.sh
#   deepseek_with_fallback -p "prompt"
#
# Environment variables:
#   DEEPSEEK_API_KEY       required -- your DeepSeek API key
#   DEEPSEEK_TIMEOUT_S=60  per-attempt timeout in seconds (default 60)
#   DEEPSEEK_BASE_URL      API base URL (default https://api.deepseek.com)
#   DEEPSEEK_TEMPERATURE=0 temperature for deterministic output (default 0)
#
# SECURITY NOTES:
#   - PATH is set to a fixed value to prevent caller-controlled hijack of
#     curl, grep, cat, rm, mktemp.
#   - API key is passed via -H header, never embedded in URLs.
#   - Temp files are created with 0600 perms and cleaned up via trap on
#     EXIT/INT/TERM (when run as a script).
#   - Response body is NOT filtered for ANSI sequences (curl doesn't emit
#     them), but the error path strips control chars as a defence-in-depth.

__DEEPSEEK_WRAPPER_FALLBACK_CHAIN=("v4-pro" "v4-flash")

__DEEPSEEK_WRAPPER_MODEL_MAP_v4_pro="deepseek-v4-pro"
__DEEPSEEK_WRAPPER_MODEL_MAP_v4_flash="deepseek-v4-flash"

__DEEPSEEK_WRAPPER_RATE_LIMIT_PATTERNS='rate.*limit|quota.*exceeded|too many requests|\b429\b|capacity.*exhausted'

deepseek_with_fallback() {
  local _saved_path="$PATH"
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

  if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
    echo "ERROR: DEEPSEEK_API_KEY environment variable not set" >&2
    export PATH="$_saved_path"
    return 1
  fi

  local base_url="${DEEPSEEK_BASE_URL:-https://api.deepseek.com}"
  local timeout_s="${DEEPSEEK_TIMEOUT_S:-60}"
  local temperature="${DEEPSEEK_TEMPERATURE:-0}"
  local start_idx=0
  local user_prompt=""
  local system_prompt=""
  local err_log=""

  __deepseek_wrapper_cleanup() {
    if [ -n "$err_log" ] && [ -e "$err_log" ]; then
      rm -f "$err_log"
    fi
  }

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
        for m in "${__DEEPSEEK_WRAPPER_FALLBACK_CHAIN[@]}"; do
          if [ "$m" = "$requested_model" ]; then
            start_idx=$i
            found=1
            break
          fi
          i=$((i+1))
        done
        if [ $found -eq 0 ]; then
          echo "ERROR: unknown model '$requested_model' (chain: ${__DEEPSEEK_WRAPPER_FALLBACK_CHAIN[*]})" >&2
          export PATH="$_saved_path"
          return 2
        fi
        shift 2
        ;;
      -p)
        if [ -z "${2:-}" ]; then
          echo "ERROR: -p requires a prompt argument" >&2
          export PATH="$_saved_path"
          return 2
        fi
        user_prompt="$2"
        shift 2
        ;;
      -s)
        if [ -z "${2:-}" ]; then
          echo "ERROR: -s requires a system prompt argument" >&2
          export PATH="$_saved_path"
          return 2
        fi
        system_prompt="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done

  if [ -z "$user_prompt" ]; then
    if [ ! -t 0 ]; then
      user_prompt=$(cat)
    fi
  fi

  if [ -z "$user_prompt" ]; then
    echo "ERROR: no prompt provided (use -p or pipe via stdin)" >&2
    export PATH="$_saved_path"
    return 2
  fi

  local i=$start_idx
  while [ $i -lt ${#__DEEPSEEK_WRAPPER_FALLBACK_CHAIN[@]} ]; do
    local model_alias="${__DEEPSEEK_WRAPPER_FALLBACK_CHAIN[$i]}"

    local model_id=""
    case "$model_alias" in
      v4-pro)   model_id="$__DEEPSEEK_WRAPPER_MODEL_MAP_v4_pro" ;;
      v4-flash) model_id="$__DEEPSEEK_WRAPPER_MODEL_MAP_v4_flash" ;;
    esac

    err_log=$(mktemp -t deepseek-wrapper.XXXXXX) || {
      echo "ERROR: mktemp failed; check TMPDIR permissions" >&2
      export PATH="$_saved_path"
      return 1
    }
    chmod 600 "$err_log" 2>/dev/null || true

    echo "[deepseek-wrapper] trying model: $model_alias ($model_id)" >&2

    local messages_json=""
    if [ -n "$system_prompt" ]; then
      messages_json=$(printf '[{"role":"system","content":%s},{"role":"user","content":%s}]' \
        "$(printf '%s' "$system_prompt" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')" \
        "$(printf '%s' "$user_prompt" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")
    else
      messages_json=$(printf '[{"role":"user","content":%s}]' \
        "$(printf '%s' "$user_prompt" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')")
    fi

    local request_body
    request_body=$(printf '{"model":"%s","messages":%s,"temperature":%s,"stream":false}' \
      "$model_id" "$messages_json" "$temperature")

    local http_code
    http_code=$(curl -s -w '%{http_code}' \
      --max-time "$timeout_s" \
      -X POST "${base_url}/v1/chat/completions" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${DEEPSEEK_API_KEY}" \
      -d "$request_body" \
      -o "$err_log" 2>/dev/null)
    local exit_code=$?

    if [ $exit_code -ne 0 ]; then
      if [ $exit_code -eq 28 ]; then
        echo "[deepseek-wrapper] $model_alias timed out after ${timeout_s}s" >&2
      else
        echo "[deepseek-wrapper] $model_alias curl failed (exit $exit_code)" >&2
      fi
      __deepseek_wrapper_cleanup
      export PATH="$_saved_path"
      return $exit_code
    fi

    if [ "$http_code" = "200" ]; then
      cat "$err_log"
      __deepseek_wrapper_cleanup
      export PATH="$_saved_path"
      return 0
    fi

    local is_rate_limit=0
    if [ "$http_code" = "429" ]; then
      is_rate_limit=1
    elif grep -iE "$__DEEPSEEK_WRAPPER_RATE_LIMIT_PATTERNS" "$err_log" >/dev/null 2>&1; then
      is_rate_limit=1
    fi

    if [ $is_rate_limit -eq 1 ]; then
      echo "[deepseek-wrapper] $model_alias rate-limited (HTTP $http_code); trying next model" >&2
      __deepseek_wrapper_cleanup
      i=$((i+1))
      continue
    fi

    echo "[deepseek-wrapper] $model_alias failed (HTTP $http_code); aborting" >&2
    LC_ALL=C tr -d '\000-\010\013\014\016-\037' < "$err_log" >&2
    __deepseek_wrapper_cleanup
    export PATH="$_saved_path"
    return 1
  done

  echo "[deepseek-wrapper] all models in fallback chain exhausted; try again later" >&2
  export PATH="$_saved_path"
  return 1
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  set -uo pipefail
  trap 'rm -f /tmp/deepseek-wrapper.* 2>/dev/null || true' EXIT INT TERM
  deepseek_with_fallback "$@"
fi
