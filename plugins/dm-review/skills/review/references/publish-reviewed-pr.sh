#!/usr/bin/env bash
# Host resolves WORKFLOW_KERNEL once from its trusted dependency bundle.
# producer-input is a closed map of preserve-review-evidence file arguments.
# readiness-input contains the explicit current owner and handoff facts.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/review-owner-context.sh"
OPERATION= REPO= RUN_ROOT= PRODUCER= READINESS= PR=
declare -A SEEN=()
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] && [ -z "${SEEN[$1]:-}" ] || exit 2
  SEEN[$1]=1
  case "$1" in
    --operation) OPERATION="$2" ;; --repository-root) REPO="$2" ;;
    --run-root) RUN_ROOT="$2" ;; --producer-input) PRODUCER="$2" ;;
    --readiness-input) READINESS="$2" ;; --pr) PR="$2" ;;
    *) exit 2 ;;
  esac
  shift 2
done
case "$OPERATION:$PR" in create:) ;; ready:https://github.com/*/pull/*) ;; *) exit 2 ;; esac
for file in "$PRODUCER" "$READINESS"; do
  review_safe_path "$file"
  [ -f "$file" ] && [ -r "$file" ] && [ "$(stat -c %h -- "$file")" = 1 ] || review_refuse 'missing or unsafe publication input'
done
jq -e 'type=="object" and (keys|sort)==(["owner","readiness","uiNonImpact"]|sort)' "$READINESS" >/dev/null || exit 2
OWNER="$(jq -c .owner "$READINESS")"
review_owner_validate "$OWNER" "$REPO"
[ "$RUN_ROOT" = "$(jq -r .run_root <<< "$OWNER")" ] || review_refuse 'current run root mismatch'
RUN="$(jq -r .run_id <<< "$OWNER")"
REPOSITORY="$(jq -r .repository <<< "$OWNER")"
if [ "$OPERATION" = ready ]; then
  [[ "$PR" =~ ^https://github.com/$REPOSITORY/pull/[0-9]+$ ]] || review_refuse 'foreign PR'
fi
FIELDS=(request receipts lane-receipts raw-lane-outputs raw-findings decisions private-router-directory report)
jq -e --argjson fields "$(printf '%s\n' "${FIELDS[@]}" | jq -R . | jq -s .)" '
  type=="object" and (keys|sort)==($fields|sort) and
  all(.[]; type=="string" and startswith("/") and length<=4096 and (test("[\u0000-\u001f\u007f]")|not))
' "$PRODUCER" >/dev/null || exit 2
ARGV=(preserve-review-evidence --run-root "$RUN_ROOT" --repository-root "$REPO")
for field in "${FIELDS[@]}"; do
  value="$(jq -r --arg field "$field" '.[$field]' "$PRODUCER")"
  review_safe_path "$value"
  # Report may live in the reviewed checkout; every other input is run-owned.
  if [ "$field" != report ]; then
    [[ "$value" = "$RUN_ROOT/"* ]] || review_refuse 'foreign producer file'
  else
    [[ "$value" = "$RUN_ROOT/"* || "$value" = "$REPO/"* ]] || review_refuse 'foreign report'
  fi
  ARGV+=("--$field" "$value")
done
REQUEST="$(jq -r .request "$PRODUCER")"
jq -e --arg run "$RUN" '.run_id==$run' "$REQUEST" >/dev/null || review_refuse 'request owner mismatch'
[ -n "${WORKFLOW_KERNEL:-}" ] && [ -x "$WORKFLOW_KERNEL" ] || review_refuse 'trusted Kernel launcher unavailable'
review_safe_path "$WORKFLOW_KERNEL"
if [[ "$HERE" = */plugins/dm-review/skills/review/references ]]; then
  DEPOT_ROOT="${HERE%/plugins/dm-review/skills/review/references}"
  [ "$WORKFLOW_KERNEL" = "$DEPOT_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh" ] || review_refuse 'foreign source Kernel launcher'
fi
# Resolve no executable from the reviewed project or PATH. The host supplies
# the exact dependency launcher; its own resolver validates the runtime bundle.
[[ "$WORKFLOW_KERNEL" = */workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh ||
   "$WORKFLOW_KERNEL" = */workflow-kernel/*/skills/workflow-kernel/references/workflow-kernel-launcher.sh ]] || review_refuse 'invalid Kernel launcher'
TEMP="$(mktemp -d "${TMPDIR:-/tmp}/publish-reviewed-pr.XXXXXX")"
trap 'rm -rf -- "$TEMP"' EXIT
# This is the coverage authority. No gh call occurs before complete production
# evidence succeeds, even if the caller says CLEAN, green or accepted.
"$WORKFLOW_KERNEL" "${ARGV[@]}" > "$TEMP/production.json" || review_refuse 'required producer validation failed'
jq -e '.status=="complete"' "$TEMP/production.json" >/dev/null || review_refuse 'required producer coverage incomplete'
DECISIONS="$(jq -r .decisions "$PRODUCER")"
jq -e 'all(.decisions[]; .finding_disposition!="retained")' "$DECISIONS" >/dev/null || review_refuse 'unresolved retained finding in producer evidence'
HEAD="$(git -C "$REPO" rev-parse HEAD)"
[ -z "$(git -C "$REPO" status --porcelain)" ] || review_refuse 'dirty candidate source'
jq -e --arg head "$HEAD" '.readiness.finalHead==$head' "$READINESS" >/dev/null || review_refuse 'caller readiness facts are stale'
EVIDENCE="$(jq -r .evidence_path "$TEMP/production.json")"
jq -e --arg repository "github.com/$REPOSITORY" --arg head "$HEAD" '.source_repository==$repository and .source_head==$head' "$REQUEST" >/dev/null || review_refuse 'stale candidate evidence'
jq --arg head "$HEAD" --arg evidence "$EVIDENCE" --slurpfile request "$REQUEST" '
  .readiness | .finalHead=$head | .dirty=false |
  .coverage={status:"complete",head:$head,gaps:[],requiredBrowserCases:$request[0].required_browser_cases,evidence:$evidence}
' "$READINESS" > "$TEMP/handoff.json"
if [ "$OPERATION" = create ]; then
  jq '.feedbackSettled=false' "$TEMP/handoff.json" > "$TEMP/update.json"
  mv -- "$TEMP/update.json" "$TEMP/handoff.json"
fi
# Designer acceptance is owner input. A changed head needs an explicit bounded
# non-impact proof plus the actual unchanged UI paths, never a true flag alone.
if jq -e '.ui.acceptance!=null and .ui.acceptance.head!=.finalHead' "$TEMP/handoff.json" >/dev/null; then
  ACCEPTED="$(jq -r .ui.acceptance.head "$TEMP/handoff.json")"
  jq -e --arg from "$ACCEPTED" --arg to "$HEAD" '.uiNonImpact | type=="object" and
    (keys|sort)==(["fromHead","toHead","paths","evidence"]|sort) and .fromHead==$from and .toHead==$to and
    (.paths|type=="array" and length>0 and all(.[];type=="string" and test("^[A-Za-z0-9_./-]+$") and (split("/")|all(.[];. != ".." and . != "")))) and
    (.evidence|type=="string")' "$READINESS" >/dev/null || review_refuse 'designer acceptance is stale: missing UI non-impact proof'
  PROOF="$(jq -r .uiNonImpact.evidence "$READINESS")"
  review_safe_path "$PROOF"
  [[ "$PROOF" = "$RUN_ROOT/"* ]] && [ -f "$PROOF" ] || review_refuse 'missing UI non-impact evidence'
  jq -e --slurpfile input "$READINESS" '(keys|sort)==(["fromHead","toHead","paths","reason"]|sort) and
    .fromHead==$input[0].uiNonImpact.fromHead and .toHead==$input[0].uiNonImpact.toHead and
    .paths==$input[0].uiNonImpact.paths and (.reason|type=="string" and length>0)' "$PROOF" >/dev/null || review_refuse 'invalid source-bound UI non-impact judgment'
  mapfile -t UI_PATHS < <(jq -r '.uiNonImpact.paths[]' "$READINESS")
  git -C "$REPO" merge-base --is-ancestor "$ACCEPTED" "$HEAD" || review_refuse 'designer acceptance ancestry mismatch'
  git -C "$REPO" diff --quiet "$ACCEPTED" "$HEAD" -- "${UI_PATHS[@]}" || review_refuse 'UI changed since designer acceptance'
  jq '.ui.acceptance.unchangedSince=true' "$TEMP/handoff.json" > "$TEMP/update.json"
  mv -- "$TEMP/update.json" "$TEMP/handoff.json"
fi
"$HERE/operator-handoff.sh" --gate candidate "$TEMP/handoff.json" > "$TEMP/handoff.md" || { cat "$TEMP/handoff.md"; exit 3; }
BRANCH="$(git -C "$REPO" symbolic-ref --quiet --short HEAD)" || review_refuse 'detached candidate head'
git -C "$REPO" check-ref-format "refs/heads/$BRANCH" || exit 2
REMOTE_HEAD="$(git -C "$REPO" ls-remote --exit-code origin "refs/heads/$BRANCH" | awk '{print $1}')" || review_refuse 'remote candidate unavailable'
[ "$REMOTE_HEAD" = "$HEAD" ] || review_refuse 'local and remote candidate heads differ'
if [ "$OPERATION" = ready ]; then
  gh pr view "$PR" --repo "$REPOSITORY" --json headRefOid,headRefName,state,isDraft,reviewDecision > "$TEMP/pr.json"
  jq -e --arg head "$HEAD" --arg branch "$BRANCH" '.headRefOid==$head and .headRefName==$branch and .state=="OPEN" and .isDraft==true' "$TEMP/pr.json" >/dev/null || review_refuse 'actual PR head/state differs'
  # gh returns nonzero for pending/failed checks; keep that a visible blocker.
  gh pr checks "$PR" --repo "$REPOSITORY" --json name,bucket,link > "$TEMP/checks.json" || review_refuse 'actual PR checks failed or pending'
  jq -e --slurpfile actual "$TEMP/checks.json" 'all(.checks[]|select(.stage=="pr"); .name as $name | any($actual[0][]; .name==$name))' "$TEMP/handoff.json" >/dev/null || review_refuse 'required PR check absent from actual PR'
  OWNER_NAME="${REPOSITORY%/*}"; REPO_NAME="${REPOSITORY#*/}"; NUMBER="${PR##*/}"
  gh api graphql -f query='query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){headRefOid reviewThreads(first:100){nodes{isResolved} pageInfo{hasNextPage}}}}}' \
    -f owner="$OWNER_NAME" -f name="$REPO_NAME" -F number="$NUMBER" > "$TEMP/feedback.json"
  jq -e --arg head "$HEAD" '.data.repository.pullRequest | .headRefOid==$head and .reviewThreads.pageInfo.hasNextPage==false and all(.reviewThreads.nodes[];.isResolved==true)' "$TEMP/feedback.json" >/dev/null || review_refuse 'actual PR feedback unsettled or incomplete'
  jq -e '.reviewDecision!="CHANGES_REQUESTED"' "$TEMP/pr.json" >/dev/null || review_refuse 'changes requested on PR'
  jq --slurpfile checks "$TEMP/checks.json" '.checks += ($checks[0] | map({name:.name,link:.link,stage:"pr",status:(if .bucket=="pass" then "pass" elif .bucket=="pending" then "pending" else "fail" end)}))' "$TEMP/handoff.json" > "$TEMP/update.json"
  mv -- "$TEMP/update.json" "$TEMP/handoff.json"
  "$HERE/operator-handoff.sh" --gate merge "$TEMP/handoff.json" > "$TEMP/handoff.md" || { cat "$TEMP/handoff.md"; exit 3; }
fi
# Recheck source/remote immediately before the only mutation.
[ "$(git -C "$REPO" rev-parse HEAD)" = "$HEAD" ] && [ -z "$(git -C "$REPO" status --porcelain)" ] || review_refuse 'candidate changed during publication'
[ "$(git -C "$REPO" ls-remote --exit-code origin "refs/heads/$BRANCH" | awk '{print $1}')" = "$HEAD" ] || review_refuse 'remote candidate changed during publication'
if [ "$OPERATION" = create ]; then
  gh pr create --repo "$REPOSITORY" --head "$BRANCH" --draft --title "$(jq -r .target "$TEMP/handoff.json")" --body-file "$TEMP/handoff.md"
else
  gh pr view "$PR" --repo "$REPOSITORY" --json headRefOid > "$TEMP/final-pr.json"
  jq -e --arg head "$HEAD" '.headRefOid==$head' "$TEMP/final-pr.json" >/dev/null || review_refuse 'actual PR head changed during publication'
  gh pr ready "$PR" --repo "$REPOSITORY"
fi
cat "$TEMP/handoff.md"
