#!/usr/bin/env bash
# Runner-owned preparation and redispatch verification for schema-v2 interim
# request-envelope authorization. This helper never contacts a provider: it
# invokes openrouter-wrapper.sh only in canonical render-only mode.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

MODE="${1:-}"
[ -n "$MODE" ] || { echo "runner-batch-authorization: prepare|verify required" >&2; exit 2; }
shift

WRAPPER=""
AUTHORIZATION_HELPER=""
SYSTEM_FILE=""
USER_FILE=""
MODEL=""
FALLBACK=""
TIMEOUT=""
WORKLOAD=""
TARGET_AGENT_NAME=""
MANIFEST=""
BATCH_FILE=""
BATCH_DIGEST=""
RUN_ID=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --wrapper) WRAPPER="${2:-}"; shift 2 ;;
    --authorization-helper) AUTHORIZATION_HELPER="${2:-}"; shift 2 ;;
    --system-file) SYSTEM_FILE="${2:-}"; shift 2 ;;
    --user-file) USER_FILE="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --fallback) FALLBACK="${2:-}"; shift 2 ;;
    --timeout) TIMEOUT="${2:-}"; shift 2 ;;
    --workload) WORKLOAD="${2:-}"; shift 2 ;;
    --target-agent-name) TARGET_AGENT_NAME="${2:-}"; shift 2 ;;
    --manifest) MANIFEST="${2:-}"; shift 2 ;;
    --batch-file) BATCH_FILE="${2:-}"; shift 2 ;;
    --batch-digest) BATCH_DIGEST="${2:-}"; shift 2 ;;
    --run-id) RUN_ID="${2:-}"; shift 2 ;;
    *) echo "runner-batch-authorization: unknown argument: $1" >&2; exit 2 ;;
  esac
done

[ -f "$WRAPPER" ] && [ -x "$AUTHORIZATION_HELPER" ] &&
  [ -r "$SYSTEM_FILE" ] && [ -r "$USER_FILE" ] &&
  [ -n "$MODEL" ] && [[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] &&
  [ -n "$WORKLOAD" ] && [ -n "$TARGET_AGENT_NAME" ] && [ -n "$MANIFEST" ] || {
  echo "runner-batch-authorization: required input unavailable or malformed" >&2
  exit 2
}
case "$MODE" in
  prepare) ;;
  verify)
    [ -r "$BATCH_FILE" ] && [[ "$BATCH_DIGEST" =~ ^[0-9a-f]{64}$ ]] &&
      [ -n "$RUN_ID" ] || {
      echo "runner-batch-authorization: batch inputs unavailable or malformed" >&2
      exit 2
    }
    ;;
  *) echo "runner-batch-authorization: prepare|verify required" >&2; exit 2 ;;
esac

REQUEST_FILE=$(mktemp) || {
  echo "runner-batch-authorization: could not allocate request envelope" >&2
  exit 2
}
BATCH_SNAPSHOT=""
cleanup() {
  rm -f "$REQUEST_FILE"
  [ -z "$BATCH_SNAPSHOT" ] || rm -f "$BATCH_SNAPSHOT"
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

if ! env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$SYSTEM_FILE" \
    OPENROUTER_TARGET_AGENT_NAME="$TARGET_AGENT_NAME" \
    OPENROUTER_WORKLOAD="$WORKLOAD" \
    OPENROUTER_REQUEST_ENVELOPE_OUTPUT="$REQUEST_FILE" \
    bash "$WRAPPER" "$MODEL" - "$TIMEOUT" "$FALLBACK" < "$USER_FILE"; then
  echo "runner-batch-authorization: request envelope rendering failed" >&2
  exit 2
fi
[ -r "$REQUEST_FILE" ] && [ -s "$REQUEST_FILE" ] || {
  echo "runner-batch-authorization: rendered request envelope is unreadable or empty" >&2
  exit 2
}

if [ "$MODE" = "prepare" ]; then
  if ! REQUEST_ENVELOPE_SHA256=$("$AUTHORIZATION_HELPER" snapshot-envelope \
      --output "$MANIFEST" --request-file "$REQUEST_FILE"); then
    echo "runner-batch-authorization: request envelope snapshot failed" >&2
    exit 2
  fi
  [[ "$REQUEST_ENVELOPE_SHA256" =~ ^[0-9a-f]{64}$ ]] &&
    [ -r "$MANIFEST" ] && [ -s "$MANIFEST" ] || {
    echo "runner-batch-authorization: request envelope snapshot is malformed or unavailable" >&2
    exit 2
  }
  INSPECTION_PATH=$(jq -er '.inspectionPath | select(type == "string" and length > 0)' \
    "$MANIFEST") || {
    echo "runner-batch-authorization: request envelope inspection path is unavailable" >&2
    exit 2
  }
  [ -r "$INSPECTION_PATH" ] && [ -s "$INSPECTION_PATH" ] || {
    echo "runner-batch-authorization: retained request envelope is unavailable" >&2
    exit 2
  }
  jq -n --arg digest "$REQUEST_ENVELOPE_SHA256" --arg manifest "$MANIFEST" \
    --arg inspection "$INSPECTION_PATH" \
    '{authorizationMode:"prepare-interim-operator-batch", authorizationScope:"exact-request-envelope-bytes", requestEnvelopeSha256:$digest, manifest:$manifest, inspectionPath:$inspection}'
  exit 0
fi

# Verify the redispatch against the immutable PREPARATION manifest. Rewriting
# that file from the redispatch bytes immediately before verify-batch made the
# helper's prepare-vs-redispatch comparison tautological; exact batch
# membership still protected transmission, but the advertised drift check was
# dead.
[ -r "$MANIFEST" ] && [ -s "$MANIFEST" ] || {
  echo "runner-batch-authorization: preparation manifest is unavailable" >&2
  exit 2
}

BATCH_SNAPSHOT=$(mktemp) || {
  echo "runner-batch-authorization: could not allocate batch snapshot" >&2
  exit 2
}
if ! cp "$BATCH_FILE" "$BATCH_SNAPSHOT"; then
  echo "runner-batch-authorization: batch snapshot failed" >&2
  exit 2
fi
ACTUAL_BATCH_DIGEST=$(shasum -a 256 "$BATCH_SNAPSHOT" | awk '{print $1}') || {
  echo "runner-batch-authorization: batch digest could not be computed" >&2
  exit 2
}
[ "$ACTUAL_BATCH_DIGEST" = "$BATCH_DIGEST" ] || {
  echo "runner-batch-authorization: batch file does not match its declared digest" >&2
  exit 2
}
if ! VERIFICATION_JSON=$("$AUTHORIZATION_HELPER" verify-batch \
    --batch-file "$BATCH_SNAPSHOT" --run-id "$RUN_ID" \
    --lane-id "$TARGET_AGENT_NAME" \
    --manifest "$MANIFEST" --request-file "$REQUEST_FILE"); then
  echo "runner-batch-authorization: redispatch request envelope is not authorized" >&2
  exit 2
fi
[ -n "$VERIFICATION_JSON" ] || {
  echo "runner-batch-authorization: redispatch authorization receipt is empty" >&2
  exit 2
}
printf '%s\n' "$VERIFICATION_JSON"
