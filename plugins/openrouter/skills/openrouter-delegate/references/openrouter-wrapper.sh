#!/usr/bin/env bash
# openrouter-wrapper.sh -- generalized single-turn model runner for the World B
# OpenRouter rail. Stable exit codes (0/28/1/2) and direct text stdout let the
# generic review-agent runner map success, timeout, exhausted, and invocation
# outcomes without provider-specific response parsing. Arguments are positional:
# <model> <prompt|-> [overall-timeout] [fallback].
#
# Usage:
#   ./openrouter-wrapper.sh <model-slug> <prompt|-> [timeout_s] [fallback-slug]
#     <prompt|->  literal prompt, or "-" to read prompt from stdin
#
# Env:
#   OPENROUTER_API_KEY   required unless OPENROUTER_API_KEY_FILE is used
#   OPENROUTER_API_KEY_FILE
#                       optional regular, non-symlink key file owned by the
#                       current UID with mode 0600; mutually exclusive with
#                       OPENROUTER_API_KEY
#   OPENROUTER_SYSTEM    optional system prompt (default: terse coding assistant)
#   OPENROUTER_SYSTEM_FILE
#                       optional byte-preserving system prompt file; mutually
#                       exclusive with OPENROUTER_SYSTEM
#   OPENROUTER_BASE      production is pinned to https://openrouter.ai/api/v1;
#                       fixture-key requests may override to loopback HTTP only
#   OPENROUTER_ZDR       1 -> no-train/no-retain providers (data_collection: deny)
#   OPENROUTER_WORKLOAD  quality|security|direct|bulk|mechanical (default quality)
#   OPENROUTER_PROVIDER_SORT
#                       price|throughput|latency|exacto; overrides workload routing
#   OPENROUTER_PROVIDER_ORDER
#                       optional comma-separated provider/endpoint slugs
#   OPENROUTER_FALLBACK_PROVIDER_ORDER
#                       optional provider/endpoint slugs appended for the fallback
#                       model in the same native model-fallback request
#   OPENROUTER_ALLOW_FALLBACKS
#                       0|1 for provider fallback (default 1)
#   OPENROUTER_OVERALL_TIMEOUT
#                       completion budget when timeout_s is omitted (default 3600)
#   OPENROUTER_CONNECT_TIMEOUT
#                       TCP/TLS connection timeout seconds (default 30)
#   OPENROUTER_FIRST_BYTE_TIMEOUT
#                       maximum seconds before the first streamed byte (default 600)
#   OPENROUTER_IDLE_TIMEOUT
#                       maximum seconds without streamed progress (default 600)
#   OPENROUTER_RUN_ID
#                       optional run identity; automated runners supply it,
#                       while direct receipts represent its absence as null
#   OPENROUTER_LANE_ID  optional receipt lane identity; automated runners
#                       supply it, while direct receipts fall back to the target
#                       agent name when available
#   OPENROUTER_RECEIPT_FILE
#                       optional content-free success or failure receipt path
#
# Exit codes:
#   0  success   28 timeout   1 exhausted/error   2 bad args
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"   # fixed PATH: prevent caller-controlled dependency hijack

MODEL="${1:-}"
PROMPT_ARG="${2:-}"
TIMEOUT="${3:-${OPENROUTER_OVERALL_TIMEOUT:-3600}}"
FALLBACK="${4:-}"
if [ -z "$MODEL" ] || [ -z "$PROMPT_ARG" ]; then
  echo "usage: $0 <model> <prompt|-> [timeout] [fallback]" >&2
  exit 2
fi

validate_model_slug() {
  local slug="$1"
  [ "$(printf '%s' "$slug" | wc -c | tr -d '[:space:]')" -le 128 ] || {
    echo "### RUNNER FAILURE: model slug exceeds 128 bytes" >&2
    return 1
  }
  [[ "$slug" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:-]*$ ]] &&
    [[ "$slug" != *".."* ]]
}

model_matches_family() {
  local response_model="$1" family="$2"
  case "$response_model" in
    "$family"|"$family"-*|"$family":*) return 0 ;;
    *) return 1 ;;
  esac
}

for candidate in "$MODEL" "$FALLBACK"; do
  [ -z "$candidate" ] && continue
  validate_model_slug "$candidate" || {
    echo "### RUNNER FAILURE: invalid OpenRouter model slug '$candidate'" >&2
    exit 2
  }
  candidate_origin="$(printf '%s' "$candidate" | tr '[:upper:]' '[:lower:]')"
  case "$candidate_origin" in
    anthropic/*)
      echo "### RUNNER FAILURE: native-vendor-origin invariant rejected OpenRouter model '$candidate'" >&2
      exit 2
      ;;
  esac
done
CREDENTIAL_LOADER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/openrouter-credential.sh"
[ -r "$CREDENTIAL_LOADER" ] || {
  echo "### RUNNER FAILURE: coherent OpenRouter credential loader unavailable" >&2
  exit 2
}
# shellcheck source=openrouter-credential.sh
. "$CREDENTIAL_LOADER"
if load_openrouter_api_key; then
  :
else
  credential_rc=$?
  if [ "$credential_rc" -eq 2 ]; then
    echo "### RUNNER FAILURE: OPENROUTER_API_KEY and OPENROUTER_API_KEY_FILE are mutually exclusive" >&2
    exit 2
  fi
  echo "### RUNNER FAILURE: OPENROUTER_API_KEY_FILE must be a non-symlink regular file owned by the current UID with mode 0600 and one non-empty line" >&2
  exit 1
fi

PRODUCTION_BASE="https://openrouter.ai/api/v1"
BASE="${OPENROUTER_BASE:-$PRODUCTION_BASE}"
if [ "$BASE" != "$PRODUCTION_BASE" ]; then
  if [ "$OPENROUTER_API_KEY" != "test" ]; then
    echo "### RUNNER FAILURE: OPENROUTER_BASE override requires the fixture API key" >&2
    exit 2
  fi
  if [[ "$BASE" =~ ^http://(127\.0\.0\.1|localhost):([1-9][0-9]{0,4})(/[^?#]*)?$ ]]; then
    BASE_PORT="${BASH_REMATCH[2]}"
    [ "$BASE_PORT" -le 65535 ] || {
      echo "### RUNNER FAILURE: invalid loopback OPENROUTER_BASE port" >&2
      exit 2
    }
  else
    echo "### RUNNER FAILURE: OPENROUTER_BASE override must be a controlled loopback HTTP endpoint" >&2
    exit 2
  fi
fi

if [ "${OPENROUTER_SYSTEM+x}" = x ] && [ "${OPENROUTER_SYSTEM_FILE+x}" = x ]; then
  echo "### RUNNER FAILURE: OPENROUTER_SYSTEM and OPENROUTER_SYSTEM_FILE are mutually exclusive" >&2
  exit 2
fi
SYSTEM_SOURCE_FILE="${OPENROUTER_SYSTEM_FILE:-}"
if [ "${OPENROUTER_SYSTEM_FILE+x}" = x ]; then
  [ -n "$SYSTEM_SOURCE_FILE" ] && [ -f "$SYSTEM_SOURCE_FILE" ] && [ -r "$SYSTEM_SOURCE_FILE" ] || {
    echo "### RUNNER FAILURE: OPENROUTER_SYSTEM_FILE must be a readable regular file" >&2
    exit 2
  }
else
  SYSTEM="${OPENROUTER_SYSTEM:-You are a terse, precise coding assistant. Output only what was asked.}"
fi
PROVIDER_ORDER="${OPENROUTER_PROVIDER_ORDER:-}"
FALLBACK_PROVIDER_ORDER="${OPENROUTER_FALLBACK_PROVIDER_ORDER:-}"
PROVIDER_SORT="${OPENROUTER_PROVIDER_SORT:-}"
ALLOW_FALLBACKS="${OPENROUTER_ALLOW_FALLBACKS:-1}"
WORKLOAD="${OPENROUTER_WORKLOAD:-quality}"
CONNECT_TIMEOUT="${OPENROUTER_CONNECT_TIMEOUT:-30}"
FIRST_BYTE_TIMEOUT="${OPENROUTER_FIRST_BYTE_TIMEOUT:-600}"
IDLE_TIMEOUT="${OPENROUTER_IDLE_TIMEOUT:-600}"
CURRENT_RUN_ID="${OPENROUTER_RUN_ID:-}"
TARGET_AGENT_NAME="${OPENROUTER_TARGET_AGENT_NAME:-}"
RECEIPT_LANE_ID="${OPENROUTER_LANE_ID:-$TARGET_AGENT_NAME}"

validate_positive_integer() {
  local name="$1" value="$2"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || {
    echo "### RUNNER FAILURE: $name must be a positive integer" >&2
    exit 2
  }
}

validate_positive_integer timeout "$TIMEOUT"
validate_positive_integer OPENROUTER_CONNECT_TIMEOUT "$CONNECT_TIMEOUT"
validate_positive_integer OPENROUTER_FIRST_BYTE_TIMEOUT "$FIRST_BYTE_TIMEOUT"
validate_positive_integer OPENROUTER_IDLE_TIMEOUT "$IDLE_TIMEOUT"

case "$ALLOW_FALLBACKS" in
  0|1) ;;
  *) echo "### RUNNER FAILURE: OPENROUTER_ALLOW_FALLBACKS must be 0 or 1" >&2; exit 2 ;;
esac
case "$PROVIDER_SORT" in
  ""|price|throughput|latency|exacto) ;;
  *) echo "### RUNNER FAILURE: invalid OPENROUTER_PROVIDER_SORT" >&2; exit 2 ;;
esac
case "$WORKLOAD" in
  quality|security|direct|bulk|mechanical) ;;
  *) echo "### RUNNER FAILURE: invalid OPENROUTER_WORKLOAD" >&2; exit 2 ;;
esac
case "$TARGET_AGENT_NAME" in
  "") ;;
  *[!a-z0-9-]*) echo "### RUNNER FAILURE: invalid OPENROUTER_TARGET_AGENT_NAME" >&2; exit 2 ;;
  *) ;;
esac
case "$TARGET_AGENT_NAME" in
  security-auditor*)
    # This caller label catches accidental role/model drift. It is not, by
    # itself, an adversarial identity boundary.
    [ "$MODEL" = "moonshotai/kimi-k3" ] &&
      [ "$FALLBACK" = "openai/gpt-5.6-terra" ] || {
      echo "### RUNNER FAILURE: security review role requires Kimi K3 primary and GPT-5.6 Terra fallback" >&2
      exit 2
    }
    ;;
esac

# The private working root is created BEFORE any authorization check so every
# artifact those checks read can be snapshotted into a directory this process
# owns. Mode 700 under a mktemp -d name is what makes the snapshot copies
# unswappable by the caller between validation and use.
RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/openrouter-wrapper.XXXXXX")" || exit 1
chmod 700 "$RUN_ROOT"
INVOCATION_ID="$(printf '%s' "$RUN_ROOT" | shasum -a 256 | awk '{print $1}')" || exit 1
[[ "$INVOCATION_ID" =~ ^[0-9a-f]{64}$ ]] || {
  echo "### RUNNER FAILURE: could not create invocation identity" >&2
  exit 1
}
curl_pid=""
transport_launching=0
transport_signal_pending=0
terminate_transport() {
  [ -n "$curl_pid" ] || return 0
  if kill -0 "$curl_pid" >/dev/null 2>&1; then
    kill "$curl_pid" >/dev/null 2>&1 || true
    local attempt=0
    while kill -0 "$curl_pid" >/dev/null 2>&1 && [ "$attempt" -lt 20 ]; do
      sleep 0.1
      attempt=$((attempt + 1))
    done
    if kill -0 "$curl_pid" >/dev/null 2>&1; then
      kill -KILL "$curl_pid" >/dev/null 2>&1 || true
    fi
  fi
  wait "$curl_pid" >/dev/null 2>&1 || true
  curl_pid=""
}
cleanup() {
  terminate_transport
  rm -rf "$RUN_ROOT"
}
handle_signal() {
  if [ "$transport_launching" -eq 1 ]; then
    transport_signal_pending=1
    return
  fi
  trap '' HUP INT TERM
  terminate_transport
  if [ -n "${MODEL_CANDIDATES:-}" ] && [ -n "${EFFECTIVE_SORT:-}" ] &&
      [[ "${TRANSMITTED_REQUEST_ENVELOPE_SHA256:-}" =~ ^[0-9a-f]{64}$ ]] &&
      type write_failure_receipt >/dev/null 2>&1; then
    write_failure_receipt error interrupted "" || true
  fi
  exit 1
}
trap cleanup EXIT
trap handle_signal HUP INT TERM

for configured_order in "$PROVIDER_ORDER" "$FALLBACK_PROVIDER_ORDER"; do
  [ -z "$configured_order" ] && continue
  case "$configured_order" in
    *".."*|,*|*,|*,,*|*[!A-Za-z0-9._,/-]*)
      echo "### RUNNER FAILURE: invalid OpenRouter provider order" >&2
      exit 2
      ;;
  esac
done

PROMPT_SOURCE_FILE="$RUN_ROOT/user.prompt"
if [ "$PROMPT_ARG" = "-" ]; then
  cat > "$PROMPT_SOURCE_FILE" || exit 1
else
  printf '%s' "$PROMPT_ARG" > "$PROMPT_SOURCE_FILE" || exit 1
fi

if [ -z "$SYSTEM_SOURCE_FILE" ]; then
  SYSTEM_SOURCE_FILE="$RUN_ROOT/system.prompt"
  printf '%s' "$SYSTEM" > "$SYSTEM_SOURCE_FILE" || exit 1
fi

MODEL_CANDIDATES="$(jq -cn --arg primary "$MODEL" --arg fallback "$FALLBACK" '
  if $fallback == "" then [$primary] else [$primary, $fallback] end
')"

effective_provider_sort() {
  if [ -n "$PROVIDER_SORT" ]; then
    printf '%s' "$PROVIDER_SORT"
    return
  fi
  case "$WORKLOAD" in
    direct|bulk|mechanical)
      printf 'throughput'
      ;;
    quality|security)
      case "$MODEL,$FALLBACK" in
        *moonshotai/kimi-k3*) printf 'exacto' ;;
      esac
      ;;
  esac
}

combined_provider_order() {
  if [ -n "$PROVIDER_ORDER" ] && [ -n "$FALLBACK_PROVIDER_ORDER" ]; then
    printf '%s,%s' "$PROVIDER_ORDER" "$FALLBACK_PROVIDER_ORDER"
  elif [ -n "$PROVIDER_ORDER" ]; then
    printf '%s' "$PROVIDER_ORDER"
  else
    printf '%s' "$FALLBACK_PROVIDER_ORDER"
  fi
}

EFFECTIVE_SORT="$(effective_provider_sort)"
EFFECTIVE_ORDER="$(combined_provider_order)"

build_provider() {
  jq -n \
    --argjson req "$([ "${OPENROUTER_REQUIRE_PARAMS:-1}" = "1" ] && echo true || echo false)" \
    --arg zdr "${OPENROUTER_ZDR:-0}" \
    --arg sort "$EFFECTIVE_SORT" \
    --arg order "$EFFECTIVE_ORDER" \
    --argjson allow "$([ "$ALLOW_FALLBACKS" = "1" ] && echo true || echo false)" '
    {require_parameters: $req, allow_fallbacks: $allow}
    + (if $zdr == "1" then {data_collection: "deny", zdr: true} else {} end)
    + (if $order != ""
       then {order: ($order | split(","))}
       elif $sort != ""
       then {sort: $sort}
       else {}
       end)'
}

write_failure_receipt() {
  local outcome="$1" failure_kind="$2" timeout_kind="$3" http_status="${4:-}"
  local receipt_tmp
  [ -z "${OPENROUTER_RECEIPT_FILE:-}" ] && return 0
  receipt_tmp="${OPENROUTER_RECEIPT_FILE}.tmp.$$"
  (
    umask 077
    jq -n \
      --arg outcome "$outcome" \
      --arg invocation "$INVOCATION_ID" \
      --arg failure "$failure_kind" \
      --arg timeout "$timeout_kind" \
      --arg http "$http_status" \
      --arg requested "$MODEL" \
      --argjson candidates "$MODEL_CANDIDATES" \
      --arg workload "$WORKLOAD" \
      --arg sort "$EFFECTIVE_SORT" \
      --arg runid "${CURRENT_RUN_ID:-}" \
      --arg lane "$RECEIPT_LANE_ID" \
      --arg requestdigest "${TRANSMITTED_REQUEST_ENVELOPE_SHA256:-}" '
      {
        schemaVersion: 2,
        invocationId: $invocation,
        outcome: $outcome,
        failureKind: $failure,
        timeout: (if $timeout == "" then null else {kind: $timeout} end),
        httpStatus: (if $http == "" then null else ($http | tonumber) end),
        requestedModel: $requested,
        modelCandidates: $candidates,
        attemptedModel: null,
        attemptedModels: null,
        attemptProvenance: "not_reported_by_completion",
        fallbackUsed: null,
        responseModel: null,
        responseModelProvenance: "not_available",
        servingProvider: null,
        servingProviderProvenance: "not_reported_by_completion",
        usage: null,
        routing: {
          workload: $workload,
          sort: (if $sort == "" then null else $sort end)
        },
        authorization: {
          runId: (if $runid == "" then null else $runid end),
          laneId: (if $lane == "" then null else $lane end),
          requestEnvelopeSha256: (
            if $requestdigest == "" then null else $requestdigest end
          )
        }
      }' > "$receipt_tmp"
  ) || {
    rm -f "$receipt_tmp"
    echo "### RUNNER FAILURE: could not write OpenRouter failure receipt" >&2
    return 1
  }
  mv "$receipt_tmp" "$OPENROUTER_RECEIPT_FILE"
}

write_success_receipt() {
  local response_file="$1" attempted_model="$2" fallback_used="$3" receipt_tmp
  [ -z "${OPENROUTER_RECEIPT_FILE:-}" ] && return 0
  receipt_tmp="${OPENROUTER_RECEIPT_FILE}.tmp.$$"
  (
    umask 077
    jq \
      --arg requested "$MODEL" \
      --arg invocation "$INVOCATION_ID" \
      --arg attempted "$attempted_model" \
      --argjson candidates "$MODEL_CANDIDATES" \
      --argjson fallback "$fallback_used" \
      --arg workload "$WORKLOAD" \
      --arg sort "$EFFECTIVE_SORT" \
      --arg runid "${CURRENT_RUN_ID:-}" \
      --arg lane "$RECEIPT_LANE_ID" \
      --arg requestdigest "${TRANSMITTED_REQUEST_ENVELOPE_SHA256:-}" '
      {
        schemaVersion: 2,
        invocationId: $invocation,
        outcome: "success",
        failureKind: null,
        timeout: null,
        httpStatus: 200,
        generationId: .id,
        created: (.created // null),
        requestedModel: $requested,
        modelCandidates: $candidates,
        attemptedModel: $attempted,
        attemptedModels: (
          if $fallback then $candidates else [$requested] end
        ),
        attemptProvenance: "response_model",
        fallbackUsed: $fallback,
        responseModel: .model,
        responseModelProvenance: "response",
        servingProvider: (.provider // null),
        servingProviderProvenance: (
          if (.provider | type) == "string" and (.provider | length) > 0
          then "response"
          else "not_reported_by_completion"
          end
        ),
        usage: (.usage // null),
        routing: {
          workload: $workload,
          sort: (if $sort == "" then null else $sort end)
        },
        authorization: {
          runId: (if $runid == "" then null else $runid end),
          laneId: (if $lane == "" then null else $lane end),
          requestEnvelopeSha256: (
            if $requestdigest == "" then null else $requestdigest end
          )
        }
      }' "$response_file" > "$receipt_tmp"
  ) || {
    rm -f "$receipt_tmp"
    echo "### RUNNER FAILURE: could not write OpenRouter success receipt" >&2
    return 1
  }
  mv "$receipt_tmp" "$OPENROUTER_RECEIPT_FILE"
}

request_file="$RUN_ROOT/request.json"
stream_file="$RUN_ROOT/response.stream"
status_file="$RUN_ROOT/http.status"
curl_error_file="$RUN_ROOT/curl.stderr"
events_file="$RUN_ROOT/events.jsonl"
response_file="$RUN_ROOT/response.json"
provider="$(build_provider)"

if [ -n "$FALLBACK" ]; then
  jq -n \
    --arg primary "$MODEL" \
    --arg fallback "$FALLBACK" \
    --rawfile system "$SYSTEM_SOURCE_FILE" \
    --rawfile prompt "$PROMPT_SOURCE_FILE" \
    --argjson provider "$provider" '
    {
      models: [$primary, $fallback],
      provider: $provider,
      stream: true,
      stream_options: {include_usage: true},
      messages: [
        {role: "system", content: $system},
        {role: "user", content: $prompt}
      ]
    }' > "$request_file"
else
  jq -n \
    --arg model "$MODEL" \
    --rawfile system "$SYSTEM_SOURCE_FILE" \
    --rawfile prompt "$PROMPT_SOURCE_FILE" \
    --argjson provider "$provider" '
    {
      model: $model,
      provider: $provider,
      stream: true,
      stream_options: {include_usage: true},
      messages: [
        {role: "system", content: $system},
        {role: "user", content: $prompt}
      ]
    }' > "$request_file"
fi

# The bytes curl posts, held in process memory. curl is fed these bytes on
# stdin (`--data-binary @-`) and is never handed a path, so there is no reopen
# between hashing and the POST.
TRANSMIT_BYTES="$(cat "$request_file")" || {
  echo "### RUNNER FAILURE: could not read the request body for transmission" >&2
  exit 2
}
[ -n "$TRANSMIT_BYTES" ] || {
  echo "### RUNNER FAILURE: could not read the request body for transmission" >&2
  exit 2
}
TRANSMITTED_REQUEST_ENVELOPE_SHA256="$(printf '%s' "$TRANSMIT_BYTES" | shasum -a 256 | awk '{print $1}')" || {
  echo "### RUNNER FAILURE: could not compute the request-envelope hash" >&2
  exit 2
}
[[ "$TRANSMITTED_REQUEST_ENVELOPE_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
  echo "### RUNNER FAILURE: could not compute the request-envelope hash" >&2
  exit 2
}

: > "$stream_file"
: > "$status_file"
: > "$curl_error_file"
authorization_header_file="$RUN_ROOT/authorization.header"
printf 'Authorization: Bearer %s\n' "$OPENROUTER_API_KEY" > "$authorization_header_file" || {
  echo "### RUNNER FAILURE: could not prepare the OpenRouter authorization header" >&2
  exit 1
}
chmod 600 "$authorization_header_file"
# curl reads the credential from the private run root. Keep it out of both the
# child process argv and environment, where same-host diagnostics can expose it.
unset OPENROUTER_API_KEY OPENROUTER_API_KEY_FILE
transport_launching=1
printf '%s' "$TRANSMIT_BYTES" | curl -N -sS -o "$stream_file" -w '%{http_code}' \
  "$BASE/chat/completions" \
  -H "@$authorization_header_file" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://designmachines.dev" \
  -H "X-Title: world-b-runner" \
  --connect-timeout "$CONNECT_TIMEOUT" \
  --max-time "$TIMEOUT" \
  --data-binary @- \
  > "$status_file" 2> "$curl_error_file" &
curl_pid=$!
transport_launching=0
if [ "$transport_signal_pending" -eq 1 ]; then
  handle_signal
fi
started_at="$(date +%s)"
last_progress_at="$started_at"
last_size=0
first_byte_seen=0
timeout_kind=""

while kill -0 "$curl_pid" >/dev/null 2>&1; do
  sleep 1
  now="$(date +%s)"
  current_size="$(wc -c < "$stream_file" | tr -d '[:space:]')"
  if [ "$current_size" -gt "$last_size" ]; then
    first_byte_seen=1
    last_progress_at="$now"
    last_size="$current_size"
  fi
  if [ $((now - started_at)) -ge "$TIMEOUT" ]; then
    timeout_kind="overall"
  elif [ "$first_byte_seen" -eq 0 ] &&
       [ $((now - started_at)) -ge "$FIRST_BYTE_TIMEOUT" ]; then
    timeout_kind="first_byte"
  elif [ "$first_byte_seen" -eq 1 ] &&
       [ $((now - last_progress_at)) -ge "$IDLE_TIMEOUT" ]; then
    timeout_kind="idle"
  fi
  if [ -n "$timeout_kind" ]; then
    terminate_transport
    write_failure_receipt timeout "stream_timeout" "$timeout_kind" || true
    echo "### RUNNER TIMEOUT ($MODEL, ${TIMEOUT}s, $timeout_kind)" >&2
    exit 28
  fi
done

wait "$curl_pid"
curl_rc=$?
curl_pid=""
http="$(cat "$status_file")"
if [ "$curl_rc" -eq 28 ]; then
  write_failure_receipt timeout "curl_timeout" "overall" "$http" || true
  echo "### RUNNER TIMEOUT ($MODEL, ${TIMEOUT}s, overall)" >&2
  exit 28
fi
if [ "$curl_rc" -ne 0 ]; then
  write_failure_receipt error "transport_error" "" "$http" || true
  echo "### RUNNER FAILURE ($MODEL, transport error $curl_rc)" >&2
  exit 1
fi
if [ "$http" != "200" ]; then
  write_failure_receipt error "http_error" "" "$http" || true
  echo "### RUNNER FAILURE ($MODEL, HTTP $http)" >&2
  exit 1
fi

awk '
  /^data:/ {
    sub(/^data:[[:space:]]*/, "")
    if ($0 != "[DONE]") print
  }
' "$stream_file" > "$events_file"

# OpenRouter terminates a stream immediately after an in-band error event, so
# that official error shape does not owe a later [DONE] marker. Classify a
# well-formed error event before applying the generic completion-marker check;
# buffered partial content remains private on either failure path.
if [ -s "$events_file" ] && jq -s -e '
  any(.[];
    (.error? != null)
    or (.choices[0].error? != null)
    or (.choices[0].finish_reason? == "error")
  )
' "$events_file" >/dev/null 2>&1; then
  write_failure_receipt error "stream_error" "" "$http" || true
  echo "### RUNNER FAILURE: OpenRouter stream reported an error" >&2
  exit 1
fi

if ! grep -Eq '^data:[[:space:]]*\[DONE\][[:space:]]*$' "$stream_file"; then
  write_failure_receipt error "incomplete_stream" "" "$http" || true
  echo "### RUNNER FAILURE: OpenRouter stream ended without [DONE]" >&2
  exit 1
fi
if [ ! -s "$events_file" ] ||
   ! jq -s -e '
     all(.[];
       (.error? == null)
       and (.choices[0].error? == null)
       and (.choices[0].finish_reason? != "error")
     )
   ' "$events_file" >/dev/null 2>&1; then
  write_failure_receipt error "stream_error" "" "$http" || true
  echo "### RUNNER FAILURE: OpenRouter stream reported an error" >&2
  exit 1
fi

if ! jq -s '
  {
    id: ([.[].id? | select(type == "string" and length > 0)] | first // null),
    created: ([.[].created? | select(type == "number")] | first // null),
    model: ([.[].model? | select(type == "string" and length > 0)] | first // null),
    provider: ([.[].provider? | select(type == "string" and length > 0)] | first // null),
    usage: ([.[].usage? | select(type == "object")] | last // null),
    choices: [{
      message: {
        content: ([.[].choices[0].delta.content? | select(type == "string")] | join(""))
      }
    }]
  }
' "$events_file" > "$response_file"; then
  write_failure_receipt error "malformed_stream" "" "$http" || true
  echo "### RUNNER FAILURE: could not assemble OpenRouter stream" >&2
  exit 1
fi

response_model="$(jq -er '
  select(
    (.id | type) == "string" and (.id | length) > 0
    and (.model | type) == "string" and (.model | length) > 0
    and (.choices[0].message.content | type) == "string"
    and (.choices[0].message.content | length) > 0
  )
  | .model
' "$response_file" 2>/dev/null)" || {
  write_failure_receipt error "missing_generation_provenance" "" "$http" || true
  echo "### RUNNER FAILURE: OpenRouter response omitted required generation provenance" >&2
  exit 1
}

validate_model_slug "$response_model" || {
  write_failure_receipt error "malformed_model_provenance" "" "$http" || true
  echo "### RUNNER FAILURE: OpenRouter response returned malformed model provenance" >&2
  exit 1
}
case "$(printf '%s' "$response_model" | tr '[:upper:]' '[:lower:]')" in
  anthropic/*)
    write_failure_receipt error "native_vendor_origin" "" "$http" || true
    echo "### RUNNER FAILURE: native-vendor-origin invariant rejected served model '$response_model'" >&2
    exit 1
    ;;
esac

fallback_used=false
attempted_model="$MODEL"
if model_matches_family "$response_model" "$MODEL"; then
  :
elif [ -n "$FALLBACK" ] && model_matches_family "$response_model" "$FALLBACK"; then
  fallback_used=true
  attempted_model="$FALLBACK"
else
  write_failure_receipt error "unexpected_model_provenance" "" "$http" || true
  echo "### RUNNER FAILURE: served model '$response_model' does not match any requested model family" >&2
  exit 1
fi

write_success_receipt "$response_file" "$attempted_model" "$fallback_used" || exit 1
jq -r '.choices[0].message.content' "$response_file"
