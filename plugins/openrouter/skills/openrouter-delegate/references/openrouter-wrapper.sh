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
#   OPENROUTER_AUTHORIZATION_MODE
#                       exact-digest|trusted-boundary|interim-operator-batch|
#                       unspecified for receipts
#   OPENROUTER_APPROVED_REQUEST_ENVELOPE_SHA256
#                       optional exact request-envelope digest; required by the
#                       dm-review exact-digest runner and rechecked immediately
#                       before provider contact
#   OPENROUTER_AUTHORIZATION_RUN_ID
#                       optional authorization-run identity for non-batch modes;
#                       automated runners supply it, while direct interactive
#                       receipts represent its absence as null
#   OPENROUTER_LANE_ID  optional authorization-lane identity; automated runners
#                       supply it, while direct receipts fall back to the target
#                       agent name when available
#   OPENROUTER_BATCH_AUTHORIZATION_FILE
#                       required when the mode is interim-operator-batch: the
#                       run-scoped batch authorization file written by
#                       payload-authorization.sh batch-approve
#   OPENROUTER_BATCH_AUTHORIZATION_DIGEST
#                       required when the mode is interim-operator-batch: the
#                       sha256 of that file's exact bytes, receipted alongside
#                       the mode
#   OPENROUTER_BATCH_RUN_ID
#                       required when the mode is interim-operator-batch: the
#                       CURRENT run id. The wrapper refuses a batch whose
#                       .run_id names a different run, so a batch approved for
#                       one run can never authorize transmission in another.
#                       This is enforced here independently of verify-batch:
#                       the wrapper must not assume any earlier step ran.
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
if [ -n "${OPENROUTER_API_KEY:-}" ] && [ -n "${OPENROUTER_API_KEY_FILE:-}" ]; then
  echo "### RUNNER FAILURE: OPENROUTER_API_KEY and OPENROUTER_API_KEY_FILE are mutually exclusive" >&2
  exit 2
fi
if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  [ -n "${OPENROUTER_API_KEY_FILE:-}" ] || {
    echo "### RUNNER FAILURE: OPENROUTER_API_KEY or OPENROUTER_API_KEY_FILE required" >&2
    exit 1
  }
  [ -x /usr/bin/python3 ] || {
    echo "### RUNNER FAILURE: /usr/bin/python3 required to validate OPENROUTER_API_KEY_FILE" >&2
    exit 1
  }
  OPENROUTER_API_KEY="$(/usr/bin/python3 -I - "$OPENROUTER_API_KEY_FILE" <<'PY'
import os
import stat
import sys

path = sys.argv[1]
try:
    metadata = os.lstat(path)
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise ValueError
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise ValueError
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise ValueError
        value = os.read(descriptor, 8193)
    finally:
        os.close(descriptor)
    if value.endswith(b"\r\n"):
        value = value[:-2]
    elif value.endswith(b"\n"):
        value = value[:-1]
    if not value or len(value) > 8192 or b"\n" in value or b"\r" in value or b"\0" in value:
        raise ValueError
    sys.stdout.write(value.decode("utf-8"))
except (OSError, UnicodeDecodeError, ValueError):
    raise SystemExit(1)
PY
)" || {
    echo "### RUNNER FAILURE: OPENROUTER_API_KEY_FILE must be a non-symlink regular file owned by the current UID with mode 0600 and one non-empty line" >&2
    exit 1
  }
fi
export OPENROUTER_API_KEY

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
APPROVED_REQUEST_ENVELOPE_SHA256="${OPENROUTER_APPROVED_REQUEST_ENVELOPE_SHA256:-}"
CURRENT_RUN_ID="${OPENROUTER_AUTHORIZATION_RUN_ID:-}"
TARGET_AGENT_NAME="${OPENROUTER_TARGET_AGENT_NAME:-}"
AUTHORIZATION_LANE_ID="${OPENROUTER_LANE_ID:-$TARGET_AGENT_NAME}"

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
if [ -n "$APPROVED_REQUEST_ENVELOPE_SHA256" ] &&
   [[ ! "$APPROVED_REQUEST_ENVELOPE_SHA256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "### RUNNER FAILURE: invalid approved request envelope digest" >&2
  exit 2
fi
if [ "$AUTHORIZATION_MODE" = "exact-digest" ] &&
   [ -z "$APPROVED_REQUEST_ENVELOPE_SHA256" ] &&
   [ -z "${OPENROUTER_REQUEST_ENVELOPE_OUTPUT:-}" ]; then
  echo "### RUNNER FAILURE: exact-digest requires an approved request envelope digest" >&2
  exit 2
fi
case "$TARGET_AGENT_NAME" in
  "") ;;
  *[!a-z0-9-]*) echo "### RUNNER FAILURE: invalid OPENROUTER_TARGET_AGENT_NAME" >&2; exit 2 ;;
  *) ;;
esac
if [ "$AUTHORIZATION_MODE" = "interim-operator-batch" ] && [ -z "$TARGET_AGENT_NAME" ]; then
  echo "### RUNNER FAILURE: interim-operator-batch requires OPENROUTER_TARGET_AGENT_NAME" >&2
  exit 2
fi
case "$TARGET_AGENT_NAME" in
  security-auditor*)
    # This caller label catches accidental role/model drift. It is not, by
    # itself, an adversarial identity boundary. Interim mode additionally
    # requires the transmitted digest and model candidates to match the
    # durable operator-reviewed lane entry; exact-digest mode remains bounded
    # by its per-payload human approval.
    [ "$MODEL" = "moonshotai/kimi-k3" ] &&
      [ "$FALLBACK" = "z-ai/glm-5.2" ] || {
      echo "### RUNNER FAILURE: security review role requires Kimi K3 primary and GLM-5.2 fallback" >&2
      exit 2
    }
    ;;
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

require_interim_broker_absent() {
  local state
  state="$(broker_state)"
  case "$state" in
    ready)
      echo "### RUNNER FAILURE: broker available; interim mode retired on this host" >&2
      return 2
      ;;
    present_not_ready)
      echo "### RUNNER FAILURE: broker_present_not_ready; broker client is installed but does not probe ready -- interim mode withheld" >&2
      return 2
      ;;
    absent)
      return 0
      ;;
    *)
      echo "### RUNNER FAILURE: broker state unresolved; interim mode withheld" >&2
      return 2
      ;;
  esac
}

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

if [ "$AUTHORIZATION_MODE" = "interim-operator-batch" ]; then
  require_interim_broker_absent || exit $?
  BATCH_AUTHORIZATION_FILE="${OPENROUTER_BATCH_AUTHORIZATION_FILE:-}"
  DECLARED_BATCH_DIGEST="${OPENROUTER_BATCH_AUTHORIZATION_DIGEST:-}"
  CURRENT_RUN_ID="${OPENROUTER_BATCH_RUN_ID:-}"
  [ -n "$BATCH_AUTHORIZATION_FILE" ] && [ -f "$BATCH_AUTHORIZATION_FILE" ] &&
    [ -r "$BATCH_AUTHORIZATION_FILE" ] || {
    echo "### RUNNER FAILURE: interim-operator-batch requires a readable batch authorization file" >&2
    exit 2
  }
  [[ "$DECLARED_BATCH_DIGEST" =~ ^[0-9a-f]{64}$ ]] || {
    echo "### RUNNER FAILURE: interim-operator-batch requires the batch authorization digest" >&2
    exit 2
  }
  [ -n "$CURRENT_RUN_ID" ] || {
    echo "### RUNNER FAILURE: interim-operator-batch requires the current run id" >&2
    exit 2
  }
  SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
  AUTHORIZATION_HELPER="$SCRIPT_DIR/payload-authorization.sh"
  MODEL_MATRIX="$SCRIPT_DIR/model-matrix.json"
  [ -x "$AUTHORIZATION_HELPER" ] && [ -r "$MODEL_MATRIX" ] || {
    echo "### RUNNER FAILURE: interim authorization bundle is incomplete" >&2
    exit 2
  }
  for candidate in "$MODEL" "$FALLBACK"; do
    [ -z "$candidate" ] && continue
    jq -e --arg candidate "$candidate" \
      'any(.models[]; .slug == $candidate)' "$MODEL_MATRIX" >/dev/null 2>&1 || {
      echo "### RUNNER FAILURE: interim model is absent from the installed model matrix" >&2
      exit 2
    }
  done
  # SNAPSHOT ONCE. Everything below -- digest, schema, run binding, timestamps
  # and the later membership test -- reads this private copy, never the
  # caller-supplied path. Re-reading the original between the hash and the
  # membership test would leave a window in which the bytes that were validated
  # and the bytes that were tested for membership are different files.
  BATCH_AUTHORIZATION_SNAPSHOT="$RUN_ROOT/batch-authorization.snapshot.json"
  (
    umask 077
    cat "$BATCH_AUTHORIZATION_FILE" > "$BATCH_AUTHORIZATION_SNAPSHOT"
  ) || {
    echo "### RUNNER FAILURE: could not snapshot the batch authorization file" >&2
    exit 2
  }
  BATCH_AUTHORIZATION_SHA256="$(shasum -a 256 "$BATCH_AUTHORIZATION_SNAPSHOT" | awk '{print $1}')" || {
    echo "### RUNNER FAILURE: could not digest the batch authorization file" >&2
    exit 2
  }
  [ "$BATCH_AUTHORIZATION_SHA256" = "$DECLARED_BATCH_DIGEST" ] || {
    echo "### RUNNER FAILURE: batch authorization file does not match its declared digest" >&2
    exit 2
  }
  jq -e --arg expected "$INTERIM_PROGRAM_SUNSET" \
    '.program_sunset == $expected' "$BATCH_AUTHORIZATION_SNAPSHOT" >/dev/null 2>&1 || {
    echo "### RUNNER FAILURE: batch program sunset does not match the wrapper release" >&2
    exit 2
  }
  # One OpenRouter-owned typed validator owns schema, run, expiry, lifetime,
  # and sunset semantics. The wrapper passes its private immutable snapshot so
  # the helper and the later membership check inspect the same batch bytes.
  "$AUTHORIZATION_HELPER" validate-batch \
    --batch-file "$BATCH_AUTHORIZATION_SNAPSHOT" \
    --run-id "$CURRENT_RUN_ID" >/dev/null || exit 2
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
      --arg authorization "$AUTHORIZATION_MODE" \
      --arg batchdigest "$BATCH_AUTHORIZATION_SHA256" \
      --arg runid "${CURRENT_RUN_ID:-}" \
      --arg lane "$AUTHORIZATION_LANE_ID" \
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
          mode: $authorization,
          batchSha256: (if $batchdigest == "" then null else $batchdigest end),
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
      --arg authorization "$AUTHORIZATION_MODE" \
      --arg batchdigest "$BATCH_AUTHORIZATION_SHA256" \
      --arg runid "${CURRENT_RUN_ID:-}" \
      --arg lane "$AUTHORIZATION_LANE_ID" \
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
          mode: $authorization,
          batchSha256: (if $batchdigest == "" then null else $batchdigest end),
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

# Preparation mode uses this same renderer without contacting the provider.
# The caller can snapshot and approve these exact bytes, then invoke the
# wrapper normally with unchanged inputs. Keeping rendering here prevents a
# second implementation from drifting in whitespace, provider fields, model
# versus models selection, or message ordering.
if [ -n "${OPENROUTER_REQUEST_ENVELOPE_OUTPUT:-}" ]; then
  RENDERED_REQUEST_BYTES="$(cat "$request_file")" || {
    echo "### RUNNER FAILURE: could not read the rendered request envelope" >&2
    exit 2
  }
  (
    umask 077
    printf '%s' "$RENDERED_REQUEST_BYTES" > "$OPENROUTER_REQUEST_ENVELOPE_OUTPUT"
  ) || {
    echo "### RUNNER FAILURE: could not materialize the request envelope" >&2
    exit 2
  }
  exit 0
fi

# The bytes curl posts, held in process memory. curl is fed these bytes on
# stdin (`--data-binary @-`) and is never handed a path, so there is no reopen
# between any check and the POST. Under interim mode this same in-memory copy
# is what the payload digest is computed over.
TRANSMIT_BYTES=""
if [ "$AUTHORIZATION_MODE" != "interim-operator-batch" ]; then
  TRANSMIT_BYTES="$(cat "$request_file")" || {
    echo "### RUNNER FAILURE: could not read the request body for transmission" >&2
    exit 2
  }
  [ -n "$TRANSMIT_BYTES" ] || {
    echo "### RUNNER FAILURE: could not read the request body for transmission" >&2
    exit 2
  }
fi

if [ "$AUTHORIZATION_MODE" = "interim-operator-batch" ]; then
  # Digest binding at the point of disclosure, over the bytes actually about to
  # be sent. `verify-batch` runs in the calling lane, but this wrapper must not
  # assume it ran. The exact request envelope curl is about to POST--including
  # model(s), provider routing, streaming options, roles, and ordered message
  # content--must already be bound to this lane in the validated batch.
  #
  # ONE OPEN, ONE COPY. Copying the request body to another path and handing
  # curl that path still leaves curl reopening a mutable name after the digest
  # was taken, so the bytes hashed and the bytes sent are only assumed to be
  # equal. Instead: open the private copy on a dedicated descriptor, UNLINK the
  # path immediately so no name resolves to it any more, read the bytes once
  # through that descriptor into process memory, and drive both the digest and
  # the POST from that single in-memory copy. curl is fed stdin, never a path.
  TRANSMIT_FILE="$RUN_ROOT/request.transmit.json"
  (
    umask 077
    cat "$request_file" > "$TRANSMIT_FILE"
  ) || {
    echo "### RUNNER FAILURE: could not snapshot the request body for batch digest binding" >&2
    exit 2
  }
  [ -r "$TRANSMIT_FILE" ] || {
    echo "### RUNNER FAILURE: could not bind the request body to a transmission descriptor" >&2
    exit 2
  }
  exec 9<"$TRANSMIT_FILE" || {
    echo "### RUNNER FAILURE: could not bind the request body to a transmission descriptor" >&2
    exit 2
  }
  rm -f "$TRANSMIT_FILE" || {
    echo "### RUNNER FAILURE: could not unlink the bound request body path" >&2
    exit 2
  }
  TRANSMIT_BYTES="$(cat <&9)" || {
    echo "### RUNNER FAILURE: could not read the bound request body" >&2
    exit 2
  }
  exec 9<&- || {
    echo "### RUNNER FAILURE: could not release the transmission descriptor" >&2
    exit 2
  }
  [ -n "$TRANSMIT_BYTES" ] || {
    echo "### RUNNER FAILURE: could not read the bound request body" >&2
    exit 2
  }
  printf '%s' "$TRANSMIT_BYTES" | jq -e '
    (.messages | type) == "array"
    and (.messages | length) > 0
    and (all(.messages[]; (.content | type) == "string"))
  ' >/dev/null 2>&1 || {
    echo "### RUNNER FAILURE: non-string message content cannot be bound to the batch authorization; interim mode withheld" >&2
    exit 2
  }
  # The nonzero return is CHECKED, not inferred from the shape of the output: a
  # read or extraction failure inside the digest must fail closed rather than
  # yield a partial digest that happens to look like a sha256.
  TRANSMITTED_REQUEST_ENVELOPE_SHA256="$(printf '%s' "$TRANSMIT_BYTES" | shasum -a 256 | awk '{print $1}')" || {
    echo "### RUNNER FAILURE: could not compute the transmitted request envelope digest" >&2
    exit 2
  }
  [[ "$TRANSMITTED_REQUEST_ENVELOPE_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "### RUNNER FAILURE: could not compute the transmitted request envelope digest" >&2
    exit 2
  }
  jq -e --arg digest "$TRANSMITTED_REQUEST_ENVELOPE_SHA256" \
    --arg lane "$TARGET_AGENT_NAME" --argjson models "$MODEL_CANDIDATES" '
    any(.lanes[];
      .lane_id == $lane
      and .requestEnvelopeSha256 == $digest
      and .modelCandidates == $models)
  ' "$BATCH_AUTHORIZATION_SNAPSHOT" >/dev/null 2>&1 || {
    echo "### RUNNER FAILURE: transmitted request envelope is not bound to this approved lane and model set" >&2
    exit 2
  }
  # Broker retirement is a disclosure-time invariant, not a process-start
  # observation. Prompt ingestion and envelope validation can block long
  # enough for the broker to appear after the first probe. Recheck only after
  # the exact transmitted bytes have passed membership and immediately before
  # opening the provider connection.
  require_interim_broker_absent || exit $?
fi

if [ -z "${TRANSMITTED_REQUEST_ENVELOPE_SHA256:-}" ]; then
  TRANSMITTED_REQUEST_ENVELOPE_SHA256="$(printf '%s' "$TRANSMIT_BYTES" | shasum -a 256 | awk '{print $1}')" || {
    echo "### RUNNER FAILURE: could not compute the transmitted request envelope digest" >&2
    exit 2
  }
  [[ "$TRANSMITTED_REQUEST_ENVELOPE_SHA256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "### RUNNER FAILURE: could not compute the transmitted request envelope digest" >&2
    exit 2
  }
fi

if [ "$AUTHORIZATION_MODE" = "exact-digest" ]; then
  if [ "$TRANSMITTED_REQUEST_ENVELOPE_SHA256" != "$APPROVED_REQUEST_ENVELOPE_SHA256" ]; then
    echo "### RUNNER FAILURE: transmitted request envelope digest was not approved" >&2
    exit 2
  fi
fi

: > "$stream_file"
: > "$status_file"
: > "$curl_error_file"
transport_launching=1
printf '%s' "$TRANSMIT_BYTES" | curl -N -sS -o "$stream_file" -w '%{http_code}' \
  "$BASE/chat/completions" \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
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
