#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SELECT="$ROOT/plugins/dm-review/skills/review/references/review-next-action.sh"
RECOMMEND="$ROOT/plugins/model-router/skills/model-router/references/operator-recommendation.sh"
MATRIX="$ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/review-next-action.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }

HEAD="$(printf 'a%.0s' {1..40})"
OLD="$(printf 'b%.0s' {1..40})"
base_input() {
  jq -cn --arg head "$HEAD" --arg target 'PR #42 at aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' \
    '{target:$target,finalHead:$head,highConsequence:false,materialChangesAfterEvidence:false,
      policyAllowsNoReview:false,prFeedbackSettled:true,priorReview:null,
      requiredCoveragePassedAtFinalHead:false,requiredRenderedGap:false,
      securitySensitive:false,unresolvedFindings:0}'
}

base_input > "$TMP/quick.json"
"$SELECT" "$TMP/quick.json" > "$TMP/quick.out"
assert grep -Fxq 'Review: needed' "$TMP/quick.out"
assert grep -Fxq 'Action: /dm-review quick PR #42 at aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$TMP/quick.out"
assert grep -Fxq 'recommendationRole: review-coordinator' "$TMP/quick.out"

base_input | jq --arg head "$HEAD" '.requiredCoveragePassedAtFinalHead=true |
  .priorReview={head:$head,mode:"quick",status:"passed"}' > "$TMP/satisfied.json"
"$SELECT" "$TMP/satisfied.json" > "$TMP/satisfied.out"
assert grep -Fxq 'Review: already satisfied' "$TMP/satisfied.out"
assert grep -Fxq 'modelWork: false' "$TMP/satisfied.out"
assert sh -c '! grep -q "recommendationRole" "$1"' sh "$TMP/satisfied.out"

base_input | jq '.policyAllowsNoReview=true' > "$TMP/not-warranted.json"
"$SELECT" "$TMP/not-warranted.json" > "$TMP/not-warranted.out"
assert grep -Fxq 'Review: not warranted' "$TMP/not-warranted.out"

base_input | jq '.policyAllowsNoReview=true | .prFeedbackSettled=false' > "$TMP/unsettled-feedback.json"
"$SELECT" "$TMP/unsettled-feedback.json" > "$TMP/unsettled-feedback.out"
assert grep -Fxq 'Review: needed' "$TMP/unsettled-feedback.out"

base_input | jq --arg old "$OLD" '.unresolvedFindings=2 |
  .priorReview={head:$old,mode:"full",status:"findings"}' > "$TMP/findings.json"
"$SELECT" "$TMP/findings.json" > "$TMP/findings.out"
assert grep -Fxq 'Action: /dm-review-loop --max-iterations 2 PR #42 at aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$TMP/findings.out"
assert grep -Fq 'reuse unaffected passing lanes' "$TMP/findings.out"

base_input | jq '.requiredRenderedGap=true' > "$TMP/visual.json"
"$SELECT" "$TMP/visual.json" > "$TMP/visual.out"
assert grep -Fxq 'Action: /dm-review-visual PR #42 at aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$TMP/visual.out"

base_input | jq '.securitySensitive=true' > "$TMP/full.json"
"$SELECT" "$TMP/full.json" > "$TMP/full.out"
assert grep -Fxq 'Action: /dm-review PR #42 at aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' "$TMP/full.out"

cat > "$TMP/healthy.json" <<'JSON'
{"codex":{"state":"ok","authMode":"subscription"},"claude":{"state":"unavailable","authMode":"none"},"openrouter":{"state":"ok"}}
JSON
"$RECOMMEND" --role review-coordinator --capability read-repository \
  --capability long-context --capability structured-output --effort medium \
  --matrix-file "$MATRIX" --availability-file "$TMP/healthy.json" \
  --format markdown > "$TMP/recommendation.md"
assert grep -Fxq -- '- Model: gpt-5.6-sol' "$TMP/recommendation.md"
assert grep -Fxq -- '- Harness/rail: Codex' "$TMP/recommendation.md"
assert grep -Fxq -- '- Effort: medium' "$TMP/recommendation.md"
assert test "$(grep -c '^- Fallback:' "$TMP/recommendation.md")" -eq 1
assert grep -Fq -- '- Matrix evidence:' "$TMP/recommendation.md"

printf 'review-next-action: %d assertions passed\n' "$pass"
