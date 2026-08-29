#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
SUITE="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json"
ROLE_POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/depot-role-benchmark.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }
reject() { if "$@" >/dev/null 2>&1; then printf 'FAIL: unexpectedly accepted: %s\n' "$*" >&2; exit 1; fi; pass=$((pass+1)); }

write_receipt() {
  local case_id="$1" destination="$2" role workload
  role="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .role' "$SUITE")"
  workload="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .workload' "$SUITE")"
  jq -n --arg caseId "$case_id" --arg role "$role" --arg workload "$workload" '
    {schemaVersion:2,outcome:"success",requestedModel:"fixture/model",
     modelCandidates:["fixture/model"],responseModel:"fixture/model",responseModelProvenance:"response",
     servingProvider:"fixture",servingProviderProvenance:"response",attemptedModel:"fixture/model",
     attemptedModels:["fixture/model"],attemptProvenance:"response_model",fallbackUsed:false,
     benchmark:{suiteId:"depot-role-v2",caseId:$caseId,role:$role,workload:$workload},
     usage:{prompt_tokens:10,completion_tokens:5}}' > "$destination"
}

score_fixture() {
  local case_id="$1" output="$2" attempt_dir="$3"
  mkdir -p "$attempt_dir"
  write_receipt "$case_id" "$attempt_dir/receipt.json"
  "$RUNNER" --score --case "$case_id" --output-file "$output" \
    --receipt-file "$attempt_dir/receipt.json" --result-file "$attempt_dir/result.json"
}

assert test -x "$RUNNER"
assert jq -e '
  .schemaVersion == 2 and .suiteId == "depot-role-v2" and .suiteRevision == 1
  and .behavioralContract.revision == 1
  and .behavioralContract.digest == "sha256:3ecea8dc49c02a8a8ac2a6e7ede9993fb6609f7520d5438ab8bf0cf9170ba32a"
  and .measurementPolicy.liveProviderRequiredForFixtureValidation == false
  and (.cases | length) >= 18
' "$SUITE"
assert sh -c "[ \"\$('$RUNNER' --list | wc -l | tr -d ' ')\" = 18 ]"

# role-policy.json is the sole role inventory authority. Every current role has
# at least two distinct case IDs and task types; unknown suite roles are rejected.
assert jq -n -e --slurpfile suite "$SUITE" --slurpfile policy "$ROLE_POLICY" '
  ($policy[0].roles | keys | sort) as $policyRoles
  | ($suite[0].cases | map(.role) | unique | sort) as $suiteRoles
  | $suiteRoles == $policyRoles
  and all($policyRoles[]; . as $role
    | ($suite[0].cases | map(select(.role == $role))) as $cases
    | ($cases | length) >= 2
      and ($cases | map(.id) | unique | length) >= 2
      and ($cases | map(.taskType) | unique | length) >= 2)
'

# Required case contract, closed workload values, capability fit, and explicit
# applicability are validated without manufacturing tool/browser/multi-turn data.
assert jq -n -e --slurpfile suite "$SUITE" --slurpfile policy "$ROLE_POLICY" '
  all($suite[0].cases[]; . as $case
    | (.id | type == "string" and length > 0)
      and (.revision | type == "number" and . >= 1)
      and (.promptRevision | type == "number" and . >= 1)
      and (.role | type == "string") and (.taskType | type == "string" and length > 0)
      and (.objective | type == "string" and length > 0)
      and (.requiredCapabilities | type == "array" and length > 0)
      and (.workload == "mechanical" or .workload == "quality" or .workload == "security")
      and (.executionMode | type == "string" and startswith("single-turn-sealed-"))
      and (.prompt | type == "string" and contains("Return one raw JSON object"))
      and (.outputContract | type == "object")
      and (.mandatoryAssertions | type == "array" and length >= 3)
      and (.semanticCriteria | type == "array" and length > 0)
      and (.validatorCriteria | type == "array" and length == 1)
      and .validatorCriteria[0].id == .validatorId
      and (.fixtureProvenance | type == "object" and .liveAccess == false)
      and (.applicability | keys | sort) == (["browser","multiTurn","repositoryValidation","toolUse"] | sort)
      and all(.applicability[]; type == "boolean")
      and all(.requiredCapabilities[]; . as $needed
        | any($policy[0].roles[$case.role][]; .capabilities | index($needed) != null)))
  and ([$suite[0].cases[] | select(.applicability.toolUse)] | length) == 0
  and ([$suite[0].cases[] | select(.applicability.browser)] | length) == 0
  and ([$suite[0].cases[] | select(.applicability.multiTurn)] | length) == 0
  and ([$suite[0].cases[] | select(.applicability.repositoryValidation)] | length) > 0
'
assert jq -e '
  all(.cases[]; . as $case
    | (($case.mandatoryAssertions + $case.semanticCriteria) | map(.id) | sort) == ($case.disclosedAssertions | sort)
      and all(($case.mandatoryAssertions + $case.semanticCriteria)[]; (.id | length) > 0 and (.description | length) > 0)
      and all($case.validatorCriteria[]; (.id | length) > 0 and (.description | length) > 0))
' "$SUITE"
assert jq -e '
  all(.cases[] | select(.role == "security-review"); .workload == "security" and (.prompt | test("small|4-50|two developers"; "i")))
  and all(.cases[] | select(.role == "builder-fast"); .workload == "mechanical")
  and all(.cases[] | select(.role == "editorial"); .workload == "quality" and .humanRubricRequired == true)
' "$SUITE"
assert jq -e '
  .humanRubricContract.path == "<attempt-directory>/human-rubric.json"
  and .humanRubricContract.join == "normalized-output-artifact-sha256"
  and all(.cases[] | select(.humanRubricRequired == true);
    .humanRubric.rubricRevision == 1 and (.humanRubric.criteria | length) == 2
    and ((.humanRubric.criteria | map(.id) | unique | length) == (.humanRubric.criteria | length)))
' "$SUITE"

# Every checked-in expected answer exercises the public scorer and validator.
while IFS= read -r case_id; do
  jq --arg id "$case_id" '.cases[] | select(.id == $id) | .expected' "$SUITE" > "$TMP/expected-output"
  score_fixture "$case_id" "$TMP/expected-output" "$TMP/expected-$case_id"
  assert jq -e --arg id "$case_id" '
    .caseId == $id and .suiteId == "depot-role-v2" and .overallSuccess
    and .contractPassed and .mandatoryPassed and .semanticPassed and .validationPassed
    and .qualityScore == 100 and (.benchmarkFault | not)
  ' "$TMP/expected-$case_id/result.json"
  if jq -e --arg id "$case_id" '.cases[] | select(.id == $id) | .humanRubricRequired == true' "$SUITE" >/dev/null; then
    assert jq -e '.humanRubricEvidence.status == "absent" and .humanQuality == null and .overallSuccess' "$TMP/expected-$case_id/result.json"
  else
    assert jq -e '.humanRubricEvidence.status == "not-applicable" and .humanQuality == null' "$TMP/expected-$case_id/result.json"
  fi
done < <(jq -r '.cases[].id' "$SUITE")

# Documented judgment alternatives pass without hidden labels or exact wording.
while IFS=$'\t' read -r case_id alternative_count; do
  index=0
  while [ "$index" -lt "$alternative_count" ]; do
    jq --arg id "$case_id" --argjson index "$index" \
      '.cases[] | select(.id == $id) | .semanticAlternatives[$index].output' "$SUITE" > "$TMP/alternative-output"
    score_fixture "$case_id" "$TMP/alternative-output" "$TMP/alternative-$case_id-$index"
    assert jq -e '.overallSuccess and .qualityScore == 100 and (.benchmarkFault | not)' \
      "$TMP/alternative-$case_id-$index/result.json"
    index=$((index+1))
  done
done < <(jq -r '.cases[] | [.id, (.semanticAlternatives | length)] | @tsv' "$SUITE")
assert jq -e '
  .cases[] | select(.id == "assembly-next-chunk")
  | (.semanticAlternatives | length) > 0
  and (.prompt | contains("no exact nextChunk label, executor label, or capability wording is required"))
' "$SUITE"

# Every deliberate negative fails its named public assertion rather than a
# hidden wording oracle or benchmark fault.
while IFS=$'\t' read -r case_id fixture_count; do
  index=0
  while [ "$index" -lt "$fixture_count" ]; do
    jq --arg id "$case_id" --argjson index "$index" \
      '.cases[] | select(.id == $id) | .negativeFixtures[$index].output' "$SUITE" > "$TMP/negative-output"
    jq --arg id "$case_id" --argjson index "$index" \
      '.cases[] | select(.id == $id) | .negativeFixtures[$index].mustFailAssertionIds' "$SUITE" > "$TMP/must-fail"
    score_fixture "$case_id" "$TMP/negative-output" "$TMP/negative-$case_id-$index"
    assert jq -e --slurpfile required "$TMP/must-fail" '
      . as $result | (.overallSuccess | not) and (.benchmarkFault | not)
      and all($required[0][]; . as $id | any($result.assertions[]; .id == $id and (.pass | not)))
    ' "$TMP/negative-$case_id-$index/result.json"
    index=$((index+1))
  done
done < <(jq -r '.cases[] | [.id, (.negativeFixtures | length)] | @tsv' "$SUITE")

# Removing a scorer assertion from the disclosed prompt contract is a benchmark
# fault. This guards against a regression to hidden exact-value scoring.
jq '(.cases[] | select(.id == "review-zero-deferral") | .disclosedAssertions) -= ["review.AUTH-1"]' \
  "$SUITE" > "$TMP/undisclosed-suite.json"
jq '.cases[] | select(.id == "review-zero-deferral") | .expected' "$SUITE" > "$TMP/output"
mkdir -p "$TMP/undisclosed"
write_receipt review-zero-deferral "$TMP/undisclosed/receipt.json"
DEPOT_BENCH_SUITE="$TMP/undisclosed-suite.json" "$RUNNER" --score --case review-zero-deferral \
  --output-file "$TMP/output" --receipt-file "$TMP/undisclosed/receipt.json" \
  --result-file "$TMP/undisclosed/result.json"
assert jq -e '
  .benchmarkFault and (.comparable | not) and .failureStage == "prompt/contract"
  and .failureClass == "benchmark-prompt-contract-fault" and .modelConclusion == null
' "$TMP/undisclosed/result.json"

# Blinded editorial evidence is a separate digest-bound axis. Invalid or absent
# evidence never changes deterministic model gates.
EDITORIAL_CASE=editorial-member-update
jq --arg id "$EDITORIAL_CASE" '.cases[] | select(.id == $id) | .expected' "$SUITE" > "$TMP/editorial-output"
jq -s 'if length == 1 and (.[0] | type) == "object" then .[0] else empty end' \
  "$TMP/editorial-output" > "$TMP/editorial-normalized"
editorial_digest="sha256:$(sha256sum "$TMP/editorial-normalized" | awk '{print $1}')"

make_human_receipt() {
  local destination="$1"
  jq -n --arg digest "$editorial_digest" '
    {schemaVersion:1,suiteId:"depot-role-v2",caseId:"editorial-member-update",caseRevision:1,
     rubricRevision:1,outputArtifactSha256:$digest,blindToCandidate:true,
     observedAt:"2026-08-29T00:00:00Z",criterionScores:{"member-clarity":5,"member-voice":4}}' > "$destination"
}

mkdir -p "$TMP/human-valid"
make_human_receipt "$TMP/human-valid/human-rubric.json"
write_receipt "$EDITORIAL_CASE" "$TMP/human-valid/receipt.json"
"$RUNNER" --score --case "$EDITORIAL_CASE" --output-file "$TMP/editorial-output" \
  --receipt-file "$TMP/human-valid/receipt.json" --result-file "$TMP/human-valid/result.json"
assert jq -e '
  .overallSuccess and .humanRubricEvidence.status == "accepted"
  and .humanQuality.rubricRevision == 1 and .humanQuality.meanScore == 4.5
  and .humanQuality.criterionScores == {"member-clarity":5,"member-voice":4}
' "$TMP/human-valid/result.json"
assert jq -e '
  (keys | sort) == (["blindToCandidate","caseId","caseRevision","criterionScores","observedAt","outputArtifactSha256","rubricRevision","schemaVersion","suiteId"] | sort)
  and ([.. | objects | keys[]] | map(select(. != "blindToCandidate" and test("candidate|model|provider|transport"; "i"))) | length) == 0
' "$TMP/human-valid/human-rubric.json"

for fixture in unblinded digest-mismatch case-mismatch rubric-mismatch unknown-criterion identity-bearing; do
  mkdir -p "$TMP/human-$fixture"
  make_human_receipt "$TMP/human-$fixture/human-rubric.json"
  case "$fixture" in
    unblinded) jq '.blindToCandidate = false' "$TMP/human-$fixture/human-rubric.json" > "$TMP/human-mutated" ;;
    digest-mismatch) jq '.outputArtifactSha256 = "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"' "$TMP/human-$fixture/human-rubric.json" > "$TMP/human-mutated" ;;
    case-mismatch) jq '.caseRevision = 999' "$TMP/human-$fixture/human-rubric.json" > "$TMP/human-mutated" ;;
    rubric-mismatch) jq '.rubricRevision = 999' "$TMP/human-$fixture/human-rubric.json" > "$TMP/human-mutated" ;;
    unknown-criterion) jq '.criterionScores = {"member-clarity":5,"unknown":4}' "$TMP/human-$fixture/human-rubric.json" > "$TMP/human-mutated" ;;
    identity-bearing) jq '.model = "forbidden/model"' "$TMP/human-$fixture/human-rubric.json" > "$TMP/human-mutated" ;;
  esac
  mv "$TMP/human-mutated" "$TMP/human-$fixture/human-rubric.json"
  write_receipt "$EDITORIAL_CASE" "$TMP/human-$fixture/receipt.json"
  "$RUNNER" --score --case "$EDITORIAL_CASE" --output-file "$TMP/editorial-output" \
    --receipt-file "$TMP/human-$fixture/receipt.json" --result-file "$TMP/human-$fixture/result.json"
  assert jq -e '
    .overallSuccess and .contractPassed and .mandatoryPassed and .semanticPassed and .validationPassed
    and .humanRubricEvidence.status == "rejected" and .humanQuality == null
  ' "$TMP/human-$fixture/result.json"
done

printf '%s\n' 'not-json' > "$TMP/output"
score_fixture review-zero-deferral "$TMP/output" "$TMP/invalid-json"
assert jq -e '.parsed == false and .qualityScore == 0 and (.overallSuccess | not)' "$TMP/invalid-json/result.json"
reject "$RUNNER" --prepare --case absent --output-file "$TMP/prompt"

printf 'openrouter role benchmark: %d assertions passed\n' "$pass"
