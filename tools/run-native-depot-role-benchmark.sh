#!/usr/bin/env bash
# Run one depot-role-v2 case against one exact native subscription model.
# This complements the OpenRouter-owned runner without changing its provider
# boundary. It retains raw CLI telemetry privately and emits the same scored
# result shape plus transport/billing provenance.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUITE="${DEPOT_BENCH_SUITE:-$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json}"
ROLE_POLICY="${DEPOT_BENCH_ROLE_POLICY:-$ROOT/plugins/model-router/skills/model-router/references/role-policy.json}"
BENCH="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
CODEX_BIN="${DEPOT_BENCH_CODEX_BIN:-codex}"
CLAUDE_BIN="${DEPOT_BENCH_CLAUDE_BIN:-claude}"

CASE_ID=""
MODEL=""
TRANSPORT=""
EFFORT="medium"
RESULT_DIR=""

usage() {
  printf '%s\n' \
    'usage: run-native-depot-role-benchmark.sh --case ID --transport codex-cli|claude-cli --model EXACT_ID --effort low|medium|high|max --result-dir PATH'
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --case) CASE_ID="${2:-}"; shift 2 ;;
    --model) MODEL="${2:-}"; shift 2 ;;
    --transport) TRANSPORT="${2:-}"; shift 2 ;;
    --effort) EFFORT="${2:-}"; shift 2 ;;
    --result-dir) RESULT_DIR="${2:-}"; shift 2 ;;
    *) usage >&2; exit 2 ;;
  esac
done

[ -n "$CASE_ID" ] && [ -n "$MODEL" ] && [ -n "$TRANSPORT" ] && [ -n "$RESULT_DIR" ] || { usage >&2; exit 2; }
case "$TRANSPORT" in codex-cli|claude-cli) ;; *) usage >&2; exit 2 ;; esac
case "$EFFORT" in low|medium|high|max) ;; *) usage >&2; exit 2 ;; esac
[ -x "$BENCH" ] || { printf 'native benchmark: OpenRouter scorer unavailable\n' >&2; exit 2; }

require_json_file() {
  [ -f "$1" ] && [ ! -L "$1" ] && jq -e 'type == "object"' "$1" >/dev/null 2>&1 || {
    printf 'native benchmark: malformed JSON authority: %s\n' "$1" >&2
    exit 2
  }
}

require_json_file "$SUITE"
require_json_file "$ROLE_POLICY"
jq -e '
  .schemaVersion == 2 and (.suiteId | type == "string" and length > 0)
  and (.cases | type == "array" and length > 0)
  and all(.cases[]; type == "object"
    and (.id | type == "string" and length > 0)
    and (.role | type == "string" and length > 0)
    and (.workload | type == "string" and IN("quality","security","direct","bulk","mechanical"))
    and (.requiredCapabilities | type == "array" and all(.[]; type == "string" and length > 0)))
  and (([.cases[].id] | unique | length) == (.cases | length))
' "$SUITE" >/dev/null 2>&1 || {
  printf 'native benchmark: malformed v2 benchmark suite\n' >&2
  exit 2
}
jq -e '
  .schemaVersion == 1 and (.roles | type == "object")
  and all(.roles | to_entries[];
    (.key | type == "string" and length > 0) and (.value | type == "array")
    and all(.value[]; type == "object"
      and (.model | type == "string" and length > 0)
      and (.provider | type == "string" and length > 0)
      and (.transport | type == "string" and length > 0)
      and (.billing | type == "string" and length > 0)
      and (.capabilities | type == "array" and all(.[]; type == "string" and length > 0))))
' "$ROLE_POLICY" >/dev/null 2>&1 || {
  printf 'native benchmark: malformed role policy\n' >&2
  exit 2
}

case_json="$(jq -c --arg id "$CASE_ID" '.cases[] | select(.id == $id)' "$SUITE")"
[ -n "$case_json" ] || { printf 'native benchmark: unknown case\n' >&2; exit 2; }
case_role="$(jq -r '.role' <<<"$case_json")"
workload="$(jq -r '.workload' <<<"$case_json")"
required_capabilities="$(jq -c '.requiredCapabilities' <<<"$case_json")"
candidate_json="$(jq -c --arg role "$case_role" --arg model "$MODEL" --arg transport "$TRANSPORT" \
  --argjson needed "$required_capabilities" '
    [.roles[$role][]? | . as $candidate
      | select(.model == $model and .transport == $transport
        and all($needed[]; . as $cap | $candidate.capabilities | index($cap) != null))]
    | if length == 1 then .[0] else empty end
  ' "$ROLE_POLICY")"
[ -n "$candidate_json" ] || {
  printf 'native benchmark: model/transport is not eligible for the case role and capabilities\n' >&2
  exit 2
}

if [ -e "$RESULT_DIR" ]; then
  [ -d "$RESULT_DIR" ] && [ ! -L "$RESULT_DIR" ] || {
    printf 'native benchmark: result directory must be a real directory\n' >&2; exit 2
  }
  [ -z "$(find "$RESULT_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ] || {
    printf 'native benchmark: result directory must be empty\n' >&2; exit 2
  }
else
  mkdir -p "$RESULT_DIR"
fi
chmod 700 "$RESULT_DIR"
RESULT_DIR="$(cd "$RESULT_DIR" && pwd)"
PROMPT="$RESULT_DIR/prompt.txt"
OUTPUT="$RESULT_DIR/output.json"
RECEIPT="$RESULT_DIR/receipt.json"
RESULT="$RESULT_DIR/result.json"
RAW="$RESULT_DIR/native-events.json"
STDERR_FILE="$RESULT_DIR/native-stderr.txt"

"$BENCH" --prepare --case "$CASE_ID" --output-file "$PROMPT"
start="$(date +%s)"
status=0
telemetry_valid=false
output_present=false
identity_json='{"identity":null,"provenance":"not_available","ambiguous":false,"primaryUsage":null,"ancillaryUsage":[]}'
usage_json='{"prompt_tokens":null,"completion_tokens":null,"reasoning_tokens":null,"cache_read_tokens":null,"cache_creation_tokens":null,"cost":null}'
fallback_json='{"used":null,"provenance":"not_available","attemptedModel":null,"attemptedModels":[]}'
provider_json='{"provider":null,"provenance":"not_available"}'

if [ "$TRANSPORT" = codex-cli ]; then
  set +e
  (
    cd "$RESULT_DIR"
    "$CODEX_BIN" exec --ephemeral --ignore-user-config --skip-git-repo-check \
      --sandbox read-only --model "$MODEL" \
      --config "model_reasoning_effort=\"$EFFORT\"" \
      --json --output-last-message "$OUTPUT" - < "$PROMPT"
  ) > "$RAW" 2> "$STDERR_FILE"
  status=$?
  set -e
  [ -s "$OUTPUT" ] && output_present=true
  if jq -s -e 'length > 0 and all(.[]; type == "object")' "$RAW" >/dev/null 2>&1; then
    telemetry_valid=true
    identity_json="$(jq -sc '
      [.[].model?, .[].response?.model?, .[].turn?.model?]
      | flatten | map(select(type == "string" and length > 0)) | unique as $models
      | {identity:(if ($models | length) == 1 then $models[0] else null end),
         provenance:(if ($models | length) == 1 then "cli-event-response-model"
           elif ($models | length) > 1 then "ambiguous-cli-event-models" else "not_available" end),
         ambiguous:(($models | length) > 1),primaryUsage:null,ancillaryUsage:[]}
    ' "$RAW")"
    usage_json="$(jq -sc '
      [.. | objects | select(
        has("input_tokens") or has("output_tokens") or has("reasoning_tokens") or
        has("input_usage_count") or has("output_usage_count") or
        has("cached_input_tokens") or has("cache_read_usage_count") or
        has("cache_creation_input_tokens") or has("cache_creation_usage_count")
      )] | last // {} as $usage
      | {prompt_tokens:($usage.input_tokens // $usage.input_usage_count // null),
         completion_tokens:($usage.output_tokens // $usage.output_usage_count // null),
         reasoning_tokens:($usage.reasoning_tokens // $usage.reasoning_usage_count // null),
         cache_read_tokens:($usage.cached_input_tokens // $usage.cache_read_input_tokens // $usage.cache_read_usage_count // null),
         cache_creation_tokens:($usage.cache_creation_input_tokens // $usage.cache_creation_usage_count // null),cost:null}
    ' "$RAW")"
    fallback_json="$(jq -sc '
      . as $events
      | [$events[].fallbackUsed?, $events[].fallback_used?] | flatten | map(select(type == "boolean")) | unique as $values
      | [$events[].attemptedModels?, $events[].attempted_models?] | flatten | map(select(type == "string" and length > 0)) as $attempts
      | {used:(if ($values | length) == 1 then $values[0] else null end),
         provenance:(if ($values | length) == 1 then "cli-event" elif ($values | length) > 1 then "ambiguous-cli-events" else "not_available" end),
         attemptedModel:($attempts | last // null),attemptedModels:$attempts}
    ' "$RAW")"
    provider_json="$(jq -sc '
      [.[].provider?, .[].response?.provider?] | flatten | map(select(type == "string" and length > 0)) | unique as $providers
      | {provider:(if ($providers | length) == 1 then $providers[0] else null end),
         provenance:(if ($providers | length) == 1 then "cli-event" elif ($providers | length) > 1 then "ambiguous-cli-events" else "not_available" end)}
    ' "$RAW")"
  fi
else
  set +e
  (
    cd "$RESULT_DIR"
    "$CLAUDE_BIN" --print --model "$MODEL" --effort "$EFFORT" --tools "" \
      --no-session-persistence --output-format json < "$PROMPT"
  ) > "$RAW" 2> "$STDERR_FILE"
  status=$?
  set -e
  if jq -e '
    type == "object"
    and ((has("usage") | not) or (.usage | type == "object"))
    and ((has("modelUsage") | not) or (.modelUsage | type == "object" and all(.[]; type == "object")))
  ' "$RAW" >/dev/null 2>&1; then
    telemetry_valid=true
    if jq -e '.structured_output | type == "object"' "$RAW" >/dev/null 2>&1; then
      jq '.structured_output' "$RAW" > "$OUTPUT"
    elif jq -e '.result | type == "string"' "$RAW" >/dev/null 2>&1; then
      jq -r '.result' "$RAW" > "$OUTPUT"
    fi
    [ -s "$OUTPUT" ] && output_present=true
    identity_json="$(jq -c '
      def usage_rows($root): ($root.modelUsage // {} | to_entries
        | map({model:.key,usage:.value,outputTokens:(.value.outputTokens // .value.output_tokens // null)}));
      . as $root
      | [($root.model // empty),($root.response.model // empty)] | map(select(type == "string" and length > 0)) | unique as $explicit
      | usage_rows($root) as $rows
      | if ($explicit | length) == 1 then $explicit[0] as $primary
          | {identity:$primary,provenance:"explicit-response-model",ambiguous:false,
             primaryUsage:($rows | map(select(.model == $primary)) | first // null),
             ancillaryUsage:($rows | map(select(.model != $primary)))}
        elif ($explicit | length) > 1 then
          {identity:null,provenance:"ambiguous-explicit-response-models",ambiguous:true,
           primaryUsage:null,ancillaryUsage:$rows}
        else
          [$rows[] | select(.outputTokens | type == "number" and . > 0)] as $positive
          | ($positive | map(.outputTokens) | max // null) as $maximum
          | [$positive[] | select(.outputTokens == $maximum)] as $winners
          | if ($winners | length) == 1 then $winners[0].model as $primary
              | {identity:$primary,provenance:"modelUsage-unique-max-output-tokens",ambiguous:false,
                 primaryUsage:($winners[0]),ancillaryUsage:($rows | map(select(.model != $primary)))}
            elif ($winners | length) > 1 then
              {identity:null,provenance:"modelUsage-tied-max-output-tokens",ambiguous:true,
               primaryUsage:null,ancillaryUsage:$rows}
            else
              {identity:null,provenance:"not_available",ambiguous:false,
               primaryUsage:null,ancillaryUsage:$rows}
            end
        end
    ' "$RAW")"
    usage_json="$(jq -c '
      (.usage // {}) as $usage
      | {prompt_tokens:($usage.input_tokens // null),completion_tokens:($usage.output_tokens // null),
         reasoning_tokens:($usage.reasoning_tokens // $usage.output_tokens_details.reasoning_tokens // null),
         cache_read_tokens:($usage.cache_read_input_tokens // null),
         cache_creation_tokens:($usage.cache_creation_input_tokens // null),cost:null}
    ' "$RAW")"
    fallback_json="$(jq -c '
      . as $root
      | [$root.fallbackUsed?,$root.fallback_used?] | map(select(type == "boolean")) | unique as $values
      | [($root.attemptedModels // empty),($root.attempted_models // empty)] | flatten | map(select(type == "string" and length > 0)) as $attempts
      | {used:(if ($values | length) == 1 then $values[0] else null end),
         provenance:(if ($values | length) == 1 then "response" elif ($values | length) > 1 then "ambiguous-response-fields" else "not_available" end),
         attemptedModel:($attempts | last // null),attemptedModels:$attempts}
    ' "$RAW")"
    provider_json="$(jq -c --argjson identity "$identity_json" '
      . as $root
      | [($root.provider // empty),($root.response.provider // empty),
       (if $identity.identity == null then empty
        else ($root.modelUsage[$identity.identity].provider // empty) end)]
      | map(select(type == "string" and length > 0)) | unique as $providers
      | {provider:(if ($providers | length) == 1 then $providers[0] else null end),
         provenance:(if ($providers | length) == 1 then "response" elif ($providers | length) > 1 then "ambiguous-response-fields" else "not_available" end)}
    ' "$RAW")"
  fi
fi

[ -f "$OUTPUT" ] || : > "$OUTPUT"

end="$(date +%s)"
duration="$((end-start))"
outcome=success
failure_kind=null
if [ "$status" -ne 0 ]; then outcome=failed; failure_kind=cli-nonzero-status
elif [ "$telemetry_valid" != true ]; then outcome=failed; failure_kind=malformed-telemetry
elif [ "$output_present" != true ]; then outcome=failed; failure_kind=missing-output
fi

response_model="$(jq -r '.identity // empty' <<<"$identity_json")"
response_provenance="$(jq -r '.provenance' <<<"$identity_json")"
serving_provider="$(jq -r '.provider // empty' <<<"$provider_json")"
provider_provenance="$(jq -r '.provenance' <<<"$provider_json")"
billing="$(jq -r '.billing' <<<"$candidate_json")"

jq -n \
  --arg requested "$MODEL" --arg response "$response_model" --arg responseProvenance "$response_provenance" \
  --arg provider "$serving_provider" --arg providerProvenance "$provider_provenance" \
  --arg transport "$TRANSPORT" --arg billing "$billing" --arg effort "$EFFORT" \
  --arg outcome "$outcome" --arg failureKind "$failure_kind" --argjson usage "$usage_json" \
  --argjson identity "$identity_json" --argjson fallback "$fallback_json" \
  --arg suite "$(jq -r '.suiteId' "$SUITE")" --arg caseId "$CASE_ID" --arg role "$case_role" --arg workload "$workload" '
  {schemaVersion:2,requestedModel:$requested,
   modelCandidates:(if $fallback.used == true and ($fallback.attemptedModels | length) > 0
     then $fallback.attemptedModels else [$requested] end),
   responseModel:(if $response == "" then null else $response end),
   responseModelProvenance:(if $response == "" then $responseProvenance else "response" end),
   primaryModelProvenance:$responseProvenance,
   servingProvider:(if $provider == "" then null else $provider end),
   servingProviderProvenance:(if $provider == "" then $providerProvenance else "response" end),
   transport:$transport,billingMode:$billing,effort:$effort,outcome:$outcome,
   failureKind:(if $failureKind == "null" then null else $failureKind end),usage:$usage,
   primaryModelUsage:$identity.primaryUsage,ancillaryModelUsage:$identity.ancillaryUsage,
   identityAmbiguous:$identity.ambiguous,
   fallbackUsed:$fallback.used,fallbackProvenance:$fallback.provenance,
   attemptedModel:(if $fallback.used == false and $response != "" then $response else $fallback.attemptedModel end),
   attemptedModels:(if $fallback.used == false and $response != "" then [$response] else $fallback.attemptedModels end),
   attemptProvenance:(if $fallback.used != null and $response != "" then "response_model" else $fallback.provenance end),
   tokenProvenance:(if ([ $usage.prompt_tokens,$usage.completion_tokens,$usage.reasoning_tokens,
                           $usage.cache_read_tokens,$usage.cache_creation_tokens ] | any(. != null))
     then "native-cli" else "native-cli-unavailable" end),
   costProvenance:"subscription-no-call-cost-reported",
   benchmark:{suiteId:$suite,caseId:$caseId,role:$role,workload:$workload},
   ambiguity_resolved:true,
   ambiguity_summary:"A unique maximum positive output-token count is primary when explicit response identity is absent; ties are ambiguous."}
' > "$RECEIPT"

"$BENCH" --score --case "$CASE_ID" --output-file "$OUTPUT" \
  --receipt-file "$RECEIPT" --result-file "$RESULT" --duration-seconds "$duration"
jq --arg transport "$TRANSPORT" --arg billing "$billing" \
  --arg effort "$EFFORT" --arg outcome "$outcome" \
  '. + {transport:$transport,billingMode:$billing,effort:$effort,outcome:$outcome}' \
  "$RESULT" > "$RESULT.tmp"
mv "$RESULT.tmp" "$RESULT"
cat "$RESULT"
if [ "$status" -eq 0 ] && [ "$outcome" != success ]; then exit 1; fi
exit "$status"
