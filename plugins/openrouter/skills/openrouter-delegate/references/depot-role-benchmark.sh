#!/usr/bin/env bash
# Manual, one-candidate-at-a-time Depot role benchmark. This is an operator
# measurement surface, not an orchestrator or an automatic model sweep.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE="$DIR/depot-role-benchmark-suite.json"
MATRIX="$DIR/model-matrix.json"
BOUNDARY="$DIR/delegation-boundary.sh"
POLICY="$DIR/delegation-security-policy.json"
WRAPPER="$DIR/openrouter-wrapper.sh"
COMMAND="${1:-}"
shift || true

CASE_ID=""
MODEL=""
OUTPUT_FILE=""
RECEIPT_FILE=""
RESULT_FILE=""
RESULT_DIR=""
DURATION="0"

usage() {
  printf '%s\n' \
    'usage: depot-role-benchmark.sh --list' \
    '       depot-role-benchmark.sh --prepare --case ID --output-file PATH' \
    '       depot-role-benchmark.sh --score --case ID --output-file PATH --receipt-file PATH --result-file PATH [--duration-seconds N]' \
    '       depot-role-benchmark.sh --run --case ID --model EXACT_SLUG --result-dir PATH'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) CASE_ID="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --output-file) OUTPUT_FILE="${2:-}"; shift 2 ;;
    --receipt-file) RECEIPT_FILE="${2:-}"; shift 2 ;;
    --result-file) RESULT_FILE="${2:-}"; shift 2 ;;
    --result-dir) RESULT_DIR="${2:-}"; shift 2 ;;
    --duration-seconds) DURATION="${2:-}"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done

case_exists() { jq -e --arg id "$CASE_ID" 'any(.cases[]; .id == $id)' "$SUITE" >/dev/null; }
require_case() {
  [ -n "$CASE_ID" ] && case_exists || { printf 'benchmark: unknown or missing case\n' >&2; exit 2; }
}
require_regular() { [ -f "$1" ] && [ ! -L "$1" ] || { printf 'benchmark: regular file required\n' >&2; exit 2; }; }

score_case() {
  local score=0 parsed=true
  if ! jq -e 'type == "object"' "$OUTPUT_FILE" >/dev/null 2>&1; then parsed=false; fi
  if [ "$parsed" = true ]; then
    case "$CASE_ID" in
      pipeline-legacy-translation)
        jq -e '.chunks | type == "array" and length == 1' "$OUTPUT_FILE" >/dev/null && score=$((score+20))
        jq -e '.chunks[0] | .id == "docs-1" and .executorRole == "builder-fast" and .executorEffort == "low"' "$OUTPUT_FILE" >/dev/null && score=$((score+25))
        jq -e '.chunks[0].executorCapabilities == ["read-repository","write-repository","structured-output"]' "$OUTPUT_FILE" >/dev/null && score=$((score+25))
        jq -e '.chunks[0] | has("executor") | not' "$OUTPUT_FILE" >/dev/null && score=$((score+15))
        jq -e '.chunks[0].legacyExecutorTranslation | .occurred == true and .source == "openrouter"' "$OUTPUT_FILE" >/dev/null && score=$((score+15))
        ;;
      review-zero-deferral)
        for pair in AUTH-1:P1 ROUTE-2:P2 DOC-3:P3; do
          id="${pair%%:*}"; severity="${pair##*:}"
          jq -e --arg id "$id" --arg severity "$severity" 'any(.findings[]?; .id == $id and .severity == $severity)' "$OUTPUT_FILE" >/dev/null && score=$((score+25))
        done
        jq -e '.deferred == false and (.findings | length) == 3' "$OUTPUT_FILE" >/dev/null && score=$((score+25))
        ;;
      assembly-next-chunk)
        jq -e '.nextChunk == "depot-role-benchmark"' "$OUTPUT_FILE" >/dev/null && score=$((score+30))
        jq -e '.executorRole == "builder-fast"' "$OUTPUT_FILE" >/dev/null && score=$((score+20))
        jq -e '.executorCapabilities == ["read-repository","write-repository","structured-output"]' "$OUTPUT_FILE" >/dev/null && score=$((score+20))
        jq -e '.rejectedComplexity | type == "array" and length > 0' "$OUTPUT_FILE" >/dev/null && score=$((score+15))
        ! jq -e '.nextChunk | test("issue[ #]*86|floor|daemon|broker|database|mcp|workflow-engine"; "i")' "$OUTPUT_FILE" >/dev/null && score=$((score+15))
        ;;
      mechanical-owned-edit)
        jq -e '.targetPath == "config/fixture.json"' "$OUTPUT_FILE" >/dev/null && score=$((score+20))
        jq -e '.newContent == {schemaVersion:1,enabled:true}' "$OUTPUT_FILE" >/dev/null && score=$((score+50))
        jq -e '.verification == "jq -e '\''.schemaVersion == 1 and .enabled == true'\'' config/fixture.json"' "$OUTPUT_FILE" >/dev/null && score=$((score+30))
        ;;
    esac
  fi
  jq -n --arg suite "depot-role-v1" --arg caseId "$CASE_ID" \
    --argjson parsed "$parsed" --argjson score "$score" --argjson duration "$DURATION" \
    --slurpfile receipt "$RECEIPT_FILE" '
      {schemaVersion:1,suiteId:$suite,caseId:$caseId,parsed:$parsed,qualityScore:$score,
       durationSeconds:$duration,requestedModel:($receipt[0].requestedModel // null),
       servedModel:($receipt[0].responseModel // null),provider:($receipt[0].servingProvider // null),
       usage:($receipt[0].usage // null),fallbackUsed:($receipt[0].fallbackUsed // null)}' > "$RESULT_FILE"
}

case "$COMMAND" in
  --list)
    jq -r '.cases[] | [.id,.role,.taskType,.objective] | @tsv' "$SUITE"
    ;;
  --prepare)
    require_case
    [ -n "$OUTPUT_FILE" ] || { usage >&2; exit 2; }
    jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .prompt' "$SUITE" > "$OUTPUT_FILE"
    ;;
  --score)
    require_case
    [ -n "$OUTPUT_FILE" ] && [ -n "$RECEIPT_FILE" ] && [ -n "$RESULT_FILE" ] || { usage >&2; exit 2; }
    [[ "$DURATION" =~ ^[0-9]+([.][0-9]+)?$ ]] || { printf 'benchmark: invalid duration\n' >&2; exit 2; }
    require_regular "$OUTPUT_FILE"; require_regular "$RECEIPT_FILE"
    score_case
    ;;
  --run)
    require_case
    [ -n "$MODEL" ] && [ -n "$RESULT_DIR" ] || { usage >&2; exit 2; }
    jq -e --arg model "$MODEL" 'any(.models[]; .slug == $model and .catalog_status == "available")' "$MATRIX" >/dev/null || { printf 'benchmark: exact available matrix model required\n' >&2; exit 2; }
    mkdir -p "$RESULT_DIR"; chmod 700 "$RESULT_DIR"
    prompt="$RESULT_DIR/prompt.txt"; system="$RESULT_DIR/system.txt"; output="$RESULT_DIR/output.json"
    receipt="$RESULT_DIR/receipt.json"; result="$RESULT_DIR/result.json"
    jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .prompt' "$SUITE" > "$prompt"
    printf '%s\n' 'You are completing one bounded Depot benchmark. Return JSON only. You have no command authority.' > "$system"
    "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" --content-file "$system" --content-file "$prompt" >/dev/null
    start="$(date +%s)"
    env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$system" OPENROUTER_WORKLOAD=mechanical \
      OPENROUTER_ALLOW_FALLBACKS=0 OPENROUTER_RECEIPT_FILE="$receipt" \
      "$WRAPPER" "$MODEL" - 3600 < "$prompt" > "$output"
    end="$(date +%s)"; DURATION="$((end-start))"; OUTPUT_FILE="$output"; RECEIPT_FILE="$receipt"; RESULT_FILE="$result"
    score_case
    cat "$result"
    ;;
  *) usage >&2; exit 2 ;;
esac
