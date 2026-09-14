#!/usr/bin/env bash
# Deterministic terminal review-action selector. Model recommendation remains
# model-router-owned and is requested only when this emits modelWork=true.
set -euo pipefail

[ "$#" -eq 1 ] || { printf '%s\n' 'usage: review-next-action INPUT.json' >&2; exit 2; }
INPUT="$1"
[ -r "$INPUT" ] && [ ! -L "$INPUT" ] || exit 2

jq -e '
  type == "object" and
  (keys | sort) == (["finalHead","highConsequence","materialChangesAfterEvidence","policyAllowsNoReview","prFeedbackSettled","priorReview","requiredCoveragePassedAtFinalHead","requiredRenderedGap","securitySensitive","target","unresolvedFindings"] | sort) and
  (.target | type == "string" and test("^[A-Za-z0-9#][A-Za-z0-9#:/._@ -]{0,255}$")) and
  (.finalHead | type == "string" and test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
  (.unresolvedFindings | type == "number" and . >= 0 and floor == .) and
  all([.highConsequence,.materialChangesAfterEvidence,.policyAllowsNoReview,.prFeedbackSettled,.requiredCoveragePassedAtFinalHead,.requiredRenderedGap,.securitySensitive][]; type == "boolean") and
  (.priorReview == null or ((.priorReview | type) == "object" and
    (.priorReview | keys | sort) == (["head","mode","status"] | sort) and
    (.priorReview.head | type == "string" and test("^[0-9a-f]{40}([0-9a-f]{24})?$")) and
    (.priorReview.mode | IN("quick","full","visual","affected-lanes")) and
    (.priorReview.status | IN("passed","incomplete","findings"))))
' "$INPUT" >/dev/null || exit 2

TARGET="$(jq -r '.target' "$INPUT")"
FINAL_HEAD="$(jq -r '.finalHead' "$INPUT")"
UNRESOLVED="$(jq -r '.unresolvedFindings' "$INPUT")"
RENDERED_GAP="$(jq -r '.requiredRenderedGap' "$INPUT")"
COVERED="$(jq -r '.requiredCoveragePassedAtFinalHead' "$INPUT")"
MATERIAL="$(jq -r '.materialChangesAfterEvidence' "$INPUT")"
FEEDBACK="$(jq -r '.prFeedbackSettled' "$INPUT")"
POLICY_NO_REVIEW="$(jq -r '.policyAllowsNoReview' "$INPUT")"
SENSITIVE="$(jq -r '.securitySensitive' "$INPUT")"
CONSEQUENCE="$(jq -r '.highConsequence' "$INPUT")"
PRIOR_HEAD="$(jq -r '.priorReview.head // ""' "$INPUT")"
PRIOR_STATUS="$(jq -r '.priorReview.status // ""' "$INPUT")"

review=needed
model_work=true
reuse='None.'
if [ "$UNRESOLVED" -gt 0 ]; then
  action="/dm-review-loop --max-iterations 2 $TARGET"
  why="Retained findings require one repair batch and an affected-lane recheck."
  [ -n "$PRIOR_HEAD" ] && reuse="Prior review at $PRIOR_HEAD; reuse unaffected passing lanes."
elif [ "$RENDERED_GAP" = true ]; then
  action="/dm-review-visual $TARGET"
  why="Required rendered evidence is the only remaining review gap."
  [ -n "$PRIOR_HEAD" ] && reuse="Prior source review at $PRIOR_HEAD; reuse its unaffected lanes."
elif [ "$COVERED" = true ] && [ "$MATERIAL" = false ] && [ "$FEEDBACK" = true ] &&
     [ "$PRIOR_HEAD" = "$FINAL_HEAD" ] && [ "$PRIOR_STATUS" = passed ]; then
  review='already satisfied'
  model_work=false
  action="Proceed with the next repository action for $TARGET."
  why="Required review and feedback coverage already passed at the final head."
  reuse="All required evidence bound to $FINAL_HEAD."
elif [ "$POLICY_NO_REVIEW" = true ] && [ "$FEEDBACK" = true ] && [ "$SENSITIVE" = false ] && [ "$CONSEQUENCE" = false ]; then
  review='not warranted'
  model_work=false
  action="Run the repository's mandatory checks for $TARGET."
  why="Repository policy permits this narrow mechanical or documentation change without another model review."
else
  if [ "$SENSITIVE" = true ] || [ "$CONSEQUENCE" = true ]; then
    action="/dm-review $TARGET"
    why="The uncovered final diff is security-sensitive or high-consequence."
  else
    action="/dm-review quick $TARGET"
    why="Ordinary implementation lacks review coverage at the final head."
  fi
  [ -n "$PRIOR_HEAD" ] && reuse="Prior evidence at $PRIOR_HEAD remains reusable only for unaffected coverage."
fi

printf 'Review: %s\n' "$review"
printf 'Action: %s\n' "$action"
printf 'Why: %s\n' "$why"
printf 'Reuse: %s\n' "$reuse"
printf 'modelWork: %s\n' "$model_work"
if [ "$model_work" = true ]; then
  printf 'recommendationRole: review-coordinator\n'
  printf 'recommendationCapabilities: read-repository,long-context,structured-output\n'
  printf 'recommendationEffort: medium\n'
fi
