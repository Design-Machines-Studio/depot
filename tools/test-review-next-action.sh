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
BASE="$(printf 'c%.0s' {1..40})"
OLD="$(printf 'b%.0s' {1..40})"
base_input() {
  jq -cn --arg base "$BASE" --arg head "$HEAD" --arg target '42' \
    '{target:$target,baseCommit:$base,dirtyState:false,finalHead:$head,highConsequence:false,materialChangesAfterEvidence:false,
      policyAllowsNoReview:false,prFeedbackSettled:true,priorReview:null,
      requiredCoveragePassedAtFinalHead:false,requiredRenderedGap:false,
      securitySensitive:false,unresolvedFindings:0}'
}

base_input > "$TMP/quick.json"
"$SELECT" "$TMP/quick.json" > "$TMP/quick.out"
assert grep -Fxq 'Review: needed' "$TMP/quick.out"
assert grep -Fxq 'Action: Run `/dm-review quick --base-commit cccccccccccccccccccccccccccccccccccccccc --head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 42`.' "$TMP/quick.out"
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
assert grep -Fxq 'Action: Run `/dm-review-loop --max-iterations 2 --base-commit cccccccccccccccccccccccccccccccccccccccc --head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 42`.' "$TMP/findings.out"
assert grep -Fq 'reuse unaffected passing lanes' "$TMP/findings.out"

base_input | jq --arg old "$OLD" '.unresolvedFindings=2 | .highConsequence=true |
  .priorReview={head:$old,mode:"full",status:"findings"}' > "$TMP/high-consequence-findings.json"
"$SELECT" "$TMP/high-consequence-findings.json" > "$TMP/high-consequence-findings.out"
assert grep -Fxq 'Action: Run `/dm-review-loop --full --max-iterations 2 --base-commit cccccccccccccccccccccccccccccccccccccccc --head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 42`.' "$TMP/high-consequence-findings.out"

base_input | jq '.requiredRenderedGap=true' > "$TMP/visual.json"
"$SELECT" "$TMP/visual.json" > "$TMP/visual.out"
assert grep -Fxq 'Action: Run `/dm-review-visual --base-commit cccccccccccccccccccccccccccccccccccccccc --head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa`.' "$TMP/visual.out"

base_input | jq '.securitySensitive=true' > "$TMP/full.json"
"$SELECT" "$TMP/full.json" > "$TMP/full.out"
assert grep -Fxq 'Action: Run `/dm-review --base-commit cccccccccccccccccccccccccccccccccccccccc --head-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa 42`.' "$TMP/full.out"

base_input | jq '.target="PR #42"' > "$TMP/unsafe-target.json"
assert sh -c '! "$1" "$2" >/dev/null 2>&1' sh "$SELECT" "$TMP/unsafe-target.json"

base_input | jq '.baseCommit=.finalHead' > "$TMP/empty-range.json"
assert sh -c '! "$1" "$2" >/dev/null 2>&1' sh "$SELECT" "$TMP/empty-range.json"

base_input | jq '.dirtyState=true | .baseCommit=.finalHead | .unresolvedFindings=1' > "$TMP/dirty-standalone-findings.json"
"$SELECT" "$TMP/dirty-standalone-findings.json" > "$TMP/dirty-standalone-findings.out"
assert grep -Fxq 'Action: Commit the current dirty checkout at HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa to seal its repair boundary, then generate a new exact-range review-loop action.' "$TMP/dirty-standalone-findings.out"
assert grep -Fxq 'modelWork: false' "$TMP/dirty-standalone-findings.out"

base_input | jq '.dirtyState=true | .baseCommit=.finalHead | .requiredRenderedGap=true' > "$TMP/dirty-visual.json"
"$SELECT" "$TMP/dirty-visual.json" > "$TMP/dirty-visual.out"
assert grep -Fxq 'Action: Commit the current dirty checkout at HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa to seal its source boundary, then generate a new exact-range visual-review action.' "$TMP/dirty-visual.out"
assert grep -Fxq 'modelWork: false' "$TMP/dirty-visual.out"
assert grep -Fxq 'Reuse: None; dirty-state evidence is valid only in the active checkout.' "$TMP/dirty-visual.out"

base_input | jq '.dirtyState=true | .baseCommit=.finalHead' > "$TMP/dirty-complete.json"
"$SELECT" "$TMP/dirty-complete.json" > "$TMP/dirty-complete.out"
assert grep -Fxq 'Action: Complete or commit the current dirty checkout at HEAD aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa before starting another review command.' "$TMP/dirty-complete.out"
assert grep -Fxq 'modelWork: false' "$TMP/dirty-complete.out"
assert grep -Fxq 'Reuse: None; dirty-state evidence is valid only in the active checkout.' "$TMP/dirty-complete.out"

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

mkdir -p "$TMP/profile-recommendation/.dm"
git -C "$TMP/profile-recommendation" init -q
printf '%s\n' '{"allowPaidClaudeCredits":"yes","disabledCandidates":["opus"]}' > "$TMP/profile-recommendation/.dm/model-router.local.json"
jq '.codex.state="unavailable" | .claude.state="ok" | .claude.authMode="subscription" | .openrouter.state="ok"' \
  "$TMP/healthy.json" > "$TMP/profile-availability.json"
(
  cd "$TMP/profile-recommendation"
  "$RECOMMEND" --role architect --capability read-repository --capability long-context \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --availability-file "$TMP/profile-availability.json" --format markdown
) > "$TMP/invalid-profile-recommendation.md"
assert grep -Fxq -- '- Model: opus' "$TMP/invalid-profile-recommendation.md"

jq '.codex.state="unavailable" | .codex.authMode="none" |
  .claude={state:"ok",authMode:"subscription",plan:"credits-only"} |
  .openrouter.state="ok"' "$TMP/healthy.json" > "$TMP/credits-only-availability.json"
printf '%s\n' '{"allowPaidClaudeCredits":false}' > "$TMP/profile-recommendation/.dm/model-router.local.json"
(
  cd "$TMP/profile-recommendation"
  "$RECOMMEND" --role architect --capability read-repository --capability long-context \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --availability-file "$TMP/credits-only-availability.json" --format markdown
) > "$TMP/credits-disabled-recommendation.md"
assert grep -Fxq -- '- Model: qwen/qwen3.8-max' "$TMP/credits-disabled-recommendation.md"

printf '%s\n' '{"allowPaidClaudeCredits":true}' > "$TMP/profile-recommendation/.dm/model-router.local.json"
(
  cd "$TMP/profile-recommendation"
  "$RECOMMEND" --role architect --capability read-repository --capability long-context \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --availability-file "$TMP/credits-only-availability.json" --format markdown
) > "$TMP/credits-enabled-recommendation.md"
assert grep -Fxq -- '- Model: opus' "$TMP/credits-enabled-recommendation.md"
assert grep -Fq -- '- Cost: paid Claude credits;' "$TMP/credits-enabled-recommendation.md"

jq '.claude.state="unknown"' "$TMP/credits-only-availability.json" > "$TMP/credits-only-unknown-availability.json"
(
  cd "$TMP/profile-recommendation"
  "$RECOMMEND" --role architect --capability read-repository --capability long-context \
    --capability structured-output --effort medium --matrix-file "$MATRIX" \
    --availability-file "$TMP/credits-only-unknown-availability.json" --format markdown
) > "$TMP/credits-enabled-unknown-recommendation.md"
assert grep -Fxq -- '- Model: opus' "$TMP/credits-enabled-unknown-recommendation.md"
assert grep -Fq -- 'candidate attemptable' "$TMP/credits-enabled-unknown-recommendation.md"

printf 'review-next-action: %d assertions passed\n' "$pass"
