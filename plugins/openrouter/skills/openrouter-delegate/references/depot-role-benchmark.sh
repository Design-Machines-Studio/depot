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
  local input="$1" destination="$2" parsed="$3" passed
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
      add_assertion "$destination" pipeline.identity-role-effort semantic "$passed" 25 'declared id, role, and effort' 'Use the exact disclosed mapping.'
      passed=false; jq -e '.chunks[0].executorCapabilities == ["read-repository","write-repository","structured-output"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.capabilities semantic "$passed" 25 'declared ordered capabilities' 'Use the exact disclosed capability array.'
      passed=false; jq -e '.chunks[0] | has("executor") | not' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.legacy-field-removed semantic "$passed" 15 'executor is absent' 'Remove the legacy executor field.'
      passed=false; jq -e '.chunks[0].legacyExecutorTranslation | .occurred == true and .sourceField == "executor"' "$input" >/dev/null && passed=true
      add_assertion "$destination" pipeline.translation-provenance semantic "$passed" 15 'declared translation provenance' 'Record the disclosed legacy translation.'
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
      passed=false; jq -e '.nextChunk == "depot-role-benchmark"' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.next-chunk semantic "$passed" 30 'depot-role-benchmark' 'Choose the demonstrated benchmark chunk.'
      passed=false; jq -e '.executorRole == "builder-fast"' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.executor-role semantic "$passed" 20 'builder-fast' 'Use the declared provider-neutral role.'
      passed=false; jq -e '.executorCapabilities == ["read-repository","write-repository","structured-output"]' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.capabilities semantic "$passed" 20 'declared ordered capabilities' 'Use the exact capability array.'
      passed=false; jq -e '.rejectedComplexity | type == "array" and length > 0' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.rejected-complexity semantic "$passed" 15 'non-empty rejectedComplexity' 'Name rejected scope.'
      passed=false; ! jq -e '.nextChunk | test("issue[ #]*86|floor|daemon|broker|database|mcp|workflow-engine"; "i")' "$input" >/dev/null && passed=true
      add_assertion "$destination" assembly.exclusions semantic "$passed" 15 'nextChunk excludes forbidden scope' 'Keep the selected chunk inside the prompt exclusions.'
      ;;
    mechanical-owned-edit)
      passed=false; jq -e '(.targetPath | type) == "string" and (.newContent | type) == "object" and (.verification | type) == "string"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.complete-envelope mandatory "$passed" 0 'all declared fields with the required types' 'Return targetPath, newContent, and verification.'
      passed=false; jq -e '.targetPath == "config/fixture.json"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.target semantic "$passed" 20 'config/fixture.json' 'Use the owned target path.'
      passed=false; jq -e '.newContent == {schemaVersion:1,enabled:true}' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.content semantic "$passed" 50 'the disclosed complete JSON content' 'Change only enabled to true.'
      passed=false; jq -e '.verification == "jq -e '\''.schemaVersion == 1 and .enabled == true'\'' config/fixture.json"' "$input" >/dev/null && passed=true
      add_assertion "$destination" mechanical.verification semantic "$passed" 30 'the disclosed fixed verification' 'Copy the exact verification string.'
      ;;
    *) printf 'benchmark: scorer has no allowlisted case dispatch\n' >&2; exit 2 ;;
  esac
}

run_validator() {
  local input="$1" validator_id="$2" parsed="$3"
  case "$validator_id" in
    none) printf 'true' ;;
    review-finding-order)
      if [ "$parsed" = true ] && jq -e '[.findings[]?.id] == ["AUTH-1","ROUTE-2","DOC-3"]' "$input" >/dev/null; then
        printf 'true'
      else
        printf 'false'
      fi
      ;;
    *) printf 'unknown' ;;
  esac
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
  local assertions_file normalized_file audit_file reasons_file bindings_file
  local transport_status identity_confidence identity_provenance transport endpoint_provider workload
  local mandatory_passed semantic_passed semantic_score validation_passed validator_id contract_passed
  local expected_validation receipt_binding_ok identity_evidence_ok result_parent
  local benchmark_fault=false comparable=false overall_success=false failure_class failure_stage failure_owner model_conclusion
  local prompt_fault=false scorer_fault=false parser_fault=false harness_fault=false binding_fault=false

  work="$(mktemp -d "${TMPDIR:-/tmp}/depot-benchmark-score.XXXXXX")"
  audit_file=""
  case_json="$work/case.json"; normalized_file="$work/normalized.json"; assertions_file="$work/assertions.ndjson"
  expected_file="$work/expected.json"; expected_assertions="$work/expected-assertions.ndjson"
  reasons_file="$work/reasons.ndjson"; bindings_file="$work/bindings.json"
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
