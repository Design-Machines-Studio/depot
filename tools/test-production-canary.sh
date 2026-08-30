#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/plugins/openrouter/skills/openrouter-delegate/references"
RUNNER="$DIR/depot-role-production-canary.sh"
UNITS="$DIR/depot-role-production-canary-work-units.json"
SUITE="$DIR/depot-role-benchmark-suite.json"
POLICY="$ROOT/plugins/model-router/skills/model-router/references/role-policy.json"
OPENROUTER_MANIFEST="$ROOT/plugins/openrouter/.claude-plugin/plugin.json"
MODEL_ROUTER_MANIFEST="$ROOT/plugins/model-router/.claude-plugin/plugin.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/depot-production-canary-test.XXXXXX")"
trap 'if [ "${DEPOT_CANARY_KEEP_TMP:-0}" = 1 ]; then printf "retained fixture root: %s\\n" "$TMP"; else rm -rf "$TMP"; fi' EXIT
pass=0

assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }
reject() { if "$@" >/dev/null 2>&1; then printf 'FAIL: unexpectedly accepted: %s\n' "$*" >&2; exit 1; fi; pass=$((pass+1)); }
digest_file() { sha256sum "$1" | awk '{print "sha256:" $1}'; }

assert rg -F 'date -u +%Y%m%dt%H%M%Sz' "$RUNNER"
assert rg -F 'CANARY_TEMP_ROOT="$temp_root"; CANARY_WORKTREE="$worktree"' "$RUNNER"
assert rg -F 'if ! cleanup_owned_resources; then' "$RUNNER"
assert rg -F '.validationPassed == true and .benchmarkFault == false' "$RUNNER"
assert jq -e 'has("repositoryIdentity") | not' "$UNITS"
assert jq -e 'has("sealedSuite") | not' "$UNITS"
assert jq -e 'has("rolePolicy") | not' "$UNITS"
assert rg -F 'cat -- "$path"' "$RUNNER"
reject rg -F "sed -n '1,220p'" "$RUNNER"
reject rg -F "sed -n '1,\$p'" "$RUNNER"
reject rg -F 'bypassPermissions' "$RUNNER"

make_attempt() {
  local unit_id="$1" destination="$2" unit role case_id candidate transport provider work_digest fixture_digest validation_digest
  local case_digest scorer_digest policy_digest openrouter_version model_router_version context_total applicable cost_bound measured coverage allowed
  unit="$(jq -c --arg id "$unit_id" '.workUnits[] | select(.id == $id)' "$UNITS")"
  role="$(jq -r '.role' <<<"$unit")"; case_id="$(jq -r '.sealedCaseId' <<<"$unit")"
  candidate="$(jq -r --arg role "$role" '.roles[$role][0].model' "$POLICY")"
  transport="$(jq -r --arg role "$role" '.roles[$role][0].transport' "$POLICY")"
  provider="$(jq -r --arg role "$role" '.roles[$role][0].provider' "$POLICY")"
  allowed="$(jq -c --arg role "$role" --arg candidate "$candidate" \
    '([$candidate] + (.roles[$role][0].servedIdentities // [])) | unique' "$POLICY")"
  work_digest="$(jq -cS . <<<"$unit" | sha256sum | awk '{print "sha256:" $1}')"
  fixture_digest="$(jq -cS '.fixture // {}' <<<"$unit" | sha256sum | awk '{print "sha256:" $1}')"
  validation_digest="$(jq -cnS --argjson unit "$unit" --argjson case "$(jq -c --arg id "$case_id" '.cases[] | select(.id == $id)' "$SUITE")" \
    '{repositoryValidator:$unit.repositoryValidator,sealedCaseId:$unit.sealedCaseId,mandatoryAssertions:$case.mandatoryAssertions,validatorId:$case.validatorId}' \
    | sha256sum | awk '{print "sha256:" $1}')"
  case_digest="$(jq -r --arg id "$case_id" '.bindings.cases[$id].caseDigest' "$SUITE")"
  scorer_digest="$(jq -r --arg id "$case_id" '.bindings.cases[$id].scorerDigest' "$SUITE")"
  policy_digest="$(digest_file "$POLICY")"
  openrouter_version="$(jq -r '.version' "$OPENROUTER_MANIFEST")"; model_router_version="$(jq -r '.version' "$MODEL_ROUTER_MANIFEST")"
  context_total="$(jq -r '.contextPaths | length' <<<"$unit")"; applicable="$(jq -r '.toolCoverage.applicable' <<<"$unit")"
  if [ "$transport" = openrouter ]; then cost_bound=0.5; measured=0.01; coverage=measured; else cost_bound=null; measured=null; coverage=subscription; fi

  mkdir -p "$destination"
  printf 'bounded prompt\n' > "$destination/prompt.txt"
  printf '{}\n' > "$destination/output.json"
  : > "$destination/patch.diff"
  jq -n --arg caseId "$case_id" '{schemaVersion:2,caseId:$caseId,validationPassed:true,overallSuccess:true,benchmarkFault:false,
    assertions:[{id:"strict-json-object",class:"mandatory",pass:true}]}' > "$destination/validation.json"
  jq -n --arg model "$candidate" --arg provider "$provider" --arg transport "$transport" \
    '{requestedModel:$model,responseModel:$model,servingProvider:$provider,transport:$transport,fallbackUsed:false,usage:{cost:0.01}}' > "$destination/transport-receipt.json"

  jq -n --arg attemptId "fixture-${unit_id}" --arg unitId "$unit_id" --argjson unitRevision "$(jq -r '.revision' <<<"$unit")" \
    --arg workDigest "$work_digest" --arg fixtureDigest "$fixture_digest" --arg validationDigest "$validation_digest" \
    --arg caseId "$case_id" --arg caseDigest "$case_digest" --arg scorerDigest "$scorer_digest" --arg policyDigest "$policy_digest" \
    --arg openrouterVersion "$openrouter_version" --arg modelRouterVersion "$model_router_version" --arg role "$role" \
    --arg candidate "$candidate" --arg transport "$transport" --arg provider "$provider" --argjson allowed "$allowed" --arg coverage "$coverage" \
    --argjson contextTotal "$context_total" --argjson applicable "$applicable" --argjson maximumBound "$cost_bound" --argjson measured "$measured" \
    --arg promptDigest "$(digest_file "$destination/prompt.txt")" --argjson promptBytes "$(wc -c < "$destination/prompt.txt")" \
    --arg outputDigest "$(digest_file "$destination/output.json")" --argjson outputBytes "$(wc -c < "$destination/output.json")" \
    --arg patchDigest "$(digest_file "$destination/patch.diff")" --argjson patchBytes "$(wc -c < "$destination/patch.diff")" \
    --arg validationArtifactDigest "$(digest_file "$destination/validation.json")" --argjson validationBytes "$(wc -c < "$destination/validation.json")" \
    --arg receiptDigest "$(digest_file "$destination/transport-receipt.json")" --argjson receiptBytes "$(wc -c < "$destination/transport-receipt.json")" '
    {schemaVersion:1,evidenceClass:"production-canary",harnessVersion:1,attemptId:$attemptId,
     repository:{identity:"Design-Machines-Studio/depot",baseRevision:"50946ef1dad6aa879a0b4feb701222102d9e4229",headRevision:"50946ef1dad6aa879a0b4feb701222102d9e4229",cleanBase:true,patchDigest:$patchDigest,changedFileCount:0},
     bindings:{workUnitId:$unitId,workUnitRevision:$unitRevision,workUnitDigest:$workDigest,taskFixtureDigest:$fixtureDigest,
       validationContractDigest:$validationDigest,sealedSuiteId:"depot-role-v2",sealedCaseId:$caseId,sealedCaseDigest:$caseDigest,
       sealedScorerDigest:$scorerDigest,rolePolicyDigest:$policyDigest,pluginVersions:{openrouter:$openrouterVersion,"model-router":$modelRouterVersion}},
     identity:{role:$role,requestedCandidate:$candidate,transport:$transport,servedIdentity:$candidate,provider:$provider,
       aliasResolution:{status:"exact",allowedServedIdentities:$allowed},fallbackUsed:false},
     boundaries:{fixtureIntegrity:true,evaluatorBinding:true,validatorIntegrity:true,repositoryIntegrity:true,
       instrumentationComplete:true,requiredToolAvailable:true,harnessComplete:true},
     quality:{firstPassValidity:true,finalValidity:true,mandatoryAssertions:[{id:"strict-json-object",pass:true}],
       usefulFindings:(if ($role|startswith("review-")) then 1 else null end),falsePositives:(if ($role|startswith("review-")) then 0 else null end),
       correctionCount:0,validationAttempts:1},
     timing:{startedAt:"2026-08-29T00:00:00Z",firstUsefulAt:"2026-08-29T00:00:01Z",validAt:"2026-08-29T00:00:01Z",
       endedAt:"2026-08-29T00:00:01Z",timeToFirstUsefulSeconds:1,timeToValidSeconds:1,totalDurationSeconds:1},
     telemetry:{toolCallsByClass:{repositoryRead:1,repositoryWrite:0,validation:1,other:0},tokens:{input:null,output:null,reasoning:null},
       contextCoverage:{applicable:true,observed:$contextTotal,total:$contextTotal,rate:1,reason:"fixture"},
       toolCoverage:(if $applicable then {applicable:true,observed:1,total:1,rate:1,reason:"fixture"} else {applicable:false,observed:null,total:null,rate:null,reason:"not applicable"} end)},
     cost:{currency:"USD",maximumBoundUsd:$maximumBound,measuredUsd:$measured,receiptCoverage:$coverage},
     artifacts:[
       {kind:"prompt",path:"prompt.txt",sha256:$promptDigest,bytes:$promptBytes},
       {kind:"output",path:"output.json",sha256:$outputDigest,bytes:$outputBytes},
       {kind:"patch",path:"patch.diff",sha256:$patchDigest,bytes:$patchBytes},
       {kind:"validation",path:"validation.json",sha256:$validationArtifactDigest,bytes:$validationBytes},
       {kind:"transport-receipt",path:"transport-receipt.json",sha256:$receiptDigest,bytes:$receiptBytes}],
     outcome:{transportSuccess:true,benchmarkFault:false,faultOwner:null,faultCode:null,comparable:true,modelConclusion:"valid",evidenceState:"comparable-but-insufficient"}}
  ' > "$destination/attempt.json"
}

# Every current role validates under one shared attempt contract.
while IFS= read -r unit_id; do
  make_attempt "$unit_id" "$TMP/$unit_id"
  "$RUNNER" --validate --attempt-file "$TMP/$unit_id/attempt.json" --artifact-root "$TMP/$unit_id" > "$TMP/$unit_id/result.json"
  assert jq -e '.comparable and (.benchmarkFault | not) and .modelConclusion == "valid" and .evidenceState == "comparable-but-insufficient"' "$TMP/$unit_id/result.json"
done < <(jq -r '.workUnits[].id' "$UNITS")

BASE="$TMP/canary-research-claim-map"

mkdir "$TMP/cross-model"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/cross-model/"
jq '.identity.servedIdentity="other/model" | .identity.aliasResolution.status="unmapped"' "$TMP/cross-model/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/cross-model/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/cross-model/attempt.json" --artifact-root "$TMP/cross-model" > "$TMP/cross-model/result.json"
assert jq -e '(.benchmarkFault | not) and (.comparable | not) and .modelConclusion == null and .evidenceState == "incompatible"' "$TMP/cross-model/result.json"

mkdir "$TMP/fallback"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/fallback/"
jq '.identity.fallbackUsed=true' "$TMP/fallback/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/fallback/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/fallback/attempt.json" --artifact-root "$TMP/fallback" > "$TMP/fallback/result.json"
assert jq -e '(.benchmarkFault | not) and (.comparable | not) and .modelConclusion == null' "$TMP/fallback/result.json"

mkdir "$TMP/evaluator"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/evaluator/"
jq '.bindings.sealedScorerDigest="sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"' "$TMP/evaluator/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/evaluator/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/evaluator/attempt.json" --artifact-root "$TMP/evaluator" > "$TMP/evaluator/result.json"
assert jq -e '.benchmarkFault and .faultOwner == "evaluator" and .modelConclusion == null' "$TMP/evaluator/result.json"

mkdir "$TMP/drift"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/drift/"
jq '.repository.headRevision="ffffffffffffffffffffffffffffffffffffffff" | .quality.correctionCount=null' "$TMP/drift/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/drift/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/drift/attempt.json" --artifact-root "$TMP/drift" > "$TMP/drift/result.json"
assert jq -e '.benchmarkFault and .faultOwner == "repository" and .faultCode == "repository-drift" and .modelConclusion == null' "$TMP/drift/result.json"

mkdir "$TMP/symlink"; cp "$BASE"/{output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/symlink/"; ln -s "$BASE/prompt.txt" "$TMP/symlink/prompt.txt"
"$RUNNER" --validate --attempt-file "$TMP/symlink/attempt.json" --artifact-root "$TMP/symlink" > "$TMP/symlink/result.json"
assert jq -e '.benchmarkFault and .faultOwner == "harness" and (.diagnostics | length) == 1 and .modelConclusion == null' "$TMP/symlink/result.json"

mkdir "$TMP/path-escape"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/path-escape/"
jq '.artifacts[0].path="../prompt.txt"' "$TMP/path-escape/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/path-escape/attempt.json"
reject "$RUNNER" --validate --attempt-file "$TMP/path-escape/attempt.json" --artifact-root "$TMP/path-escape"

mkdir "$TMP/telemetry"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/telemetry/"
jq '.quality.correctionCount=null' "$TMP/telemetry/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/telemetry/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/telemetry/attempt.json" --artifact-root "$TMP/telemetry" > "$TMP/telemetry/result.json"
assert jq -e '.benchmarkFault and .faultOwner == "instrumentation" and .modelConclusion == null' "$TMP/telemetry/result.json"

mkdir "$TMP/missing-paid-cost"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/missing-paid-cost/"
jq '.cost.measuredUsd=null | .cost.receiptCoverage="missing"' "$TMP/missing-paid-cost/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/missing-paid-cost/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/missing-paid-cost/attempt.json" --artifact-root "$TMP/missing-paid-cost" > "$TMP/missing-paid-cost/result.json"
assert jq -e '.benchmarkFault and .faultOwner == "instrumentation" and .faultCode == "missing-paid-cost-receipt" and .modelConclusion == null' "$TMP/missing-paid-cost/result.json"

mkdir "$TMP/over-paid-bound"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/over-paid-bound/"
jq '.cost.maximumBoundUsd=1.01' "$TMP/over-paid-bound/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/over-paid-bound/attempt.json"
reject "$RUNNER" --validate --attempt-file "$TMP/over-paid-bound/attempt.json" --artifact-root "$TMP/over-paid-bound"

mkdir "$TMP/failed-validation"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/failed-validation/"
jq '.validationPassed=false | .overallSuccess=false | .assertions[0].pass=false' "$TMP/failed-validation/validation.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/failed-validation/validation.json"
jq --arg digest "$(digest_file "$TMP/failed-validation/validation.json")" --argjson bytes "$(wc -c < "$TMP/failed-validation/validation.json")" '
  .quality.firstPassValidity=false | .quality.finalValidity=false | .quality.mandatoryAssertions[0].pass=false
  | .timing.validAt=null | .timing.timeToValidSeconds=null
  | (.artifacts[] | select(.kind == "validation") | .sha256)=$digest
  | (.artifacts[] | select(.kind == "validation") | .bytes)=$bytes
' "$TMP/failed-validation/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/failed-validation/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/failed-validation/attempt.json" --artifact-root "$TMP/failed-validation" > "$TMP/failed-validation/result.json"
assert jq -e '(.benchmarkFault | not) and .comparable and .modelConclusion == "invalid"' "$TMP/failed-validation/result.json"

REVIEW="$TMP/canary-review-fast-false-positive"
jq '.validationPassed=false | .overallSuccess=false | .assertions[0].pass=false' "$REVIEW/validation.json" > "$TMP/mutated"; mv "$TMP/mutated" "$REVIEW/validation.json"
jq --arg digest "$(digest_file "$REVIEW/validation.json")" --argjson bytes "$(wc -c < "$REVIEW/validation.json")" '
  .quality.falsePositives=1 | .quality.finalValidity=false | .quality.mandatoryAssertions[0].pass=false
  | (.artifacts[] | select(.kind == "validation") | .sha256)=$digest
  | (.artifacts[] | select(.kind == "validation") | .bytes)=$bytes
' "$REVIEW/attempt.json" > "$TMP/review-false-positive.json"
"$RUNNER" --validate --attempt-file "$TMP/review-false-positive.json" --artifact-root "$REVIEW" > "$TMP/review-false-positive-result.json"
assert jq -e '.comparable and .quality.falsePositives == 1 and .modelConclusion == "invalid"' "$TMP/review-false-positive-result.json"

mkdir "$TMP/benchmark-fault"; cp "$BASE"/{prompt.txt,output.json,patch.diff,validation.json,transport-receipt.json,attempt.json} "$TMP/benchmark-fault/"
jq '.boundaries.fixtureIntegrity=false' "$TMP/benchmark-fault/attempt.json" > "$TMP/mutated"; mv "$TMP/mutated" "$TMP/benchmark-fault/attempt.json"
"$RUNNER" --validate --attempt-file "$TMP/benchmark-fault/attempt.json" --artifact-root "$TMP/benchmark-fault" > "$TMP/benchmark-fault/result.json"
assert jq -e '.benchmarkFault and .evidenceState == "benchmark-faulted" and .modelConclusion == null' "$TMP/benchmark-fault/result.json"

jq '.schemaVersion=99' "$BASE/attempt.json" > "$TMP/unknown-schema.json"
reject "$RUNNER" --validate --attempt-file "$TMP/unknown-schema.json" --artifact-root "$BASE"

jq '.timing.startedAt="not-a-timestamp"' "$BASE/attempt.json" > "$TMP/bad-timestamp.json"
reject "$RUNNER" --validate --attempt-file "$TMP/bad-timestamp.json" --artifact-root "$BASE"
jq '.quality.unexpected=true' "$BASE/attempt.json" > "$TMP/extra-quality-key.json"
reject "$RUNNER" --validate --attempt-file "$TMP/extra-quality-key.json" --artifact-root "$BASE"
jq '.repository.identity="example/other"' "$BASE/attempt.json" > "$TMP/bad-repository-identity.json"
reject "$RUNNER" --validate --attempt-file "$TMP/bad-repository-identity.json" --artifact-root "$BASE"
jq '.telemetry.contextCoverage={applicable:true,observed:2,total:1,rate:2,reason:"invalid"}' "$BASE/attempt.json" > "$TMP/bad-coverage.json"
reject "$RUNNER" --validate --attempt-file "$TMP/bad-coverage.json" --artifact-root "$BASE"

# Disabled native transport and result-directory containment fail before provider contact.
reject "$RUNNER" --run --work-unit canary-architect-routing-boundary --transport claude-cli \
  --model fable --effort high --base-revision HEAD --result-dir "$TMP/claude-disabled"
assert test ! -e "$TMP/claude-disabled"
reject env DEPOT_CANARY_SOURCE_ONLY=1 bash -c '
  runner="$1"; result="$2"; set --; source "$runner"; RESULT_DIR="$result"; prepare_result_dir
' _ "$RUNNER" "$ROOT/.depot-canary-result-test"
assert test ! -e "$ROOT/.depot-canary-result-test"
mkdir "$TMP/result-target"
ln -s "$TMP/result-target" "$TMP/result-link"
reject env DEPOT_CANARY_SOURCE_ONLY=1 bash -c '
  runner="$1"; result="$2"; set --; source "$runner"; RESULT_DIR="$result"; prepare_result_dir
' _ "$RUNNER" "$TMP/result-link"

# Helper-level fault retention and artifact bounding remain offline and deterministic.
assert env DEPOT_CANARY_SOURCE_ONLY=1 bash -c '
  runner="$1"; scratch="$2"; set --; source "$runner"
  RESULT_DIR="$scratch"; mkdir -p "$RESULT_DIR"
  if ensure_openrouter_receipt "$RESULT_DIR/receipt.json" "$RESULT_DIR/raw.json" model case role workload 17; then exit 1; fi
  jq -e '\''.[0].failureKind == "missing-transport-receipt" and .[1] == {}'\'' \
    <(jq -s . "$RESULT_DIR/receipt.json" "$RESULT_DIR/raw.json") >/dev/null
  retain_scorer_fault "$RESULT_DIR/score.json" case
  jq -e '\''.benchmarkFault and .failureClass == "scorer-failure"'\'' "$RESULT_DIR/score.json" >/dev/null
  head -c 100 /dev/zero > "$RESULT_DIR/patch.diff"
  if bound_retained_artifact "$RESULT_DIR/patch.diff" 16; then exit 1; fi
  [ "$(wc -c < "$RESULT_DIR/patch.diff")" -eq 16 ]
  head -c 100 /dev/zero > "$RESULT_DIR/transport-events-2.json"
  if bound_retained_artifact "$RESULT_DIR/transport-events-2.json" 16; then exit 1; fi
  [ "$(wc -c < "$RESULT_DIR/transport-events-2.json")" -eq 16 ]
  : > "$RESULT_DIR/output-1.json"; : > "$RESULT_DIR/output-2.json"
  : > "$RESULT_DIR/transport-receipt-1.json"; : > "$RESULT_DIR/transport-events-1.json"
  : > "$RESULT_DIR/validation-1.json"; : > "$RESULT_DIR/system.txt"; : > "$RESULT_DIR/diagnostic-1.txt"
  prune_unretained_attempt_artifacts "$RESULT_DIR/output-2.json" "$RESULT_DIR/receipt.json" "$RESULT_DIR/raw.json" "$RESULT_DIR/score.json"
  [ -e "$RESULT_DIR/output-2.json" ] && [ ! -e "$RESULT_DIR/output-1.json" ] \
    && [ ! -e "$RESULT_DIR/system.txt" ] && [ ! -e "$RESULT_DIR/diagnostic-1.txt" ]
' _ "$RUNNER" "$TMP/helpers"

# Builder validators reject additions outside the exact owned fixture set.
assert env DEPOT_CANARY_SOURCE_ONLY=1 bash -c '
  runner="$1"; scratch="$2"; set --; source "$runner"
  unit="$(work_unit_json canary-builder-fast-owned-edit)"
  mkdir -p "$scratch/.depot-canary/config"
  printf '\''{"schemaVersion":1,"enabled":true}\n'\'' > "$scratch/.depot-canary/config/fixture.json"
  repository_validation builder-fast-owned-edit "$scratch" "$unit"
  : > "$scratch/.depot-canary/extra.json"
  ! repository_validation builder-fast-owned-edit "$scratch" "$unit"
' _ "$RUNNER" "$TMP/builder-files"

# Prompt construction retains bounded context beyond the former hidden 220-line cutoff.
assert env DEPOT_CANARY_SOURCE_ONLY=1 bash -c '
  runner="$1"; scratch="$2"; set --; source "$runner"
  mkdir -p "$scratch/worktree"
  for line in $(seq 1 250); do printf "context-line-%s\n" "$line"; done > "$scratch/worktree/long.txt"
  unit="$(work_unit_json canary-research-claim-map | jq '\''.contextPaths=["long.txt"]'\'')"
  BASE_REVISION=50946ef1dad6aa879a0b4feb701222102d9e4229
  build_prompt "$unit" "$scratch/worktree" "$scratch/prompt.txt"
  grep -Fx "context-line-250" "$scratch/prompt.txt" >/dev/null
' _ "$RUNNER" "$TMP/full-context"

printf 'production canary: %d assertions passed (offline; no provider contact)\n' "$pass"
