#!/usr/bin/env bash
# Host resolves WORKFLOW_KERNEL once from its trusted dependency bundle.
# producer-input is a closed map of preserve-review-evidence file arguments.
# readiness-input contains the explicit current owner and handoff facts.
set -euo pipefail
GH_HOST_BIN="$(command -v gh || true)"
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
# The host CLI may live outside the fixed child PATH (for example ~/.local/bin).
# Capture it before reset, as the existing external-finding collector does.
gh() { "$GH_HOST_BIN" "$@"; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/review-owner-context.sh"
OPERATION= REPO= RUN_ROOT= PRODUCER= READINESS= PR= FEATURE_BRANCH=
SEEN=' '
while [ "$#" -gt 0 ]; do
  [ "$#" -ge 2 ] || exit 2
  case "$1" in
    --operation) OPERATION="$2" ;; --repository-root) REPO="$2" ;;
    --run-root) RUN_ROOT="$2" ;; --producer-input) PRODUCER="$2" ;;
    --readiness-input) READINESS="$2" ;; --pr) PR="$2" ;;
    --feature-branch) FEATURE_BRANCH="$2" ;;
    *) exit 2 ;;
  esac
  case "$SEEN" in *" $1 "*) exit 2 ;; esac
  SEEN="$SEEN$1 "
  shift 2
done
case "$OPERATION:$PR" in create:) ;; ready:https://github.com/*/pull/*|request-review:https://github.com/*/pull/*) ;; *) exit 2 ;; esac
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
if [ -z "${DM_REVIEW_DEVELOPMENT_TEST_ROOT:-}" ]; then
  case "$GH_HOST_BIN" in /*) [ -x "$GH_HOST_BIN" ] || review_refuse 'host GitHub CLI unavailable' ;; *) review_refuse 'host GitHub CLI unavailable' ;; esac
  case "$GH_HOST_BIN" in "$REPO"/*|"$RUN_ROOT"/*) review_refuse 'GitHub CLI must come from the host, outside reviewed source and run evidence' ;; esac
fi
for file in "$PRODUCER" "$READINESS"; do
  review_safe_path "$file"
  [ -f "$file" ] && [ -r "$file" ] && [ "$(review_stat links "$file")" = 1 ] || review_refuse 'missing or unsafe publication input'
done
jq -e 'type=="object" and ((keys-["feedback"])|sort)==(["approvedBase","owner","readiness","uiNonImpact"]|sort) and
  (.approvedBase|type=="string" and length>0 and length<=1024 and (test("[\u0000-\u001f\u007f]")|not))' "$READINESS" >/dev/null || exit 2
OWNER="$(jq -c .owner "$READINESS")"
review_owner_validate "$OWNER" "$REPO"
[ "$RUN_ROOT" = "$(jq -r .run_root <<< "$OWNER")" ] || review_refuse 'current run root mismatch'
RUN="$(jq -r .run_id <<< "$OWNER")"
REPOSITORY="$(jq -r .repository <<< "$OWNER")"
# Copy approvedBase from the approved task/plan, never GitHub's default. Git
# resolves the exact local/origin branch name; no SHA, tag or foreign remote.
# This publication branch does not change original review source base/head.
APPROVED_BASE="$(jq -r .approvedBase "$READINESS")"
[[ "$APPROVED_BASE" != -* ]] || review_refuse 'invalid approved base branch'
BASE_REF="$(git -C "$REPO" rev-parse --symbolic-full-name --verify --end-of-options "$APPROVED_BASE")" || review_refuse 'approved base branch unavailable or ambiguous'
case "$BASE_REF" in
  refs/heads/*)
    BASE="${BASE_REF#refs/heads/}"
    [ "$APPROVED_BASE" = "$BASE" ] || [ "$APPROVED_BASE" = "$BASE_REF" ] || review_refuse 'approved base must name a branch explicitly' ;;
  refs/remotes/origin/*)
    BASE="${BASE_REF#refs/remotes/origin/}"
    [ "$APPROVED_BASE" = "origin/$BASE" ] || [ "$APPROVED_BASE" = "$BASE_REF" ] || review_refuse 'approved base must name a branch explicitly' ;;
  *) review_refuse 'approved base must name a local or origin branch' ;;
esac
git -C "$REPO" check-ref-format "refs/heads/$BASE" || review_refuse 'invalid approved base branch'
git -C "$REPO" rev-parse --verify "$BASE_REF^{commit}" >/dev/null || review_refuse 'approved base is not a commit branch'
if [ "$OPERATION" != create ]; then
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
if [ "$OPERATION" = create ]; then
  "$HERE/operator-handoff.sh" --gate candidate "$TEMP/handoff.json" > "$TEMP/handoff.md" || { cat "$TEMP/handoff.md"; exit 3; }
else
  # Gate source verification before GitHub access. Cached PR outcomes must
  # remain refreshable; fresh facts replace them before the final merge gate.
  jq '.checks |= map(select(.stage=="candidate"))' "$TEMP/handoff.json" > "$TEMP/candidate-handoff.json"
  "$HERE/operator-handoff.sh" --gate candidate "$TEMP/candidate-handoff.json" > "$TEMP/handoff.md" || { cat "$TEMP/handoff.md"; exit 3; }
fi
# The approved manifest/task supplies the branch after canonical transfer;
# the original detached producer still owns the state and source evidence.
ATTACHED="$(git -C "$REPO" symbolic-ref --quiet HEAD)" || ATTACHED=
case "$SEEN" in
  *" --feature-branch "*) BRANCH="$FEATURE_BRANCH" ;;
  *) [ -n "$ATTACHED" ] || review_refuse 'detached candidate requires --feature-branch from approved task/manifest'
     BRANCH="${ATTACHED#refs/heads/}" ;;
esac
case "$BRANCH" in ''|-*|refs/*|HEAD) review_refuse 'unsafe feature branch' ;; esac
git -C "$REPO" check-ref-format "refs/heads/$BRANCH" || review_refuse 'unsafe feature branch'
check_local_branch() {
  local attached
  attached="$(git -C "$REPO" symbolic-ref --quiet HEAD)" || attached=
  [ -z "$attached" ] || [ "$attached" = "refs/heads/$BRANCH" ] || review_refuse 'attached candidate branch differs'
  [ "$(git -C "$REPO" show-ref --verify --hash "refs/heads/$BRANCH")" = "$HEAD" ] || review_refuse 'local feature branch missing or differs from reviewed head'
}
remote_branch_head() {
  git -C "$REPO" ls-remote --exit-code origin "refs/heads/$BRANCH" | awk -v ref="refs/heads/$BRANCH" '$2==ref {print $1}'
}
check_local_branch
REMOTE_HEAD="$(remote_branch_head)" || review_refuse 'remote candidate unavailable'
[ "$REMOTE_HEAD" = "$HEAD" ] || review_refuse 'local and remote candidate heads differ'
if [ "$OPERATION" != create ]; then
  gh pr view "$PR" --repo "$REPOSITORY" --json headRefOid,headRefName,baseRefName,state,isDraft,reviewDecision > "$TEMP/pr.json"
  jq -e --arg head "$HEAD" --arg branch "$BRANCH" '.headRefOid==$head and .headRefName==$branch and .state=="OPEN" and (.isDraft|type=="boolean")' "$TEMP/pr.json" >/dev/null || review_refuse 'actual PR head/state differs'
  jq -e --arg base "$BASE" '.baseRefName==$base' "$TEMP/pr.json" >/dev/null || review_refuse 'actual PR base differs from approved base; restore the approved PR target and retry publication'
  if [ "$OPERATION" = request-review ]; then
    # Starting GitHub review/checks is a publication checkpoint, not merge
    # readiness. Some required workflows cannot report while a PR is draft.
    [ "$(git -C "$REPO" rev-parse HEAD)" = "$HEAD" ] && [ -z "$(git -C "$REPO" status --porcelain)" ] || review_refuse 'candidate changed before review request'
    check_local_branch
    [ "$(remote_branch_head)" = "$HEAD" ] || review_refuse 'remote candidate changed before review request'
    if jq -e '.isDraft' "$TEMP/pr.json" >/dev/null; then gh pr ready "$PR" --repo "$REPOSITORY"; fi
    # No CI result or formal approval is invented. The same owner's ready
    # operation must collect them and settle fresh feedback before merge.
    jq '.feedbackSettled=false | .checks |= map(select(.stage=="candidate"))' "$TEMP/handoff.json" > "$TEMP/review-handoff.json"
    "$HERE/operator-handoff.sh" --gate candidate "$TEMP/review-handoff.json"
    printf '%s\n' 'Review/checks requested. Agent next action: wait for actual PR results, settle feedback, then rerun the supported ready operation. Merge readiness has not passed.'
    exit 0
  fi
fi
if [ "$OPERATION" = ready ]; then
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
  jq -e '.reviewDecision!="REVIEW_REQUIRED"' "$TEMP/pr.json" >/dev/null || requirements_block 'required approving PR reviews are missing' 'settle the required PR review approval, then retry readiness.'
  # Settlement covers bodies/conversation/check evidence as well as threads.
  # Recollect once, then carry judgments only across byte-identical sources;
  # changed/new sources require host evaluation in this same owner, not a flag.
  jq -e '.feedback | type=="object" and (keys|sort)==(["intake","decisions"]|sort) and
    all(.[]; type=="string" and startswith("/"))' "$READINESS" >/dev/null || review_refuse 'current-head feedback intake/decisions required'
  INTAKE="$(jq -r .feedback.intake "$READINESS")"
  FEEDBACK_DECISIONS="$(jq -r .feedback.decisions "$READINESS")"
  for file in "$INTAKE" "$FEEDBACK_DECISIONS"; do
    review_private "$file"
    [[ "$file" = "$RUN_ROOT/"* ]] && [ -f "$file" ] && [ "$(review_stat links "$file")" = 1 ] || review_refuse 'foreign feedback evidence'
  done
  jq -e --arg repo "$REPOSITORY" --argjson pr "$NUMBER" --arg head "$HEAD" '
    .repository==$repo and .pr_number==$pr and .inspected_head==$head' "$INTAKE" >/dev/null || review_refuse 'feedback repository/PR/head mismatch'
  "$HERE/external-finding-settlement.sh" --intake "$INTAKE" --decisions "$FEEDBACK_DECISIONS" --current-head "$HEAD" > "$TEMP/settlement.json" || review_refuse 'external feedback unsettled'
  FRESH_REL="review/publication-feedback-${TEMP##*.}"
  "$WORKFLOW_KERNEL" owned-run-create --run-root "$RUN_ROOT" --kind raw-output --relative-path "$FRESH_REL" >/dev/null
  FRESH="$RUN_ROOT/$FRESH_REL"
  # Production never inherits the collector's source-test tool overrides.
  (
    unset DM_REVIEW_TEST_MODE DM_REVIEW_TEST_GH_BIN DM_REVIEW_TEST_MAX_ITEMS DM_REVIEW_TEST_MAX_CHECK_SUITES
    if [ -n "${DM_REVIEW_DEVELOPMENT_TEST_ROOT:-}" ]; then
      export DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$TEST_ROOT/bin/gh"
    fi
    PATH="${GH_HOST_BIN%/*}:$PATH" /bin/bash "$HERE/external-finding-intake.sh" --repo "$REPOSITORY" --pr "$NUMBER" --output "$FRESH/intake.json" \
      --max-pr-body-source-bytes "$(jq -r .pull_request.body.source.max_bytes "$INTAKE")"
  ) > "$TEMP/intake-result.json" || review_refuse "fresh external feedback intake incomplete: $FRESH_REL/intake.json"
  jq -cS 'del(.collected_at,.collection_cutoff,.pull_request.body.source.path)' "$INTAKE" > "$TEMP/prior-feedback.json"
  jq -cS 'del(.collected_at,.collection_cutoff,.pull_request.body.source.path)' "$FRESH/intake.json" > "$TEMP/fresh-feedback.json"
  cmp -s "$TEMP/prior-feedback.json" "$TEMP/fresh-feedback.json" || review_refuse "external feedback changed; evaluate $FRESH_REL/intake.json and settle before ready"
  jq --slurpfile fresh "$FRESH/intake.json" '.collection_cutoff=$fresh[0].collection_cutoff' "$FEEDBACK_DECISIONS" > "$FRESH/decisions.json"
  "$HERE/external-finding-settlement.sh" --intake "$FRESH/intake.json" --decisions "$FRESH/decisions.json" --current-head "$HEAD" > "$TEMP/fresh-settlement.json" || review_refuse 'fresh external feedback unsettled'
  jq --arg pr "$PR" --slurpfile checks "$TEMP/checks.json" --slurpfile required "$TEMP/required.json" '
    (.checks | map(select(.stage=="pr" and .required!=false))) as $declared |
    .feedbackSettled=true |
    .checks = ((.checks | map(select(.stage=="candidate"))) +
      ($checks[0] | map(. as $check | {name:.name,link:.link,stage:"pr",
        required:(any($required[0][]; .name==$check.name) or any($declared[]; .name==$check.name)),
        status:(if .bucket=="pass" then "pass" elif .bucket=="pending" then "pending" elif .bucket=="skipping" then "skipped" else "fail" end)})) +
      (if ($required[0]|length)==0 then [{name:"Required PR checks",link:$pr,stage:"pr",required:false,status:"not_applicable"}] else [] end))
  ' "$TEMP/handoff.json" > "$TEMP/update.json"
  mv -- "$TEMP/update.json" "$TEMP/handoff.json"
  "$HERE/operator-handoff.sh" --gate merge "$TEMP/handoff.json" > "$TEMP/handoff.md" || { cat "$TEMP/handoff.md"; exit 3; }
fi
if [ "$OPERATION" = ready ]; then
  gh pr view "$PR" --repo "$REPOSITORY" --json headRefOid,headRefName,baseRefName,isDraft > "$TEMP/final-pr.json"
  jq -e --arg head "$HEAD" --arg branch "$BRANCH" --arg base "$BASE" '.headRefOid==$head and .headRefName==$branch and .baseRefName==$base and (.isDraft|type=="boolean")' "$TEMP/final-pr.json" >/dev/null || review_refuse 'actual PR head/base changed during publication'
fi
# Recheck source/remote immediately before the only mutation.
[ "$(git -C "$REPO" rev-parse HEAD)" = "$HEAD" ] && [ -z "$(git -C "$REPO" status --porcelain)" ] || review_refuse 'candidate changed during publication'
check_local_branch
[ "$(remote_branch_head)" = "$HEAD" ] || review_refuse 'remote candidate changed during publication'
if [ "$OPERATION" = create ]; then
  gh pr create --repo "$REPOSITORY" --head "$BRANCH" --base "$BASE" --draft --title "$(jq -r .target "$TEMP/handoff.json")" --body-file "$TEMP/handoff.md"
else
  if jq -e '.isDraft' "$TEMP/final-pr.json" >/dev/null; then gh pr ready "$PR" --repo "$REPOSITORY"; fi
fi
cat "$TEMP/handoff.md"
