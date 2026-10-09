#!/usr/bin/env bash
# operator-handoff.sh -- deterministic designer-facing readiness handoff.
#
# Projects validated final-head facts from the workflow owner into exactly one
# of: Ready to merge, UI check needed, Not ready. It names one designer action
# and links detail. It never asks the designer to run a review command or to
# inspect backend code. review-next-action.sh stays the internal selector.
#
# Coverage facts come from the Kernel preserve-review-evidence producer (the
# publication wrapper fills them); narrative verdicts and passing CI never
# substitute for them.
#
# Usage:
#   operator-handoff.sh [--gate candidate|merge] INPUT.json
#
# --gate candidate  exit 3 unless only pending checks, PR feedback or designer
#                   UI acceptance remain (draft PR checkpoint).
# --gate merge      exit 3 unless the status is Ready to merge.
# The handoff is printed to stdout in every non-usage case.
#
# Dependencies: jq.
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH

usage() { printf '%s\n' 'usage: operator-handoff.sh [--gate candidate|merge] INPUT.json' >&2; exit 2; }

GATE=""
if [ "${1:-}" = --gate ]; then
  [ "$#" -ge 2 ] || usage
  case "$2" in candidate|merge) GATE="$2" ;; *) usage ;; esac
  shift 2
fi
[ "$#" -eq 1 ] || usage
INPUT="$1"
[ -f "$INPUT" ] && [ -r "$INPUT" ] && [ ! -L "$INPUT" ] || usage

SHA='^[0-9a-f]{40}([0-9a-f]{24})?$'
jq -e --arg sha "$SHA" '
  def str: type == "string" and length > 0 and length <= 2048 and (test("[\u0000-\u001f\u007f]") | not);
  def sha: type == "string" and test($sha);
  type == "object" and
  ((keys - ["workspace"]) | sort) == (["checks","coverage","detail","dirty","feedbackSettled","finalHead","findings","lanes","target","ui"] | sort) and
  (.target | str) and (.detail | str) and (.finalHead | sha) and
  (.workspace == null or (.workspace | type=="object" and (keys|sort)==(["clean","paths","nextAction"]|sort) and
    (.clean|type=="boolean") and (.paths|type=="array" and all(.[]; str)) and
    (.nextAction==null or (.nextAction|str)) and
    (if .clean then (.paths|length)==0 and .nextAction==null else (.paths|length)>0 and .nextAction!=null end))) and
  (.dirty | type == "boolean") and (.feedbackSettled | type == "boolean") and
  (.coverage | type == "object" and (keys | sort) == (["evidence","gaps","head","requiredBrowserCases","status"] | sort)) and
  (.coverage.status | IN("complete","incomplete","missing")) and
  (.coverage.head == null or (.coverage.head | sha)) and
  (.coverage.gaps | type == "array" and all(.[]; str)) and
  (.coverage.requiredBrowserCases | type == "array" and all(.[]; str)) and
  (.coverage.evidence == null or (.coverage.evidence | str)) and
  (.lanes | type == "array" and
    ([.[].area] | sort) == (["Architecture","Fixture/distribution","Security","Simplicity","Testing"] | sort) and
    all(.[]; type == "object" and (keys | sort) == (["area","evidence","note","status"] | sort) and
      (.status | IN("covered","omitted","exempt")) and
      (.note == null or (.note | str)) and (.evidence == null or (.evidence | str)) and
      (.status != "exempt" or .note != null) and (.status != "covered" or .evidence != null))) and
  (.findings | type == "array" and all(.[]; type == "object" and (keys | sort) == (["location","problem","severity"] | sort) and
    (.severity | IN("P1","P2","P3")) and (.location | str) and (.problem | str))) and
  (.checks | type == "array" and all(.[]; type == "object" and ((keys - ["required"]) | sort) == (["link","name","stage","status"] | sort) and
    (.required==null or (.required|type=="boolean")) and
    (.stage | IN("candidate","pr")) and
    (.name | str) and (.status | IN("pass","pending","fail","skipped","not_applicable")) and (.link == null or (.link | str)) and
    (if (.status|IN("skipped","not_applicable")) then .stage=="pr" and .link!=null else true end))) and
  (.ui | type == "object" and (keys | sort) == (["acceptance","changed","preview","tasks"] | sort) and
    (.changed | type == "boolean") and (.preview == null or (.preview | str)) and
    (.tasks | type == "array" and all(.[]; str)) and
    (.acceptance == null or (.acceptance | type == "object" and (keys | sort) == (["head","unchangedSince"] | sort) and
      (.head | sha) and (.unchangedSince | type == "boolean"))))
' "$INPUT" >/dev/null || exit 2

# Gap kinds deferrable at the draft checkpoint: pending, feedback.
RESULT="$(jq -r '
  def short: .[0:12];
  . as $in |
  [
    (if .workspace != null and (.workspace.clean | not) then {kind:"workspace",text:("Temporary files remain at " + (.workspace.paths|join(", ")) + ".")} else empty end),
    (if .dirty then {kind:"source", text:"The checkout has uncommitted changes at \(.finalHead | short). The agent must commit the repairs and remove its temporary files."} else empty end),
    (if .coverage.status == "missing" or .coverage.head == null then {kind:"source", text:"No review evidence exists for head \(.finalHead | short)."}
     elif .coverage.head != .finalHead then {kind:"source", text:"Review evidence is for \(.coverage.head | short), not the current head \(.finalHead | short)."}
     else empty end),
    (if .coverage.status == "incomplete" or (.coverage.gaps | length) > 0 then {kind:"coverage", text:"Review coverage is incomplete: \(if (.coverage.gaps | length) > 0 then (.coverage.gaps | join(", ")) else "the required review did not finish" end)."} else empty end),
    (if .coverage.status == "complete" and .coverage.evidence == null then {kind:"coverage", text:"The retained review evidence link is missing."} else empty end),
    (.lanes[] | select(.status == "omitted") | {kind:"coverage", text:"\(.area) review did not run."}),
    (.findings[] | {kind:"finding", text:"\(.severity) \(.location): \(.problem)"}),
    (if any(.checks[]; .stage=="candidate") | not then {kind:"candidate",text:"Candidate verification results are missing."} else empty end),
    (.checks[] | select((.status|IN("skipped","not_applicable")) and .required!=false) | {kind:"check", text:"Required check \(.name) is \(.status); it has not passed."}),
    (.checks[] | select(.status == "fail") | {kind:"check", text:"\(.name) failed."}),
    (.checks[] | select(.status == "pending") | {kind:(if .stage == "pr" then "pending" else "check" end), text:"\(.name) is still running."}),
    (if .feedbackSettled | not then {kind:"feedback", text:"PR feedback is not settled yet."} else empty end),
    (if .ui.changed and .ui.preview == null then {kind:"ui", text:"The UI changed but no preview link is available."} else empty end),
    (if .ui.changed and (.ui.tasks | length) == 0 then {kind:"ui", text:"The UI changed but no UI check tasks are listed."} else empty end)
  ] as $gaps |
  (.ui.changed and (.ui.acceptance == null or (.ui.acceptance.head != .finalHead and (.ui.acceptance.unchangedSince | not)))) as $needs_ui |
  (if ($gaps | length) > 0 then "Not ready" elif $needs_ui then "UI check needed" else "Ready to merge" end) as $status |
  {
    status: $status,
    candidate_blocked: ([$gaps[] | select(.kind != "pending" and .kind != "feedback")] | length > 0),
    text: ([
      "## \($status)", "",
      (if $status == "Ready to merge" then "Required automated review and checks passed at \(.finalHead | short)."
       elif $status == "UI check needed" then "Automated checks passed at \(.finalHead | short). The UI change needs your eyes in the browser."
       else "Work remains before this can merge. The agent handles the gaps below." end), "",
      "Workspace: " + (if (.dirty|not) and (.workspace==null or .workspace.clean) then "clean" else "Not ready" end), "",
      "**Your action:** " + (if $status == "Ready to merge" then "Merge \(.target)."
        elif $status == "UI check needed" then "Open the preview at \(.ui.preview) and check the tasks below. Tell the agent what you accept or what to change."
        else "None yet. You will get a new handoff when it is ready." end),
      (if $status=="Not ready" then "", "**Agent next action:** " +
        (if any($gaps[]; .kind=="candidate") then "Run the required source/build/verification checks for this head and record their results."
         elif .workspace!=null and (.workspace.clean|not) then .workspace.nextAction
         else "Resolve the remaining gaps below and check readiness again at this head." end) else empty end),
      (if $status == "UI check needed" then ("", "### UI check", (.ui.tasks | to_entries[] | "\(.key + 1). \(.value)")) else empty end),
      "", "### Completed",
      ([
        (if .coverage.status == "complete" and .coverage.head == .finalHead and (.dirty | not) then "- Review coverage complete at \(.finalHead | short)." else empty end),
        (if .coverage.status == "complete" and .coverage.head == .finalHead and (.coverage.requiredBrowserCases | length) > 0 then "- Browser checks passed: \(.coverage.requiredBrowserCases | join(", "))." else empty end),
        (.checks[] | select(.status == "pass") | "- \(.name) passed."),
        (.checks[] | select(.required==false and (.status|IN("skipped","not_applicable"))) | "- \(.name): \(if .status=="skipped" then "optional check skipped" else "not applicable (no required PR checks)" end)."),
        (if .feedbackSettled then "- PR feedback settled." else empty end),
        (if .ui.changed and ($needs_ui | not) then "- Designer UI acceptance recorded." else empty end)
      ] | if length == 0 then ["- None yet."] else . end | .[]),
      "", "### Remaining",
      (if ($gaps | length) == 0 and ($needs_ui | not) then "- None."
       else ($gaps[] | "- \(.text)"), (if $needs_ui then "- Designer UI acceptance at \(.finalHead | short)." else empty end) end),
      "", "### Review coverage", "",
      "| Area | Status | Evidence |", "|------|--------|----------|",
      (.lanes | sort_by(.area)[] | "| \(.area) | \(if .status == "covered" then "Covered" elif .status == "exempt" then "Exempt: \(.note)" else "Not run\(if .note then ": \(.note)" else "" end)" end) | \(.evidence // "--") |"),
      "", "### Detail", "",
      "Full report: \(.detail)",
      (if .coverage.evidence then "Retained evidence: \(.coverage.evidence)" else empty end)
    ] | join("\n"))
  } | "\(.status)\t\(.candidate_blocked)\n\(.text)"
' "$INPUT")"

STATUS="$(printf '%s\n' "$RESULT" | head -n 1 | cut -f 1)"
CANDIDATE_BLOCKED="$(printf '%s\n' "$RESULT" | head -n 1 | cut -f 2)"
printf '%s\n' "$RESULT" | tail -n +2

case "$GATE" in
  candidate) [ "$CANDIDATE_BLOCKED" = false ] || exit 3 ;;
  merge) [ "$STATUS" = "Ready to merge" ] || exit 3 ;;
esac
exit 0
