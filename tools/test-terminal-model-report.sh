#!/usr/bin/env bash
set -euo pipefail

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RENDERER="$ROOT/plugins/model-router/skills/model-router/references/render-terminal-report.sh"
FIXTURES="$ROOT/plugins/model-router/skills/model-router/tests/terminal-report"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/terminal-model-report-tests.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

"$RENDERER" --receipt-index "$FIXTURES/terminal-receipt-index.json" \
  --status complete --json-output "$TMP/report.json" --markdown-output "$TMP/report.md" >/dev/null

assert jq -e '.schemaVersion == 1 and .runStatus == "complete"' "$TMP/report.json"
assert jq -e '.summary.measuredPaidCostUsd == 0.103' "$TMP/report.json"
assert jq -e '.summary.subscriptionCalls == 1 and .summary.paidCreditCalls == 1' "$TMP/report.json"
assert jq -e '.summary.fallbacks == 2 and .summary.unmeasuredUsageOrCostCalls == 4' "$TMP/report.json"
assert jq -e '.summary.inputReceiptReferences == 11 and .summary.validReceiptObjects == 9 and .summary.deduplicatedReceipts == 7 and .summary.ignoredReceiptReferences == 2 and .summary.duplicateReceiptObjects == 2' "$TMP/report.json"
assert jq -e '.matrixSnapshots == ["openrouter:2026-08-25", "fictional:2026-08-26"]' "$TMP/report.json"
assert jq -e '[.calls[].receiptId] == ["dispatch-000000000000000000000001","dispatch-000000000000000000000002","dispatch-000000000000000000000003","dispatch-000000000000000000000004","dispatch-000000000000000000000005","dispatch-000000000000000000000006","dispatch-000000000000000000000007"]' "$TMP/report.json"
assert jq -e '.calls[3].attempts[0].result == "failed" and .calls[3].attempts[1].served == true and .calls[3].attempts[1].model == "fictional/second-reviewer"' "$TMP/report.json"
assert jq -e '.calls[4].attempts[0].served == false and .calls[4].billingMode == "unavailable"' "$TMP/report.json"
assert jq -e '.calls[6].attempts[0].model == "unavailable" and .calls[6].attempts[0].duration.status == "unavailable" and .calls[6].attempts[0].billedCost.status == "unavailable"' "$TMP/report.json"
assert grep -Fq 'fictional/first-reviewer (attempted)' "$TMP/report.md"
assert grep -Fq 'fictional/second-reviewer (served)' "$TMP/report.md"
assert grep -Fq 'subscription allowance' "$TMP/report.md"
assert grep -Fq 'Paid total: `$0.103 measured`' "$TMP/report.md"
assert sh -c "! grep -Eq 'ARBITRARY_PROVIDER|REFLECTED_INPUT|REFLECTED MATRIX|MODEL_OUTPUT|CREDENTIAL|UNRELATED_TEXT|duplicate-must-not-replace-first' '$TMP/report.json' '$TMP/report.md'"

cp "$TMP/report.json" "$TMP/report-first.json"
cp "$TMP/report.md" "$TMP/report-first.md"
"$RENDERER" --receipt-index "$FIXTURES/terminal-receipt-index.json" \
  --status complete --json-output "$TMP/report.json" --markdown-output "$TMP/report.md" >/dev/null
assert cmp -s "$TMP/report-first.json" "$TMP/report.json"
assert cmp -s "$TMP/report-first.md" "$TMP/report.md"

set +e
"$RENDERER" --receipt-index "$FIXTURES/terminal-receipt-index.json" \
  --status in-progress --json-output "$TMP/in-progress.json" --markdown-output "$TMP/in-progress.md" \
  >"$TMP/in-progress.stdout" 2>"$TMP/in-progress.stderr"
in_progress_rc=$?
set -e
assert test "$in_progress_rc" -eq 2
assert grep -Fxq 'terminal-model-report: non-terminal-status' "$TMP/in-progress.stderr"
assert test ! -e "$TMP/in-progress.json"
assert test ! -e "$TMP/in-progress.md"

"$RENDERER" --receipt-index "$FIXTURES/terminal-receipt-index.json" \
  --status blocked --json-output "$TMP/blocked.json" --markdown-output "$TMP/blocked.md" >/dev/null
assert jq -e '.runStatus == "blocked" and (.calls | length) == 7' "$TMP/blocked.json"
assert grep -Fxq 'Run: BLOCKED' "$TMP/blocked.md"

printf 'terminal-model-report: %d assertions passed\n' "$pass"
