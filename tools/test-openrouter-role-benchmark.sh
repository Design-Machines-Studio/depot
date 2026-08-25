#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/depot-role-benchmark.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }

assert test -x "$RUNNER"
assert sh -c "[ \"\$('$RUNNER' --list | wc -l | tr -d ' ')\" = 4 ]"
"$RUNNER" --prepare --case pipeline-legacy-translation --output-file "$TMP/prompt"
assert grep -Fq 'provider-neutral contract' "$TMP/prompt"

printf '%s\n' '{"chunks":[{"id":"docs-1","executorRole":"builder-fast","executorCapabilities":["read-repository","write-repository","structured-output"],"executorEffort":"low","legacyExecutorTranslation":{"occurred":true,"source":"openrouter"}}]}' > "$TMP/output"
printf '%s\n' '{"requestedModel":"fixture/model","responseModel":"fixture/model-v1","servingProvider":"fixture","usage":{"prompt_tokens":10,"completion_tokens":5,"cost":0.001},"fallbackUsed":false}' > "$TMP/receipt"
"$RUNNER" --score --case pipeline-legacy-translation --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result" --duration-seconds 2
assert jq -e '.qualityScore == 100 and .durationSeconds == 2 and .servedModel == "fixture/model-v1" and .usage.cost == 0.001' "$TMP/result"

printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
"$RUNNER" --score --case review-zero-deferral --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result"
assert jq -e '.qualityScore == 100' "$TMP/result"

printf '%s\n' '{"nextChunk":"depot-role-benchmark","executorRole":"builder-fast","executorCapabilities":["read-repository","write-repository","structured-output"],"rejectedComplexity":["Issue #86 Floor observation schemas","daemon","generic workflow engine"]}' > "$TMP/output"
"$RUNNER" --score --case assembly-next-chunk --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result"
assert jq -e '.qualityScore == 100' "$TMP/result"

printf '%s\n' '{"targetPath":"config/fixture.json","newContent":{"schemaVersion":1,"enabled":true},"verification":"jq -e '\''.schemaVersion == 1 and .enabled == true'\'' config/fixture.json"}' > "$TMP/output"
"$RUNNER" --score --case mechanical-owned-edit --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result"
assert jq -e '.qualityScore == 100' "$TMP/result"

printf '%s\n' 'not-json' > "$TMP/output"
"$RUNNER" --score --case review-zero-deferral --output-file "$TMP/output" --receipt-file "$TMP/receipt" --result-file "$TMP/result"
assert jq -e '.parsed == false and .qualityScore == 0' "$TMP/result"

if "$RUNNER" --prepare --case absent --output-file "$TMP/prompt" >/dev/null 2>&1; then
  printf 'FAIL: unknown case accepted\n' >&2; exit 1
fi
pass=$((pass+1))

printf 'openrouter role benchmark: %d assertions passed\n' "$pass"
