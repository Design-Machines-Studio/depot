#!/usr/bin/env bash
# Manual, one-candidate-at-a-time Depot role benchmark. This is an operator
# measurement surface, not an orchestrator or an automatic model sweep.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CANONICAL_SUITE="$DIR/depot-role-benchmark-suite.json"
CANONICAL_MATRIX="$DIR/model-matrix.json"
CANONICAL_BOUNDARY="$DIR/delegation-boundary.sh"
CANONICAL_POLICY="$DIR/delegation-security-policy.json"
CANONICAL_WRAPPER="$DIR/openrouter-wrapper.sh"
CANONICAL_ROLE_POLICY="$DIR/../../../../model-router/skills/model-router/references/role-policy.json"
COMMAND="${1:-}"
shift || true

SUITE="$CANONICAL_SUITE"
MATRIX="$CANONICAL_MATRIX"
BOUNDARY="$CANONICAL_BOUNDARY"
POLICY="$CANONICAL_POLICY"
WRAPPER="$CANONICAL_WRAPPER"
if [ "$COMMAND" != --run ]; then
  SUITE="${DEPOT_BENCH_SUITE:-$SUITE}"
  MATRIX="${DEPOT_BENCH_MATRIX:-$MATRIX}"
fi

CASE_ID=""
MODEL=""
OUTPUT_FILE=""
RECEIPT_FILE=""
RESULT_FILE=""
RESULT_DIR=""
ROLE_POLICY=""
FAULT_FILE=""
DURATION="0"
BEHAVIOR_REVISION=1
BEHAVIOR_DIGEST="sha256:3ecea8dc49c02a8a8ac2a6e7ede9993fb6609f7520d5438ab8bf0cf9170ba32a"
NORMALIZER_REVISION=1
SCORER_REVISION=1

usage() {
  printf '%s\n' \
    'usage: depot-role-benchmark.sh --list' \
    '       depot-role-benchmark.sh --prepare --case ID --output-file PATH' \
    '       depot-role-benchmark.sh --score --case ID --output-file PATH --receipt-file PATH --result-file PATH [--fault-file PATH] [--duration-seconds N]' \
    '       depot-role-benchmark.sh --offline-run --case ID --model EXACT_SLUG --role-policy PATH --output-file PATH --receipt-file PATH --result-dir PATH' \
    '       depot-role-benchmark.sh --run --case ID --model EXACT_SLUG --role-policy PATH --result-dir PATH'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) CASE_ID="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --output-file) OUTPUT_FILE="${2:-}"; shift 2 ;;
    --receipt-file) RECEIPT_FILE="${2:-}"; shift 2 ;;
    --result-file) RESULT_FILE="${2:-}"; shift 2 ;;
    --result-dir) RESULT_DIR="${2:-}"; shift 2 ;;
    --role-policy) ROLE_POLICY="${2:-}"; shift 2 ;;
    --fault-file) FAULT_FILE="${2:-}"; shift 2 ;;
    --duration-seconds) DURATION="${2:-}"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done

require_regular() {
  [ -f "$1" ] && [ ! -L "$1" ] || { printf 'benchmark: regular file required: %s\n' "$1" >&2; exit 2; }
}
require_json_object() {
  require_regular "$1"
  jq -e 'type == "object"' "$1" >/dev/null 2>&1 || {
    printf 'benchmark: malformed JSON object: %s\n' "$1" >&2
    exit 2
  }
}
sha256_file() { sha256sum "$1" | awk '{print "sha256:" $1}'; }

require_new_result_path() {
  local target input
  target="$(realpath -m -- "$RESULT_FILE")"
  [ -d "$(dirname "$target")" ] || { printf 'benchmark: result parent directory must exist\n' >&2; exit 2; }
  [ ! -e "$RESULT_FILE" ] && [ ! -L "$RESULT_FILE" ] || {
    printf 'benchmark: result file must not already exist: %s\n' "$RESULT_FILE" >&2
    exit 2
  }
  for input in "$SUITE" "$OUTPUT_FILE" "$RECEIPT_FILE" ${FAULT_FILE:+"$FAULT_FILE"}; do
    [ "$target" != "$(realpath -m -- "$input")" ] || {
      printf 'benchmark: result file must be distinct from every input artifact\n' >&2
      exit 2
    }
  done
}

require_json_object "$SUITE"
case_exists() { jq -e --arg id "$CASE_ID" 'any(.cases[]; .id == $id)' "$SUITE" >/dev/null; }
require_case() {
  [ -n "$CASE_ID" ] && case_exists || { printf 'benchmark: unknown or missing case\n' >&2; exit 2; }
}

case_workload() {
  local workload
  workload="$(jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .workload // empty' "$SUITE")"
  if [ -z "$workload" ] && [ "$(jq -r '.schemaVersion' "$SUITE")" = 1 ]; then
    case "$(jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .taskType' "$SUITE")" in
      bounded-edit|structured-transformation) workload=mechanical ;;
      finding-classification|bounded-planning) workload=quality ;;
    esac
  fi
  case "$workload" in
    quality|security|direct|bulk|mechanical) printf '%s' "$workload" ;;
    *) printf 'benchmark: case has missing or invalid workload\n' >&2; exit 2 ;;
  esac
}

# scorer-closure-begin
add_assertion() {
  local destination="$1" id="$2" class="$3" passed="$4" weight="$5" expected="$6" hint="$7"
  jq -n --arg id "$id" --arg class "$class" --argjson passed "$passed" \
    --argjson weight "$weight" --arg expected "$expected" --arg hint "$hint" '
      {id:$id,pass:$passed,class:$class,expected:$expected,
       actual:(if $passed then "matched" else "mismatch" end),repairHint:$hint}
      + (if $class == "semantic" then {weight:$weight} else {} end)' >> "$destination"
}

evaluate_case() {
  local input="$1" destination="$2" parsed="$3" passed id severity
  : > "$destination"
  add_assertion "$destination" strict-json-object mandatory "$STRICT_OK" 0 \
    'one raw JSON object without prose or Markdown' 'Return the object directly as JSON.'
  if [ "$parsed" != true ]; then
    add_assertion "$destination" normalized-json-object mandatory false 0 \
      'one parseable object after the permitted normalization' 'Remove prose, extra fences, arrays, or malformed JSON.'
    return
  fi
  add_assertion "$destination" normalized-json-object mandatory true 0 \
    'one parseable object after the permitted normalization' 'Return one JSON object.'
  case "$CASE_ID" in
    pipeline-legacy-translation)
      passed=false; jq -e '.chunks | type == "array" and length == 1' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.single-chunk-envelope mandatory "$passed" 0 'chunks is an array with one entry' 'Return the translated chunk in the sole chunks entry.'
      passed=false; jq -e '.chunks[0] | .id == "docs-1" and .executorRole == "builder-fast" and .executorEffort == "medium"' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.identity-role-effort semantic "$passed" 20 'disclosed id, role, and effort' 'Derive the values from the sealed policy excerpt.'
      passed=false; jq -e '.chunks[0].executorCapabilities == ["read-repository","write-repository","structured-output"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.capabilities semantic "$passed" 20 'disclosed ordered capabilities' 'Derive the capability array from the sealed policy excerpt.'
      passed=false; jq -e '.chunks[0] | (has("executor") or has("kind")) | not' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.legacy-field-removed semantic "$passed" 20 'executor and kind are absent' 'Remove both legacy fields as disclosed.'
      passed=false; jq -e '.chunks[0].legacyExecutorTranslation | .occurred == true and .sourceField == "executor"' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.translation-provenance semantic "$passed" 20 'disclosed translation provenance' 'Record the disclosed legacy translation.'
      add_assertion "$destination" pipeline.envelope-quality semantic true 20 'valid sole-entry envelope' 'Return exactly one translated chunk.'
      ;;
    review-zero-deferral)
      passed=false; jq -e '.findings | type == "array" and length == 3' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.complete-envelope mandatory "$passed" 0 'three findings' 'Return all three disclosed findings.'
      for pair in AUTH-1:P1 ROUTE-2:P2 DOC-3:P3; do
        id="${pair%%:*}"; severity="${pair##*:}"; passed=false
        jq -e --arg id "$id" --arg severity "$severity" 'any(.findings[]?; .id == $id and .severity == $severity)' "$input" >/dev/null && passed=true
        add_assertion "$destination" "review.$id" semantic "$passed" 25 "$id has severity $severity" 'Use the severity disclosed in the prompt.'
      done
      passed=false; jq -e '.deferred == false and (.findings | length) == 3' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.zero-deferral semantic "$passed" 25 'deferred is false with all findings retained' 'Do not defer a seeded finding.'
      ;;
    assembly-next-chunk)
      passed=false; jq -e '(.nextChunk | type) == "string" and (.executorRole | type) == "string" and (.executorCapabilities | type) == "array" and (.rejectedComplexity | type) == "array"' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.complete-envelope mandatory "$passed" 0 'all declared fields with the required types' 'Return every field named by the prompt.'
      passed=false; jq -e '.nextChunk | test("benchmark|corpus|scor"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.next-chunk semantic "$passed" 25 'benchmark corpus/scorer direction in clear wording' 'Choose the demonstrated benchmark work; no exact label is required.'
      passed=false; jq -e '.executorRole | length > 0 and (test("openrouter|openai|anthropic|claude|codex|model"; "i") | not)' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.executor-role semantic "$passed" 15 'non-empty provider-neutral role wording' 'Do not name a provider or model.'
      passed=false; jq -e '.executorCapabilities | length > 0 and all(.[]; type == "string" and length > 0 and (test("openrouter|openai|anthropic|claude|codex|model"; "i") | not))' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.capabilities semantic "$passed" 15 'non-empty provider-neutral capability wording' 'Describe applicable capabilities without provider identity.'
      passed=false; jq -e '.rejectedComplexity | type == "array" and length > 0' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.rejected-complexity semantic "$passed" 20 'non-empty rejectedComplexity' 'Name rejected unsupported scope.'
      passed=false; ! jq -e '.nextChunk | test("issue[ #]*86|floor|daemon|broker|database|mcp|hosted|workflow[ -]?engine"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.exclusions semantic "$passed" 25 'selected chunk excludes disclosed unsupported machinery' 'Keep the selected chunk inside the prompt exclusions.'
      ;;
    mechanical-owned-edit)
      passed=false; jq -e '(.targetPath | type) == "string" and (.newContent | type) == "object" and (.verification | type) == "string" and (.validationOutcome | type) == "string"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.complete-envelope mandatory "$passed" 0 'all declared fields with the required types' 'Return targetPath, newContent, and verification.'
      passed=false; jq -e '.targetPath == "config/fixture.json"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.target semantic "$passed" 20 'config/fixture.json' 'Use the owned target path.'
      passed=false; jq -e '.newContent == {schemaVersion:1,enabled:true}' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.content semantic "$passed" 40 'the disclosed complete JSON content' 'Change only enabled to true.'
      passed=false; jq -e '.verification == "jq -e '\''.schemaVersion == 1 and .enabled == true'\'' config/fixture.json"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.verification semantic "$passed" 20 'the disclosed fixed verification' 'Copy the exact verification string.'
      passed=false; jq -e '.validationOutcome == "passed"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.validation-outcome semantic "$passed" 20 'passed' 'Report the disclosed validation outcome.'
      ;;
    architect-routing-tradeoff)
      passed=false; jq -e '
        (.decision | type) == "string" and (.rationale | type) == "string"
        and (((.preservedBoundary | type) == "string" and (.preservedBoundary | length) > 0)
          or ((.preservedBoundary | type) == "array" and (.preservedBoundary | length) > 0
            and all(.preservedBoundary[]; type == "string" and length > 0)))
        and (((.rejected | type) == "string" and (.rejected | length) > 0)
          or ((.rejected | type) == "array" and (.rejected | length) > 0
            and all(.rejected[]; type == "string" and length > 0)))
      ' "$input" >/dev/null && passed=true
      add_assertion "$destination" architect.tradeoff-envelope mandatory "$passed" 0 'decision, rationale, preservedBoundary, and rejected' 'Return every contracted field.'
      passed=false; jq -e '.decision | test("preserv|keep|current ownership|policy-owned|deterministic"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" architect.policy-owned-selection semantic "$passed" 25 'preserve deterministic policy-owned selection' 'Keep selection in role policy.'
      passed=false; jq -e '([.preservedBoundary] | flatten | map(select(type == "string"))) as $boundaries | any($boundaries[]; test("pipeline"; "i")) and any($boundaries[]; test("role[ -]?policy|role policy"; "i"))' "$input" >/dev/null && passed=true
      add_assertion "$destination" architect.pipeline-ownership semantic "$passed" 25 'both role-policy and Pipeline ownership' 'Name both disclosed owners.'
      passed=false; jq -e '([.rejected] | flatten | map(select(type == "string"))) as $rejected | any($rejected[]; test("ranker|learned"; "i")) and any($rejected[]; test("database|persistent"; "i"))' "$input" >/dev/null && passed=true
      add_assertion "$destination" architect.rejects-ranker-db semantic "$passed" 25 'reject learned ranking and persistence' 'Reject both unsupported mechanisms.'
      passed=false; jq -e '.rationale | test("no current consumer|already served|unsupported|not require"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" architect.evidence-rationale semantic "$passed" 25 'rationale grounded in current-consumer evidence' 'Use the sealed evidence, not future speculation.'
      ;;
    plan-approved-scope-audit)
      passed=false; jq -e '(.omissions | type) == "array" and (.omissions | length) > 0 and (.scopeCreep | type) == "array" and (.scopeCreep | length) > 0 and (.preservedDecisions | type) == "array" and (.preservedDecisions | length) > 0' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.scope-envelope mandatory "$passed" 0 'three non-empty arrays' 'Return omissions, scopeCreep, and preservedDecisions.'
      passed=false; jq -e '[.omissions[]] | any(.[]; test("negative fixture"; "i")) and any(.[]; test("blind.*receipt|receipt.*digest"; "i"))' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.omissions semantic "$passed" 25 'both disclosed approved-requirement omissions' 'Name negative fixtures and the blinded digest-bound receipt.'
      passed=false; jq -e '[.scopeCreep[]] | any(.[]; test("hosted.*judge|LLM judge"; "i")) and any(.[]; test("routing database|database"; "i"))' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.scope-creep semantic "$passed" 25 'hosted judge and routing database' 'Name both unsupported additions.'
      passed=false; jq -e '[.preservedDecisions[]] | any(.[]; test("18|role-complete"; "i")) and any(.[]; test("named assertion"; "i"))' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.preserved-decisions semantic "$passed" 25 '18-case breadth and named assertions' 'Preserve both valid decisions.'
      passed=false; jq -e '(.omissions | length) == 2 and (.scopeCreep | length) == 2 and (.preservedDecisions | length) == 2' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.no-invented-issues semantic "$passed" 25 'only the disclosed closed issue sets' 'Do not invent other issues.'
      ;;
    plan-contradiction-repair)
      passed=false; jq -e '(.contradiction | type) == "string" and (.correction | type) == "string" and (.preservedDecisions | type) == "array"' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.contradiction-envelope mandatory "$passed" 0 'contradiction, correction, and preservedDecisions' 'Return every contracted field.'
      passed=false; jq -e '.contradiction | test("statement 3|3") and test("statement 1|1")' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.contradiction-found semantic "$passed" 25 'statement 3 contradicts statement 1' 'Identify the disclosed contradiction.'
      passed=false; jq -e '.correction | test("local runner|local"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.local-correction semantic "$passed" 25 'local runner correction' 'Move negative-fixture validation to the local runner.'
      passed=false; jq -e '[.preservedDecisions[]?] | any(.[]; test("statement 2|expected-output|local.*scor"; "i")) and any(.[]; test("statement 4|role-policy|inventory"; "i"))' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.valid-decisions-preserved semantic "$passed" 25 'statements 2 and 4 preserved' 'Preserve both disclosed valid decisions.'
      passed=false; jq -e '.correction | test("no provider call|without.*provider|offline"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" plan.no-provider-call semantic "$passed" 25 'no provider call' 'State the disclosed offline boundary.'
      ;;
    builder-multifile-repair)
      passed=false; jq -e '(.files | type) == "array" and (.files | length) == 2 and (.validation | type) == "object"' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.multifile-envelope mandatory "$passed" 0 'two complete files and validation' 'Return exactly two file artifacts and validation.'
      passed=false; jq -e 'any(.files[]?; .path == "suite.json" and .content == {coveredRoles:["architect","builder"]})' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.suite-artifact semantic "$passed" 25 'complete repaired suite.json' 'Return the disclosed complete suite artifact.'
      passed=false; jq -e 'any(.files[]?; .path == "test.json" and .content == {expectedRoleCount:2,expectedCaseCount:4})' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.test-artifact semantic "$passed" 25 'complete repaired test.json' 'Return the disclosed complete test artifact.'
      passed=false; jq -e '[.files[].path] | sort == ["suite.json","test.json"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.owned-paths semantic "$passed" 25 'only suite.json and test.json' 'Do not modify policy.json or another path.'
      passed=false; jq -e '.validation == {command:"./tools/test-role-fixture.sh",outcome:"passed"}' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.validation-result semantic "$passed" 25 'disclosed command passed' 'Report the fixed deterministic outcome.'
      ;;
    builder-validation-feedback-repair)
      passed=false; jq -e '(.targetPath | type) == "string" and (.correctedContent | type) == "object" and (.changedKeys | type) == "array" and (.validation | type) == "object"' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.feedback-envelope mandatory "$passed" 0 'target, complete content, changed keys, and validation' 'Return every contracted field.'
      passed=false; jq -e '.targetPath == "case.json"' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.feedback-target semantic "$passed" 20 'case.json' 'Use the disclosed target.'
      passed=false; jq -e '.correctedContent == {revision:1,role:"review-deep",workload:"quality",enabled:true}' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.minimal-correction semantic "$passed" 40 'only workload changes to quality' 'Preserve every other sealed value.'
      passed=false; jq -e '.changedKeys == ["workload"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.changed-keys semantic "$passed" 20 'changedKeys is exactly workload' 'Report only the changed key.'
      passed=false; jq -e '.validation == {code:"ok",outcome:"passed"}' "$input" >/dev/null && passed=true
      add_assertion "$destination" builder.feedback-validation semantic "$passed" 20 'code ok and outcome passed' 'Report the fixed feedback result.'
      ;;
    review-false-positive-control)
      passed=false; jq -e '(.retained | type) == "array" and (.retained | length) == 2 and (.rejected | type) == "array" and (.rejected | length) == 2 and (.deferred | type) == "boolean"' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.control-envelope mandatory "$passed" 0 'two retained, two rejected, and deferred' 'Return the closed control set.'
      passed=false; jq -e '[.retained[].id] | sort == ["TP-1","TP-2"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.true-positive-recall semantic "$passed" 25 'both true positives retained' 'Retain TP-1 and TP-2.'
      passed=false; jq -e 'any(.retained[]; .id == "TP-1" and .severity == "P2") and any(.retained[]; .id == "TP-2" and .severity == "P1")' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.severity-control semantic "$passed" 25 'TP-1/P2 and TP-2/P1' 'Use the disclosed severities.'
      passed=false; jq -e '.rejected | sort == ["FP-1","FP-2"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.false-positive-control semantic "$passed" 25 'both false positives rejected' 'Reject FP-1 and FP-2.'
      passed=false; jq -e '.deferred == false' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.control-zero-deferral semantic "$passed" 25 'deferred is false' 'Do not defer the closed set.'
      ;;
    review-cross-file-invariant)
      passed=false; jq -e '(.findings | type) == "array" and (.findings | length) == 1 and (.rejected | type) == "array" and (.deferred | type) == "boolean"' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.invariant-envelope mandatory "$passed" 0 'one finding, rejected control, and deferred' 'Return the closed invariant result.'
      passed=false; jq -e '.findings[0] | .id == "INV-1" and .severity == "P1"' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.invariant-defect semantic "$passed" 25 'INV-1/P1' 'Retain the disclosed invariant defect.'
      passed=false; jq -e '.findings[0].trace | sort == ["inventory-test.sh","role-policy.json","suite.json"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.invariant-trace semantic "$passed" 25 'three-file invariant trace' 'Trace role policy, suite, and inventory test.'
      passed=false; jq -e '.rejected == ["FP-ENUM"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.invariant-fp-control semantic "$passed" 25 'FP-ENUM rejected' 'Keep role policy as the authority.'
      passed=false; jq -e '.deferred == false' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.invariant-zero-deferral semantic "$passed" 25 'deferred is false' 'Do not defer the closed finding.'
      ;;
    review-validation-claims)
      passed=false; jq -e '(.verifiedClaims | type) == "array" and (.rejectedClaims | type) == "array" and (.findings | type) == "array" and (.deferred | type) == "boolean"' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.claim-envelope mandatory "$passed" 0 'verified/rejected claims, findings, and deferred' 'Return every contracted field.'
      passed=false; jq -e '.verifiedClaims == ["C1"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.verified-claim semantic "$passed" 25 'C1 verified only' 'Honor the successful inventory receipt.'
      passed=false; jq -e '.rejectedClaims == ["C2"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.rejected-claim semantic "$passed" 25 'C2 rejected' 'Reject the failed full-suite claim.'
      passed=false; jq -e '.findings == [{id:"VAL-1",severity:"P1"}]' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.validation-finding semantic "$passed" 25 'VAL-1/P1' 'Retain the unknown-validator finding.'
      passed=false; jq -e '.deferred == false' "$input" >/dev/null && passed=true
      add_assertion "$destination" review.claim-zero-deferral semantic "$passed" 25 'deferred is false' 'Do not defer the evidence-backed finding.'
      ;;
    security-auth-boundary)
      passed=false; jq -e '(.findings | type) == "array" and (.findings | length) == 1 and (.rejected | type) == "array" and (.deferred | type) == "boolean"' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.auth-envelope mandatory "$passed" 0 'one finding, rejected control, and deferred' 'Return the closed security result.'
      passed=false; jq -e '.findings[0] | .id == "AUTHZ-1" and .severity == "P1"' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.reachable-authz semantic "$passed" 25 'AUTHZ-1/P1' 'Retain the reachable authorization defect.'
      passed=false; jq -e '.findings[0].boundary == "project membership before delete"' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.authz-boundary semantic "$passed" 25 'project membership before delete' 'Name the disclosed boundary.'
      passed=false; jq -e '.rejected == ["OWASP-1"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.auth-fp-control semantic "$passed" 25 'OWASP-1 rejected' 'Reject generic internet-scale speculation.'
      passed=false; jq -e '.deferred == false' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.auth-zero-deferral semantic "$passed" 25 'deferred is false' 'Do not defer the reachable defect.'
      ;;
    security-release-integrity)
      passed=false; jq -e '(.findings | type) == "array" and (.findings | length) == 1 and (.rejected | type) == "array" and (.deferred | type) == "boolean"' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.release-envelope mandatory "$passed" 0 'one finding, rejected control, and deferred' 'Return the closed security result.'
      passed=false; jq -e '.findings[0] | .id == "REL-1" and .severity == "P1"' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.release-defect semantic "$passed" 25 'REL-1/P1' 'Retain the reachable release-integrity defect.'
      passed=false; jq -e '.findings[0].repairBoundary == "digest from independently authenticated release metadata"' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.release-boundary semantic "$passed" 25 'independently authenticated release metadata' 'Name the disclosed repair boundary.'
      passed=false; jq -e '.rejected == ["SIEM-1"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.release-fp-control semantic "$passed" 25 'SIEM-1 rejected' 'Reject unsupported enterprise monitoring.'
      passed=false; jq -e '.deferred == false' "$input" >/dev/null && passed=true
      add_assertion "$destination" security.release-zero-deferral semantic "$passed" 25 'deferred is false' 'Do not defer the reachable defect.'
      ;;
    research-claim-source-map)
      passed=false; jq -e '(.claims | type) == "array" and (.claims | length) == 3 and (.excludedSources | type) == "array"' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.map-envelope mandatory "$passed" 0 'three claims and excludedSources' 'Return the closed source map.'
      passed=false; jq -e '[.claims[].text] == ["Depot policy has nine roles","Pipeline owns workflow depth and role intent","Install size is roughly 4-50 users"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.claim-accuracy semantic "$passed" 25 'three disclosed claims' 'Preserve the sealed claim text.'
      passed=false; jq -e '[.claims[] | {id,sourceIds}] == [{id:"C1",sourceIds:["S1"]},{id:"C2",sourceIds:["S2"]},{id:"C3",sourceIds:["S3"]}]' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.source-mapping semantic "$passed" 25 'C1/S1, C2/S2, C3/S3' 'Use only each supporting sealed source.'
      passed=false; jq -e 'all(.claims[]; .certainty == "supported")' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.certainty semantic "$passed" 25 'supported for every claim' 'Use the disclosed certainty.'
      passed=false; jq -e '.excludedSources == []' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.sealed-only semantic "$passed" 25 'no outside sources' 'Do not cite outside the sealed pack.'
      ;;
    research-conflicting-evidence)
      passed=false; jq -e '(.conclusion | type) == "string" and (.supportingSourceIds | type) == "array" and (.conflictingSourceIds | type) == "array" and (.certainty | type) == "string" and (.excludedSources | type) == "array"' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.conflict-envelope mandatory "$passed" 0 'all reconciliation fields' 'Return every contracted field.'
      passed=false; jq -e '.conclusion | test("current policy|policy.*current"; "i") and test("nine|9"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.current-conclusion semantic "$passed" 25 'current policy has nine roles' 'Reconcile to the current source.'
      passed=false; jq -e '.supportingSourceIds == ["S1","S3"] and .conflictingSourceIds == ["S2"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.conflict-mapping semantic "$passed" 25 'S1/S3 support and S2 conflict' 'Map the sealed provenance exactly.'
      passed=false; jq -e '.certainty == "high-with-superseded-conflict"' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.uncertainty-label semantic "$passed" 25 'high-with-superseded-conflict' 'Disclose the superseded conflict.'
      passed=false; jq -e '.excludedSources == []' "$input" >/dev/null && passed=true
      add_assertion "$destination" research.conflict-sealed-only semantic "$passed" 25 'no outside sources' 'Use only the sealed pack.'
      ;;
    editorial-member-update)
      passed=false; jq -e '(.audience | type) == "string" and (.copy | type) == "string" and (.preservedFacts | type) == "array" and (.inventedFacts | type) == "array"' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.member-envelope mandatory "$passed" 0 'audience, copy, preservedFacts, and inventedFacts' 'Return every contracted field.'
      passed=false; jq -e '
        def affirmative_price_or_launch:
          test("(approved|confirmed|set|announced|scheduled)[^.!?]{0,20}(price|pricing|launch)|(price|pricing)[^.!?]{0,20}(approved|confirmed|set|announced)|(made|approved|confirmed)[^.!?]{0,20}launch commitment|launch commitment[^.!?]{0,20}(exists|approved|confirmed|made)|scheduled[^.!?]{0,20}public launch"; "i");
        def denies_price:
          test("does not include[^.!?]{0,20}(a )?(price|pricing)|(no|without)[^.!?]{0,12}(approved |confirmed |set |announced )?(price|pricing)|(price|pricing)[^.!?]{0,12}(is|has been)?[^.!?]{0,8}not (approved|confirmed|set|announced)"; "i");
        def denies_launch_commitment:
          test("does not include[^.!?]{0,30}launch commitment|(no|without)[^.!?]{0,20}launch commitment|launch commitment[^.!?]{0,12}(is|has been)?[^.!?]{0,8}not (made|approved|confirmed)"; "i");
        .preservedFacts == ["September 15","12 members","two facilitated sessions","no price or launch commitment"]
        and (.copy | test("September 15") and test("12 members") and test("two facilitated sessions")
          and denies_price
          and denies_launch_commitment
          and (affirmative_price_or_launch | not))
      ' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.member-facts semantic "$passed" 25 'all four disclosed facts' 'Preserve every source fact.'
      passed=false; jq -e '.audience == "Assembly cooperative members"' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.member-audience semantic "$passed" 25 'Assembly cooperative members' 'Use the named audience.'
      passed=false; jq -e '.inventedFacts == []' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.member-no-invention semantic "$passed" 25 'no invented facts' 'Keep inventedFacts empty.'
      passed=false; jq -e '(.copy | [scan("[^[:space:]]+")] | length) as $n | $n >= 45 and $n <= 70 and (.copy | test("revolutionary|seamless|leverage|game-changing"; "i") | not)' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.member-constraints semantic "$passed" 25 '45-70 words and no disclosed forbidden words' 'Meet the visible length and word constraints.'
      ;;
    editorial-release-note)
      passed=false; jq -e '(.headline | type) == "string" and (.summary | type) == "string" and (.bullets | type) == "array" and (.preservedClaims | type) == "array" and (.inventedFacts | type) == "array"' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.release-envelope mandatory "$passed" 0 'headline, summary, bullets, preservedClaims, and inventedFacts' 'Return every contracted field.'
      passed=false; jq -e '
        .preservedClaims == ["18 sealed cases","nine roles with two cases each","offline fixture tests","routing unchanged"]
        and ([.bullets[]? | select(type == "string")] as $bullets
          | any($bullets[]; test("18|eighteen"; "i") and test("nine|9"; "i") and test("two|2"; "i"))
          and any($bullets[]; test("offline"; "i") and test("fixture|test"; "i"))
          and any($bullets[];
            (test("not[^.!?]{0,12}unchanged|no longer[^.!?]{0,12}unchanged|routing[^.!?]{0,30}(now changes|has changed|is changed)|candidate selection[^.!?]{0,30}(now changes|has changed|is changed)"; "i") | not)
            and test("routing[^.!?]{0,40}(unchanged|does not change|is not changed)|does not change[^.!?]{0,40}routing|no[^.!?]{0,20}routing change|without[^.!?]{0,20}changing[^.!?]{0,20}routing"; "i")))
      ' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.release-claims semantic "$passed" 25 'all four disclosed claims' 'Preserve every source claim.'
      passed=false; jq -e '(.headline | [scan("[^[:space:]]+")] | length) as $h | (.summary | [scan("[^[:space:]]+")] | length) as $s | $h >= 4 and $h <= 9 and $s >= 18 and $s <= 35 and (.bullets | length) == 3 and all(.bullets[]; type == "string")' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.release-structure semantic "$passed" 25 'disclosed headline, summary, and three-bullet structure' 'Meet the visible structure constraints.'
      passed=false; jq -e '.inventedFacts == []' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.release-no-invention semantic "$passed" 25 'no invented facts' 'Keep inventedFacts empty.'
      passed=false; jq -e '[.headline,.summary,.bullets[]] | join(" ") | test("best|breakthrough|revolutionary|guaranteed"; "i") | not' "$input" >/dev/null && passed=true
      add_assertion "$destination" editorial.release-tone semantic "$passed" 25 'none of the disclosed hype words' 'Use factual, proportionate language.'
      ;;
    *) printf 'benchmark: scorer has no allowlisted case dispatch\n' >&2; exit 2 ;;
  esac
}

run_validator() {
  local input="$1" validator_id="$2" parsed="$3"
  case "$validator_id" in
    none) printf 'true' ;;
    pipeline-legacy-transform)
      if [ "$parsed" = true ] && jq -e '. == {chunks:[{id:"docs-1",executorRole:"builder-fast",executorCapabilities:["read-repository","write-repository","structured-output"],executorEffort:"medium",legacyExecutorTranslation:{occurred:true,sourceField:"executor"}}]}' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    review-finding-order)
      if [ "$parsed" = true ] && jq -e '[.findings[]?.id] == ["AUTH-1","ROUTE-2","DOC-3"]' "$input" >/dev/null; then
        printf 'true'
      else
        printf 'false'
      fi
      ;;
    architect-bounded-chunk)
      if [ "$parsed" = true ] && jq -e '(.nextChunk | test("benchmark|corpus|scor"; "i")) and (.nextChunk | test("floor|daemon|broker|database|mcp|hosted|workflow[ -]?engine"; "i") | not) and (.rejectedComplexity | length > 0)' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    mechanical-owned-json)
      if [ "$parsed" = true ] && jq -e '. == {targetPath:"config/fixture.json",newContent:{schemaVersion:1,enabled:true},verification:"jq -e '\''.schemaVersion == 1 and .enabled == true'\'' config/fixture.json",validationOutcome:"passed"}' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    architect-routing-boundary)
      if [ "$parsed" = true ] && jq -e '([.preservedBoundary] | flatten | map(select(type == "string"))) as $boundaries | ([.rejected] | flatten | map(select(type == "string"))) as $rejected | (any($boundaries[]; test("pipeline"; "i")) and any($boundaries[]; test("role[ -]?policy|role policy"; "i"))) and (any($rejected[]; test("ranker|learned"; "i")) and any($rejected[]; test("database|persistent"; "i")))' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    plan-approved-scope)
      if [ "$parsed" = true ] && jq -e '(.omissions | length) == 2 and (.scopeCreep | length) == 2 and (.preservedDecisions | length) == 2 and ([.omissions[]] | any(.[]; test("negative fixture"; "i")) and any(.[]; test("blind.*receipt|receipt.*digest"; "i")))' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    plan-contradiction)
      if [ "$parsed" = true ] && jq -e '(.contradiction | test("statement 3|3") and test("statement 1|1")) and (.correction | test("local|offline"; "i")) and (.preservedDecisions | length) == 2' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    builder-multifile-coherence)
      if [ "$parsed" = true ] && jq -e '[.files[].path] | sort == ["suite.json","test.json"]' "$input" >/dev/null && jq -e 'any(.files[]; .path == "suite.json" and (.content.coveredRoles | length) == 2) and any(.files[]; .path == "test.json" and .content.expectedRoleCount == 2 and .content.expectedCaseCount == 4) and .validation.outcome == "passed"' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    builder-validation-repair)
      if [ "$parsed" = true ] && jq -e '.targetPath == "case.json" and .correctedContent == {revision:1,role:"review-deep",workload:"quality",enabled:true} and .changedKeys == ["workload"] and .validation == {code:"ok",outcome:"passed"}' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    review-control-set)
      if [ "$parsed" = true ] && jq -e '([.retained[].id] | sort) == ["TP-1","TP-2"] and (.rejected | sort) == ["FP-1","FP-2"] and .deferred == false' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    review-invariant-set)
      if [ "$parsed" = true ] && jq -e '.findings == [{id:"INV-1",severity:"P1",trace:["role-policy.json","suite.json","inventory-test.sh"]}] and .rejected == ["FP-ENUM"] and .deferred == false' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    review-validation-claims)
      if [ "$parsed" = true ] && jq -e '.verifiedClaims == ["C1"] and .rejectedClaims == ["C2"] and .findings == [{id:"VAL-1",severity:"P1"}] and .deferred == false' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    security-auth-boundary)
      if [ "$parsed" = true ] && jq -e '.findings == [{id:"AUTHZ-1",severity:"P1",boundary:"project membership before delete"}] and .rejected == ["OWASP-1"] and .deferred == false' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    security-release-integrity)
      if [ "$parsed" = true ] && jq -e '.findings == [{id:"REL-1",severity:"P1",repairBoundary:"digest from independently authenticated release metadata"}] and .rejected == ["SIEM-1"] and .deferred == false' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    research-source-map)
      if [ "$parsed" = true ] && jq -e '[.claims[] | {id,sourceIds}] == [{id:"C1",sourceIds:["S1"]},{id:"C2",sourceIds:["S2"]},{id:"C3",sourceIds:["S3"]}] and .excludedSources == []' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    research-conflict)
      if [ "$parsed" = true ] && jq -e '(.conclusion | test("nine|9"; "i")) and .supportingSourceIds == ["S1","S3"] and .conflictingSourceIds == ["S2"] and .certainty == "high-with-superseded-conflict" and .excludedSources == []' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    editorial-member-facts)
      if [ "$parsed" = true ] && jq -e '
        def negative_cue: "(no|not|without|does not|is not|has no|there is no|does not include)";
        .audience == "Assembly cooperative members"
        and .preservedFacts == ["September 15","12 members","two facilitated sessions","no price or launch commitment"]
        and .inventedFacts == []
        and ((.copy | [scan("[^[:space:]]+")] | length) as $n | $n >= 45 and $n <= 70)
        and (.copy | test("September 15") and test("12 members") and test("two facilitated sessions")
          and test(negative_cue + "[^.!?]{0,60}price"; "i")
          and test(negative_cue + "[^.!?]{0,60}launch[^.!?]{0,20}commitment"; "i")
          and (test("revolutionary|seamless|leverage|game-changing"; "i") | not))
      ' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    editorial-release-structure)
      if [ "$parsed" = true ] && jq -e '
        .preservedClaims == ["18 sealed cases","nine roles with two cases each","offline fixture tests","routing unchanged"]
        and .inventedFacts == []
        and ((.headline | [scan("[^[:space:]]+")] | length) as $h | $h >= 4 and $h <= 9)
        and ((.summary | [scan("[^[:space:]]+")] | length) as $s | $s >= 18 and $s <= 35)
        and (.bullets | length) == 3 and all(.bullets[]; type == "string")
        and ([.bullets[]] as $bullets
          | any($bullets[]; test("18|eighteen"; "i") and test("nine|9"; "i") and test("two|2"; "i"))
          and any($bullets[]; test("offline"; "i") and test("fixture|test"; "i"))
          and any($bullets[];
            test("routing[^.!?]{0,40}(unchanged|does not change|is not changed)|does not change[^.!?]{0,40}routing|no[^.!?]{0,20}routing change|without[^.!?]{0,20}changing[^.!?]{0,20}routing"; "i")))
        and ([.headline,.summary,.bullets[]] | join(" ") | test("best|breakthrough|revolutionary|guaranteed"; "i") | not)
      ' "$input" >/dev/null; then printf 'true'; else printf 'false'; fi
      ;;
    *) printf 'unknown' ;;
  esac
}

evaluate_human_rubric() {
  local case_file="$1" normalized_file="$2" destination="$3" attempt_dir receipt_file artifact_digest
  if ! jq -e '.humanRubricRequired == true' "$case_file" >/dev/null; then
    jq -n '{required:false,status:"not-applicable",reason:null,humanQuality:null}' > "$destination"
    return
  fi
  attempt_dir="$(dirname "$(realpath -m -- "$RESULT_FILE")")"
  receipt_file="$attempt_dir/human-rubric.json"
  if [ ! -e "$receipt_file" ] && [ ! -L "$receipt_file" ]; then
    jq -n '{required:true,status:"absent",reason:"human-rubric.json is absent",humanQuality:null}' > "$destination"
    return
  fi
  if [ ! -f "$receipt_file" ] || [ -L "$receipt_file" ] || ! jq -e 'type == "object"' "$receipt_file" >/dev/null 2>&1; then
    jq -n '{required:true,status:"rejected",reason:"malformed human rubric receipt",humanQuality:null}' > "$destination"
    return
  fi
  artifact_digest="$(sha256_file "$normalized_file")"
  jq -n --slurpfile receipt "$receipt_file" --slurpfile case "$case_file" \
    --arg suiteId "$(jq -r '.suiteId' "$SUITE")" --arg caseId "$CASE_ID" \
    --arg artifactDigest "$artifact_digest" '
      ($receipt[0]) as $r | ($case[0]) as $c
      | ($c.humanRubric.criteria | map(.id) | sort) as $criterionIds
      | ($r.criterionScores | if type == "object" then keys | sort else [] end) as $scoreIds
      | if ($r | keys | sort) != (["blindToCandidate","caseId","caseRevision","criterionScores","observedAt","outputArtifactSha256","rubricRevision","schemaVersion","suiteId"] | sort) then
          {required:true,status:"rejected",reason:"malformed or identity-bearing human rubric fields",humanQuality:null}
        elif $r.blindToCandidate != true then
          {required:true,status:"rejected",reason:"human rubric is not blinded",humanQuality:null}
        elif $r.schemaVersion != 1 or ($r.observedAt | type) != "string"
          or ($r.observedAt | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$") | not) then
          {required:true,status:"rejected",reason:"malformed human rubric receipt",humanQuality:null}
        elif $r.suiteId != $suiteId or $r.caseId != $caseId or $r.caseRevision != $c.revision
          or $r.rubricRevision != $c.humanRubric.rubricRevision then
          {required:true,status:"rejected",reason:"human rubric case or rubric mismatch",humanQuality:null}
        elif $r.outputArtifactSha256 != $artifactDigest then
          {required:true,status:"rejected",reason:"human rubric output digest mismatch",humanQuality:null}
        elif $scoreIds != $criterionIds
          or ([$r.criterionScores[]] | all(.[]; (type == "number") and . >= 1 and . <= 5) | not) then
          {required:true,status:"rejected",reason:"unknown criterion IDs or invalid criterion scores",humanQuality:null}
        else
          {required:true,status:"accepted",reason:null,
           humanQuality:{rubricRevision:$r.rubricRevision,criterionScores:$r.criterionScores,
             meanScore:([$r.criterionScores[]] | add / length)}}
        end
    ' > "$destination"
}

aggregate_assertions() {
  local assertions_file="$1"
  contract_passed=false; mandatory_passed=false; semantic_passed=false; semantic_score=0
  [ "$STRICT_OK" = true ] && [ "$NORMALIZED_OK" = true ] && contract_passed=true
  if [ "$NORMALIZED_OK" = true ] && ! jq -s -e '
    any(.[]; .class == "mandatory"
      and (.id != "strict-json-object" and .id != "normalized-json-object")
      and .pass == false)
  ' "$assertions_file" >/dev/null; then mandatory_passed=true; fi
  if jq -s -e '[.[] | select(.class == "semantic")] as $semantic
    | ($semantic | length) > 0 and all($semantic[]; .pass)' "$assertions_file" >/dev/null; then
    semantic_passed=true
  fi
  semantic_score="$(jq -s '[.[] | select(.class == "semantic" and .pass) | .weight] | add // 0' "$assertions_file")"
}

classify_failure() {
  : > "$reasons_file"
  if [ "$prompt_fault" = true ]; then
    failure_class=benchmark-prompt-contract-fault; failure_stage=prompt/contract; failure_owner=benchmark; model_conclusion=null
    jq -n '"prompt or schema does not disclose every scored assertion"' >> "$reasons_file"
  elif [ "$scorer_fault" = true ]; then
    failure_class=benchmark-scorer-fault; failure_stage=scorer; failure_owner=benchmark; model_conclusion=null
    jq -n '"scorer or validator contradicts the declared case"' >> "$reasons_file"
  elif [ "$parser_fault" = true ]; then
    failure_class=benchmark-parser-normalizer-fault; failure_stage=parser/normalizer; failure_owner=benchmark; model_conclusion=null
    jq -n '"normalizer rejected an input accepted by its code-owned fixture contract"' >> "$reasons_file"
  elif [ "$harness_fault" = true ] || [ "$binding_fault" = true ]; then
    failure_class=benchmark-harness-fault; failure_stage=harness; failure_owner=benchmark; model_conclusion=null
    if [ "$harness_fault" = true ]; then
      jq -n '"receipt evidence is absent or does not match the declared case"' >> "$reasons_file"
    fi
    if [ "$binding_fault" = true ]; then
      jq -n '"suite, case, prompt, scorer, or normalizer binding mismatch"' >> "$reasons_file"
    fi
  elif [ "$transport_status" != success ]; then
    failure_class=transport-failure; failure_stage=transport; failure_owner=operational; model_conclusion=null
    jq -n '"provider or CLI transport did not complete successfully"' >> "$reasons_file"
  elif [ "$identity_confidence" != confirmed ]; then
    failure_class=unknown-served-identity; failure_stage=identity; failure_owner=operational; model_conclusion=null
    jq -n '"served identity, endpoint provider, or fallback provenance is not confirmed by the receipt"' >> "$reasons_file"
  elif [ "$contract_passed" != true ]; then
    failure_class=visible-output-contract-violation; failure_stage=format/contract; failure_owner=model; model_conclusion=contract-failure
    jq -n '"visible output violated the disclosed strict JSON object contract"' >> "$reasons_file"
  elif [ "$mandatory_passed" != true ]; then
    failure_class=mandatory-assertion-failure; failure_stage=mandatory; failure_owner=model; model_conclusion=mandatory-failure
    jq -n '"one or more disclosed mandatory assertions failed"' >> "$reasons_file"
  elif [ "$semantic_passed" != true ]; then
    failure_class=semantic-assertion-failure; failure_stage=semantic; failure_owner=model; model_conclusion=semantic-failure
    jq -n '"one or more disclosed semantic assertions failed"' >> "$reasons_file"
  elif [ "$validation_passed" != true ]; then
    failure_class=deterministic-validation-failure; failure_stage=validation; failure_owner=model; model_conclusion=validation-failure
    jq -n '"code-owned deterministic validation failed"' >> "$reasons_file"
  else
    failure_class=none; failure_stage=none; failure_owner=none; model_conclusion=success
  fi
}

determine_comparability() {
  benchmark_fault=false; comparable=false; overall_success=false
  if [ "$prompt_fault" = true ] || [ "$scorer_fault" = true ] || [ "$parser_fault" = true ] \
    || [ "$harness_fault" = true ] || [ "$binding_fault" = true ]; then benchmark_fault=true; fi
  if [ "$benchmark_fault" = false ] && [ "$transport_status" = success ] \
    && [ "$identity_confidence" = confirmed ]; then comparable=true; fi
  if [ "$comparable" = true ] && [ "$contract_passed" = true ] && [ "$mandatory_passed" = true ] \
    && [ "$semantic_passed" = true ] && [ "$validation_passed" = true ]; then overall_success=true; fi
}
# scorer-closure-end

normalize_output() {
  local raw_file="$1" normalized_file="$2"
  STRICT_OK=false
  NORMALIZED_OK=false
  NORMALIZATION="none"
  if jq -s -e 'if length == 1 and (.[0] | type) == "object" then .[0] else empty end' \
    "$raw_file" > "$normalized_file" 2>/dev/null && [ -s "$normalized_file" ]; then
    STRICT_OK=true; NORMALIZED_OK=true; NORMALIZATION="strict-raw-object"
    return
  fi
  if jq -Rsr '
    capture("\\A[ \\t]*```(?:json|JSON)?[ \\t]*\\r?\\n(?<inner>(?s:.*))\\r?\\n```[ \\t]*(?:\\r?\\n)?\\z").inner
    | fromjson | select(type == "object")
  ' "$raw_file" > "$normalized_file" 2>/dev/null && [ -s "$normalized_file" ]; then
    NORMALIZED_OK=true; NORMALIZATION="whole-response-markdown-json-fence"
  else
    : > "$normalized_file"
  fi
}

score_case() {
  local work case_json suite_id suite_revision suite_digest case_revision case_digest
  local prompt_revision prompt_digest scorer_digest normalizer_digest expected_file expected_assertions
  local assertions_file normalized_file audit_file reasons_file bindings_file human_evidence_file
  local transport_status identity_confidence identity_provenance transport endpoint_provider workload
  local mandatory_passed semantic_passed semantic_score validation_passed validator_id contract_passed
  local expected_validation receipt_binding_ok identity_evidence_ok result_parent
  local benchmark_fault=false comparable=false overall_success=false failure_class failure_stage failure_owner model_conclusion
  local prompt_fault=false scorer_fault=false parser_fault=false harness_fault=false binding_fault=false

  work="$(mktemp -d "${TMPDIR:-/tmp}/depot-benchmark-score.XXXXXX")"
  audit_file=""
  case_json="$work/case.json"; normalized_file="$work/normalized.json"; assertions_file="$work/assertions.ndjson"
  expected_file="$work/expected.json"; expected_assertions="$work/expected-assertions.ndjson"
  reasons_file="$work/reasons.ndjson"; bindings_file="$work/bindings.json"; human_evidence_file="$work/human-evidence.json"
  trap 'rm -rf "$work"; [ -z "${audit_file:-}" ] || rm -f "$audit_file"' RETURN
  jq --arg id "$CASE_ID" '.cases[] | select(.id == $id)' "$SUITE" > "$case_json"
  workload="$(case_workload)"
  normalize_output "$OUTPUT_FILE" "$normalized_file"
  evaluate_case "$normalized_file" "$assertions_file" "$NORMALIZED_OK"

  suite_id="$(jq -r 'if .schemaVersion == 1 then "depot-role-v2" else .suiteId end' "$SUITE")"
  suite_revision="$(jq -r '.suiteRevision // 1' "$SUITE")"
  case_revision="$(jq -r '.revision // 1' "$case_json")"; prompt_revision="$(jq -r '.promptRevision // 1' "$case_json")"
  jq -cS 'del(.bindings)' "$SUITE" > "$work/suite-content.json"; suite_digest="$(sha256_file "$work/suite-content.json")"
  jq -cS 'del(.bindings)' "$case_json" > "$work/case-content.json"; case_digest="$(sha256_file "$work/case-content.json")"
  jq -j '.prompt' "$case_json" > "$work/prompt-content"
  prompt_digest="$(sha256_file "$work/prompt-content")"
  awk '/^# scorer-closure-begin$/{emit=1} /^# scorer-closure-end$/{print; emit=0} emit' \
    "${BASH_SOURCE[0]}" > "$work/scorer-content"
  jq -cS '{id,expected,assertionIds,assertions,validatorId:(.validatorId // "none")}' \
    "$case_json" >> "$work/scorer-content"
  scorer_digest="$(sha256_file "$work/scorer-content")"
  awk '/^normalize_output\(\) \{/{emit=1} /^score_case\(\) \{/{emit=0} emit' \
    "${BASH_SOURCE[0]}" > "$work/normalizer-content"
  normalizer_digest="$(sha256_file "$work/normalizer-content")"
  jq -n --slurpfile suite "$SUITE" --slurpfile case "$case_json" \
    --arg suiteDigest "$suite_digest" --arg caseDigest "$case_digest" --arg promptDigest "$prompt_digest" \
    --arg scorerDigest "$scorer_digest" --arg normalizerDigest "$normalizer_digest" \
    --argjson suiteRevision "$suite_revision" --argjson caseRevision "$case_revision" --argjson promptRevision "$prompt_revision" \
    --argjson scorerRevision "$SCORER_REVISION" --argjson normalizerRevision "$NORMALIZER_REVISION" '
      def check($declared; $actual): {declared:($declared // $actual),actual:$actual,match:(($declared // $actual) == $actual)};
      {suiteRevision:check($suite[0].bindings.suiteRevision;$suiteRevision),
       suiteDigest:check($suite[0].bindings.suiteDigest;$suiteDigest),
       caseRevision:check($case[0].bindings.caseRevision;$caseRevision),
       caseDigest:check($case[0].bindings.caseDigest;$caseDigest),
       promptRevision:check($case[0].bindings.promptRevision;$promptRevision),
       promptDigest:check($case[0].bindings.promptDigest;$promptDigest),
       scorerRevision:check($case[0].bindings.scorerRevision;$scorerRevision),
       scorerDigest:check($case[0].bindings.scorerDigest;$scorerDigest),
       normalizerRevision:check($suite[0].bindings.normalizerRevision;$normalizerRevision),
       normalizerDigest:check($suite[0].bindings.normalizerDigest;$normalizerDigest)}' > "$bindings_file"
  if ! jq -e 'all(.[]; .match)' "$bindings_file" >/dev/null; then binding_fault=true; fi

  jq '.expected' "$case_json" > "$expected_file"
  STRICT_OK=true; evaluate_case "$expected_file" "$expected_assertions" true
  if jq -s -e 'any(.[]; .pass == false)' "$expected_assertions" >/dev/null; then scorer_fault=true; fi
  STRICT_OK="$(jq -sr 'first(.[] | select(.id == "strict-json-object") | .pass)' "$assertions_file")"

  if jq -e 'has("assertionIds") or has("assertions")' "$case_json" >/dev/null; then
    if ! jq -s -e --slurpfile case "$case_json" '
      [.[].id] | sort as $actual
      | [($case[0].assertionIds // $case[0].assertions)[]
          | if type == "string" then . else .id end] | sort as $declared
      | $actual == $declared
    ' "$assertions_file" >/dev/null; then scorer_fault=true; fi
  fi

  if jq -e 'has("disclosedAssertions")' "$case_json" >/dev/null; then
    if ! jq -s -e --slurpfile case "$case_json" '
      [.[].id] as $ids | all($ids[]; . as $id | $case[0].disclosedAssertions | index($id) != null)
    ' "$assertions_file" >/dev/null; then prompt_fault=true; fi
  fi
  if jq -e '.formatRequirementDisclosed == false' "$case_json" >/dev/null; then prompt_fault=true; fi

  validator_id="$(jq -r '.validatorId // "none"' "$case_json")"
  validation_passed="$(run_validator "$normalized_file" "$validator_id" "$NORMALIZED_OK")"
  expected_validation="$(run_validator "$expected_file" "$validator_id" true)"
  if [ "$validation_passed" = unknown ]; then scorer_fault=true; validation_passed=false; fi
  if [ "$expected_validation" != true ]; then scorer_fault=true; fi
  evaluate_human_rubric "$case_json" "$normalized_file" "$human_evidence_file"

  if [ -n "$FAULT_FILE" ]; then
    require_json_object "$FAULT_FILE"
    if jq -e '.schemaVersion == 1 and .code == "normalizer-fixture-rejection" and .fixtureId == "whole-response-json-fence" and .expectedAccepted == true and .observedAccepted == false' "$FAULT_FILE" >/dev/null; then
      parser_fault=true
    else
      printf 'benchmark: invalid parser fault attestation\n' >&2; exit 2
    fi
  fi

  receipt_binding_ok=false
  if jq -e --arg suite "$suite_id" --arg caseId "$CASE_ID" \
    --arg role "$(jq -r '.role' "$case_json")" --arg workload "$workload" '
      (.benchmark | type) == "object"
      and .benchmark.suiteId == $suite and .benchmark.caseId == $caseId
      and .benchmark.role == $role and .benchmark.workload == $workload
    ' "$RECEIPT_FILE" >/dev/null; then receipt_binding_ok=true; else harness_fault=true; fi

  transport_status="$(jq -r 'if .outcome == "success" then "success" else "failed" end' "$RECEIPT_FILE")"
  transport=openrouter
  endpoint_provider="$(jq -r '.servingProvider // empty' "$RECEIPT_FILE")"
  identity_confidence=unknown
  identity_provenance="$(jq -r '.responseModelProvenance // "not-available"' "$RECEIPT_FILE")"
  identity_evidence_ok=false
  if jq -e '
    def nonempty: type == "string" and length > 0;
    . as $receipt
    | ($receipt.requestedModel | nonempty) and ($receipt.responseModel | nonempty)
    and $receipt.responseModelProvenance == "response"
    and ($receipt.servingProvider | nonempty) and $receipt.servingProviderProvenance == "response"
    and ($receipt.fallbackUsed | type) == "boolean"
    and ($receipt.modelCandidates | type) == "array" and all($receipt.modelCandidates[]; nonempty)
    and ($receipt.attemptedModel | nonempty)
    and ($receipt.attemptedModels | type) == "array" and all($receipt.attemptedModels[]; nonempty)
    and $receipt.attemptProvenance == "response_model"
    and (if $receipt.fallbackUsed then
      ($receipt.modelCandidates | length) > 1
      and $receipt.modelCandidates[0] == $receipt.requestedModel
      and $receipt.attemptedModels == $receipt.modelCandidates
      and $receipt.attemptedModel == $receipt.responseModel
      and ($receipt.modelCandidates | index($receipt.responseModel)) != null
    else
      $receipt.modelCandidates == [$receipt.requestedModel]
      and $receipt.attemptedModels == [$receipt.requestedModel]
      and $receipt.attemptedModel == $receipt.requestedModel
      and $receipt.responseModel == $receipt.requestedModel
    end)
  ' "$RECEIPT_FILE" >/dev/null; then identity_evidence_ok=true; fi
  if [ "$receipt_binding_ok" = true ] && [ "$identity_evidence_ok" = true ]; then identity_confidence=confirmed; fi

  aggregate_assertions "$assertions_file"
  classify_failure
  determine_comparability

  result_parent="$(dirname "$(realpath -m -- "$RESULT_FILE")")"
  audit_file="$(mktemp "$result_parent/.depot-benchmark-result.XXXXXX")"
  jq -n --rawfile raw "$OUTPUT_FILE" --slurpfile normalized "$normalized_file" --slurpfile receipt "$RECEIPT_FILE" \
    --slurpfile assertions "$assertions_file" --slurpfile reasons "$reasons_file" --slurpfile bindings "$bindings_file" \
    --slurpfile human "$human_evidence_file" \
    --arg suiteId "$suite_id" --arg caseId "$CASE_ID" --arg role "$(jq -r '.role' "$case_json")" \
    --arg observedAt "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg rawDigest "$(sha256_file "$OUTPUT_FILE")" \
    --arg normalization "$NORMALIZATION" --arg transport "$transport" --arg endpointProvider "$endpoint_provider" \
    --arg transportStatus "$transport_status" --arg identityConfidence "$identity_confidence" --arg identityProvenance "$identity_provenance" \
    --arg workload "$workload" --arg failureClass "$failure_class" --arg failureStage "$failure_stage" --arg failureOwner "$failure_owner" \
    --arg modelConclusion "$model_conclusion" --arg validatorId "$validator_id" --arg behaviorDigest "$BEHAVIOR_DIGEST" \
    --argjson behaviorRevision "$BEHAVIOR_REVISION" --argjson duration "$DURATION" --argjson strict "$STRICT_OK" \
    --argjson normalizedOk "$NORMALIZED_OK" --argjson contract "$contract_passed" --argjson mandatory "$mandatory_passed" \
    --argjson semantic "$semantic_passed" --argjson score "$semantic_score" --argjson validation "$validation_passed" \
    --argjson benchmarkFault "$benchmark_fault" --argjson comparable "$comparable" --argjson overall "$overall_success" '
      {schemaVersion:2,suiteId:$suiteId,caseId:$caseId,role:$role,observedAt:$observedAt,
       behavioralContract:{revision:$behaviorRevision,digest:$behaviorDigest},evidenceBindings:$bindings[0],
       rawOutput:$raw,rawOutputDigest:$rawDigest,
       normalizedOutput:(if $normalizedOk then $normalized[0] else null end),
       transport:$transport,endpointProvider:(if $endpointProvider == "" then null else $endpointProvider end),
       transportOutcome:{status:$transportStatus,failureKind:($receipt[0].failureKind // null),httpStatus:($receipt[0].httpStatus // null)},
       identityStatus:{confidence:$identityConfidence,provenance:$identityProvenance,
         receiptBinding:($receipt[0].benchmark // null)},
       requestedIdentity:($receipt[0].requestedModel // null),servedIdentity:($receipt[0].responseModel // null),
       fallback:{used:(if $receipt[0] | has("fallbackUsed") then $receipt[0].fallbackUsed else null end),
         attemptedIdentity:($receipt[0].attemptedModel // null),attemptedIdentities:($receipt[0].attemptedModels // null),
         provenance:($receipt[0].attemptProvenance // null)},
       workload:$workload,durationSeconds:$duration,usage:($receipt[0].usage // null),
       strictParse:{passed:$strict},normalizedParse:{passed:$normalizedOk,normalization:$normalization},
       contractPassed:$contract,mandatoryPassed:$mandatory,semanticPassed:$semantic,semanticScore:$score,
       validationPassed:$validation,validatorId:$validatorId,assertions:$assertions,
       humanRubricEvidence:($human[0] | del(.humanQuality)),humanQuality:$human[0].humanQuality,
       failureClass:$failureClass,failureStage:$failureStage,failureOwner:$failureOwner,
       failureReasons:$reasons,benchmarkFault:$benchmarkFault,comparable:$comparable,
       modelConclusion:(if $modelConclusion == "null" then null else $modelConclusion end),overallSuccess:$overall,
       qualityScore:$score,parsed:$normalizedOk,
       requestedModel:($receipt[0].requestedModel // null),servedModel:($receipt[0].responseModel // null),
       provider:($receipt[0].servingProvider // null),fallbackUsed:(if $receipt[0] | has("fallbackUsed") then $receipt[0].fallbackUsed else null end)}' > "$audit_file"
  ln "$audit_file" "$RESULT_FILE" || { printf 'benchmark: result file appeared before publication\n' >&2; return 2; }
  rm -f "$audit_file"
  audit_file=""
}

validate_run_inputs() {
  local role capabilities
  require_json_object "$ROLE_POLICY"; require_json_object "$MATRIX"
  workload="$(case_workload)"
  role="$(jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .role' "$SUITE")"
  capabilities="$(jq -c --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .requiredCapabilities // []' "$SUITE")"
  jq -e --arg model "$MODEL" 'any(.models[]; .slug == $model and .catalog_status == "available")' "$MATRIX" >/dev/null || {
    printf 'benchmark: exact available matrix model required\n' >&2; exit 2
  }
  jq -e --arg role "$role" --arg model "$MODEL" --argjson needed "$capabilities" '
    any(.roles[$role][]?; . as $candidate
      | .model == $model and .transport == "openrouter"
        and all($needed[]; . as $cap | $candidate.capabilities | index($cap) != null))
  ' "$ROLE_POLICY" >/dev/null || {
    printf 'benchmark: model is not eligible for the case role and capabilities\n' >&2; exit 2
  }
}

prepare_result_dir() {
  if [ -e "$RESULT_DIR" ]; then
    [ -d "$RESULT_DIR" ] && [ ! -L "$RESULT_DIR" ] || {
      printf 'benchmark: result directory must be a real directory\n' >&2; exit 2
    }
    [ -z "$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ] || {
      printf 'benchmark: result directory must be empty\n' >&2; exit 2
    }
  else
    mkdir -p "$RESULT_DIR"
  fi
  chmod 700 "$RESULT_DIR"
}

bind_receipt_to_case() {
  local bound suite_id role workload
  suite_id="$(jq -r 'if .schemaVersion == 1 then "depot-role-v2" else .suiteId end' "$SUITE")"
  role="$(jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .role' "$SUITE")"
  workload="$(case_workload)"
  bound="${RECEIPT_FILE}.bound.$$"
  jq --arg suite "$suite_id" --arg caseId "$CASE_ID" --arg role "$role" --arg workload "$workload" \
    '.benchmark = {suiteId:$suite,caseId:$caseId,role:$role,workload:$workload}' \
    "$RECEIPT_FILE" > "$bound"
  mv "$bound" "$RECEIPT_FILE"
}

reject_live_overrides() {
  local variable
  for variable in DEPOT_BENCH_SUITE DEPOT_BENCH_MATRIX DEPOT_BENCH_BOUNDARY \
    DEPOT_BENCH_SECURITY_POLICY DEPOT_BENCH_WRAPPER; do
    if [ -n "${!variable+x}" ]; then
      printf 'benchmark: --run rejects asset override %s\n' "$variable" >&2
      exit 2
    fi
  done
  [ "$(realpath -- "$ROLE_POLICY")" = "$(realpath -- "$CANONICAL_ROLE_POLICY")" ] || {
    printf 'benchmark: --run requires the checked-in role policy\n' >&2
    exit 2
  }
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
    require_regular "$OUTPUT_FILE"; require_json_object "$RECEIPT_FILE"
    [ -z "$FAULT_FILE" ] || require_json_object "$FAULT_FILE"
    require_new_result_path
    score_case
    ;;
  --offline-run)
    require_case
    [ -n "$MODEL" ] && [ -n "$ROLE_POLICY" ] && [ -n "$OUTPUT_FILE" ] \
      && [ -n "$RECEIPT_FILE" ] && [ -n "$RESULT_DIR" ] || { usage >&2; exit 2; }
    require_regular "$OUTPUT_FILE"; require_json_object "$RECEIPT_FILE"
    validate_run_inputs
    prepare_result_dir
    source_output="$OUTPUT_FILE"; source_receipt="$RECEIPT_FILE"
    prompt="$RESULT_DIR/prompt.txt"; system="$RESULT_DIR/system.txt"; output="$RESULT_DIR/output.json"
    receipt="$RESULT_DIR/receipt.json"; result="$RESULT_DIR/result.json"
    jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .prompt' "$SUITE" > "$prompt"
    printf '%s\n' 'You are completing one bounded Depot benchmark. Return JSON only. You have no command authority.' > "$system"
    cp "$source_output" "$output"; cp "$source_receipt" "$receipt"
    OUTPUT_FILE="$output"; RECEIPT_FILE="$receipt"; RESULT_FILE="$result"
    bind_receipt_to_case
    require_new_result_path
    score_case
    cat "$result"
    ;;
  --run)
    require_case
    [ -n "$MODEL" ] && [ -n "$ROLE_POLICY" ] && [ -n "$RESULT_DIR" ] || { usage >&2; exit 2; }
    require_json_object "$ROLE_POLICY"
    reject_live_overrides
    validate_run_inputs
    prepare_result_dir
    workload="$(case_workload)"
    prompt="$RESULT_DIR/prompt.txt"; system="$RESULT_DIR/system.txt"; output="$RESULT_DIR/output.json"
    receipt="$RESULT_DIR/receipt.json"; result="$RESULT_DIR/result.json"
    jq -r --arg id "$CASE_ID" '.cases[] | select(.id == $id) | .prompt' "$SUITE" > "$prompt"
    printf '%s\n' 'You are completing one bounded Depot benchmark. Return JSON only. You have no command authority.' > "$system"
    "$BOUNDARY" --mode artifact-delegation --policy "$POLICY" --content-file "$system" --content-file "$prompt" >/dev/null
    start="$(date +%s)"
    set +e
    env -u OPENROUTER_SYSTEM OPENROUTER_SYSTEM_FILE="$system" OPENROUTER_WORKLOAD="$workload" \
      OPENROUTER_RECEIPT_FILE="$receipt" "$WRAPPER" "$MODEL" - 3600 < "$prompt" > "$output"
    wrapper_status=$?
    set -e
    if [ ! -f "$receipt" ]; then
      jq -n --argjson status "$wrapper_status" \
        '{schemaVersion:2,outcome:"error",failureKind:"wrapper-exit-without-receipt",
          failureReason:("wrapper exit " + ($status | tostring)),requestedModel:null,
          responseModel:null,servingProvider:null,fallbackUsed:null}' > "$receipt"
    fi
    end="$(date +%s)"; DURATION="$((end-start))"; OUTPUT_FILE="$output"; RECEIPT_FILE="$receipt"; RESULT_FILE="$result"
    require_json_object "$RECEIPT_FILE"
    bind_receipt_to_case
    require_new_result_path
    score_case
    cat "$result"
    [ "$wrapper_status" -eq 0 ] || exit "$wrapper_status"
    ;;
  *) usage >&2; exit 2 ;;
esac
