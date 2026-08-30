#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
CHECKED_SUITE="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json"
ROLE_POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/benchmark-evidence-contract.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0

assert() {
  "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
  pass=$((pass+1))
}
reject() {
  if "$@" >/dev/null 2>&1; then
    printf 'FAIL: command unexpectedly succeeded: %s\n' "$*" >&2
    exit 1
  fi
  pass=$((pass+1))
}
score() {
  local suite="$1" output="$2" receipt="$3" result="$4"
  shift 4
  rm -f "$result"
  DEPOT_BENCH_SUITE="$suite" DEPOT_BENCH_ROLE_POLICY="$ROLE_POLICY" \
    "$RUNNER" --score --case review-zero-deferral \
    --output-file "$output" --receipt-file "$receipt" --result-file "$result" "$@"
}

jq '
  .schemaVersion = 2
  | .suiteId = "depot-role-fixture-v2"
  | .suiteRevision = 1
  | .bindings = null
  | .cases |= map(
      .revision = 1 | .promptRevision = 1
      | .workload = (if .taskType == "bounded-edit" or .taskType == "structured-transformation" then "mechanical" else "quality" end)
      | .requiredCapabilities = ["structured-output"]
    )
' "$CHECKED_SUITE" > "$TMP/suite.json"

printf '%s\n' '{"schemaVersion":2,"outcome":"success","requestedModel":"fixture/requested","modelCandidates":["fixture/requested"],"responseModel":"fixture/requested","responseModelProvenance":"response","servingProvider":"fixture-endpoint","servingProviderProvenance":"response","attemptedModel":"fixture/requested","attemptedModels":["fixture/requested"],"attemptProvenance":"response_model","fallbackUsed":false,"routing":{"workload":"quality"},"benchmark":{"suiteId":"depot-role-fixture-v2","caseId":"review-zero-deferral","role":"review-fast","workload":"quality"},"usage":{"prompt_tokens":10,"completion_tokens":5}}' > "$TMP/receipt.json"
printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/bootstrap-result.json"
jq --slurpfile result "$TMP/bootstrap-result.json" '
  .bindings = {
    suiteRevision:$result[0].evidenceBindings.suiteRevision.actual,
    suiteDigest:$result[0].evidenceBindings.suiteDigest.actual,
    normalizerRevision:$result[0].evidenceBindings.normalizerRevision.actual,
    normalizerDigest:$result[0].evidenceBindings.normalizerDigest.actual,
    cases:{"review-zero-deferral":{
      caseRevision:$result[0].evidenceBindings.caseRevision.actual,
      caseDigest:$result[0].evidenceBindings.caseDigest.actual,
      promptRevision:$result[0].evidenceBindings.promptRevision.actual,
      promptDigest:$result[0].evidenceBindings.promptDigest.actual,
      scorerRevision:$result[0].evidenceBindings.scorerRevision.actual,
      scorerDigest:$result[0].evidenceBindings.scorerDigest.actual
    }}
  }
' "$TMP/suite.json" > "$TMP/bound-suite.json"
mv "$TMP/bound-suite.json" "$TMP/suite.json"
cp "$TMP/output" "$TMP/raw-copy"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json" --duration-seconds 2
assert jq -e '
  .schemaVersion == 2 and .strictParse.passed and .normalizedParse.passed
  and .normalizedParse.normalization == "strict-raw-object"
  and .contractPassed and .mandatoryPassed and .semanticPassed and .semanticScore == 100
  and .validationPassed and .overallSuccess and .comparable and (.benchmarkFault | not)
  and .transport == "openrouter" and .endpointProvider == "fixture-endpoint"
  and .requestedIdentity == "fixture/requested" and .servedIdentity == "fixture/requested"
  and .identityStatus.confidence == "confirmed" and .failureClass == "none"
  and .behavioralContract.revision == 1
  and .behavioralContract.digest == "sha256:3ecea8dc49c02a8a8ac2a6e7ede9993fb6609f7520d5438ab8bf0cf9170ba32a"
  and ([.evidenceBindings[] | .match] | all) and .durationSeconds == 2
  and (.assertions | length > 1) and (all(.assertions[]; (.id | length) > 0 and (.class == "mandatory" or .class == "semantic")))
' "$TMP/result.json"
jq -j '.rawOutput' "$TMP/result.json" > "$TMP/raw-extracted"
assert cmp "$TMP/raw-copy" "$TMP/raw-extracted"

printf '%s\n' '```json' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' '```' > "$TMP/output"
cp "$TMP/output" "$TMP/fenced-copy"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  (.strictParse.passed | not) and .normalizedParse.passed
  and .normalizedParse.normalization == "whole-response-markdown-json-fence"
  and (.contractPassed | not) and .semanticPassed and .semanticScore == 100
  and .failureStage == "format/contract" and .failureOwner == "model"
  and .failureClass == "visible-output-contract-violation" and .comparable
  and (.overallSuccess | not) and (.benchmarkFault | not)
' "$TMP/result.json"
jq -j '.rawOutput' "$TMP/result.json" > "$TMP/fenced-extracted"
assert cmp "$TMP/fenced-copy" "$TMP/fenced-extracted"

for fixture in prose multiple objects array malformed; do
  case "$fixture" in
    prose) printf '%s\n' 'Here is the answer:' '```json' '{"findings":[]}' '```' > "$TMP/output" ;;
    multiple) printf '%s\n' '```json' '{"findings":[]}' '```' '```json' '{}' '```' > "$TMP/output" ;;
    objects) printf '%s\n' '{}' '{}' > "$TMP/output" ;;
    array) printf '%s\n' '[]' > "$TMP/output" ;;
    malformed) printf '%s\n' '```json' '{"findings":' '```' > "$TMP/output" ;;
  esac
  score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
  assert jq -e --arg fixture "$fixture" '
    (.strictParse.passed | not) and (.normalizedParse.passed | not)
    and .normalizedOutput == null and .failureStage == "format/contract"
    and .failureOwner == "model" and .modelConclusion == "contract-failure"
    and (.failureReasons | length > 0) and .comparable and (.benchmarkFault | not)
  ' "$TMP/result.json"
done

# Scoring the retained v1 corpus emits a distinct v2 evidence-suite identity.
printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
score "$CHECKED_SUITE" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '.schemaVersion == 2 and .suiteId == "depot-role-v2"' "$TMP/result.json"

# A parseable but partial answer is retained without being called successful.
printf '%s\n' '{"findings":[],"deferred":false}' > "$TMP/output"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  .strictParse.passed and .normalizedParse.passed and .contractPassed and (.mandatoryPassed | not)
  and (.semanticPassed | not) and .semanticScore < 100 and (.overallSuccess | not)
  and .failureStage == "mandatory" and .failureClass == "mandatory-assertion-failure"
  and .modelConclusion == "mandatory-failure"
' "$TMP/result.json"

# Hidden prompt/schema assertions are benchmark faults, not model conclusions.
jq '.cases[1].disclosedAssertions = ["strict-json-object"]' "$TMP/suite.json" > "$TMP/prompt-fault-suite.json"
score "$TMP/prompt-fault-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  .failureStage == "prompt/contract" and .failureOwner == "benchmark"
  and .failureClass == "benchmark-prompt-contract-fault" and .benchmarkFault
  and (.comparable | not) and .modelConclusion == null
' "$TMP/result.json"

# A declared expected answer that fails its own scorer is a scorer fault.
jq '.cases[1].expected.findings[0].severity = "P9"' "$TMP/suite.json" > "$TMP/scorer-fault-suite.json"
score "$TMP/scorer-fault-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  .failureStage == "scorer" and .failureOwner == "benchmark"
  and .failureClass == "benchmark-scorer-fault" and .benchmarkFault
  and (.comparable | not) and .modelConclusion == null
' "$TMP/result.json"

# The scorer digest covers aggregation, validator, attribution, and comparability code.
printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
scorer_digest="$(jq -r '.evidenceBindings.scorerDigest.actual' "$TMP/result.json")"
jq --arg digest "$scorer_digest" '.cases[1].bindings.scorerDigest = $digest' \
  "$TMP/suite.json" > "$TMP/scorer-bound-suite.json"
sed 's/one or more disclosed mandatory assertions failed/one or more declared mandatory assertions failed/' \
  "$RUNNER" > "$TMP/mutated-runner.sh"
chmod +x "$TMP/mutated-runner.sh"
DEPOT_BENCH_SUITE="$TMP/scorer-bound-suite.json" DEPOT_BENCH_ROLE_POLICY="$ROLE_POLICY" \
  "$TMP/mutated-runner.sh" --score \
  --case review-zero-deferral --output-file "$TMP/output" --receipt-file "$TMP/receipt.json" \
  --result-file "$TMP/mutated-result.json"
assert jq -e --arg baseline "$scorer_digest" '
  .evidenceBindings.scorerDigest.actual != $baseline
  and (.evidenceBindings.scorerDigest.match | not)
  and .benchmarkFault and (.comparable | not)
' "$TMP/mutated-result.json"

# Suite assertion and validator IDs are data, but dispatch remains code-owned.
jq '.cases[1].assertionIds = ["suite-supplied-command"]' "$TMP/suite.json" > "$TMP/unknown-assertion-suite.json"
score "$TMP/unknown-assertion-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '.failureStage == "scorer" and .benchmarkFault and (.comparable | not)' "$TMP/result.json"
jq --arg marker "$TMP/suite-command-ran" '.cases[1].validatorId = ("none;touch " + $marker)' \
  "$TMP/suite.json" > "$TMP/unknown-validator-suite.json"
score "$TMP/unknown-validator-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '.failureStage == "scorer" and .benchmarkFault and (.comparable | not)' "$TMP/result.json"
assert test ! -e "$TMP/suite-command-ran"

# Parser defects require a closed, regular-file fixture attestation.
printf '%s\n' '{"schemaVersion":1,"code":"normalizer-fixture-rejection","fixtureId":"whole-response-json-fence","expectedAccepted":true,"observedAccepted":false}' > "$TMP/parser-fault.json"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json" --fault-file "$TMP/parser-fault.json"
assert jq -e '
  .failureStage == "parser/normalizer" and .failureOwner == "benchmark"
  and .failureClass == "benchmark-parser-normalizer-fault" and .benchmarkFault
  and (.comparable | not) and .modelConclusion == null
' "$TMP/result.json"

# Receipt binding is explicit. Absent or forged suite/case/role/workload evidence
# makes identity unknown and is retained as a non-comparable harness fault.
for binding in absent suiteId caseId role workload; do
  case "$binding" in
    absent) jq 'del(.benchmark)' "$TMP/receipt.json" ;;
    suiteId) jq '.benchmark.suiteId = "forged-suite"' "$TMP/receipt.json" ;;
    caseId) jq '.benchmark.caseId = "wrong-case"' "$TMP/receipt.json" ;;
    role) jq '.benchmark.role = "architect"' "$TMP/receipt.json" ;;
    workload) jq '.benchmark.workload = "bulk"' "$TMP/receipt.json" ;;
  esac > "$TMP/harness-receipt.json"
  score "$TMP/suite.json" "$TMP/output" "$TMP/harness-receipt.json" "$TMP/result.json"
  assert jq -e '
    .identityStatus.confidence == "unknown"
    and .failureStage == "harness" and .failureOwner == "benchmark"
    and .failureClass == "benchmark-harness-fault" and .benchmarkFault
    and (.comparable | not) and .modelConclusion == null
  ' "$TMP/result.json"
done

printf '%s\n' '{"schemaVersion":2,"outcome":"error","failureKind":"http_error","httpStatus":429,"requestedModel":"fixture/requested","responseModel":null,"fallbackUsed":null,"servingProvider":null,"benchmark":{"suiteId":"depot-role-fixture-v2","caseId":"review-zero-deferral","role":"review-fast","workload":"quality"}}' > "$TMP/transport-receipt.json"
score "$TMP/suite.json" "$TMP/output" "$TMP/transport-receipt.json" "$TMP/result.json"
assert jq -e '
  .transportOutcome.status == "failed" and .failureStage == "transport"
  and .failureOwner == "operational" and .failureClass == "transport-failure"
  and (.benchmarkFault | not) and (.comparable | not) and .modelConclusion == null
' "$TMP/result.json"

jq '.responseModel = null | .fallbackUsed = null' "$TMP/receipt.json" > "$TMP/identity-receipt.json"
score "$TMP/suite.json" "$TMP/output" "$TMP/identity-receipt.json" "$TMP/result.json"
assert jq -e '
  .transportOutcome.status == "success" and .identityStatus.confidence == "unknown"
  and .failureStage == "identity" and .failureOwner == "operational"
  and .failureClass == "unknown-served-identity" and (.benchmarkFault | not)
  and (.comparable | not) and .modelConclusion == null
' "$TMP/result.json"

# Requested-model aliases, missing response provenance, and inconsistent
# fallback evidence cannot confirm the served identity.
for identity_fault in requested-alias missing-provenance fallback-inconsistent; do
  case "$identity_fault" in
    requested-alias) jq '.responseModelProvenance = "requested_model"' "$TMP/receipt.json" ;;
    missing-provenance) jq 'del(.responseModelProvenance)' "$TMP/receipt.json" ;;
    fallback-inconsistent) jq '.fallbackUsed = true | .modelCandidates += ["fixture/fallback"]' "$TMP/receipt.json" ;;
  esac > "$TMP/identity-receipt.json"
  score "$TMP/suite.json" "$TMP/output" "$TMP/identity-receipt.json" "$TMP/result.json"
  assert jq -e '
    .identityStatus.confidence == "unknown" and .failureStage == "identity"
    and .failureOwner == "operational" and .failureClass == "unknown-served-identity"
    and (.benchmarkFault | not) and (.comparable | not) and .modelConclusion == null
  ' "$TMP/result.json"
done

# Semantic and validation failures become model evidence only after known-good gates.
printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P2"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  .contractPassed and .mandatoryPassed and (.semanticPassed | not) and .semanticScore == 75
  and .failureStage == "semantic" and .failureOwner == "model"
  and .failureClass == "semantic-assertion-failure" and .modelConclusion == "semantic-failure"
  and .comparable and (.overallSuccess | not) and (.benchmarkFault | not)
' "$TMP/result.json"

printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
jq '.cases[1].validatorId = "review-finding-order"' "$TMP/suite.json" > "$TMP/validation-suite.json"
printf '%s\n' '{"findings":[{"id":"DOC-3","severity":"P3"},{"id":"ROUTE-2","severity":"P2"},{"id":"AUTH-1","severity":"P1"}],"deferred":false}' > "$TMP/output"
score "$TMP/validation-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  .contractPassed and .mandatoryPassed and .semanticPassed and (.validationPassed | not)
  and .failureStage == "validation" and .failureOwner == "model"
  and .failureClass == "deterministic-validation-failure" and .modelConclusion == "validation-failure"
  and .comparable and (.overallSuccess | not) and (.benchmarkFault | not)
' "$TMP/result.json"

# The validator self-test rejects a declared expected answer that the validator
# itself cannot accept, making the defect benchmark-owned rather than model-owned.
jq '.cases[1].validatorId = "review-finding-order" | .cases[1].expected.findings |= reverse' \
  "$TMP/suite.json" > "$TMP/broken-validator-suite.json"
score "$TMP/broken-validator-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
assert jq -e '
  .failureStage == "scorer" and .failureOwner == "benchmark"
  and .failureClass == "benchmark-scorer-fault" and .benchmarkFault
  and (.comparable | not) and .modelConclusion == null
' "$TMP/result.json"

# Every comparability binding independently blocks aggregation when it mismatches.
for binding in suite case prompt scorer normalizer; do
  case "$binding" in
    suite) jq '.bindings.suiteRevision = 999' "$TMP/suite.json" ;;
    case) jq '.bindings.cases["review-zero-deferral"].caseRevision = 999' "$TMP/suite.json" ;;
    prompt) jq '.bindings.cases["review-zero-deferral"].promptDigest = "sha256:wrong"' "$TMP/suite.json" ;;
    scorer) jq '.bindings.cases["review-zero-deferral"].scorerRevision = 999' "$TMP/suite.json" ;;
    normalizer) jq '.bindings.normalizerDigest = "sha256:wrong"' "$TMP/suite.json" ;;
  esac > "$TMP/binding-suite.json"
  score "$TMP/binding-suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/result.json"
  assert jq -e --arg binding "$binding" '
    .benchmarkFault and (.comparable | not) and .failureStage == "harness"
    and .failureOwner == "benchmark" and .modelConclusion == null
    and (any(.evidenceBindings[]; .match == false))
  ' "$TMP/result.json"
done

# Requested/served/fallback provenance is copied without identity substitution.
jq '.requestedModel="fixture/requested-exact"
  | .modelCandidates=["fixture/requested-exact","fixture/fallback-exact"]
  | .responseModel="fixture/fallback-exact"
  | .attemptedModel="fixture/fallback-exact"
  | .attemptedModels=["fixture/requested-exact","fixture/fallback-exact"]
  | .fallbackUsed=true | .attemptProvenance="response_model"' \
  "$TMP/receipt.json" > "$TMP/fallback-receipt.json"
score "$TMP/suite.json" "$TMP/output" "$TMP/fallback-receipt.json" "$TMP/result.json"
assert jq -e '
  .requestedIdentity == "fixture/requested-exact" and .servedIdentity == "fixture/fallback-exact"
  and .identityStatus.confidence == "confirmed" and (.comparable | not)
  and .failureClass == "model-fallback-unattributable" and .modelConclusion == null
  and .fallback.used == true and .fallback.attemptedIdentity == "fixture/fallback-exact"
  and .fallback.attemptedIdentities == ["fixture/requested-exact","fixture/fallback-exact"]
  and .fallback.provenance == "response_model"
' "$TMP/result.json"

# Score publication never overwrites retained evidence and rejects every input
# alias, including the optional parser-fault artifact.
printf '%s\n' '{"findings":[{"id":"AUTH-1","severity":"P1"},{"id":"ROUTE-2","severity":"P2"},{"id":"DOC-3","severity":"P3"}],"deferred":false}' > "$TMP/output"
score "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/retained-result.json"
cp "$TMP/retained-result.json" "$TMP/retained-copy.json"
reject env DEPOT_BENCH_SUITE="$TMP/suite.json" DEPOT_BENCH_ROLE_POLICY="$ROLE_POLICY" \
  "$RUNNER" --score --case review-zero-deferral \
  --output-file "$TMP/output" --receipt-file "$TMP/receipt.json" --result-file "$TMP/retained-result.json"
assert cmp "$TMP/retained-copy.json" "$TMP/retained-result.json"
printf '%s\n' '{"schemaVersion":1,"code":"normalizer-fixture-rejection","fixtureId":"whole-response-json-fence","expectedAccepted":true,"observedAccepted":false}' > "$TMP/parser-fault-alias.json"
for alias in "$TMP/suite.json" "$TMP/output" "$TMP/receipt.json" "$TMP/parser-fault-alias.json"; do
  fault_args=()
  [ "$alias" != "$TMP/parser-fault-alias.json" ] || fault_args=(--fault-file "$TMP/parser-fault-alias.json")
  reject env DEPOT_BENCH_SUITE="$TMP/suite.json" DEPOT_BENCH_ROLE_POLICY="$ROLE_POLICY" \
    "$RUNNER" --score --case review-zero-deferral \
    --output-file "$TMP/output" --receipt-file "$TMP/receipt.json" --result-file "$alias" "${fault_args[@]}"
done

# Provider-capable --run rejects all asset overrides and non-canonical role
# policies before transport. Fixture overrides are confined to --offline-run.
printf '%s\n' '#!/usr/bin/env bash' 'printf called > "${CALL_MARKER:?}"' 'exit 99' > "$TMP/wrapper-stub.sh"
chmod +x "$TMP/wrapper-stub.sh"
printf '%s\n' '{"models":[{"slug":"fixture/model","catalog_status":"available"}]}' > "$TMP/matrix.json"
printf '%s\n' '{"roles":{"review-fast":[{"model":"fixture/model","transport":"openrouter","capabilities":["structured-output"]}]}}' > "$TMP/policy.json"
printf '%s\n' '{"roles":{"review-fast":[]}}' > "$TMP/ineligible-policy.json"
printf '%s\n' 'not-json' > "$TMP/malformed-policy.json"

run_reject() {
  local suite="$1" policy="$2" result_dir="$3"
  CALL_MARKER="$TMP/wrapper-called" DEPOT_BENCH_SUITE="$suite" DEPOT_BENCH_MATRIX="$TMP/matrix.json" \
    DEPOT_BENCH_WRAPPER="$TMP/wrapper-stub.sh" "$RUNNER" --offline-run --case review-zero-deferral \
    --model fixture/model --role-policy "$policy" --output-file "$TMP/output" \
    --receipt-file "$TMP/receipt.json" --result-dir "$result_dir"
}

reject run_reject "$TMP/suite.json" "$TMP/ineligible-policy.json" "$TMP/run-ineligible"
reject run_reject "$TMP/suite.json" "$TMP/malformed-policy.json" "$TMP/run-malformed"
reject env CALL_MARKER="$TMP/wrapper-called" DEPOT_BENCH_SUITE="$TMP/suite.json" \
  DEPOT_BENCH_MATRIX="$TMP/matrix.json" DEPOT_BENCH_WRAPPER="$TMP/wrapper-stub.sh" \
  "$RUNNER" --offline-run --case review-zero-deferral --model fixture/model \
  --output-file "$TMP/output" --receipt-file "$TMP/receipt.json" --result-dir "$TMP/run-missing-policy"
jq '.cases[1].workload = "guessed"' "$TMP/suite.json" > "$TMP/invalid-workload-suite.json"
reject run_reject "$TMP/invalid-workload-suite.json" "$TMP/policy.json" "$TMP/run-workload"
jq '.cases[1].requiredCapabilities = ["long-context"]' "$TMP/suite.json" > "$TMP/capability-suite.json"
reject run_reject "$TMP/capability-suite.json" "$TMP/policy.json" "$TMP/run-capability"
mkdir "$TMP/non-empty-result"; printf occupied > "$TMP/non-empty-result/retained.json"
reject run_reject "$TMP/suite.json" "$TMP/policy.json" "$TMP/non-empty-result"
assert test ! -e "$TMP/wrapper-called"
assert test -f "$TMP/non-empty-result/retained.json"

# A fully eligible offline run selects the case workload, binds the receipt,
# and cannot invoke even a caller-supplied wrapper.
CALL_MARKER="$TMP/wrapper-called" DEPOT_BENCH_SUITE="$TMP/suite.json" \
  DEPOT_BENCH_MATRIX="$TMP/matrix.json" DEPOT_BENCH_WRAPPER="$TMP/wrapper-stub.sh" \
  "$RUNNER" --offline-run --case review-zero-deferral --model fixture/model \
  --role-policy "$TMP/policy.json" --output-file "$TMP/output" \
  --receipt-file "$TMP/receipt.json" --result-dir "$TMP/success-run" >/dev/null
assert test ! -e "$TMP/wrapper-called"
assert jq -e '.workload == "quality" and .identityStatus.receiptBinding == {
    suiteId:"depot-role-fixture-v2",caseId:"review-zero-deferral",role:"review-fast",workload:"quality"
  } and .transport == "openrouter" and .endpointProvider == "fixture-endpoint" and .overallSuccess' \
  "$TMP/success-run/result.json"

ROLE_POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
reject env DEPOT_BENCH_SUITE="$TMP/suite.json" CALL_MARKER="$TMP/wrapper-called" \
  DEPOT_BENCH_WRAPPER="$TMP/wrapper-stub.sh" "$RUNNER" --run \
  --case pipeline-legacy-translation --model deepseek/deepseek-v4-flash-0731 \
  --role-policy "$ROLE_POLICY" --result-dir "$TMP/live-override-rejected"
reject env CALL_MARKER="$TMP/wrapper-called" "$RUNNER" --run \
  --case pipeline-legacy-translation --model deepseek/deepseek-v4-flash-0731 \
  --role-policy "$TMP/policy.json" --result-dir "$TMP/live-policy-rejected"
mkdir "$TMP/live-non-empty"
printf retained > "$TMP/live-non-empty/retained.json"
reject "$RUNNER" --run --case pipeline-legacy-translation \
  --model deepseek/deepseek-v4-flash-0731 --role-policy "$ROLE_POLICY" \
  --result-dir "$TMP/live-non-empty"
reject "$RUNNER" --run --case pipeline-legacy-translation \
  --model z-ai/glm-5.3-flash --role-policy "$ROLE_POLICY" \
  --result-dir "$TMP/live-ineligible"
assert test ! -e "$TMP/wrapper-called"
assert test -f "$TMP/live-non-empty/retained.json"

printf 'benchmark evidence contract: %d assertions passed (offline; local stubs only)\n' "$pass"
