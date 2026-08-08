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
#   OPENROUTER_API_KEY   required
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
#   OPENROUTER_AUTHORIZATION_MODE
#                       exact-digest|trusted-boundary|interim-operator-batch|
#                       unspecified for receipts
#   OPENROUTER_BATCH_AUTHORIZATION_FILE
#                       required when the mode is interim-operator-batch: the
#                       run-scoped batch authorization file written by
#                       payload-authorization.sh batch-approve
#   OPENROUTER_BATCH_AUTHORIZATION_DIGEST
#                       required when the mode is interim-operator-batch: the
#                       sha256 of that file's exact bytes, receipted alongside
#                       the mode
#   OPENROUTER_RECEIPT_FILE
#                       optional content-free success or failure receipt path
#
# Interim operator-batch mode is a temporary, sunset-bound loosening of approval
# granularity. Setting these variables does not by itself create an
# authorization: this wrapper requires a batch file whose bytes match the
# declared digest, whose schema, run, expiry, and pinned sunset fields all
# validate, and which already contains the canonical digest of the content this
# invocation is about to transmit.
# No environment variable substitutes for the interactive confirmation.
# The batch file is PROCEDURAL and UNAUTHENTICATED: it carries no signature and
# no user-presence binding, so a same-user process can forge one. The
# interactive confirmation guards against accidental and automated entry by
# this tooling, not against same-user forgery. Closing that gap is what the
# out-of-process Workflow Authority Broker does, and it is the primary reason
# this mode is sunset-bound.
# A ready broker retires the mode: this wrapper refuses with
# "broker available; interim mode retired on this host". An installed broker
# client that does not probe ready is an unknown state and also refuses, with
# reason broker_present_not_ready.
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
[ -z "${OPENROUTER_API_KEY:-}" ] && {
  echo "### RUNNER FAILURE: OPENROUTER_API_KEY unset" >&2
  exit 1
}

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
AUTHORIZATION_MODE="${OPENROUTER_AUTHORIZATION_MODE:-unspecified}"

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
case "$AUTHORIZATION_MODE" in
  exact-digest|trusted-boundary|interim-operator-batch|unspecified) ;;
  *) echo "### RUNNER FAILURE: invalid OPENROUTER_AUTHORIZATION_MODE" >&2; exit 2 ;;
esac

# Fixed, non-overridable probe path -- a caller-selected probe would let the
# interim mode outlive a ready broker.
BROKER_CLIENT="/usr/local/bin/workflow-authority"
# Single source for the interim program sunset in this file. It must stay equal
# to PROGRAM_SUNSET in payload-authorization.sh; tools/validate-workflow-contracts.sh
# Group 8 pins the same literal in every enforcement layer so the calendar
# backstop is never self-asserted by the batch file alone.
INTERIM_PROGRAM_SUNSET="2026-09-07"
BATCH_AUTHORIZATION_SHA256=""
BATCH_AUTHORIZATION_FILE=""
# Three broker states, not two. Only "absent" leaves interim mode available.
# An installed client whose probe errors, is unparseable, or does not report
# ready is an UNKNOWN state and fails closed rather than widening exposure.
# jq decides readiness, not a substring glob: a glob false-negative on a
# formatting variation would let interim mode run above a ready broker.
broker_state() {
  if [ ! -x "$BROKER_CLIENT" ]; then
    printf 'absent'
    return 0
  fi
  local probe=""
  if ! probe="$("$BROKER_CLIENT" probe --format json 2>/dev/null)"; then
    printf 'present_not_ready'
    return 0
  fi
  if ! command -v jq >/dev/null 2>&1; then
    printf 'present_not_ready'
    return 0
  fi
  if printf '%s' "$probe" | jq -e '.status == "ready"' >/dev/null 2>&1; then
    printf 'ready'
    return 0
  fi
  printf 'present_not_ready'
}

# Canonical exact-ordered-content-bytes digest, byte-identical to the framing
# payload-authorization.sh uses when it snapshots a single content file:
# sha256(index_be64 || length_be64 || bytes).
canonical_content_digest() {
  local file="$1" size="" index_escape="" length_escape=""
  size="$(wc -c < "$file" | tr -d '[:space:]')"
  index_escape="$(printf '%016x' 0 | sed 's/../\\x&/g')"
  length_escape="$(printf '%016x' "$size" | sed 's/../\\x&/g')"
  {
    printf '%b' "$index_escape"
    printf '%b' "$length_escape"
    cat "$file"
  } | shasum -a 256 | awk '{print $1}'
}

if [ "$AUTHORIZATION_MODE" = "interim-operator-batch" ]; then
  BROKER_STATE="$(broker_state)"
  case "$BROKER_STATE" in
    ready)
      echo "### RUNNER FAILURE: broker available; interim mode retired on this host" >&2
      exit 2
      ;;
    present_not_ready)
      echo "### RUNNER FAILURE: broker_present_not_ready; broker client is installed but does not probe ready -- interim mode withheld" >&2
      exit 2
      ;;
  esac
  BATCH_AUTHORIZATION_FILE="${OPENROUTER_BATCH_AUTHORIZATION_FILE:-}"
  DECLARED_BATCH_DIGEST="${OPENROUTER_BATCH_AUTHORIZATION_DIGEST:-}"
  [ -n "$BATCH_AUTHORIZATION_FILE" ] && [ -f "$BATCH_AUTHORIZATION_FILE" ] &&
    [ -r "$BATCH_AUTHORIZATION_FILE" ] || {
    echo "### RUNNER FAILURE: interim-operator-batch requires a readable batch authorization file" >&2
    exit 2
  }
  [[ "$DECLARED_BATCH_DIGEST" =~ ^[0-9a-f]{64}$ ]] || {
    echo "### RUNNER FAILURE: interim-operator-batch requires the batch authorization digest" >&2
    exit 2
  }
  BATCH_AUTHORIZATION_SHA256="$(shasum -a 256 "$BATCH_AUTHORIZATION_FILE" | awk '{print $1}')"
  [ "$BATCH_AUTHORIZATION_SHA256" = "$DECLARED_BATCH_DIGEST" ] || {
    echo "### RUNNER FAILURE: batch authorization file does not match its declared digest" >&2
    exit 2
  }
  # The sunset is PINNED to this release's constant, not merely parsed as a
  # future date. Pinning and expiry are different controls: pinning stops a
  # hand-written batch file from asserting its own later backstop, expiry stops
  # a stale one from being replayed.
  jq -e --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --arg sunset "$INTERIM_PROGRAM_SUNSET" '
    .schema_version == 1
    and .authorization_mode == "interim_operator_batch"
    and (.run_id | type == "string" and length > 0)
    and (.payload_digests | type == "array" and length > 0)
    and (.expires_at > $now)
    and .program_sunset == $sunset
    and ((.program_sunset + "T00:00:00Z") > $now)
  ' "$BATCH_AUTHORIZATION_FILE" >/dev/null 2>&1 || {
    echo "### RUNNER FAILURE: batch authorization is expired, past program sunset, sunset-mismatched, or malformed" >&2
    exit 2
  }
fi
for configured_order in "$PROVIDER_ORDER" "$FALLBACK_PROVIDER_ORDER"; do
  [ -z "$configured_order" ] && continue
  case "$configured_order" in
    *".."*|,*|*,|*,,*|*[!A-Za-z0-9._,/-]*)
      echo "### RUNNER FAILURE: invalid OpenRouter provider order" >&2
      exit 2
      ;;
  esac
done

RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/openrouter-wrapper.XXXXXX")" || exit 1
chmod 700 "$RUN_ROOT"
cleanup() {
  rm -rf "$RUN_ROOT"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

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
      --arg failure "$failure_kind" \
      --arg timeout "$timeout_kind" \
      --arg http "$http_status" \
      --arg requested "$MODEL" \
      --argjson candidates "$MODEL_CANDIDATES" \
      --arg workload "$WORKLOAD" \
      --arg sort "$EFFECTIVE_SORT" \
      --arg authorization "$AUTHORIZATION_MODE" \
      --arg batchdigest "$BATCH_AUTHORIZATION_SHA256" '
      {
        schemaVersion: 2,
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
          mode: $authorization,
          batchSha256: (if $batchdigest == "" then null else $batchdigest end)
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
      --arg attempted "$attempted_model" \
      --argjson candidates "$MODEL_CANDIDATES" \
      --argjson fallback "$fallback_used" \
      --arg workload "$WORKLOAD" \
      --arg sort "$EFFECTIVE_SORT" \
      --arg authorization "$AUTHORIZATION_MODE" \
      --arg batchdigest "$BATCH_AUTHORIZATION_SHA256" '
      {
        schemaVersion: 2,
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
          mode: $authorization,
          batchSha256: (if $batchdigest == "" then null else $batchdigest end)
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

if [ "$AUTHORIZATION_MODE" = "interim-operator-batch" ]; then
  # Digest binding at the point of disclosure, over the bytes actually about to
  # be sent. `verify-batch` runs in the calling lane, but this wrapper must not
  # assume it ran, and must not rely on a digest taken over a separately
  # snapshotted file: a payload swapped in after verify-batch passed would
  # otherwise still be transmitted. The disclosed content is read back out of
  # the request body curl is about to POST and must already be a member of the
  # validated batch file's payload_digests.
  transmitted_content_file="$RUN_ROOT/transmitted.content"
  jq -j '[.messages[] | select(.role == "user") | .content] | add // ""' \
    "$request_file" > "$transmitted_content_file" || {
    echo "### RUNNER FAILURE: could not read transmitted content for batch digest binding" >&2
    exit 2
  }
  TRANSMITTED_PAYLOAD_SHA256="$(canonical_content_digest "$transmitted_content_file")"
  [[ "$TRANSMITTED_PAYLOAD_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "### RUNNER FAILURE: could not compute the transmitted payload digest" >&2
    exit 2
  }
  jq -e --arg digest "$TRANSMITTED_PAYLOAD_SHA256" '
    (.payload_digests | index($digest)) != null
  ' "$BATCH_AUTHORIZATION_FILE" >/dev/null 2>&1 || {
    echo "### RUNNER FAILURE: transmitted payload digest is not in the batch authorization" >&2
    exit 2
  }
fi

: > "$stream_file"
: > "$status_file"
: > "$curl_error_file"
curl -N -sS -o "$stream_file" -w '%{http_code}' \
  "$BASE/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -H "HTTP-Referer: https://designmachines.dev" \
  -H "X-Title: world-b-runner" \
  --connect-timeout "$CONNECT_TIMEOUT" \
  --max-time "$TIMEOUT" \
  --data-binary "@$request_file" \
  > "$status_file" 2> "$curl_error_file" &
curl_pid=$!
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
    kill "$curl_pid" >/dev/null 2>&1 || true
    wait "$curl_pid" >/dev/null 2>&1 || true
    write_failure_receipt timeout "stream_timeout" "$timeout_kind" || true
    echo "### RUNNER TIMEOUT ($MODEL, ${TIMEOUT}s, $timeout_kind)" >&2
    exit 28
  fi
done

wait "$curl_pid"
curl_rc=$?
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
