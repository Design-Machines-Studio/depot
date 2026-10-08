#!/usr/bin/env bash
# Host resolves WORKFLOW_KERNEL once from its trusted dependency bundle.
# producer-input is a closed map of preserve-review-evidence file arguments.
# readiness-input contains the explicit current owner and handoff facts.
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/review-owner-context.sh"
OPERATION= REPO= RUN_ROOT= PRODUCER= READINESS= PR=
SEEN=' '
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || exit 2
  case "$1" in
    --operation) OPERATION="$2" ;; --repository-root) REPO="$2" ;;
    --run-root) RUN_ROOT="$2" ;; --producer-input) PRODUCER="$2" ;;
    --readiness-input) READINESS="$2" ;; --pr) PR="$2" ;;
    *) exit 2 ;;
  esac
  case "$SEEN" in *" $1 "*) exit 2 ;; esac
  SEEN="$SEEN$1 "
  shift 2
done
case "$OPERATION:$PR" in create:) ;; ready:https://github.com/*/pull/*) ;; *) exit 2 ;; esac
# Source-development fixtures alone may supply two mocked tools. Fixed PATH
# still governs every other dependency and the real Kernel producer. This is
# deliberately restricted to a private disposable Fixture/consumer checkout;
# installed consumers and current production repositories cannot opt in.
if [ -n "${DM_REVIEW_DEVELOPMENT_TEST_ROOT:-}" ]; then
  TEST_ROOT="$DM_REVIEW_DEVELOPMENT_TEST_ROOT"
  review_private "$TEST_ROOT"
  case "${TEST_ROOT##*/}" in publish-reviewed-pr-test.*) ;; *) review_refuse 'invalid development fixture root' ;; esac
  DEPOT_ROOT="${HERE%/plugins/dm-review/skills/review/references}"
  [ "$DEPOT_ROOT" != "$HERE" ] && [ -e "$DEPOT_ROOT/.git" ] &&
    [ -f "$DEPOT_ROOT/tools/test-publish-reviewed-pr.sh" ] || review_refuse 'development tools require source checkout'
  [ "$REPO" = "$TEST_ROOT/repository" ] && [[ "$RUN_ROOT" = "$TEST_ROOT/runs/"* ]] || review_refuse 'development tools require disposable candidate'
  [ "$(review_repository "$REPO")" = Fixture/consumer ] || review_refuse 'development tools require fixture identity'
  for tool in git gh; do
    review_safe_path "$TEST_ROOT/bin/$tool"
    [ -f "$TEST_ROOT/bin/$tool" ] && [ -x "$TEST_ROOT/bin/$tool" ] &&
      [ "$(review_stat links "$TEST_ROOT/bin/$tool")" = 1 ] || review_refuse 'unsafe development tool'
  done
  git() { "$TEST_ROOT/bin/git" "$@"; }
  gh() { "$TEST_ROOT/bin/gh" "$@"; }
fi
for file in "$PRODUCER" "$READINESS"; do
  review_safe_path "$file"
  [ -f "$file" ] && [ -r "$file" ] && [ "$(review_stat links "$file")" = 1 ] || review_refuse 'missing or unsafe publication input'
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
  UI_PATHS=()
  while IFS= read -r path; do UI_PATHS+=("$path"); done < <(jq -r '.uiNonImpact.paths[]' "$READINESS")
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
  gh pr view "$PR" --repo "$REPOSITORY" --json headRefOid,headRefName,baseRefName,state,isDraft,reviewDecision > "$TEMP/pr.json"
  jq -e --arg head "$HEAD" --arg branch "$BRANCH" '.headRefOid==$head and .headRefName==$branch and .state=="OPEN" and .isDraft==true' "$TEMP/pr.json" >/dev/null || review_refuse 'actual PR head/state differs'
  BASE="$(jq -er '.baseRefName | select(type=="string" and length>0)' "$TEMP/pr.json")" || review_refuse 'actual PR base unavailable; Next action: resolve the PR base and retry publication.'
  git -C "$REPO" check-ref-format "refs/heads/$BASE" || review_refuse 'actual PR base invalid; Next action: resolve the PR base and retry publication.'
  OWNER_NAME="${REPOSITORY%/*}"; REPO_NAME="${REPOSITORY#*/}"; NUMBER="${PR##*/}"
  requirements_block() { review_refuse "$REPOSITORY base $BASE: $1; Next action: $2"; }
  # Reported contexts cannot prove an absent workflow is optional. Resolve the
  # actual base's classic protection and all active repository/organization
  # rules via GitHub's effective-branch endpoint, including every REST page.
  # https://docs.github.com/en/graphql/reference/branches
  # https://docs.github.com/en/rest/repos/rules#get-rules-for-a-branch
  gh api graphql -f query='query($owner:String!,$name:String!,$ref:String!){repository(owner:$owner,name:$name){ref(qualifiedName:$ref){name branchProtectionRule{requiresStatusChecks requiredStatusChecks{context app{id}}}}}}' \
    -f owner="$OWNER_NAME" -f name="$REPO_NAME" -f ref="refs/heads/$BASE" > "$TEMP/protection.json" || requirements_block 'classic protection lookup failed' 'restore GitHub metadata access and retry publication.'
  jq -e --arg base "$BASE" '
    (.errors==null or .errors==[]) and (.data.repository.ref | type=="object" and .name==$base and has("branchProtectionRule") and
      (.branchProtectionRule | .==null or (type=="object" and (.requiresStatusChecks|type=="boolean") and has("requiredStatusChecks") and
        (if .requiresStatusChecks then (.requiredStatusChecks|type=="array") else (.requiredStatusChecks==null or (.requiredStatusChecks|type=="array")) end) and
        all(.requiredStatusChecks[]?; (.context|type=="string" and length>0) and has("app") and (.app==null or (.app.id|type=="string" and length>0))))))
  ' "$TEMP/protection.json" >/dev/null || requirements_block 'classic protection metadata malformed or incomplete' 'obtain complete base-branch protection metadata and retry publication.'
  BASE_ENCODED="$(jq -rn --arg base "$BASE" '$base|@uri')"
  gh api --paginate --slurp "repos/$REPOSITORY/rules/branches/$BASE_ENCODED?per_page=100" > "$TEMP/rules.json" || requirements_block 'applicable ruleset lookup failed' 'restore GitHub rules metadata access and retry publication.'
  jq -e 'type=="array" and length>0 and all(.[]; type=="array" and all(.[];
    type=="object" and (.type|type=="string" and length>0) and
    (.ruleset_id|type=="number" and .>0 and floor==.) and
    (.ruleset_source_type|IN("Repository","Organization","Enterprise")) and (.ruleset_source|type=="string" and length>0) and
    (if .type=="required_status_checks" then (.parameters.required_status_checks|type=="array" and all(.[];
      (.context|type=="string" and length>0) and
      (.integration_id==null or (.integration_id|type=="number" and .>0 and floor==.)))) else true end)))
  ' "$TEMP/rules.json" >/dev/null || requirements_block 'applicable rules metadata malformed or incomplete' 'obtain all complete effective base-branch rules pages and retry publication.'
  UNMAPPED="$(jq -c '[.[][] | select(.type | IN("required_status_checks","creation","update","deletion","required_linear_history","required_signatures","pull_request","non_fast_forward","commit_message_pattern","commit_author_email_pattern","committer_email_pattern","branch_name_pattern","file_path_restriction","max_file_path_length","file_extension_restriction","max_file_size") | not)] | first // empty' "$TEMP/rules.json")"
  [ -z "$UNMAPPED" ] || requirements_block "unmappable applicable requirement $UNMAPPED" 'verify this ruleset requirement against source-bound GitHub results through a supported mapping before retrying publication.'
  jq '[.data.repository.ref.branchProtectionRule | select(.requiresStatusChecks==true) | .requiredStatusChecks[] | {name:.context,app:.app}]' "$TEMP/protection.json" > "$TEMP/configured.json"
  jq --slurpfile classic "$TEMP/configured.json" '$classic[0] + [.[][] | select(.type=="required_status_checks") | .parameters.required_status_checks[] | {name:.context,app:.integration_id}]' "$TEMP/rules.json" > "$TEMP/update.json"
  mv -- "$TEMP/update.json" "$TEMP/configured.json"
  UNMAPPED="$(jq -c '[.[]|select(.app!=null)] | first // empty' "$TEMP/configured.json")"
  [ -z "$UNMAPPED" ] || requirements_block "app-bound required check cannot be mapped from gh check rows: $UNMAPPED" 'verify the required GitHub App identity through a supported source-bound check mapping before retrying publication.'
  gh pr checks "$PR" --repo "$REPOSITORY" --json name,bucket,link > "$TEMP/checks.json" || requirements_block 'actual PR checks lookup failed' 'restore GitHub check results access and retry publication.'
  jq -e 'type=="array" and length>0 and all(.[];
    (.name|type=="string" and length>0) and (.bucket|IN("pass","fail","pending","skipping","cancel")) and
    (.link|type=="string" and length>0))' "$TEMP/checks.json" >/dev/null || requirements_block 'actual PR checks missing or invalid' 'obtain complete PR check results for this head and retry publication.'
  required_rc=0
  gh pr checks "$PR" --repo "$REPOSITORY" --required --json name,bucket,link > "$TEMP/required.json" 2> "$TEMP/required.err" || required_rc=$?
  if [ "$required_rc" -ne 0 ]; then
    # This diagnostic describes reported contexts only. The complete base
    # configuration above must also be empty; lookup errors never prove none.
    printf "no required checks reported on the '%s' branch\n" "$BRANCH" > "$TEMP/no-required.err"
    [ "$required_rc" -eq 1 ] && [ ! -s "$TEMP/required.json" ] && cmp -s "$TEMP/required.err" "$TEMP/no-required.err" || requirements_block 'required PR checks lookup failed' 'restore GitHub required-check results access and retry publication.'
    jq -e 'length==0' "$TEMP/configured.json" >/dev/null || requirements_block 'configured required check has not reported' 'run the missing required base-branch check on this PR head and retry publication.'
    printf '[]\n' > "$TEMP/required.json"
  else
    jq -e 'type=="array" and all(.[]; (.name|type=="string" and length>0) and .bucket=="pass" and (.link|type=="string" and length>0))' "$TEMP/required.json" >/dev/null || review_refuse 'required PR checks failed, pending, skipped or missing'
  fi
  jq -e --slurpfile required "$TEMP/required.json" 'all(.[]; .name as $name | any($required[0][]; .name==$name and .bucket=="pass"))' "$TEMP/configured.json" >/dev/null || requirements_block 'configured required check missing from passing required results' 'run the missing required base-branch check on this PR head and retry publication.'
  jq -e --slurpfile actual "$TEMP/checks.json" 'all(.[]; . as $required | any($actual[0][]; .name==$required.name and .bucket==$required.bucket and .link==$required.link))' "$TEMP/required.json" >/dev/null || review_refuse 'required PR check absent from actual PR'
  jq -e --slurpfile actual "$TEMP/checks.json" 'all(.checks[]|select(.stage=="pr"); .name as $name | any($actual[0][]; .name==$name))' "$TEMP/handoff.json" >/dev/null || review_refuse 'required PR check absent from actual PR'
  gh api graphql -f query='query($owner:String!,$name:String!,$number:Int!){repository(owner:$owner,name:$name){pullRequest(number:$number){headRefOid reviewThreads(first:100){nodes{isResolved} pageInfo{hasNextPage}}}}}' \
    -f owner="$OWNER_NAME" -f name="$REPO_NAME" -F number="$NUMBER" > "$TEMP/feedback.json"
  jq -e --arg head "$HEAD" '.data.repository.pullRequest | .headRefOid==$head and .reviewThreads.pageInfo.hasNextPage==false and all(.reviewThreads.nodes[];.isResolved==true)' "$TEMP/feedback.json" >/dev/null || review_refuse 'actual PR feedback unsettled or incomplete'
  jq -e '.reviewDecision!="CHANGES_REQUESTED"' "$TEMP/pr.json" >/dev/null || review_refuse 'changes requested on PR'
  jq --arg pr "$PR" --slurpfile checks "$TEMP/checks.json" --slurpfile required "$TEMP/required.json" '
    (.checks | map(select(.stage=="pr" and .required!=false))) as $declared |
    .checks = ((.checks | map(select(.stage=="candidate"))) +
      ($checks[0] | map(. as $check | {name:.name,link:.link,stage:"pr",
        required:(any($required[0][]; .name==$check.name) or any($declared[]; .name==$check.name)),
        status:(if .bucket=="pass" then "pass" elif .bucket=="pending" then "pending" elif .bucket=="skipping" then "skipped" else "fail" end)})) +
      (if ($required[0]|length)==0 then [{name:"Required PR checks",link:$pr,stage:"pr",required:false,status:"not_applicable"}] else [] end))
  ' "$TEMP/handoff.json" > "$TEMP/update.json"
  mv -- "$TEMP/update.json" "$TEMP/handoff.json"
  "$HERE/operator-handoff.sh" --gate merge "$TEMP/handoff.json" > "$TEMP/handoff.md" || { cat "$TEMP/handoff.md"; exit 3; }
fi
# Recheck source/remote immediately before the only mutation.
[ "$(git -C "$REPO" rev-parse HEAD)" = "$HEAD" ] && [ -z "$(git -C "$REPO" status --porcelain)" ] || review_refuse 'candidate changed during publication'
[ "$(git -C "$REPO" ls-remote --exit-code origin "refs/heads/$BRANCH" | awk '{print $1}')" = "$HEAD" ] || review_refuse 'remote candidate changed during publication'
if [ "$OPERATION" = create ]; then
  gh pr create --repo "$REPOSITORY" --head "$BRANCH" --draft --title "$(jq -r .target "$TEMP/handoff.json")" --body-file "$TEMP/handoff.md"
else
  gh pr view "$PR" --repo "$REPOSITORY" --json headRefOid,baseRefName > "$TEMP/final-pr.json"
  jq -e --arg head "$HEAD" --arg base "$BASE" '.headRefOid==$head and .baseRefName==$base' "$TEMP/final-pr.json" >/dev/null || review_refuse 'actual PR head/base changed during publication'
  gh pr ready "$PR" --repo "$REPOSITORY"
fi
cat "$TEMP/handoff.md"
