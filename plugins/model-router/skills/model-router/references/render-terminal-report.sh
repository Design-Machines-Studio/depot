#!/usr/bin/env bash
# render-terminal-report.sh -- terminal-only operator model and cost report.
#
# Usage:
#   render-terminal-report.sh --receipt-index INDEX --status STATUS \
#     --json-output PATH --markdown-output PATH
#
# INDEX is a schema-versioned JSON file in the exact private receipt directory.
# Its receiptFiles array contains safe basenames in deterministic dispatch order.

set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

RECEIPT_INDEX=""
STATUS=""
JSON_OUTPUT=""
MARKDOWN_OUTPUT=""

fail() {
  printf 'terminal-model-report: %s\n' "$1" >&2
  exit "${2:-1}"
}

usage() {
  fail "invalid-invocation" 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --receipt-index) [ "$#" -ge 2 ] || usage; RECEIPT_INDEX="$2"; shift 2 ;;
    --status) [ "$#" -ge 2 ] || usage; STATUS="$2"; shift 2 ;;
    --json-output) [ "$#" -ge 2 ] || usage; JSON_OUTPUT="$2"; shift 2 ;;
    --markdown-output) [ "$#" -ge 2 ] || usage; MARKDOWN_OUTPUT="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[ -n "$RECEIPT_INDEX" ] && [ -n "$STATUS" ] && [ -n "$JSON_OUTPUT" ] && [ -n "$MARKDOWN_OUTPUT" ] || usage
case "$STATUS" in complete|failed|blocked|stopped) ;; *) fail "non-terminal-status" 2 ;; esac
command -v jq >/dev/null 2>&1 || fail "jq-unavailable"
if [ -n "${MODEL_ROUTER_TEST_FAIL_MARKDOWN_PUBLICATION:-}" ] && [ "${MODEL_ROUTER_TEST_MODE:-0}" != 1 ]; then
  fail "test-hook-requires-test-mode" 2
fi

[ -f "$RECEIPT_INDEX" ] && [ ! -L "$RECEIPT_INDEX" ] || fail "receipt-index-unavailable"
INDEX_PARENT="$(cd "$(dirname "$RECEIPT_INDEX")" 2>/dev/null && pwd -P)" || fail "receipt-index-unavailable"
INDEX_NAME="$(basename "$RECEIPT_INDEX")"
RECEIPT_INDEX="$INDEX_PARENT/$INDEX_NAME"

jq -e '
  type == "object" and
  .schemaVersion == 1 and
  (.receiptFiles | type) == "array" and
  all(.receiptFiles[];
    type == "string" and
    test("^[A-Za-z0-9][A-Za-z0-9._-]{0,126}\\.json$") and
    . != "terminal-receipt-index.json")
' "$RECEIPT_INDEX" >/dev/null 2>&1 || fail "receipt-index-invalid"

validate_output() {
  local output="$1" parent name
  case "$output" in *$'\n'*|*$'\r'*|*$'\t'*|*'`'*) fail "output-destination-invalid" 2 ;; esac
  parent="$(dirname "$output")"
  name="$(basename "$output")"
  [ -n "$name" ] && [ "$name" != . ] && [ "$name" != .. ] || fail "output-destination-invalid" 2
  [ -d "$parent" ] && [ ! -L "$parent" ] || fail "output-destination-unavailable"
  parent="$(cd "$parent" 2>/dev/null && pwd -P)" || fail "output-destination-unavailable"
  if [ -e "$parent/$name" ]; then
    [ ! -L "$parent/$name" ] && [ -f "$parent/$name" ] || fail "output-destination-unavailable"
  fi
  printf '%s/%s\n' "$parent" "$name"
}

JSON_OUTPUT="$(validate_output "$JSON_OUTPUT")"
MARKDOWN_OUTPUT="$(validate_output "$MARKDOWN_OUTPUT")"
[ "$JSON_OUTPUT" != "$MARKDOWN_OUTPUT" ] || fail "output-destinations-conflict" 2

TMP_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/terminal-model-report.XXXXXX")" || fail "temporary-storage-unavailable"
cleanup() { rm -rf "$TMP_ROOT"; }
trap cleanup EXIT
VALID_RECEIPTS="$TMP_ROOT/valid-receipts.ndjson"
: > "$VALID_RECEIPTS"

INDEX_COUNT=0
VALID_COUNT=0
while IFS= read -r receipt_name; do
  INDEX_COUNT=$((INDEX_COUNT + 1))
  receipt_path="$INDEX_PARENT/$receipt_name"
  [ -f "$receipt_path" ] && [ ! -L "$receipt_path" ] || continue
  if jq -e '
    type == "object" and
    .schemaVersion == 1 and
    (.receiptId | type) == "string" and
    (.receiptId | test("^dispatch-[a-f0-9]{24}$")) and
    (.requested | type) == "object" and
    (.attempts | type) == "array" and
    all(.attempts[]; type == "object") and
    ((.served == null) or ((.served | type) == "object")) and
    ((.fallback | type) == "boolean")
  ' "$receipt_path" >/dev/null 2>&1; then
    jq -c '.' "$receipt_path" >> "$VALID_RECEIPTS"
    VALID_COUNT=$((VALID_COUNT + 1))
  fi
done < <(jq -r '.receiptFiles[]' "$RECEIPT_INDEX")

JSON_PARENT="$(dirname "$JSON_OUTPUT")"
JSON_NAME="$(basename "$JSON_OUTPUT")"
MARKDOWN_PARENT="$(dirname "$MARKDOWN_OUTPUT")"
MARKDOWN_NAME="$(basename "$MARKDOWN_OUTPUT")"
JSON_TMP="$(mktemp "$JSON_PARENT/.${JSON_NAME}.XXXXXX")" || fail "output-destination-unavailable"
MARKDOWN_TMP="$(mktemp "$MARKDOWN_PARENT/.${MARKDOWN_NAME}.XXXXXX")" || { rm -f "$JSON_TMP"; fail "output-destination-unavailable"; }

if ! jq -S -s \
  --arg status "$STATUS" \
  --arg full_report "$JSON_OUTPUT" \
  --argjson input_count "$INDEX_COUNT" \
  --argjson valid_count "$VALID_COUNT" '
  def safe_slug:
    if type == "string" and length > 0 and length <= 128 and test("^[A-Za-z0-9][A-Za-z0-9._:/+-]*$")
    then . else "unavailable" end;
  def safe_role:
    . as $value
    | if type == "string" and (["architect","builder-deep","builder-fast","editorial","plan-critic","research-fast","review-deep","review-fast","security-review"] | index($value) != null)
      then . else "unavailable" end;
  def safe_effort:
    . as $value
    | if type == "string" and (["low","medium","high","max"] | index($value) != null)
      then . else "unavailable" end;
  def safe_transport:
    . as $value
    | if type == "string" and (["codex-cli","claude-cli","openrouter"] | index($value) != null)
      then . else "unavailable" end;
  def safe_billing:
    . as $value
    | if type == "string" and (["api","included-subscription","subscription-headroom-unknown","paid-credits","unavailable"] | index($value) != null)
      then . else "unavailable" end;
  def safe_outcome:
    . as $value
    | if type == "string" and (["served","failed","skipped"] | index($value) != null)
      then . else "unavailable" end;
  def nonnegative_number: if type == "number" and . >= 0 then . else null end;
  def nonnegative_integer: if type == "number" and . >= 0 and floor == . then . else null end;
  def unique_first:
    reduce .[] as $item ({seen:{}, values:[]};
      if .seen[$item] then . else .seen[$item] = true | .values += [$item] end) | .values;
  def dedupe_receipts:
    reduce .[] as $receipt ({seen:{}, values:[]};
      if .seen[$receipt.receiptId] then .
      else .seen[$receipt.receiptId] = true | .values += [$receipt]
      end) | .values;
  def tokens($served):
    (if ($served.tokens | type) == "object" then $served.tokens else {} end) as $usage
    | (($usage.input_tokens // $usage.prompt_tokens // null) | nonnegative_integer) as $input
    | (($usage.output_tokens // $usage.completion_tokens // null) | nonnegative_integer) as $output
    | (($usage.total_tokens // null) | nonnegative_integer) as $total
    | if $served.tokenProvenance == "provider-receipt" and $total != null then
        {input:$input, output:$output, total:$total, status:"provider-reported", provenance:"provider-receipt"}
      else
        {input:null, output:null, total:null, status:"unavailable", provenance:"unavailable"}
      end;
  def duration($value):
    ($value | nonnegative_integer) as $seconds
    | {seconds:$seconds, status:(if $seconds == null then "unavailable" else "measured" end)};
  def billed_cost($served):
    ($served.billedCostUsd | nonnegative_number) as $usd
    | (if $served.costProvenance == "provider-receipt" and $usd != null then
         {usd:$usd, status:"measured", provenance:"provider-receipt"}
       else {usd:null, status:"unavailable", provenance:"unavailable"} end);
  def normalize_receipt:
    . as $receipt
    | ($receipt.served // {}) as $served
    | ($receipt.attempts | to_entries | map(select(.value.outcome == "served"))) as $served_entries
    | (if ($receipt.served | type) == "object" and ($served_entries | length) == 1 and
          $served_entries[0].value.model == $served.model and
          $served_entries[0].value.provider == $served.provider and
          $served_entries[0].value.transport == $served.transport
       then $served_entries[0].key else null end) as $served_index
    | {
        receiptId:$receipt.receiptId,
        role:($receipt.requested.role | safe_role),
        requestedEffort:($receipt.requested.effort | safe_effort),
        effectiveEffort:($receipt.effectiveEffort | safe_effort),
        matrixSnapshot:($receipt.matrixSnapshot | safe_slug),
        fallback:$receipt.fallback,
        billingMode:((if $served_index == null then "unavailable" else $served.billingMode end) | safe_billing),
        attempts:[
          $receipt.attempts | to_entries[]
          | . as $entry
          | (($entry.value.outcome | safe_outcome)) as $raw_outcome
          | ($served_index != null and $entry.key == $served_index) as $was_served
          | (if $raw_outcome == "served" and ($was_served | not) then "unavailable" else $raw_outcome end) as $outcome
          | {
              sequence:($entry.key + 1),
              model:($entry.value.model | safe_slug),
              provider:($entry.value.provider | safe_slug),
              transport:($entry.value.transport | safe_transport),
              billingMode:((if $was_served then $served.billingMode else $entry.value.billingMode end) | safe_billing),
              duration:(if $was_served then duration($served.durationSeconds) else duration($entry.value.durationSeconds) end),
              tokens:(if $was_served then tokens($served) else {input:null,output:null,total:null,status:"unavailable",provenance:"unavailable"} end),
              billedCost:(if $was_served then billed_cost($served) else {usd:null,status:"unavailable",provenance:"unavailable"} end),
              result:$outcome,
              served:$was_served
            }
        ]
      };
  dedupe_receipts as $deduped
  | ($deduped | map(normalize_receipt)) as $calls
  | ($calls | map(.matrixSnapshot) | map(select(. != "unavailable")) | unique_first) as $matrices
  | ($calls | map(.attempts[] | select(.billedCost.status == "measured") | .billedCost.usd) | add // 0) as $paid_total
  | ($calls | map(select(.billingMode == "included-subscription" or .billingMode == "subscription-headroom-unknown")) | length) as $subscription_calls
  | ($calls | map(select(.billingMode == "paid-credits")) | length) as $paid_credit_calls
  | ($calls | map(select(.fallback)) | length) as $fallbacks
  | ($calls | map(select(([.attempts[] | select(.served)][0].tokens.status // "unavailable") == "unavailable")) | length) as $unavailable_tokens
  | ($calls | map(select(([.attempts[] | select(.served)][0].billedCost.status // "unavailable") == "unavailable")) | length) as $unavailable_cost
  | ($calls | map(select(
      (([.attempts[] | select(.served)][0].tokens.status // "unavailable") == "unavailable") or
      (([.attempts[] | select(.served)][0].billedCost.status // "unavailable") == "unavailable")
    )) | length) as $unmeasured
  | {
      schemaVersion:1,
      runStatus:$status,
      matrixSnapshots:$matrices,
      calls:$calls,
      summary:{
        measuredPaidCostUsd:$paid_total,
        subscriptionCalls:$subscription_calls,
        paidCreditCalls:$paid_credit_calls,
        fallbacks:$fallbacks,
        unavailableTokenCalls:$unavailable_tokens,
        unavailableCostCalls:$unavailable_cost,
        unmeasuredUsageOrCostCalls:$unmeasured,
        inputReceiptReferences:$input_count,
        validReceiptObjects:$valid_count,
        deduplicatedReceipts:($calls | length),
        ignoredReceiptReferences:($input_count - $valid_count),
        duplicateReceiptObjects:($valid_count - ($calls | length))
      },
      fullReport:$full_report
    }
' "$VALID_RECEIPTS" > "$JSON_TMP"; then
  rm -f "$JSON_TMP" "$MARKDOWN_TMP"
  fail "json-render-failed"
fi

if ! jq -r '
  def display_money: "$" + tostring + " measured";
  def display_duration: if .status == "measured" then (.seconds|tostring) + "s" else "unavailable" end;
  def display_tokens: if .status == "provider-reported" then (.total|tostring) else "unavailable" end;
  def display_cost($billing):
    if .status == "measured" then (.usd | display_money)
    elif $billing == "included-subscription" or $billing == "subscription-headroom-unknown" then "subscription allowance"
    elif $billing == "paid-credits" then "paid-credit usage"
    else "unavailable" end;
  def matrix_line: if length == 0 then "unavailable" else join(", ") end;
  def attempt_rows:
    .calls[] as $call
    | $call.attempts[]
    | . as $attempt
    | "| \($call.role) | \($attempt.model) \(if $attempt.served then "(served)" else "(attempted)" end) | \($attempt.provider) / \($attempt.transport) | \($call.requestedEffort) / \($call.effectiveEffort) | \($attempt.duration | display_duration) | \($attempt.tokens | display_tokens) | \($attempt.billedCost | display_cost($attempt.billingMode)) | \($attempt.result)\(if $attempt.served and $call.fallback then " (fallback)" else "" end) |";
  [
    "### Model & Cost Report",
    "",
    "Run: " + (.runStatus | ascii_upcase),
    "Matrix: " + (.matrixSnapshots | matrix_line),
    "",
    "| Role | Attempted / served model | Rail | Effort requested / effective | Duration | Tokens | Billed cost | Result |",
    "|---|---|---|---|---:|---:|---:|---|",
    (attempt_rows),
    "",
    "Paid total: `" + (.summary.measuredPaidCostUsd | display_money) + "`",
    "Subscription usage: `" + (.summary.subscriptionCalls|tostring) + " calls`",
    "Paid-credit usage: `" + (.summary.paidCreditCalls|tostring) + " calls`",
    "Fallbacks: `" + (.summary.fallbacks|tostring) + "`",
    "Unmeasured usage/cost: `" + (.summary.unmeasuredUsageOrCostCalls|tostring) + " calls`",
    "Full report: `" + .fullReport + "`"
  ] | .[]
' "$JSON_TMP" > "$MARKDOWN_TMP"; then
  rm -f "$JSON_TMP" "$MARKDOWN_TMP"
  fail "markdown-render-failed"
fi

mv "$JSON_TMP" "$JSON_OUTPUT" || { rm -f "$JSON_TMP" "$MARKDOWN_TMP"; fail "json-publication-failed"; }
if [ -n "${MODEL_ROUTER_TEST_FAIL_MARKDOWN_PUBLICATION:-}" ]; then
  markdown_publication_rc=1
else
  mv "$MARKDOWN_TMP" "$MARKDOWN_OUTPUT" || markdown_publication_rc=$?
fi
if [ "${markdown_publication_rc:-0}" -ne 0 ]; then
  rm -f "$MARKDOWN_TMP" "$JSON_OUTPUT" "$MARKDOWN_OUTPUT"
  fail "markdown-publication-failed"
fi

printf '%s\n' "$MARKDOWN_OUTPUT"
