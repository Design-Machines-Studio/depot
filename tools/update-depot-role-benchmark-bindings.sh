#!/usr/bin/env bash
# Regenerate or verify repository-owned evaluator bindings for Depot role v2.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUITE="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark-suite.json"
BENCH="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/depot-role-benchmark.sh"
MODE="${1:---update}"

if [ "$MODE" != --update ] && [ "$MODE" != --check ]; then
  printf 'usage: %s [--update|--check]\n' "$0" >&2
  exit 2
fi

work="$(mktemp -d "${TMPDIR:-/tmp}/depot-benchmark-bindings.XXXXXX")"
trap 'rm -rf -- "$work"' EXIT
printf '{}\n' > "$work/cases.json"

while IFS= read -r case_id; do
  run="$work/$case_id"
  mkdir -p "$run"
  jq --arg id "$case_id" '.cases[] | select(.id == $id) | .expected' \
    "$SUITE" > "$run/output.json"
  role="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .role' "$SUITE")"
  workload="$(jq -r --arg id "$case_id" '.cases[] | select(.id == $id) | .workload' "$SUITE")"
  jq -n --arg caseId "$case_id" --arg role "$role" --arg workload "$workload" '
    {requestedModel:"fixture/exact",modelCandidates:["fixture/exact"],responseModel:"fixture/exact",
     responseModelProvenance:"response",servingProvider:"fixture-provider",servingProviderProvenance:"response",
     transport:"openrouter",outcome:"success",fallbackUsed:false,attemptedModel:"fixture/exact",
     attemptedModels:["fixture/exact"],attemptProvenance:"response_model",usage:{cost:0},
     benchmark:{suiteId:"depot-role-v2",caseId:$caseId,role:$role,workload:$workload}}' \
    > "$run/receipt.json"
  "$BENCH" --score --case "$case_id" --output-file "$run/output.json" \
    --receipt-file "$run/receipt.json" --result-file "$run/result.json" \
    --duration-seconds 1 >/dev/null
  jq --arg id "$case_id" '
    .evidenceBindings
    | {caseRevision:.caseRevision.actual,caseDigest:.caseDigest.actual,
       promptRevision:.promptRevision.actual,promptDigest:.promptDigest.actual,
       scorerRevision:.scorerRevision.actual,scorerDigest:.scorerDigest.actual}
    | {($id):.}' "$run/result.json" > "$run/one.json"
  jq -s '.[0] * .[1]' "$work/cases.json" "$run/one.json" > "$run/next.json"
  mv "$run/next.json" "$work/cases.json"
done < <(jq -r '.cases[].id' "$SUITE")

last="$(jq -r '.cases[-1].id' "$SUITE")"
jq -n --slurpfile cases "$work/cases.json" --slurpfile result "$work/$last/result.json" '
  {suiteRevision:$result[0].evidenceBindings.suiteRevision.actual,
   suiteDigest:$result[0].evidenceBindings.suiteDigest.actual,
   normalizerRevision:$result[0].evidenceBindings.normalizerRevision.actual,
   normalizerDigest:$result[0].evidenceBindings.normalizerDigest.actual,
   cases:$cases[0]}' > "$work/bindings.json"
jq --slurpfile bindings "$work/bindings.json" '.bindings = $bindings[0]' \
  "$SUITE" > "$work/suite.json"

if [ "$MODE" = --check ]; then
  if ! cmp -s "$SUITE" "$work/suite.json"; then
    printf 'Depot role benchmark evaluator bindings are stale; run %s --update\n' "$0" >&2
    exit 1
  fi
  printf 'Depot role benchmark evaluator bindings are current\n'
else
  mv "$work/suite.json" "$SUITE"
  printf 'Updated Depot role benchmark evaluator bindings\n'
fi
