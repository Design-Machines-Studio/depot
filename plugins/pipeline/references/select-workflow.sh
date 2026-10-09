#!/usr/bin/env bash
# Project the existing routing policy from a source-backed assessment. No dispatch.
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ "$#" -eq 1 ] && [ -f "$1" ] && [ -r "$1" ] && [ ! -L "$1" ] || exit 2
jq -e '
  type == "object" and
  (keys | sort) == (["acceptanceClear","designSettled","consequence","reversibility","coordination","existingPattern","verificationDefined","unansweredQuestions","explicitFull","reviewRequired","securitySensitive","minimumMode","rationale"] | sort) and
  all([.acceptanceClear,.designSettled,.existingPattern,.verificationDefined,.explicitFull,.reviewRequired,.securitySensitive][]; type == "boolean") and
  (.consequence | IN("low","medium","high")) and
  (.reversibility | IN("easy","difficult")) and
  (.coordination | IN("single-pass","ordered")) and
  (.minimumMode | IN("direct","lean","full")) and
  (.unansweredQuestions | type == "array" and all(.[]; type == "string" and length > 0)) and
  (.rationale | type == "string" and length > 0)
' "$1" >/dev/null || exit 2
jq -n --slurpfile assessment "$1" --slurpfile policy "$DIR/routing-policy.json" '
  $assessment[0] as $a | $policy[0].workflowSelection as $p |
  ($a.acceptanceClear and $a.designSettled and $a.verificationDefined) as $clear |
  ($clear and ($a.unansweredQuestions | length == 0)) as $settled |
  (if $a.explicitFull or $a.minimumMode == "full" or ($clear | not) or
      $a.consequence == "high" or $a.securitySensitive or $a.reversibility == "difficult" or
      $a.coordination == "ordered" then "full"
    elif $a.minimumMode == "lean" or $a.consequence == "medium" or
      ($a.unansweredQuestions | length > 0) or ($a.existingPattern | not) then "lean"
    else "direct" end) as $mode |
  ($settled and $a.existingPattern and $a.consequence == "low" and
    ($a.securitySensitive | not) and $a.reversibility == "easy" and
    $a.coordination == "single-pass") as $fast |
  {mode:$mode, reason:$a.rationale,
    executorRole:(if $fast then "builder-fast" else "builder-deep" end),
    executorEffort:(if $fast then "medium" else "high" end),
    stages:($p.paths[$mode].stages | map(select(. != "targeted-research" or
      ($a.unansweredQuestions | length > 0) or $a.explicitFull))),
    researchQuestions:$a.unansweredQuestions,
    independentReview:($a.reviewRequired or $mode != "direct"),
    verification:"required", reuseCompletedWork:true,
    escalationOnly:true}
'
