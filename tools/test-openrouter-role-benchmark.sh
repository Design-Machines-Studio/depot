#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
SUITE="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/depot-role-benchmark.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }

assert test -x "$RUNNER"
assert sh -c "[ \"\$('$RUNNER' --list | wc -l | tr -d ' ')\" = 4 ]"
"$RUNNER" --prepare --case pipeline-legacy-translation --output-file "$TMP/prompt"
assert grep -Fq 'provider-neutral contract' "$TMP/prompt"
assert grep -Fq '"executorRole":"builder-fast"' "$TMP/prompt"
assert grep -Fq '"executorEffort":"medium"' "$TMP/prompt"
assert grep -Fq '"executorCapabilities":["read-repository","write-repository","structured-output"]' "$TMP/prompt"
assert grep -Fq '"legacyExecutorTranslation":{"occurred":true,"sourceField":"executor"}' "$TMP/prompt"
assert grep -Fq 'no Markdown fences or prose' "$TMP/prompt"
assert grep -Fq 'Return the translated chunk as the sole entry in a top-level "chunks" array; do not return the chunk object directly.' "$TMP/prompt"

printf '%s\n' '{"chunks":[{"id":"docs-1","executor":"openrouter","kind":"docs"}]}' > "$TMP/legacy"
"$ROOT/plugins/pipeline/references/translate-legacy-executor.sh" "$TMP/legacy" > "$TMP/output"
printf '%s\n' '{"requestedModel":"fixture/model","responseModel":"fixture/model-v1","servingProvider":"fixture","usage":{"prompt_tokens":10,"completion_tokens":5,"cost":0.001},"fallbackUsed":false}' > "$TMP/receipt"
"$RUNNER" --score --case pipeline-legacy-translation --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result-legacy" --duration-seconds 2
assert jq -e '.qualityScore == 100 and .durationSeconds == 2 and .servedModel == "fixture/model-v1" and .usage.cost == 0.001 and .fallbackUsed == false' "$TMP/result-legacy"

printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
"$RUNNER" --score --case review-zero-deferral --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result-review"
assert jq -e '.qualityScore == 100' "$TMP/result-review"

printf '%s\n' '{"nextChunk":"depot-role-benchmark","executorRole":"builder-fast","executorCapabilities":["read-repository","write-repository","structured-output"],"rejectedComplexity":["Issue #86 Floor observation schemas","daemon","generic workflow engine"]}' > "$TMP/output"
"$RUNNER" --score --case assembly-next-chunk --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result-assembly"
assert jq -e '.qualityScore == 100' "$TMP/result-assembly"

printf '%s\n' '{"targetPath":"config/fixture.json","newContent":{"schemaVersion":1,"enabled":true},"verification":"jq -e '\''.schemaVersion == 1 and .enabled == true'\'' config/fixture.json"}' > "$TMP/output"
"$RUNNER" --score --case mechanical-owned-edit --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result-mechanical"
assert jq -e '.qualityScore == 100' "$TMP/result-mechanical"

# Every checked-in expected answer must satisfy its matching deterministic scorer.
while IFS= read -r case_id; do
  jq --arg case_id "$case_id" '.cases[] | select(.id == $case_id) | .expected' "$SUITE" > "$TMP/expected-output"
  "$RUNNER" --score --case "$case_id" --output-file "$TMP/expected-output" \
    --receipt-file "$TMP/receipt" --result-file "$TMP/expected-result-$case_id"
  assert jq -e --arg case_id "$case_id" \
    '.caseId == $case_id and .qualityScore == 100' "$TMP/expected-result-$case_id"
done < <(jq -r '.cases[].id' "$SUITE")

printf '%s\n' 'not-json' > "$TMP/output"
"$RUNNER" --score --case review-zero-deferral --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result-invalid"
assert jq -e '.parsed == false and .qualityScore == 0' "$TMP/result-invalid"

if "$RUNNER" --prepare --case absent --output-file "$TMP/prompt" >/dev/null 2>&1; then
  printf 'FAIL: unknown case accepted\n' >&2; exit 1
fi
pass=$((pass+1))

printf 'openrouter role benchmark: %d assertions passed\n' "$pass"
