#!/usr/bin/env bash
# Run one depot-role-v1 case against one exact native subscription model.
# This complements the OpenRouter-owned runner without changing its provider
# boundary. It retains raw CLI telemetry privately and emits the same scored
# result shape plus transport/billing provenance.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROLE_POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
BENCH="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
CODEX_BIN="${DEPOT_BENCH_CODEX_BIN:-codex}"
CLAUDE_BIN="${DEPOT_BENCH_CLAUDE_BIN:-claude}"

CASE_ID=""
MODEL=""
TRANSPORT=""
EFFORT="medium"
RESULT_DIR=""

usage() {
  printf '%s\n' \
    'usage: run-native-depot-role-benchmark.sh --case ID --transport codex-cli|claude-cli --model EXACT_ID --effort low|medium|high|max --result-dir PATH'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) CASE_ID="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --transport) TRANSPORT="${2:-}"; shift 2 ;;
    --effort) EFFORT="${2:-}"; shift 2 ;;
    --result-dir) RESULT_DIR="${2:-}"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[ -n "$CASE_ID" ] && [ -n "$MODEL" ] && [ -n "$TRANSPORT" ] && [ -n "$RESULT_DIR" ] || { usage >&2; exit 2; }
case "$TRANSPORT" in codex-cli|claude-cli) ;; *) usage >&2; exit 2 ;; esac
case "$EFFORT" in low|medium|high|max) ;; *) usage >&2; exit 2 ;; esac
[ -x "$BENCH" ] || { printf 'native benchmark: OpenRouter scorer unavailable\n' >&2; exit 2; }
jq -e --arg model "$MODEL" --arg transport "$TRANSPORT" '
  any(.roles[][]; .model == $model and .transport == $transport)
' "$ROLE_POLICY" >/dev/null || {
  printf 'native benchmark: exact model/transport pair must be admitted by role-policy.json\n' >&2
  exit 2
}

mkdir -p "$RESULT_DIR"
chmod 700 "$RESULT_DIR"
RESULT_DIR="$(cd "$RESULT_DIR" && pwd)"
PROMPT="$RESULT_DIR/prompt.txt"
OUTPUT="$RESULT_DIR/output.json"
RECEIPT="$RESULT_DIR/receipt.json"
RESULT="$RESULT_DIR/result.json"
RAW="$RESULT_DIR/native-events.json"
STDERR_FILE="$RESULT_DIR/native-stderr.txt"

"$BENCH" --prepare --case "$CASE_ID" --output-file "$PROMPT"
start="$(date +%s)"
status=0

if [ "$TRANSPORT" = codex-cli ]; then
  set +e
  (
    cd "$RESULT_DIR"
    "$CODEX_BIN" exec --ephemeral --ignore-user-config --skip-git-repo-check \
      --sandbox read-only --model "$MODEL" \
      --config "model_reasoning_effort=\"$EFFORT\"" \
      --json --output-last-message "$OUTPUT" - < "$PROMPT"
  ) > "$RAW" 2> "$STDERR_FILE"
  status=$?
  set -e
  [ -f "$OUTPUT" ] || : > "$OUTPUT"
  usage_json="$(jq -sc '
    [.. | objects | select(
      has("input_tokens") or has("output_tokens") or has("reasoning_tokens") or
      has("input_usage_count") or has("output_usage_count")
    )] | last // {}
    | {
        prompt_tokens:(.input_tokens // .input_usage_count // null),
        completion_tokens:(.output_tokens // .output_usage_count // null),
        reasoning_tokens:(.reasoning_tokens // .reasoning_usage_count // null),
        cache_read_tokens:(.cached_input_tokens // .cache_read_usage_count // null),
        cost:null
      }
  ' "$RAW" 2>/dev/null || printf '{}')"
  provider=openai
  response_model="$(jq -sr --arg fallback "$MODEL" '
    [.. | objects | .model? | select(type == "string" and length > 0)] | last // $fallback
  ' "$RAW" 2>/dev/null || printf '%s' "$MODEL")"
else
  set +e
  (
    cd "$RESULT_DIR"
    "$CLAUDE_BIN" --print --model "$MODEL" --effort "$EFFORT" --tools "" \
      --no-session-persistence --output-format json < "$PROMPT"
  ) > "$RAW" 2> "$STDERR_FILE"
  status=$?
  set -e
  if jq -e '.structured_output | type == "object"' "$RAW" >/dev/null 2>&1; then
    jq '.structured_output' "$RAW" > "$OUTPUT"
  elif jq -e '.result | type == "string"' "$RAW" >/dev/null 2>&1; then
    jq -r '.result' "$RAW" > "$OUTPUT"
  else
    : > "$OUTPUT"
  fi
  usage_json="$(jq -c '
    (.usage // {}) as $usage
    | {
        prompt_tokens:($usage.input_tokens // null),
        completion_tokens:($usage.output_tokens // null),
        reasoning_tokens:($usage.reasoning_tokens // null),
        cache_read_tokens:($usage.cache_read_input_tokens // null),
        cache_creation_tokens:($usage.cache_creation_input_tokens // null),
        cost:null
      }
  ' "$RAW" 2>/dev/null || printf '{}')"
  provider=anthropic
  response_model="$(jq -r --arg fallback "$MODEL" '
    if (.model // null | type) == "string" then .model
    elif (.modelUsage // null | type) == "object" and (.modelUsage | length) > 0 then (.modelUsage | keys[0])
    else $fallback end
  ' "$RAW" 2>/dev/null || printf '%s' "$MODEL")"
fi

end="$(date +%s)"
duration="$((end-start))"
outcome=success
[ "$status" -eq 0 ] || outcome=failed
jq -n \
  --arg requested "$MODEL" --arg response "$response_model" --arg provider "$provider" \
  --arg transport "$TRANSPORT" --arg billing included-subscription \
  --arg effort "$EFFORT" --arg outcome "$outcome" --argjson usage "$usage_json" \
  '{schemaVersion:1,requestedModel:$requested,responseModel:$response,
    servingProvider:$provider,transport:$transport,billingMode:$billing,
    effort:$effort,outcome:$outcome,usage:$usage,fallbackUsed:false,
    tokenProvenance:(if (($usage.prompt_tokens // null) == null and ($usage.completion_tokens // null) == null)
      then "native-cli-unavailable" else "native-cli" end),
    costProvenance:"subscription-not-billed"}' > "$RECEIPT"

"$BENCH" --score --case "$CASE_ID" --output-file "$OUTPUT" \
  --receipt-file "$RECEIPT" --result-file "$RESULT" --duration-seconds "$duration"
jq --arg transport "$TRANSPORT" --arg billing included-subscription \
  --arg effort "$EFFORT" --arg outcome "$outcome" \
  '. + {transport:$transport,billingMode:$billing,effort:$effort,outcome:$outcome}' \
  "$RESULT" > "$RESULT.tmp"
mv "$RESULT.tmp" "$RESULT"
cat "$RESULT"
exit "$status"
