#!/usr/bin/env bash
# Run or validate one bounded Depot production-canary attempt. The runner owns
# exactly one disposable worktree and never changes the invoking checkout.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "$DIR" rev-parse --show-toplevel)"
SCHEMA="$DIR/depot-role-production-canary-schema.json"
WORK_UNITS="$DIR/depot-role-production-canary-work-units.json"
SUITE="$DIR/depot-role-benchmark-suite.json"
MATRIX="$DIR/model-matrix.json"
BENCH="$DIR/depot-role-benchmark.sh"
WRAPPER="$DIR/openrouter-wrapper.sh"
ROLE_POLICY="$DIR/../../../../model-router/skills/model-router/references/role-policy.json"
OPENROUTER_MANIFEST="$DIR/../../../.claude-plugin/plugin.json"
MODEL_ROUTER_MANIFEST="$DIR/../../../../model-router/.claude-plugin/plugin.json"

COMMAND="${1:-}"
shift || true
ATTEMPT_FILE=""
ARTIFACT_ROOT=""
WORK_UNIT_ID=""
TRANSPORT=""
MODEL=""
EFFORT="medium"
BASE_REVISION=""
RESULT_DIR=""
MAX_CORRECTIONS="1"
CANARY_TEMP_ROOT=""
CANARY_WORKTREE=""

usage() {
  printf '%s\n' \
    'usage: depot-role-production-canary.sh --list' \
    '       depot-role-production-canary.sh --validate --attempt-file PATH --artifact-root PATH' \
    '       depot-role-production-canary.sh --run --work-unit ID --transport codex-cli|openrouter --model EXACT_ID --effort low|medium|high|max --base-revision COMMIT --result-dir PATH [--max-corrections 0|1|2]'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --attempt-file) ATTEMPT_FILE="${2:-}"; shift 2 ;;
    --artifact-root) ARTIFACT_ROOT="${2:-}"; shift 2 ;;
    --work-unit) WORK_UNIT_ID="${2:-}"; shift 2 ;;
    --transport) TRANSPORT="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --effort) EFFORT="${2:-}"; shift 2 ;;
    --base-revision) BASE_REVISION="${2:-}"; shift 2 ;;
    --result-dir) RESULT_DIR="${2:-}"; shift 2 ;;
    --max-corrections) MAX_CORRECTIONS="${2:-}"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done

require_regular() {
  [ -f "$1" ] && [ ! -L "$1" ] || {
    printf 'production canary: regular file required: %s\n' "$1" >&2
    exit 2
  }
}

require_json_object() {
  require_regular "$1"
  jq -e 'type == "object"' "$1" >/dev/null 2>&1 || {
    printf 'production canary: JSON object required: %s\n' "$1" >&2
    exit 2
  }
}

sha256_file() { sha256sum "$1" | awk '{print "sha256:" $1}'; }

require_authorities() {
  local authority
  for authority in "$SCHEMA" "$WORK_UNITS" "$SUITE" "$MATRIX" "$ROLE_POLICY" \
    "$OPENROUTER_MANIFEST" "$MODEL_ROUTER_MANIFEST"; do
    require_json_object "$authority"
  done
  [ -x "$BENCH" ] && [ -x "$WRAPPER" ] || {
    printf 'production canary: required benchmark executable unavailable\n' >&2
    exit 2
  }
  jq -e '
    .schemaVersion == 1 and .suiteId == "depot-role-production-canary-v1"
    and .harnessVersion == 1 and (.workUnits | type == "array" and length == 9)
    and (([.workUnits[].role] | unique | sort) == (["architect","builder-deep","builder-fast","editorial","plan-critic","research-fast","review-deep","review-fast","security-review"] | sort))
    and (([.workUnits[].id] | unique | length) == 9)
    and all(.workUnits[];
      (.id | type == "string" and length > 0) and (.revision | type == "number" and . >= 1)
      and (.sealedCaseId | type == "string" and length > 0)
      and (.contextPaths | type == "array" and length > 0)
      and all(.contextPaths[]; type == "string" and startswith("/") | not)
      and (.repositoryValidator | IN("no-owned-edit","builder-fast-owned-edit","builder-deep-multifile"))
      and (.toolCoverage | type == "object") and (.task | type == "string" and length > 0))
  ' "$WORK_UNITS" >/dev/null || {
    printf 'production canary: malformed work-unit authority\n' >&2
    exit 2
  }
}

work_unit_json() {
  jq -c --arg id "$1" '.workUnits[] | select(.id == $id)' "$WORK_UNITS"
}

resolve_alias() {
  local role="$1" requested="$2" transport="$3" served="$4"
  jq -cn --arg role "$role" --arg requested "$requested" --arg transport "$transport" --arg served "$served" \
    --slurpfile policy "$ROLE_POLICY" '
      [$policy[0].roles[$role][]? | select(.model == $requested and .transport == $transport)] as $matches
      | ([$requested] + (($matches[0].servedIdentities // []) | map(select(type == "string")))) | unique as $allowed
      | {candidateKnown:($matches | length == 1),allowed:$allowed,
         status:(if $served == "" then "unknown" elif $served == $requested then "exact"
           elif $transport != "openrouter" and ($allowed | index($served) != null) then "mapped" else "unmapped" end)}
    '
}

record_boundary_fault() {
  local owner="$1" code="$2" detail="${3:-}"
  [ "$boundary_fault" = false ] || return 0
  boundary_fault=true
  fault_owner="$owner"
  fault_code="$code"
  [ -z "$detail" ] || diagnostics="$detail"
}

cleanup_owned_resources() {
  [ -n "$CANARY_TEMP_ROOT" ] || return 0
  case "$CANARY_TEMP_ROOT" in "${TMPDIR:-/tmp}"/depot-production-canary.??????) ;; *) return 1 ;; esac
  [ "$CANARY_WORKTREE" = "$CANARY_TEMP_ROOT/worktree" ] || return 1
  if git -C "$ROOT" worktree list --porcelain | grep -Fx "worktree $CANARY_WORKTREE" >/dev/null 2>&1; then
    git -C "$ROOT" worktree remove --force "$CANARY_WORKTREE" >/dev/null 2>&1 || return 1
  fi
  rm -rf -- "$CANARY_TEMP_ROOT" || return 1
  CANARY_TEMP_ROOT=""
  CANARY_WORKTREE=""
}

cleanup_on_exit() {
  local rc="${1:-1}"
  trap - EXIT INT TERM
  if ! cleanup_owned_resources; then
    printf 'production canary: owned cleanup failure: %s\n' "$CANARY_TEMP_ROOT" >&2
    [ "$rc" -ne 0 ] || rc=1
  fi
  exit "$rc"
}

canonical_work_unit_digest() {
  work_unit_json "$1" | jq -cS . | sha256sum | awk '{print "sha256:" $1}'
}

canonical_fixture_digest() {
  work_unit_json "$1" | jq -cS '.fixture // {}' | sha256sum | awk '{print "sha256:" $1}'
}

canonical_validation_digest() {
  local id="$1" case_id
  case_id="$(work_unit_json "$id" | jq -r '.sealedCaseId')"
  jq -cnS --argjson unit "$(work_unit_json "$id")" \
    --argjson case "$(jq -c --arg id "$case_id" '.cases[] | select(.id == $id)' "$SUITE")" \
    '{repositoryValidator:$unit.repositoryValidator,sealedCaseId:$unit.sealedCaseId,
      mandatoryAssertions:$case.mandatoryAssertions,validatorId:$case.validatorId}' \
    | sha256sum | awk '{print "sha256:" $1}'
}

schema_shape_ok() {
  jq -e '
    def integer: type == "number" and floor == .;
    def nullable_nonnegative: . == null or (type == "number" and . >= 0);
    def timestamp:
      type == "string"
      and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$");
    def nullable_timestamp: . == null or timestamp;
    def coverage:
      type == "object"
      and (keys | sort) == (["applicable","observed","rate","reason","total"] | sort)
      and (.applicable | type == "boolean")
      and (.observed == null or (.observed | integer and . >= 0))
      and (.total == null or (.total | integer and . >= 0))
      and (.rate == null or (.rate | type == "number" and . >= 0 and . <= 1))
      and (.reason == null or (.reason | type == "string" and length <= 240));
    (keys | sort) == (["artifacts","attemptId","bindings","boundaries","cost","evidenceClass","harnessVersion","identity","outcome","quality","repository","schemaVersion","telemetry","timing"] | sort)
    and .schemaVersion == 1 and .evidenceClass == "production-canary" and .harnessVersion == 1
    and (.attemptId | type == "string" and test("^[a-z0-9][a-z0-9._-]{7,95}$"))
    and (.repository | type == "object" and (keys | sort) == (["baseRevision","changedFileCount","cleanBase","headRevision","identity","patchDigest"] | sort))
    and (.repository.identity == "Design-Machines-Studio/depot")
    and (.repository.baseRevision | type == "string" and test("^[0-9a-f]{40}$"))
    and (.repository.headRevision | type == "string" and test("^[0-9a-f]{40}$"))
    and (.repository.cleanBase | type == "boolean")
    and (.repository.patchDigest | type == "string" and test("^sha256:[0-9a-f]{64}$"))
    and (.repository.changedFileCount | integer and . >= 0 and . <= 64)
    and (.bindings | type == "object" and (keys | sort) == (["pluginVersions","rolePolicyDigest","sealedCaseDigest","sealedCaseId","sealedScorerDigest","sealedSuiteId","taskFixtureDigest","validationContractDigest","workUnitDigest","workUnitId","workUnitRevision"] | sort))
    and (.bindings.workUnitId | type == "string" and length > 0)
    and (.bindings.workUnitRevision | integer and . >= 1)
    and all(.bindings.workUnitDigest,.bindings.taskFixtureDigest,.bindings.validationContractDigest,.bindings.sealedCaseDigest,.bindings.sealedScorerDigest,.bindings.rolePolicyDigest; type == "string" and test("^sha256:[0-9a-f]{64}$"))
    and .bindings.sealedSuiteId == "depot-role-v2"
    and (.bindings.sealedCaseId | type == "string" and length > 0)
    and (.bindings.pluginVersions | type == "object" and (keys | sort) == (["model-router","openrouter"] | sort))
    and all(.bindings.pluginVersions[]; type == "string" and test("^[0-9]+\\.[0-9]+\\.[0-9]+$"))
    and (.identity | type == "object" and (keys | sort) == (["aliasResolution","fallbackUsed","provider","requestedCandidate","role","servedIdentity","transport"] | sort))
    and (.identity.role | IN("architect","plan-critic","builder-fast","builder-deep","review-fast","review-deep","security-review","research-fast","editorial"))
    and (.identity.transport | IN("codex-cli","claude-cli","openrouter"))
    and (.identity.requestedCandidate | type == "string" and length > 0 and length <= 128)
    and ((.identity.servedIdentity == null) or (.identity.servedIdentity | type == "string" and length > 0 and length <= 128))
    and ((.identity.provider == null) or (.identity.provider | type == "string" and length > 0 and length <= 128))
    and ((.identity.fallbackUsed == null) or (.identity.fallbackUsed | type == "boolean"))
    and (.identity.aliasResolution | type == "object" and (keys | sort) == (["allowedServedIdentities","status"] | sort))
    and (.identity.aliasResolution.status | IN("exact","mapped","unmapped","unknown"))
    and (.identity.aliasResolution.allowedServedIdentities | type == "array" and length <= 16 and length == (unique | length))
    and all(.identity.aliasResolution.allowedServedIdentities[]; type == "string" and length > 0 and length <= 128)
    and (.boundaries | keys | sort) == (["evaluatorBinding","fixtureIntegrity","harnessComplete","instrumentationComplete","repositoryIntegrity","requiredToolAvailable","validatorIntegrity"] | sort)
    and all(.boundaries[]; type == "boolean")
    and (.quality | type == "object" and (keys | sort) == (["correctionCount","falsePositives","finalValidity","firstPassValidity","mandatoryAssertions","usefulFindings","validationAttempts"] | sort))
    and (.quality.mandatoryAssertions | type == "array" and length > 0 and length <= 64)
    and all(.quality.mandatoryAssertions[]; (keys | sort) == ["id","pass"] and (.id | type == "string" and length > 0 and length <= 128) and (.pass | type == "boolean"))
    and ((.quality.firstPassValidity == null) or (.quality.firstPassValidity | type == "boolean"))
    and ((.quality.finalValidity == null) or (.quality.finalValidity | type == "boolean"))
    and ((.quality.usefulFindings == null) or (.quality.usefulFindings | integer and . >= 0))
    and ((.quality.falsePositives == null) or (.quality.falsePositives | integer and . >= 0))
    and ((.quality.correctionCount == null) or (.quality.correctionCount | integer and . >= 0 and . <= 2))
    and ((.quality.validationAttempts == null) or (.quality.validationAttempts | integer and . >= 1 and . <= 3))
    and (.timing | type == "object" and (keys | sort) == (["endedAt","firstUsefulAt","startedAt","timeToFirstUsefulSeconds","timeToValidSeconds","totalDurationSeconds","validAt"] | sort))
    and (.timing.startedAt | timestamp) and (.timing.firstUsefulAt | nullable_timestamp)
    and (.timing.validAt | nullable_timestamp) and (.timing.endedAt | timestamp)
    and (.timing.timeToFirstUsefulSeconds | nullable_nonnegative)
    and (.timing.timeToValidSeconds | nullable_nonnegative)
    and (.timing.totalDurationSeconds | nullable_nonnegative)
    and (.telemetry | type == "object" and (keys | sort) == (["contextCoverage","tokens","toolCallsByClass","toolCoverage"] | sort))
    and (.telemetry.toolCallsByClass == null or (.telemetry.toolCallsByClass | type == "object" and (keys | sort) == (["other","repositoryRead","repositoryWrite","validation"] | sort) and all(.[]; integer and . >= 0)))
    and (.telemetry.tokens | type == "object" and (keys | sort) == (["input","output","reasoning"] | sort))
    and all(.telemetry.tokens[]; . == null or (integer and . >= 0))
    and (.telemetry.contextCoverage | coverage) and (.telemetry.toolCoverage | coverage)
    and (.cost | type == "object" and (keys | sort) == (["currency","maximumBoundUsd","measuredUsd","receiptCoverage"] | sort))
    and (.cost.currency == "USD")
    and (.cost.maximumBoundUsd == null or (.cost.maximumBoundUsd | type == "number" and . >= 0 and . <= 1))
    and (.cost.measuredUsd == null or (.cost.measuredUsd | type == "number" and . >= 0 and . <= 1))
    and (.cost.receiptCoverage | IN("measured","subscription","missing"))
    and (.artifacts | type == "array" and length > 0 and length <= 16)
    and all(.artifacts[];
      (keys | sort) == ["bytes","kind","path","sha256"]
      and (.kind | IN("prompt","output","patch","validation","transport-receipt","diagnostic"))
      and (.path | type == "string" and length > 0 and length <= 240
        and (startswith("/") | not) and test("^[A-Za-z0-9._/-]+$"))
      and (.path | split("/") | index("..") | not)
      and (.sha256 | type == "string" and test("^sha256:[0-9a-f]{64}$"))
      and (.bytes | integer and . >= 0 and . <= 1048576))
    and (.outcome | type == "object" and (keys | sort) == (["benchmarkFault","comparable","evidenceState","faultCode","faultOwner","modelConclusion","transportSuccess"] | sort))
    and (.outcome.transportSuccess | type == "boolean")
    and (.outcome.benchmarkFault | type == "boolean")
    and (.outcome.faultOwner | IN(null,"fixture","evaluator","validator","repository","instrumentation","tool","harness"))
    and (.outcome.faultCode == null or (.outcome.faultCode | type == "string" and length <= 128))
    and (.outcome.comparable | type == "boolean")
    and (.outcome.modelConclusion | IN(null,"valid","invalid"))
    and (.outcome.evidenceState | IN("incompatible","benchmark-faulted","comparable-but-insufficient"))
  ' "$1" >/dev/null 2>&1
}

validate_artifacts() {
  local attempt="$1" root="$2" rel resolved expected_size expected_digest
  ARTIFACT_FAULT=false
  ARTIFACT_DIAGNOSTICS='[]'
  root="$(realpath -- "$root")"
  while IFS=$'\t' read -r rel expected_size expected_digest; do
    case "$rel" in /*|*'/../'*|'../'*|*'/..') ARTIFACT_FAULT=true; ARTIFACT_DIAGNOSTICS="$(jq -c --arg p "$rel" '. + ["artifact-path-escape:" + $p]' <<<"$ARTIFACT_DIAGNOSTICS")"; continue ;; esac
    if [ ! -f "$root/$rel" ] || [ -L "$root/$rel" ]; then
      ARTIFACT_FAULT=true
      ARTIFACT_DIAGNOSTICS="$(jq -c --arg p "$rel" '. + ["artifact-not-regular:" + $p]' <<<"$ARTIFACT_DIAGNOSTICS")"
      continue
    fi
    resolved="$(realpath -- "$root/$rel")"
    case "$resolved" in "$root"/*) ;; *) ARTIFACT_FAULT=true; ARTIFACT_DIAGNOSTICS="$(jq -c --arg p "$rel" '. + ["artifact-path-escape:" + $p]' <<<"$ARTIFACT_DIAGNOSTICS")"; continue ;; esac
    if [ "$(wc -c < "$resolved" | tr -d '[:space:]')" != "$expected_size" ] || [ "$(sha256_file "$resolved")" != "$expected_digest" ]; then
      ARTIFACT_FAULT=true
      ARTIFACT_DIAGNOSTICS="$(jq -c --arg p "$rel" '. + ["artifact-binding-mismatch:" + $p]' <<<"$ARTIFACT_DIAGNOSTICS")"
    fi
  done < <(jq -r '.artifacts[] | [.path,(.bytes|tostring),.sha256] | @tsv' "$attempt")
}

validate_semantic_artifact_bindings() {
  local attempt="$1" root="$2" case_id="$3" patch_path validation_path
  SEMANTIC_ARTIFACT_FAULT=false
  SEMANTIC_ARTIFACT_DIAGNOSTICS='[]'
  patch_path="$(jq -r '[.artifacts[] | select(.kind == "patch")] | if length == 1 then .[0].path else empty end' "$attempt")"
  validation_path="$(jq -r '[.artifacts[] | select(.kind == "validation")] | if length == 1 then .[0].path else empty end' "$attempt")"
  if [ -z "$patch_path" ] || [ -z "$validation_path" ]; then
    SEMANTIC_ARTIFACT_FAULT=true
    SEMANTIC_ARTIFACT_DIAGNOSTICS='["missing-or-duplicate-semantic-artifact"]'
    return
  fi
  if [ "$(jq -r --arg path "$patch_path" '.artifacts[] | select(.path == $path) | .sha256' "$attempt")" \
    != "$(jq -r '.repository.patchDigest' "$attempt")" ]; then
    SEMANTIC_ARTIFACT_FAULT=true
    SEMANTIC_ARTIFACT_DIAGNOSTICS="$(jq -c '. + ["patch-digest-summary-mismatch"]' <<<"$SEMANTIC_ARTIFACT_DIAGNOSTICS")"
  fi
  if ! jq -e --arg caseId "$case_id" --slurpfile attempt "$attempt" '
    .schemaVersion == 2 and .caseId == $caseId and (.benchmarkFault | type == "boolean")
    and (.overallSuccess | type == "boolean") and (.assertions | type == "array")
    and ([.assertions[] | select(.class == "mandatory") | {id,pass}] == $attempt[0].quality.mandatoryAssertions)
    and (($attempt[0].quality.finalValidity != true) or (.validationPassed == true and .benchmarkFault == false))
  ' "$root/$validation_path" >/dev/null 2>&1; then
    SEMANTIC_ARTIFACT_FAULT=true
    SEMANTIC_ARTIFACT_DIAGNOSTICS="$(jq -c '. + ["validation-summary-mismatch"]' <<<"$SEMANTIC_ARTIFACT_DIAGNOSTICS")"
  fi
}

refresh_attempt_validation() {
  local attempt="$1" validation="$2"
  validate_attempt "$attempt" "$RESULT_DIR" > "$validation"
  jq --slurpfile result "$validation" '.outcome = {
    transportSuccess:.outcome.transportSuccess,benchmarkFault:$result[0].benchmarkFault,
    faultOwner:$result[0].faultOwner,faultCode:$result[0].faultCode,comparable:$result[0].comparable,
    modelConclusion:$result[0].modelConclusion,evidenceState:$result[0].evidenceState}' "$attempt" > "$RESULT_DIR/attempt.tmp"
  mv "$RESULT_DIR/attempt.tmp" "$attempt"
  validate_attempt "$attempt" "$RESULT_DIR" > "$validation"
}

validate_attempt() {
  local attempt="$1" root="$2" unit_id unit case_id role requested transport served
  local alias allowed alias_expected binding_fault=false identity_ok=false transport_ok paid_limit
  local boundary_fault=false fault_owner=null fault_code=null benchmark_fault=false comparable=false conclusion=null state
  local instrumentation_ok=true paid_cost_ok=true diagnostics='[]'
  require_authorities
  require_json_object "$attempt"
  [ -d "$root" ] && [ ! -L "$root" ] || { printf 'production canary: real artifact root required\n' >&2; exit 2; }
  schema_shape_ok "$attempt" || { printf 'production canary: attempt schema rejected\n' >&2; exit 2; }

  unit_id="$(jq -r '.bindings.workUnitId' "$attempt")"
  unit="$(work_unit_json "$unit_id")"
  [ -n "$unit" ] || { printf 'production canary: unknown work unit\n' >&2; exit 2; }
  case_id="$(jq -r '.sealedCaseId' <<<"$unit")"
  role="$(jq -r '.role' <<<"$unit")"
  requested="$(jq -r '.identity.requestedCandidate' "$attempt")"
  transport="$(jq -r '.identity.transport' "$attempt")"
  served="$(jq -r '.identity.servedIdentity // empty' "$attempt")"
  alias="$(resolve_alias "$role" "$requested" "$transport" "$served")"
  allowed="$(jq -c '.allowed' <<<"$alias")"
  alias_expected="$(jq -r '.status' <<<"$alias")"
  [ "$(jq -r '.candidateKnown' <<<"$alias")" = true ] || binding_fault=true
  if [ -n "$served" ] && [ "$alias_expected" != unmapped ] \
    && [ "$(jq -r '.identity.fallbackUsed' "$attempt")" = false ]; then identity_ok=true; fi
  if [ "$(jq -r '.identity.aliasResolution.status' "$attempt")" != "$alias_expected" ] \
    || ! jq -e --argjson allowed "$allowed" '.identity.aliasResolution.allowedServedIdentities == $allowed' "$attempt" >/dev/null; then
    identity_ok=false
  fi

  if ! jq -e --arg role "$role" --arg caseId "$case_id" \
    --arg workDigest "$(canonical_work_unit_digest "$unit_id")" \
    --arg fixtureDigest "$(canonical_fixture_digest "$unit_id")" \
    --arg validationDigest "$(canonical_validation_digest "$unit_id")" \
    --arg caseDigest "$(jq -r --arg id "$case_id" '.bindings.cases[$id].caseDigest' "$SUITE")" \
    --arg scorerDigest "$(jq -r --arg id "$case_id" '.bindings.cases[$id].scorerDigest' "$SUITE")" \
    --arg policyDigest "$(sha256_file "$ROLE_POLICY")" \
    --arg openrouterVersion "$(jq -r '.version' "$OPENROUTER_MANIFEST")" \
    --arg modelRouterVersion "$(jq -r '.version' "$MODEL_ROUTER_MANIFEST")" '
      .identity.role == $role and .bindings.sealedSuiteId == "depot-role-v2"
      and .bindings.sealedCaseId == $caseId and .bindings.workUnitDigest == $workDigest
      and .bindings.taskFixtureDigest == $fixtureDigest
      and .bindings.validationContractDigest == $validationDigest
      and .bindings.sealedCaseDigest == $caseDigest and .bindings.sealedScorerDigest == $scorerDigest
      and .bindings.rolePolicyDigest == $policyDigest
      and .bindings.pluginVersions == {openrouter:$openrouterVersion,"model-router":$modelRouterVersion}
    ' "$attempt" >/dev/null; then binding_fault=true; fi

  validate_artifacts "$attempt" "$root"
  [ "$ARTIFACT_FAULT" = false ] || record_boundary_fault harness unsafe-or-unbound-artifact "$ARTIFACT_DIAGNOSTICS"
  validate_semantic_artifact_bindings "$attempt" "$root" "$case_id"
  [ "$SEMANTIC_ARTIFACT_FAULT" = false ] || record_boundary_fault evaluator invalid-validation-artifact-binding "$SEMANTIC_ARTIFACT_DIAGNOSTICS"
  if [ "$(jq -r '.repository.cleanBase' "$attempt")" != true ] \
    || [ "$(jq -r '.repository.baseRevision' "$attempt")" != "$(jq -r '.repository.headRevision' "$attempt")" ]; then
    record_boundary_fault repository repository-drift
  fi
  if [ "$binding_fault" = true ] || [ "$(jq -r '.boundaries.evaluatorBinding' "$attempt")" != true ]; then
    record_boundary_fault evaluator invalid-evaluator-binding
  elif [ "$(jq -r '.boundaries.fixtureIntegrity' "$attempt")" != true ]; then
    record_boundary_fault fixture broken-fixture
  elif [ "$(jq -r '.boundaries.validatorIntegrity' "$attempt")" != true ]; then
    record_boundary_fault validator validator-defect
  elif [ "$(jq -r '.boundaries.repositoryIntegrity' "$attempt")" != true ]; then
    record_boundary_fault repository repository-setup-failure
  elif [ "$(jq -r '.boundaries.requiredToolAvailable' "$attempt")" != true ]; then
    record_boundary_fault tool required-tool-unavailable
  elif [ "$(jq -r '.boundaries.harnessComplete' "$attempt")" != true ]; then
    record_boundary_fault harness harness-failure
  fi

  if jq -e '
    .quality.firstPassValidity == null or .quality.finalValidity == null
    or .quality.correctionCount == null or .quality.validationAttempts == null
    or .timing.totalDurationSeconds == null
    or (.telemetry.contextCoverage.applicable and (.telemetry.contextCoverage.observed == null or .telemetry.contextCoverage.total == null))
    or (.telemetry.toolCoverage.applicable and .telemetry.toolCallsByClass == null)
  ' "$attempt" >/dev/null || [ "$(jq -r '.boundaries.instrumentationComplete' "$attempt")" != true ]; then
    instrumentation_ok=false
    record_boundary_fault instrumentation missing-required-instrumentation
  fi

  if [ "$transport" = openrouter ]; then
    paid_limit="$(jq -r '.limits.paidMaximumUsd' "$WORK_UNITS")"
    if ! jq -e --argjson limit "$paid_limit" '.cost as $cost | $cost.receiptCoverage == "measured"
      and ($cost.measuredUsd | type == "number" and . >= 0 and . <= $limit)
      and ($cost.maximumBoundUsd | type == "number" and . >= $cost.measuredUsd and . <= $limit)' "$attempt" >/dev/null; then
      paid_cost_ok=false
      record_boundary_fault instrumentation missing-paid-cost-receipt
    fi
  fi

  transport_ok="$(jq -r '.outcome.transportSuccess' "$attempt")"
  if [ "$boundary_fault" = true ]; then
    benchmark_fault=true; state=benchmark-faulted
  elif [ "$transport_ok" != true ] || [ "$identity_ok" != true ]; then
    state=incompatible
  else
    comparable=true; state=comparable-but-insufficient
    if [ "$(jq -r '.quality.finalValidity' "$attempt")" = true ]; then conclusion=valid; else conclusion=invalid; fi
  fi

  jq -n --arg attemptId "$(jq -r '.attemptId' "$attempt")" --arg role "$role" \
    --arg candidate "$requested" --arg transport "$transport" --arg served "${served:-}" \
    --arg state "$state" --arg faultOwner "$fault_owner" --arg faultCode "$fault_code" \
    --arg conclusion "$conclusion" --argjson diagnostics "$diagnostics" \
    --argjson benchmarkFault "$benchmark_fault" --argjson comparable "$comparable" \
    --argjson identityConfirmed "$identity_ok" --argjson instrumentationComplete "$instrumentation_ok" \
    --argjson paidCostComplete "$paid_cost_ok" --slurpfile attempt "$attempt" '
      {schemaVersion:1,evidenceClass:"production-canary-validation",attemptId:$attemptId,
       role:$role,requestedCandidate:$candidate,transport:$transport,
       servedIdentity:(if $served == "" then null else $served end),
       benchmarkFault:$benchmarkFault,faultOwner:(if $faultOwner == "null" then null else $faultOwner end),
       faultCode:(if $faultCode == "null" then null else $faultCode end),
       comparable:$comparable,identityConfirmed:$identityConfirmed,
       instrumentationComplete:$instrumentationComplete,paidCostComplete:$paidCostComplete,
       modelConclusion:(if $conclusion == "null" then null else $conclusion end),
       evidenceState:$state,diagnostics:$diagnostics,
       quality:$attempt[0].quality,timing:$attempt[0].timing,telemetry:$attempt[0].telemetry,
       repository:$attempt[0].repository,bindings:$attempt[0].bindings,cost:$attempt[0].cost,
       artifacts:$attempt[0].artifacts}
    '
}

prepare_result_dir() {
  [ ! -L "$RESULT_DIR" ] || { printf 'production canary: real result directory required\n' >&2; exit 2; }
  RESULT_DIR="$(realpath -m -- "$RESULT_DIR")"
  case "$RESULT_DIR" in
    "$ROOT"|"$ROOT"/*)
      printf 'production canary: result directory must be outside the source checkout\n' >&2
      exit 2
      ;;
  esac
  if [ -e "$RESULT_DIR" ]; then
    [ -d "$RESULT_DIR" ] && [ ! -L "$RESULT_DIR" ] || { printf 'production canary: real result directory required\n' >&2; exit 2; }
    [ -z "$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ] || { printf 'production canary: result directory must be empty\n' >&2; exit 2; }
  else
    mkdir -p "$RESULT_DIR"
  fi
  chmod 700 "$RESULT_DIR"
}

materialize_fixture() {
  local unit="$1" worktree="$2" rel destination
  mkdir -p "$worktree/.depot-canary"
  while IFS= read -r rel; do
    case "$rel" in /*|*'..'*) printf 'production canary: unsafe fixture path\n' >&2; return 1 ;; esac
    destination="$worktree/.depot-canary/$rel"
    mkdir -p "$(dirname "$destination")"
    jq --arg path "$rel" '.fixture[$path]' <<<"$unit" > "$destination"
  done < <(jq -r '(.fixture // {}) | keys[]' <<<"$unit")
}

build_prompt() {
  local unit="$1" worktree="$2" destination="$3" context_total=0 rel path bytes sealed_prompt
  sealed_prompt="$(jq -r --arg id "$(jq -r '.sealedCaseId' <<<"$unit")" '.cases[] | select(.id == $id) | .prompt' "$SUITE")"
  {
    printf 'You are completing one bounded Depot production canary in a disposable worktree.\n'
    printf 'Do not commit, change Git state, access credentials, use the network, or inspect paths outside this repository.\n'
    printf 'Candidate identity is intentionally absent from this task.\n'
    printf 'Base revision: %s\n' "$BASE_REVISION"
    printf 'Work unit: %s\n' "$(jq -r '.id' <<<"$unit")"
    printf 'Task: %s\n' "$(jq -r '.task' <<<"$unit")"
    printf 'Use repository tools when available. Run focused validation for any edit.\n'
    printf 'Your final response must be only the JSON object required below.\n\n'
    printf '%s\n' "$sealed_prompt"
    printf '\n# Bounded repository context\n'
    while IFS= read -r rel; do
      case "$rel" in /*|*'..'*) printf 'production canary: unsafe context path\n' >&2; return 1 ;; esac
      path="$worktree/$rel"
      [ -f "$path" ] && [ ! -L "$path" ] || { printf 'production canary: context path unavailable: %s\n' "$rel" >&2; return 1; }
      bytes="$(wc -c < "$path" | tr -d '[:space:]')"
      context_total=$((context_total + bytes))
      [ "$context_total" -le "$(jq -r '.limits.contextBytes' "$WORK_UNITS")" ] || { printf 'production canary: context byte bound exceeded\n' >&2; return 1; }
      printf '\n## %s\n' "$rel"
      cat -- "$path"
    done < <(jq -r '.contextPaths[]' <<<"$unit")
  } > "$destination"
}

repository_validation() {
  local validator="$1" worktree="$2" unit="$3" expected_files actual_files
  [ -z "$(find "$worktree/.depot-canary" -type l -print -quit)" ] || return 1
  case "$validator" in
    no-owned-edit) [ -z "$(git -C "$worktree" status --porcelain --untracked-files=all | grep -v '^?? \.depot-canary/' || true)" ] ;;
    builder-fast-owned-edit)
      jq -e '.schemaVersion == 1 and .enabled == true' "$worktree/.depot-canary/config/fixture.json" >/dev/null 2>&1 ;;
    builder-deep-multifile)
      jq -e '.coveredRoles == ["architect","builder"]' "$worktree/.depot-canary/suite.json" >/dev/null 2>&1 \
        && jq -e '.expectedRoleCount == 2 and .expectedCaseCount == 4' "$worktree/.depot-canary/test.json" >/dev/null 2>&1 ;;
    *) return 2 ;;
  esac || return 1
  case "$validator" in
    builder-fast-owned-edit|builder-deep-multifile)
      expected_files="$(jq -r '(.fixture // {}) | keys[]' <<<"$unit" | sort)"
      actual_files="$(find "$worktree/.depot-canary" -type f -printf '%P\n' | sort)"
      [ "$actual_files" = "$expected_files" ]
      ;;
  esac
}

classify_review_counts() {
  local case_id="$1" output="$2"
  case "$case_id" in
    review-false-positive-control)
      jq -c '{useful:([.retained[]?.id | select(. == "TP-1" or . == "TP-2")] | unique | length),
        falsePositive:(([.retained[]?.id | select(. == "FP-1" or . == "FP-2")] + [.rejected[]? | select(. == "TP-1" or . == "TP-2")]) | length)}' "$output" 2>/dev/null || printf '{"useful":null,"falsePositive":null}' ;;
    review-cross-file-invariant)
      jq -c '{useful:([.findings[]?.id | select(. == "INV-1")] | unique | length),
        falsePositive:(([.findings[]?.id | select(. == "FP-ENUM")] + [.rejected[]? | select(. == "INV-1")]) | length)}' "$output" 2>/dev/null || printf '{"useful":null,"falsePositive":null}' ;;
    *) printf '{"useful":null,"falsePositive":null}' ;;
  esac
}

artifact_row() {
  local kind="$1" root="$2" path="$3"
  jq -cn --arg kind "$kind" --arg path "$path" --arg digest "$(sha256_file "$root/$path")" \
    --argjson bytes "$(wc -c < "$root/$path" | tr -d '[:space:]')" '{kind:$kind,path:$path,sha256:$digest,bytes:$bytes}'
}

ensure_openrouter_receipt() {
  local receipt="$1" raw="$2" requested="$3" case_id="$4" role="$5" workload="$6" status="$7"
  if [ -f "$receipt" ] && [ ! -L "$receipt" ] && jq -e 'type == "object"' "$receipt" >/dev/null 2>&1; then
    cp "$receipt" "$raw"
    return 0
  fi
  printf '{}\n' > "$raw"
  jq -n --arg requested "$requested" --arg caseId "$case_id" --arg role "$role" \
    --arg workload "$workload" --argjson status "$status" '
      {schemaVersion:2,outcome:"failed",failureKind:"missing-transport-receipt",
       requestedModel:$requested,modelCandidates:[$requested],responseModel:null,
       responseModelProvenance:"not_available",servingProvider:null,
       servingProviderProvenance:"not_available",attemptedModel:$requested,
       attemptedModels:[$requested],attemptProvenance:"request",fallbackUsed:null,
       transport:"openrouter",transportStatus:$status,usage:{},
       benchmark:{suiteId:"depot-role-v2",caseId:$caseId,role:$role,workload:$workload}}
    ' > "$receipt"
  return 1
}

retain_scorer_fault() {
  local scorer_result="$1" case_id="$2"
  jq -n --arg caseId "$case_id" '
    {schemaVersion:2,caseId:$caseId,validationPassed:false,overallSuccess:false,
     benchmarkFault:true,failureOwner:"validator",failureClass:"scorer-failure",
     assertions:[{id:"production-canary-scorer",class:"mandatory",pass:false,
       repairHint:"repair the sealed scorer before rerunning the canary"}]}
  ' > "$scorer_result"
}

bound_retained_artifact() {
  local path="$1" limit="$2" temporary
  [ "$(wc -c < "$path" | tr -d '[:space:]')" -le "$limit" ] && return 0
  temporary="$RESULT_DIR/.bounded-$(basename "$path")"
  head -c "$limit" "$path" > "$temporary"
  mv "$temporary" "$path"
  return 1
}

prune_unretained_attempt_artifacts() {
  local candidate final_output="$1" final_receipt="$2" final_raw="$3" final_score="$4"
  for candidate in "$RESULT_DIR"/output-*.json "$RESULT_DIR"/transport-receipt-*.json \
    "$RESULT_DIR"/transport-events-*.json "$RESULT_DIR"/validation-*.json; do
    [ -e "$candidate" ] || continue
    case "$candidate" in
      "$final_output"|"$final_receipt"|"$final_raw"|"$final_score") ;;
      *) rm -- "$candidate" ;;
    esac
  done
  rm -f -- "$RESULT_DIR"/diagnostic-*.txt "$RESULT_DIR/system.txt" "$RESULT_DIR/receipt.tmp"
}

run_canary() {
  local unit role case_id validator source_head remote_url temp_root worktree baseline prompt started_epoch started_at
  local attempt_index=1 valid=false first_valid=null first_useful_at=null valid_at=null first_useful_seconds=null valid_seconds=null
  local output receipt raw stderr_file scorer_result validation_ok repo_ok status end_epoch ended_at duration
  local identity_json usage_json tools_json tool_coverage context_total context_observed changed_count patch_digest
  local final_output final_receipt final_raw final_score counts useful false_positive transport_success=false
  local served='' provider='' fallback=null alias_status=unknown allowed='[]' cost_bound=null measured_cost=null cost_coverage=missing
  local fixture_ok=true evaluator_ok=true validator_ok=true repository_ok=true instrumentation_ok=true tool_ok=true harness_ok=true
  local attempt_id artifacts_file attempt_file validation_file openrouter_version model_router_version maximum_corrections paid_maximum_corrections paid_limit alias artifact_limit patch_limit retained

  require_authorities
  [ -n "$WORK_UNIT_ID" ] && [ -n "$TRANSPORT" ] && [ -n "$MODEL" ] && [ -n "$BASE_REVISION" ] && [ -n "$RESULT_DIR" ] || { usage >&2; exit 2; }
  [ "$TRANSPORT" != claude-cli ] || {
    printf 'production canary: claude-cli transport disabled until a filesystem sandbox is available\n' >&2
    exit 2
  }
  case "$TRANSPORT" in codex-cli|openrouter) ;; *) usage >&2; exit 2 ;; esac
  case "$EFFORT" in low|medium|high|max) ;; *) usage >&2; exit 2 ;; esac
  maximum_corrections="$(jq -r '.limits.maximumCorrections' "$WORK_UNITS")"
  paid_maximum_corrections="$(jq -r '.limits.paidMaximumCorrections' "$WORK_UNITS")"
  paid_limit="$(jq -r '.limits.paidMaximumUsd' "$WORK_UNITS")"
  artifact_limit="$(jq -r '.limits.artifactBytes' "$WORK_UNITS")"
  patch_limit="$(jq -r '.limits.patchBytes' "$WORK_UNITS")"
  case "$MAX_CORRECTIONS" in ''|*[!0-9]*) usage >&2; exit 2 ;; esac
  [ "$MAX_CORRECTIONS" -le "$maximum_corrections" ] || { printf 'production canary: correction limit exceeded\n' >&2; exit 2; }
  [ "$TRANSPORT" != openrouter ] || [ "$MAX_CORRECTIONS" -le "$paid_maximum_corrections" ] || { printf 'production canary: paid attempts permit no correction retry\n' >&2; exit 2; }
  unit="$(work_unit_json "$WORK_UNIT_ID")"; [ -n "$unit" ] || { printf 'production canary: unknown work unit\n' >&2; exit 2; }
  role="$(jq -r '.role' <<<"$unit")"; case_id="$(jq -r '.sealedCaseId' <<<"$unit")"; validator="$(jq -r '.repositoryValidator' <<<"$unit")"
  git -C "$ROOT" diff --quiet && git -C "$ROOT" diff --cached --quiet && [ -z "$(git -C "$ROOT" status --porcelain)" ] || { printf 'production canary: dirty source checkout rejected\n' >&2; exit 2; }
  source_head="$(git -C "$ROOT" rev-parse HEAD)"
  BASE_REVISION="$(git -C "$ROOT" rev-parse "$BASE_REVISION^{commit}")"
  [ "$source_head" = "$BASE_REVISION" ] || { printf 'production canary: source HEAD must equal immutable base\n' >&2; exit 2; }
  remote_url="$(git -C "$ROOT" remote get-url origin)"
  case "$remote_url" in git@github.com:Design-Machines-Studio/depot.git|https://github.com/Design-Machines-Studio/depot.git) ;; *) printf 'production canary: repository identity mismatch\n' >&2; exit 2 ;; esac
  jq -e --arg role "$role" --arg model "$MODEL" --arg transport "$TRANSPORT" \
    --arg caseId "$case_id" --slurpfile suite "$SUITE" '
      ($suite[0].cases[] | select(.id == $caseId) | .requiredCapabilities) as $needed
      | any(.roles[$role][]?; . as $candidate
          | .model == $model and .transport == $transport
          and all($needed[]; . as $cap | $candidate.capabilities | index($cap) != null))
    ' "$ROLE_POLICY" >/dev/null || { printf 'production canary: candidate is not policy-admitted for the work unit\n' >&2; exit 2; }

  prepare_result_dir
  temp_root="$(mktemp -d "${TMPDIR:-/tmp}/depot-production-canary.XXXXXX")"
  worktree="$temp_root/worktree"; baseline="$temp_root/baseline"
  CANARY_TEMP_ROOT="$temp_root"; CANARY_WORKTREE="$worktree"
  trap 'cleanup_on_exit $?' EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  case "$RESULT_DIR" in "$temp_root"|"$temp_root"/*) printf 'production canary: result directory overlaps disposable worktree root\n' >&2; exit 2 ;; esac
  git -C "$ROOT" worktree add --detach "$worktree" "$BASE_REVISION" >/dev/null
  [ "$(git -C "$worktree" rev-parse HEAD)" = "$BASE_REVISION" ] && [ -z "$(git -C "$worktree" status --porcelain)" ] || { printf 'production canary: repository setup failure\n' >&2; exit 2; }
  materialize_fixture "$unit" "$worktree"
  mkdir -p "$baseline"; cp -R "$worktree/.depot-canary/." "$baseline/" 2>/dev/null || true
  prompt="$RESULT_DIR/prompt.txt"; build_prompt "$unit" "$worktree" "$prompt"
  started_epoch="$(date +%s)"; started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  while [ "$attempt_index" -le $((MAX_CORRECTIONS + 1)) ]; do
    output="$RESULT_DIR/output-$attempt_index.json"; receipt="$RESULT_DIR/transport-receipt-$attempt_index.json"
    raw="$RESULT_DIR/transport-events-$attempt_index.json"; stderr_file="$RESULT_DIR/diagnostic-$attempt_index.txt"
    scorer_result="$RESULT_DIR/validation-$attempt_index.json"
    status=0
    case "$TRANSPORT" in
      codex-cli)
        set +e
        (cd "$worktree" && "${DEPOT_CANARY_CODEX_BIN:-$(command -v codex)}" exec --ephemeral --ignore-user-config \
          --sandbox workspace-write --model "$MODEL" --config "model_reasoning_effort=\"$EFFORT\"" \
          --json --output-last-message "$output" - < "$prompt") > "$raw" 2> "$stderr_file"
        status=$?
        set -e
        identity_json="$(jq -sc '
          [.. | objects | .model? | select(type == "string" and length > 0)] | unique as $models
          | [.. | objects | .provider? | select(type == "string" and length > 0)] | unique as $providers
          | [.. | objects | .fallbackUsed?, .fallback_used? | select(type == "boolean")] | unique as $fallback
          | {served:(if ($models|length)==1 then $models[0] else null end),provider:(if ($providers|length)==1 then $providers[0] else null end),fallback:(if ($fallback|length)==1 then $fallback[0] else null end)}
        ' "$raw" 2>/dev/null || printf '{"served":null,"provider":null,"fallback":null}')"
        usage_json="$(jq -sc '
          [.. | objects | .usage? | select(type == "object")] | last // {} |
          {input:(.input_tokens // .input_usage_count // null),output:(.output_tokens // .output_usage_count // null),reasoning:(.reasoning_tokens // .reasoning_usage_count // null)}
        ' "$raw" 2>/dev/null || printf '{"input":null,"output":null,"reasoning":null}')"
        tools_json="$(jq -sc '
          [.. | objects | select(.type? == "command_execution") | .command? | select(type == "string")] as $commands |
          {repositoryRead:([$commands[] | select(test("(^|[ ;])(rg|sed|jq|git (show|diff|status)|head|tail|wc)( |$)"))] | length),
           repositoryWrite:([$commands[] | select(test("apply_patch|(^|[ ;])(mv|cp|mkdir)( |$)"))] | length),
           validation:([$commands[] | select(test("test|validate|diff --check|jq -e"))] | length),
           other:([$commands[] | select((test("(^|[ ;])(rg|sed|jq|git (show|diff|status)|head|tail|wc)( |$)|apply_patch|(^|[ ;])(mv|cp|mkdir)( |$)|test|validate|diff --check|jq -e") | not))] | length)}
        ' "$raw" 2>/dev/null || printf 'null')"
        ;;
      openrouter)
        input_bytes="$(wc -c < "$prompt" | tr -d '[:space:]')"
        cost_bound="$(jq -r --arg model "$MODEL" --argjson bytes "$input_bytes" '
          .models[] | select(.slug == $model)
          | ((($bytes * .input_usd_per_m) + (.top_provider_max_completion_tokens * .output_usd_per_m)) / 1000000)
        ' "$MATRIX")"
        [ -n "$cost_bound" ] && awk -v cost="$cost_bound" -v limit="$paid_limit" 'BEGIN {exit !(cost >= 0 && cost <= limit)}' || { printf 'production canary: paid cost cannot be bounded within configured limit\n' >&2; exit 2; }
        printf '%s\n' 'You are completing one bounded Depot production canary. Return only the required JSON object.' > "$RESULT_DIR/system.txt"
        set +e
        OPENROUTER_ALLOW_FALLBACKS=0 OPENROUTER_SYSTEM_FILE="$RESULT_DIR/system.txt" OPENROUTER_WORKLOAD="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .workload' "$SUITE")" \
        OPENROUTER_RECEIPT_FILE="$receipt" "$WRAPPER" "$MODEL" - 900 < "$prompt" > "$output" 2> "$stderr_file"
        status=$?
        set -e
        if ! ensure_openrouter_receipt "$receipt" "$raw" "$MODEL" "$case_id" "$role" \
          "$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .workload' "$SUITE")" "$status"; then
          instrumentation_ok=false
        fi
        identity_json="$(jq -c '{served:(.responseModel // null),provider:(.servingProvider // null),fallback:(.fallbackUsed // null)}' "$receipt" 2>/dev/null || printf '{"served":null,"provider":null,"fallback":null}')"
        usage_json="$(jq -c '(.usage // {}) | {input:(.prompt_tokens // null),output:(.completion_tokens // null),reasoning:(.reasoning_tokens // null)}' "$receipt" 2>/dev/null || printf '{"input":null,"output":null,"reasoning":null}')"
        tools_json='{"repositoryRead":0,"repositoryWrite":0,"validation":0,"other":0}'
        ;;
    esac
    [ -f "$output" ] || : > "$output"
    served="$(jq -r '.served // empty' <<<"$identity_json")"; provider="$(jq -r '.provider // empty' <<<"$identity_json")"; fallback="$(jq -r '.fallback' <<<"$identity_json")"
    if [ "$TRANSPORT" = openrouter ]; then
      jq --arg suiteId "depot-role-v2" --arg caseId "$case_id" --arg role "$role" \
        --arg workload "$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .workload' "$SUITE")" \
        '.transport="openrouter" | .benchmark={suiteId:$suiteId,caseId:$caseId,role:$role,workload:$workload}' \
        "$receipt" > "$RESULT_DIR/receipt.tmp"
      mv "$RESULT_DIR/receipt.tmp" "$receipt"
    else
      jq -n --arg requested "$MODEL" --arg response "$served" --arg provider "$provider" --arg transport "$TRANSPORT" \
        --arg suiteId "depot-role-v2" --arg caseId "$case_id" --arg role "$role" \
        --arg workload "$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .workload' "$SUITE")" \
        --argjson fallback "$fallback" --argjson usage "$usage_json" --argjson status "$status" '
          {schemaVersion:2,outcome:(if $status == 0 then "success" else "failed" end),requestedModel:$requested,
           modelCandidates:[$requested],responseModel:(if $response == "" then null else $response end),
           responseModelProvenance:(if $response == "" then "not_available" else "response" end),
           servingProvider:(if $provider == "" then null else $provider end),servingProviderProvenance:(if $provider == "" then "not_available" else "response" end),
           attemptedModel:(if $response == "" then $requested else $response end),attemptedModels:[(if $response == "" then $requested else $response end)],
           attemptProvenance:"response_model",fallbackUsed:$fallback,transport:$transport,usage:$usage,
           benchmark:{suiteId:$suiteId,caseId:$caseId,role:$role,workload:$workload}}
        ' > "$receipt"
    fi
    final_output="$output"; final_receipt="$receipt"; final_raw="$raw"; final_score="$scorer_result"
    set +e
    "$BENCH" --score --case "$case_id" --output-file "$output" --receipt-file "$receipt" --result-file "$scorer_result" --duration-seconds "$(( $(date +%s) - started_epoch ))" >/dev/null
    scorer_status=$?
    set -e
    if [ "$scorer_status" -ne 0 ]; then
      retain_scorer_fault "$scorer_result" "$case_id"
      validator_ok=false
      harness_ok=false
      break
    fi
    repo_ok=false; repository_validation "$validator" "$worktree" "$unit" && repo_ok=true
    if [ -n "$(git -C "$worktree" status --porcelain --untracked-files=all | grep -v '^?? \.depot-canary/' || true)" ]; then repo_ok=false; fi
    if [ "$validator" = no-owned-edit ] && ! diff -qr "$baseline" "$worktree/.depot-canary" >/dev/null 2>&1; then repo_ok=false; fi
    validation_ok=false
    jq -e '.validationPassed == true and .benchmarkFault == false' "$scorer_result" >/dev/null 2>&1 && [ "$repo_ok" = true ] && validation_ok=true
    end_epoch="$(date +%s)"
    if [ "$attempt_index" -eq 1 ]; then
      first_valid="$validation_ok"
      if jq -e 'any(.assertions[]?; .class == "semantic" and .pass == true)' "$scorer_result" >/dev/null 2>&1; then
        first_useful_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; first_useful_seconds="$((end_epoch-started_epoch))"
      fi
    fi
    if [ "$validation_ok" = true ]; then valid=true; valid_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; valid_seconds="$((end_epoch-started_epoch))"; break; fi
    [ "$attempt_index" -le "$MAX_CORRECTIONS" ] || break
    {
      printf '\n\n# Validation feedback for correction %s\n' "$attempt_index"
      jq -c '{failedAssertions:[.assertions[] | select(.pass == false) | {id,repairHint}],validationPassed,benchmarkFault}' "$scorer_result"
      printf '\nInspect the existing disposable worktree, make the smallest correction, and return the complete JSON object again.\n'
    } >> "$prompt"
    attempt_index=$((attempt_index+1))
  done

  prune_unretained_attempt_artifacts "$final_output" "$final_receipt" "$final_raw" "$final_score"
  transport_success=false; [ "$status" -eq 0 ] && transport_success=true
  alias="$(resolve_alias "$role" "$MODEL" "$TRANSPORT" "$served")"
  allowed="$(jq -c '.allowed' <<<"$alias")"
  alias_status="$(jq -r '.status' <<<"$alias")"
  if [ "$TRANSPORT" = openrouter ]; then
    measured_cost="$(jq -r '.usage.cost // empty' "$final_receipt")"
    if [ -n "$measured_cost" ] && awk -v cost="$measured_cost" -v limit="$paid_limit" 'BEGIN {exit !(cost >= 0 && cost <= limit)}'; then cost_coverage=measured; else measured_cost=null; instrumentation_ok=false; fi
  else cost_bound=null; measured_cost=null; cost_coverage=subscription; fi

  if [ "$validator" = no-owned-edit ]; then
    : > "$RESULT_DIR/patch.diff"
    changed_count=0
  else
    diff -ruN "$baseline" "$worktree/.depot-canary" > "$RESULT_DIR/patch.diff" || true
    changed_count="$(find "$worktree/.depot-canary" -type f -print0 | while IFS= read -r -d '' file; do rel="${file#"$worktree/.depot-canary/"}"; if [ ! -f "$baseline/$rel" ] || ! cmp -s "$baseline/$rel" "$file"; then printf '%s\n' "$rel"; fi; done | wc -l | tr -d '[:space:]')"
  fi
  if ! bound_retained_artifact "$RESULT_DIR/patch.diff" "$patch_limit"; then
    repository_ok=false
    harness_ok=false
  fi
  patch_digest="$(sha256_file "$RESULT_DIR/patch.diff")"
  ended_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; end_epoch="$(date +%s)"; duration="$((end_epoch-started_epoch))"
  counts="$(classify_review_counts "$case_id" "$final_output")"; useful="$(jq -r '.useful' <<<"$counts")"; false_positive="$(jq -r '.falsePositive' <<<"$counts")"
  context_total="$(jq -r '.contextPaths | length' <<<"$unit")"
  if [ "$TRANSPORT" = openrouter ]; then context_observed="$context_total"
  else
    context_observed=0
    while IFS= read -r rel; do grep -F "$rel" "$final_raw" >/dev/null 2>&1 && context_observed=$((context_observed+1)); done < <(jq -r '.contextPaths[]' <<<"$unit")
  fi
  tool_coverage="$(jq -c --argjson tools "$tools_json" --argjson applicable "$(jq -r '.toolCoverage.applicable' <<<"$unit")" --arg reason "$(jq -r '.toolCoverage.reason' <<<"$unit")" '
    (if $tools == null then null else (($tools|to_entries|map(.value)|add) > 0 | if . then 1 else 0 end) end) as $observed
    | if $applicable then {applicable:true,observed:$observed,total:1,rate:$observed,reason:$reason}
    else {applicable:false,observed:null,total:null,rate:null,reason:$reason} end
  ' <<<"{}")"
  [ "$tools_json" != null ] || { if [ "$(jq -r '.toolCoverage.applicable' <<<"$unit")" = true ]; then instrumentation_ok=false; fi; }

  for retained in "$prompt" "$final_output" "$final_receipt" "$final_raw"; do
    if ! bound_retained_artifact "$retained" "$artifact_limit"; then
      instrumentation_ok=false
      harness_ok=false
    fi
  done
  if [ "$(wc -c < "$final_score" | tr -d '[:space:]')" -gt "$artifact_limit" ]; then
    retain_scorer_fault "$final_score" "$case_id"
    validator_ok=false
    harness_ok=false
  fi
  artifacts_file="$RESULT_DIR/artifacts.ndjson"; : > "$artifacts_file"
  artifact_row prompt "$RESULT_DIR" prompt.txt >> "$artifacts_file"
  artifact_row output "$RESULT_DIR" "${final_output#"$RESULT_DIR/"}" >> "$artifacts_file"
  artifact_row patch "$RESULT_DIR" patch.diff >> "$artifacts_file"
  artifact_row validation "$RESULT_DIR" "${final_score#"$RESULT_DIR/"}" >> "$artifacts_file"
  artifact_row transport-receipt "$RESULT_DIR" "${final_receipt#"$RESULT_DIR/"}" >> "$artifacts_file"
  artifact_row diagnostic "$RESULT_DIR" "${final_raw#"$RESULT_DIR/"}" >> "$artifacts_file"
  attempt_id="canary-$(date -u +%Y%m%dt%H%M%Sz)-$(printf '%s' "$BASE_REVISION$WORK_UNIT_ID$MODEL$TRANSPORT" | sha256sum | cut -c1-12)"
  openrouter_version="$(jq -r '.version' "$OPENROUTER_MANIFEST")"; model_router_version="$(jq -r '.version' "$MODEL_ROUTER_MANIFEST")"
  attempt_file="$RESULT_DIR/attempt.json"; validation_file="$RESULT_DIR/canary-validation.json"
  jq -n --arg attemptId "$attempt_id" --arg base "$BASE_REVISION" --arg patchDigest "$patch_digest" --arg unitId "$WORK_UNIT_ID" \
    --argjson unitRevision "$(jq -r '.revision' <<<"$unit")" --arg workDigest "$(canonical_work_unit_digest "$WORK_UNIT_ID")" \
    --arg fixtureDigest "$(canonical_fixture_digest "$WORK_UNIT_ID")" --arg validationDigest "$(canonical_validation_digest "$WORK_UNIT_ID")" \
    --arg caseId "$case_id" --arg caseDigest "$(jq -r --arg id "$case_id" '.bindings.cases[$id].caseDigest' "$SUITE")" \
    --arg scorerDigest "$(jq -r --arg id "$case_id" '.bindings.cases[$id].scorerDigest' "$SUITE")" --arg policyDigest "$(sha256_file "$ROLE_POLICY")" \
    --arg openrouterVersion "$openrouter_version" --arg modelRouterVersion "$model_router_version" --arg role "$role" --arg requested "$MODEL" \
    --arg transport "$TRANSPORT" --arg served "$served" --arg provider "$provider" --arg aliasStatus "$alias_status" --argjson allowed "$allowed" \
    --arg startedAt "$started_at" --arg firstUsefulAt "$first_useful_at" --arg validAt "$valid_at" --arg endedAt "$ended_at" \
    --arg costCoverage "$cost_coverage" --argjson fallback "$fallback" --argjson cleanBase true --argjson changed "$changed_count" \
    --argjson firstValid "$first_valid" --argjson finalValid "$valid" --argjson correction "$((attempt_index-1))" --argjson validations "$attempt_index" \
    --argjson useful "$useful" --argjson falsePositive "$false_positive" --argjson firstUsefulSeconds "$first_useful_seconds" \
    --argjson validSeconds "$valid_seconds" --argjson duration "$duration" --argjson tools "$tools_json" --argjson tokens "$usage_json" \
    --argjson contextObserved "$context_observed" --argjson contextTotal "$context_total" --argjson toolCoverage "$tool_coverage" \
    --argjson maximumBound "$cost_bound" --argjson measured "$measured_cost" --argjson transportSuccess "$transport_success" \
    --argjson fixtureOk "$fixture_ok" --argjson evaluatorOk "$evaluator_ok" --argjson validatorOk "$validator_ok" \
    --argjson repositoryOk "$repository_ok" --argjson instrumentationOk "$instrumentation_ok" --argjson toolOk "$tool_ok" --argjson harnessOk "$harness_ok" \
    --slurpfile score "$final_score" --slurpfile artifacts "$artifacts_file" '
      {schemaVersion:1,evidenceClass:"production-canary",harnessVersion:1,attemptId:$attemptId,
       repository:{identity:"Design-Machines-Studio/depot",baseRevision:$base,headRevision:$base,cleanBase:$cleanBase,patchDigest:$patchDigest,changedFileCount:$changed},
       bindings:{workUnitId:$unitId,workUnitRevision:$unitRevision,workUnitDigest:$workDigest,taskFixtureDigest:$fixtureDigest,
         validationContractDigest:$validationDigest,sealedSuiteId:"depot-role-v2",sealedCaseId:$caseId,sealedCaseDigest:$caseDigest,
         sealedScorerDigest:$scorerDigest,rolePolicyDigest:$policyDigest,pluginVersions:{openrouter:$openrouterVersion,"model-router":$modelRouterVersion}},
       identity:{role:$role,requestedCandidate:$requested,transport:$transport,servedIdentity:(if $served=="" then null else $served end),
         provider:(if $provider=="" then null else $provider end),aliasResolution:{status:$aliasStatus,allowedServedIdentities:$allowed},fallbackUsed:$fallback},
       boundaries:{fixtureIntegrity:$fixtureOk,evaluatorBinding:$evaluatorOk,validatorIntegrity:$validatorOk,repositoryIntegrity:$repositoryOk,
         instrumentationComplete:$instrumentationOk,requiredToolAvailable:$toolOk,harnessComplete:$harnessOk},
       quality:{firstPassValidity:$firstValid,finalValidity:$finalValid,
         mandatoryAssertions:[$score[0].assertions[] | select(.class=="mandatory") | {id,pass}],usefulFindings:$useful,falsePositives:$falsePositive,
         correctionCount:$correction,validationAttempts:$validations},
       timing:{startedAt:$startedAt,firstUsefulAt:(if $firstUsefulAt=="null" then null else $firstUsefulAt end),
         validAt:(if $validAt=="null" then null else $validAt end),endedAt:$endedAt,timeToFirstUsefulSeconds:$firstUsefulSeconds,
         timeToValidSeconds:$validSeconds,totalDurationSeconds:$duration},
       telemetry:{toolCallsByClass:$tools,tokens:$tokens,
         contextCoverage:{applicable:true,observed:$contextObserved,total:$contextTotal,rate:(if $contextTotal>0 then ($contextObserved/$contextTotal) else null end),reason:"bounded work-unit context paths"},
         toolCoverage:$toolCoverage},
       cost:{currency:"USD",maximumBoundUsd:$maximumBound,measuredUsd:$measured,receiptCoverage:$costCoverage},
       artifacts:$artifacts,
       outcome:{transportSuccess:$transportSuccess,benchmarkFault:false,faultOwner:null,faultCode:null,comparable:false,modelConclusion:null,evidenceState:"incompatible"}}
    ' > "$attempt_file"
  refresh_attempt_validation "$attempt_file" "$validation_file"
  if ! cleanup_owned_resources; then
    jq '.boundaries.harnessComplete=false' "$attempt_file" > "$RESULT_DIR/attempt.tmp"
    mv "$RESULT_DIR/attempt.tmp" "$attempt_file"
    refresh_attempt_validation "$attempt_file" "$validation_file"
    printf 'production canary: owned cleanup failure retained at %s\n' "$CANARY_TEMP_ROOT" >&2
  fi
  rm -f -- "$artifacts_file"
  trap - EXIT INT TERM
  jq -n --slurpfile attempt "$attempt_file" --slurpfile validation "$validation_file" '{attempt:$attempt[0],validation:$validation[0]}'
}

if [ "${DEPOT_CANARY_SOURCE_ONLY:-0}" = 1 ]; then
  return 0 2>/dev/null || exit 0
fi

case "$COMMAND" in
  --list)
    require_authorities
    jq -r '.workUnits[] | [.id,.role,.sealedCaseId,.repositoryValidator] | @tsv' "$WORK_UNITS"
    ;;
  --validate)
    [ -n "$ATTEMPT_FILE" ] && [ -n "$ARTIFACT_ROOT" ] || { usage >&2; exit 2; }
    validate_attempt "$ATTEMPT_FILE" "$ARTIFACT_ROOT"
    ;;
  --run) run_canary ;;
  *) usage >&2; exit 2 ;;
esac
