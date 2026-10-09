#!/usr/bin/env bash
# Production-shaped disposable fixtures exercise the real supported producer.
# No participant ran; this is source development proof, not live review proof.
set -euo pipefail
# Fixture feedback decisions must satisfy the production private-file contract.
umask 077
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLISH="$ROOT/plugins/dm-review/skills/review/references/publish-reviewed-pr.sh"
HELPER_BASH="${BASH32:-/bin/bash}"
export WORKFLOW_KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/publish-reviewed-pr-test.XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
trap 'rm -rf -- "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; [ ! -f "$TMP/rejected.out" ] || tail -n 20 "$TMP/rejected.out" >&2; exit 1; }; pass=$((pass+1)); }
REPO="$TMP/repository"; mkdir "$REPO" "$TMP/bin"
git -C "$REPO" init -q -b candidate
git -C "$REPO" config user.name Fixture
git -C "$REPO" config user.email fixture@example.test
git -C "$REPO" remote add origin https://github.com/Fixture/consumer.git
printf '.workflow-kernel/\n.claude/\n' > "$REPO/.gitignore"
printf 'reviewed source\n' > "$REPO/source.txt"
printf '<p>unchanged UI</p>\n' > "$REPO/ui.html"
git -C "$REPO" add .
git -C "$REPO" commit -qm fixture
INITIAL_HEAD="$(git -C "$REPO" rev-parse HEAD)"
git -C "$REPO" branch main
git -C "$REPO" branch release/reviewed
git -C "$REPO" branch release/topic
git -C "$REPO" update-ref refs/remotes/origin/release/reviewed "$INITIAL_HEAD"
export REAL_GIT="$(command -v git)" GH_LOG="$TMP/gh.log"
cat > "$TMP/bin/git" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [ "${3:-}" = ls-remote ]; then
  printf '%s\t%s\n' "${REMOTE_HEAD:-$("$REAL_GIT" -C "$2" rev-parse HEAD)}" "${REMOTE_REF:-$6}"
else exec "$REAL_GIT" "$@"; fi
SH
cat > "$TMP/bin/gh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$GH_LOG"
if [ "$1" = api ] && [[ "$*" != *graphql* ]]; then
  endpoint="${@: -1}"
  case "$endpoint" in
    repos/Fixture/consumer/pulls/42)
      [ "${INTAKE_MODE:-complete}" != unavailable ] || exit 1
      jq -cn --arg head "$PR_HEAD" --arg body "${FEEDBACK_PR_BODY:-Fixture PR body}" '{head:{sha:$head},body:$body,html_url:"https://github.com/Fixture/consumer/pull/42",updated_at:"2026-10-08T00:00:00Z"}'; exit 0 ;;
    *pulls/42/comments\?*) printf '[[]]\n'; exit 0 ;;
    *pulls/42/reviews\?*)
      jq -cn --arg head "$PR_HEAD" --arg body "${FEEDBACK_REVIEW_BODY:-}" '[[{id:81,html_url:"https://github.com/Fixture/consumer/pull/42#pullrequestreview-81",commit_id:$head,state:"COMMENTED",user:{login:"fixture"},submitted_at:"2026-10-08T00:00:00Z",body:$body}]]'; exit 0 ;;
    *issues/42/comments\?*)
      [ "${INTAKE_MODE:-complete}" != partial ] || exit 1
      jq -cn --arg body "${FEEDBACK_COMMENT:-}" '[[{id:82,html_url:"https://github.com/Fixture/consumer/pull/42#issuecomment-82",user:{login:"fixture"},created_at:"2026-10-08T00:00:00Z",updated_at:"2026-10-08T00:00:00Z",body:$body}]]'; exit 0 ;;
    *check-suites\?*) printf '{"total_count":0}\n'; exit 0 ;;
    *check-runs\?*) printf '[{"check_runs":[]}]\n'; exit 0 ;;
  esac
fi
case "$1 ${2:-}" in
  'pr create') printf 'https://github.com/Fixture/consumer/pull/42\n' ;;
  'pr ready') touch "$DM_REVIEW_DEVELOPMENT_TEST_ROOT/review-started" ;;
  'pr view')
    if [ -n "${MOVE_BRANCH_TO:-}" ]; then "$REAL_GIT" -C "$DM_REVIEW_DEVELOPMENT_TEST_ROOT/repository" update-ref refs/heads/candidate "$MOVE_BRANCH_TO"; fi
    draft=true
    [ ! -f "$DM_REVIEW_DEVELOPMENT_TEST_ROOT/review-started" ] || draft=false
    jq -cn --arg head "$PR_HEAD" --arg branch "${PR_BRANCH:-candidate}" --arg base "${PR_BASE:-main}" --argjson draft "$draft" '{headRefOid:$head,headRefName:$branch,baseRefName:$base,state:"OPEN",isDraft:$draft,reviewDecision:env.REVIEW_DECISION}' ;;
  'pr checks')
    required=false
    for arg in "$@"; do [ "$arg" != --required ] || required=true; done
    if [ "${READY_ONLY_CI:-false}" = true ] && [ ! -f "$DM_REVIEW_DEVELOPMENT_TEST_ROOT/review-started" ]; then printf '[]\n'; exit 0; fi
    if [ "$required" = true ]; then
      case "${REQUIRED_MODE:-checks}" in
        none) printf "no required checks reported on the 'candidate' branch\n" >&2; exit 1 ;;
        lookup-failure) printf 'error connecting to api.github.com\n' >&2; exit 1 ;;
        empty-error) exit 1 ;; empty-success) printf '[]\n'; exit 0 ;;
        diagnostic-extra) printf "no required checks reported on the 'candidate' branch\nlookup failed\n" >&2; exit 1 ;;
        wrong-branch) printf "no required checks reported on the 'foreign' branch\n" >&2; exit 1 ;;
        missing) printf '[{"name":"missing CI","bucket":"pass","link":"https://example.test/missing"}]\n'; exit 0 ;;
      esac
    fi
    case "${ALL_CHECKS_MODE:-checks}" in
      missing) printf '[]\n'; exit 0 ;;
      lookup-failure) printf 'API unavailable\n' >&2; exit 1 ;;
    esac
    jq -cn --arg bucket "${PR_BUCKET:-pass}" '[{name:"actual CI",bucket:$bucket,link:"https://example.test/ci"}]' ;;

  'api graphql')
    if [[ "$*" = *branchProtectionRule* ]]; then
      [[ "$*" = *"ref=refs/heads/${PR_BASE:-main}"* ]] || exit 2
      case "${CLASSIC_MODE:-checks}" in
        lookup-failure) printf 'API unavailable\n' >&2; exit 1 ;;
        malformed) printf '{\n'; exit 0 ;;
        incomplete) printf '{"data":{"repository":{"ref":{"name":"main"}}}}\n'; exit 0 ;;
      esac
      jq -cn --arg base "${PR_BASE:-main}" --arg mode "${CLASSIC_MODE:-checks}" '
        {data:{repository:{ref:{name:(if $mode=="wrong-base" then "foreign" else $base end),
          branchProtectionRule:(if $mode=="none" then null else
            {requiresStatusChecks:($mode!="empty"),requiredStatusChecks:(if $mode=="empty" then [] else
              [{context:(if $mode=="absent" then "missing CI" else "actual CI" end),app:(if $mode=="app-bound" then {id:"App1"} else null end)}] end)} end)}}}} |
        if $mode=="partial-error" then .errors=[{message:"not accessible"}] else . end'
    else
      jq -cn --arg head "$PR_HEAD" '{data:{repository:{pullRequest:{headRefOid:$head,reviewThreads:{nodes:[{isResolved:(env.UNRESOLVED!="true")}],pageInfo:{hasNextPage:(env.MORE_THREADS=="true")}}}}}}'
    fi ;;
  'api --paginate')
    BASE_ENCODED="$(jq -rn --arg base "${PR_BASE:-main}" '$base|@uri')"
    [ "$*" = "api --paginate --slurp repos/Fixture/consumer/rules/branches/$BASE_ENCODED?per_page=100" ] || exit 2
    case "${RULES_MODE:-none}" in
      lookup-failure) printf 'API unavailable\n' >&2; exit 1 ;;
      malformed) printf '{\n'; exit 0 ;;
      incomplete) printf '[[],null]\n'; exit 0 ;;
      none) printf '[[]]\n'; exit 0 ;;
    esac
    jq -cn --arg mode "$RULES_MODE" '
      {type:(if $mode=="workflow" then "workflows" elif $mode=="unknown" then "future_required_rule" else "required_status_checks" end),
        ruleset_id:73,ruleset_source_type:"Organization",ruleset_source:"Fixture",
        parameters:(if $mode=="workflow" then {workflows:[{path:".github/workflows/required.yml",repository_id:42,ref:"refs/heads/main"}]}
          elif $mode=="missing-parameters" then {} else
            {required_status_checks:[{context:(if $mode=="absent" or $mode=="second-page" then "missing CI" else "actual CI" end)}]} |
              if $mode=="app-bound" then .required_status_checks[0].integration_id=123 else . end end)} |
      if $mode=="second-page" then [[],[.]] else [[.]] end' ;;
  *) exit 2 ;;
esac
SH
chmod +x "$TMP/bin/git" "$TMP/bin/gh"
export DM_REVIEW_DEVELOPMENT_TEST_ROOT="$TMP"

fixture() {
  rm -f -- "$TMP/review-started"
  local id="$1" kind="${2:-live}" browser="${3:-false}" assembly
  RUN_ROOT="$("$WORKFLOW_KERNEL" owned-run-start --workflow pipeline --run-id "$id" --base "$TMP/runs" | jq -r .path)"
  STATE="$REPO/.workflow-kernel/runs/$id"; mkdir -p "$STATE"
  for path in review receipts receipts/private receipts/private/router raw; do
    "$WORKFLOW_KERNEL" owned-run-create --run-root "$RUN_ROOT" --kind raw-output --relative-path "$path" >/dev/null
  done
  export PR_HEAD="$(git -C "$REPO" rev-parse HEAD)"
  jq -cn --arg id "$id" '{run_id:$id,requested_lanes:["security"],mode:"full"}' > "$RUN_ROOT/review/request.json"
  BIND=(bind-review-source --run-root "$RUN_ROOT" --repository-root "$REPO" --request "$RUN_ROOT/review/request.json")
  if [ "$browser" = true ]; then BIND+=(--required-browser-case settings); fi
  "$WORKFLOW_KERNEL" "${BIND[@]}" > /dev/null
  printf '[]\n' > "$RUN_ROOT/review/authoritative-receipts.json"
  printf 'Security inspected source.txt. No findings.\n' > "$RUN_ROOT/raw/security.md"
  printf 'Inspect source.txt.\n' > "$RUN_ROOT/review/prompt.md"
  jq -cn '{schemaVersion:1,receiptId:("dispatch-"+("a"*24)),requested:{},fallback:false,
    served:{model:"gpt-6.1-sol",provider:"openai",family:"openai"},attempts:[{status:"completed"}],publication:{output:"published"},transportStub:false}' > "$RUN_ROOT/receipts/private/router/security.json"
  printf '%s\n' '{"schemaVersion":1,"receiptFiles":["security.json"]}' > "$RUN_ROOT/receipts/private/router/terminal-receipt-index.json"
  jq -cn '{reviewer:"security",lane:"security",requested_provider:"openai",attempted_provider:"openai",implemented_by:"codex",provider:"openai",model:"gpt-6.1-sol",
    evidence_refs:["raw/security.md"],implementer_family:"openai",reviewer_family:"openai",resolution_reason:"same-family-standard-review",
    raw_output_ref:"review/pending-output.json",raw_output_digest:("sha256:"+("0"*64)),finding_count:0}' > "$RUN_ROOT/review/companion.json"
  jq -cn --arg id "$id" --arg head "$PR_HEAD" --arg kind "$kind" '{schema_version:1,operation:"lane",run_id:$id,pass_id:"initial",lane:"security",attempt:1,reviewer:"security",
    source:{repository:"github.com/Fixture/consumer",head:$head,base:$head,worktree_ref:null,request_ref:"review/request.json"},
    requested:{designation:"full",patch_ref:null,paths:["source.txt"],evidence_refs:["review/prompt.md"],required_evidence_refs:["review/prompt.md"]},
    inspected:{paths:["source.txt"],basis:"repository",limitations:[],missing_evidence_refs:[]},
    literal:{output_ref:"raw/security.md",dispatch_receipt_ref:"receipts/private/router/security.json",companion_ref:"review/companion.json"},
    result:{status:"no_findings",findings:[],incomplete_reasons:[]},
    provenance:{kind:$kind,executed_at:(if $kind=="synthetic_test" then null else "2026-10-08T00:01:00Z" end),source_refs:["review/prompt.md"]},
    recheck:{prior_record_ref:null,selection_ref:null,repair_refs:[]}}' > "$RUN_ROOT/review/lane-input.json"
  ASSEMBLE=(assemble-review-evidence --run-root "$RUN_ROOT" --repository-root "$REPO" --request "$RUN_ROOT/review/request.json" --receipts "$RUN_ROOT/review/authoritative-receipts.json")
  if [ "$kind" = synthetic_test ]; then ASSEMBLE+=(--test-harness); fi
  assembly="$("$WORKFLOW_KERNEL" "${ASSEMBLE[@]}" --input "$RUN_ROOT/review/lane-input.json")"
  RECORD_REF="$(jq -r .record_ref <<< "$assembly")"
  jq -cn --arg id "$id" --arg ref "$(jq -r .record_ref <<< "$assembly")" '{schema_version:1,operation:"coverage",run_id:$id,pass_id:"initial",
    selection:[{lane:"security",record_ref:$ref,history_refs:[],transition_refs:[]}],decisions:[],occurred_at:"2026-10-08T00:02:00Z",required_case_refs:[],resolutions:[]}' > "$RUN_ROOT/review/coverage-input.json"
  # A missing required browser case must fail assembly, then preservation.
  if [ "$browser" = true ]; then
    if "$WORKFLOW_KERNEL" "${ASSEMBLE[@]}" --input "$RUN_ROOT/review/coverage-input.json" > "$TMP/browser-assembly.out" 2>&1; then echo 'FAIL: absent browser case accepted'; exit 1; fi
    pass=$((pass+1))
  else "$WORKFLOW_KERNEL" "${ASSEMBLE[@]}" --input "$RUN_ROOT/review/coverage-input.json" > /dev/null; fi
  printf '## CLEAN\n\n[Lane outputs](review/raw-lane-outputs.json).\n' > "$RUN_ROOT/report.md"
  PRODUCER="$TMP/$id-producer.json"; READINESS="$TMP/$id-readiness.json"
  jq -cn --arg root "$RUN_ROOT" '{request:($root+"/review/request.json"),receipts:($root+"/review/authoritative-receipts.json"),"lane-receipts":($root+"/review/review-lane-receipts.json"),
    "raw-lane-outputs":($root+"/review/raw-lane-outputs.json"),"raw-findings":($root+"/review/raw-finding-inventory.json"),decisions:($root+"/review/synthesis-decisions.json"),
    "private-router-directory":($root+"/receipts/private/router"),report:($root+"/report.md")}' > "$PRODUCER"
  jq -cn --arg id "$id" --arg root "$RUN_ROOT" --arg state "$STATE" --arg head "$PR_HEAD" '{approvedBase:"main",owner:{repository:"Fixture/consumer",workflow:"pipeline",run_id:$id,run_root:$root,state_dir:$state},uiNonImpact:null,
    readiness:{target:"Vetted candidate",detail:"https://example.test/report",finalHead:$head,dirty:false,feedbackSettled:true,
      coverage:{status:"missing",head:null,gaps:[],requiredBrowserCases:[],evidence:null},
      lanes:(["Architecture","Simplicity","Security","Testing","Fixture/distribution"]|map({area:.,status:(if .=="Security" then "covered" else "exempt" end),note:(if .=="Security" then null else "Not selected in this bounded fixture." end),evidence:(if .=="Security" then "https://example.test/security" else null end)})),
      findings:[],checks:[{name:"candidate tests",stage:"candidate",status:"pass",link:null}],ui:{changed:false,preview:null,tasks:[],acceptance:null}}}' > "$READINESS"
  settle_feedback
  : > "$GH_LOG"
}
settle_feedback() {
  local intake="$RUN_ROOT/review/external-finding-intake.json" decisions="$RUN_ROOT/review/external-finding-decisions.json"
  env DM_REVIEW_TEST_MODE=1 DM_REVIEW_TEST_GH_BIN="$TMP/bin/gh" "$ROOT/plugins/dm-review/skills/review/references/external-finding-intake.sh" --repo Fixture/consumer --pr 42 --output "$intake" >/dev/null
  jq '{schema_version:1,artifact_role:"external_finding_decisions",repository,pr_number,inspected_head,collection_cutoff,decisions:[],
    source_evidence_index:([.pull_request.source_id,.surfaces[].items[].source_id]|map({source_id:.,candidate_source_finding_ids:[],rationale:"Empty fixture feedback or PR summary contains no finding."}))}' "$intake" > "$decisions"
  change_readiness ".feedback={intake:\"$intake\",decisions:\"$decisions\"}"
}
publish() { "$HELPER_BASH" "$PUBLISH" --operation "$1" --repository-root "$REPO" --run-root "$RUN_ROOT" --producer-input "$PRODUCER" --readiness-input "$READINESS" "${@:2}"; }
reject_publish() {
  local code=0
  publish "$@" > "$TMP/rejected.out" 2>&1 || code=$?
  [ "$code" -ne 0 ] || { echo 'FAIL: rejected publication succeeded'; exit 1; }
  pass=$((pass+1))
}
no_gh() { assert test ! -s "$GH_LOG"; }
no_mutation() { assert sh -c '! grep -E "^pr (create|ready)" "$1"' sh "$GH_LOG"; }
change_readiness() { jq "$1" "$READINESS" > "$TMP/update.json"; mv "$TMP/update.json" "$READINESS"; }

fixture candidate
rm -f -- "$TMP/review-started"
change_readiness '.readiness.checks += [{name:"PR-only CI",stage:"pr",status:"pending",link:null}] | .readiness.feedbackSettled=false'
assert publish create
assert grep -Fq 'pr create --repo Fixture/consumer --head candidate --base main --draft' "$GH_LOG"
assert test "$(find "$RUN_ROOT/diagnostic/review" -name report.md | wc -l | tr -d ' ')" = 1
# Required CI can start only at ready_for_review. Requesting review is a
# distinct non-merge checkpoint; repeated readiness must not retrigger it.
fixture ready-only-workflow
export READY_ONLY_CI=true PR_BUCKET=pending
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
publish request-review --pr https://github.com/Fixture/consumer/pull/42 > "$TMP/staged.out"
assert test -f "$TMP/review-started"
assert grep -Fxq '## Not ready' "$TMP/staged.out"
assert sh -c '! grep -Fxq "## Ready to merge" "$1"' sh "$TMP/staged.out"
ready_count="$(grep -c '^pr ready ' "$GH_LOG")"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42
assert test "$(grep -c '^pr ready ' "$GH_LOG")" = "$ready_count"
export PR_BUCKET=pass
publish ready --pr https://github.com/Fixture/consumer/pull/42 > "$TMP/ready-stage.out"
assert grep -Fxq '## Ready to merge' "$TMP/ready-stage.out"
assert test "$(grep -c '^pr ready ' "$GH_LOG")" = "$ready_count"
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
assert test "$(grep -c '^pr ready ' "$GH_LOG")" = "$ready_count"
unset READY_ONLY_CI PR_BUCKET
fixture ssh-publication
git -C "$REPO" remote set-url origin ssh://git@github.com/Fixture/consumer.git
assert publish request-review --pr https://github.com/Fixture/consumer/pull/42
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
git -C "$REPO" remote set-url origin https://github.com/Fixture/consumer.git
fixture candidate
# PATH cannot select executable dependencies. Only the bounded source fixture
# mechanism above activates mocks, and never replaces the real producer.
: > "$GH_LOG"
assert env PATH="$TMP/bin" "$HELPER_BASH" "$PUBLISH" --operation create --repository-root "$REPO" --run-root "$RUN_ROOT" --producer-input "$PRODUCER" --readiness-input "$READINESS"
: > "$GH_LOG"
reject_publish create --operation create; no_gh
reject_publish create --pr https://github.com/Fixture/consumer/pull/42; no_gh
SAVED_TEST_ROOT="$DM_REVIEW_DEVELOPMENT_TEST_ROOT"
export DM_REVIEW_DEVELOPMENT_TEST_ROOT="$TMP/bin"
reject_publish create; no_gh
export DM_REVIEW_DEVELOPMENT_TEST_ROOT="$SAVED_TEST_ROOT"
SAVED_REPO="$REPO"; REPO="$ROOT"
reject_publish create; no_gh
REPO="$SAVED_REPO"
git -C "$REPO" remote set-url origin https://github.com/Actual/production.git
reject_publish create; no_gh
git -C "$REPO" remote set-url origin https://github.com/Fixture/consumer.git

fixture missing
rm "$RUN_ROOT/$(jq -r .source_snapshot.snapshot_ref "$RUN_ROOT/$RECORD_REF")"
reject_publish create; no_gh
fixture missing-source
rm "$REPO/source.txt"
reject_publish create; no_gh
git -C "$REPO" restore source.txt
fixture unsafe
rm "$RUN_ROOT/review/review-lane-receipts.json"
ln -s /etc/passwd "$RUN_ROOT/review/review-lane-receipts.json"
reject_publish create; no_gh
fixture synthetic synthetic_test
reject_publish create; no_gh
fixture browser live true
reject_publish create; no_gh
fixture dirty
printf 'unreviewed\n' >> "$REPO/source.txt"
reject_publish create; no_gh
git -C "$REPO" restore source.txt
fixture stale
printf 'new committed source\n' >> "$REPO/source.txt"
git -C "$REPO" add source.txt; git -C "$REPO" commit -qm changed
reject_publish create; no_gh
fixture shortcut
jq '. + {command:"touch /tmp/never-run",coveragePassed:true}' "$PRODUCER" > "$TMP/update.json"; mv "$TMP/update.json" "$PRODUCER"
reject_publish create; no_gh
fixture foreign
change_readiness '.owner.run_id="someone-else"'
reject_publish create; no_gh
fixture foreign-root
change_readiness '.owner.run_root += "/wrong"'
reject_publish create; no_gh
fixture foreign-state
change_readiness '.owner.state_dir += "/wrong"'
reject_publish create; no_gh
fixture noncanonical
jq '.request |= sub("/review/";"/review/../review/")' "$PRODUCER" > "$TMP/update.json"; mv "$TMP/update.json" "$PRODUCER"
reject_publish create; no_gh
fixture linked-input
ln "$PRODUCER" "$TMP/linked-producer.json"
reject_publish create; no_gh
rm "$TMP/linked-producer.json"
fixture quoted
mv "$RUN_ROOT/report.md" "$RUN_ROOT/report with spaces.md"
jq --arg report "$RUN_ROOT/report with spaces.md" '.report=$report' "$PRODUCER" > "$TMP/update.json"; mv "$TMP/update.json" "$PRODUCER"
assert publish create
fixture stale-facts
change_readiness '.readiness.finalHead="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'
reject_publish create; no_gh
fixture finding
change_readiness '.readiness.findings=[{severity:"P3",location:"source.txt:1",problem:"retained concrete defect"}]'
reject_publish create; no_gh
fixture pending-tests
change_readiness '.readiness.checks[0].status="pending"'
reject_publish create; no_gh
fixture remote
export REMOTE_HEAD="$(printf 'b%.0s' {1..40})"
reject_publish create; no_gh
unset REMOTE_HEAD

# Stage two: the Assembly-only transfer fixture covers the helper and unfinished
# browser proof. Here the unchanged Fixture/consumer identity permits bounded gh
# mocks: real Git detaches the same producer and selects its branch elsewhere.
fixture detached-producer
cp "$READINESS" "$TMP/retained-readiness.json"
cp "$RUN_ROOT/review/request.json" "$TMP/retained-request.json"
cp "$RUN_ROOT/review/authoritative-receipts.json" "$TMP/retained-receipts.json"
printf 'retained owner state\n' > "$STATE/retained"
CANONICAL="$TMP/canonical"
git -C "$REPO" worktree add -q --detach "$CANONICAL" HEAD
# Explicit attached mismatch must fail even when both branches name this SHA.
git -C "$REPO" branch same-head HEAD
reject_publish create --feature-branch same-head; no_gh
assert publish create --feature-branch candidate
: > "$GH_LOG"
git -C "$REPO" checkout -q --detach HEAD
git -C "$CANONICAL" checkout -q candidate
for operation in create ready; do
  extra=(); [ "$operation" != ready ] || extra=(--pr https://github.com/Fixture/consumer/pull/42)
  reject_publish "$operation" ${extra[@]+"${extra[@]}"}; no_gh
  for branch in '' missing main '-candidate' 'candidate~1' 'refs/heads/candidate' 'HEAD' 'candidate..bad'; do
    reject_publish "$operation" ${extra[@]+"${extra[@]}"} --feature-branch "$branch"; no_gh
  done
  reject_publish "$operation" ${extra[@]+"${extra[@]}"} --feature-branch candidate --feature-branch candidate; no_gh
  # A tag of the same name must not make exact local branch selection ambiguous.
  git -C "$REPO" tag candidate "$INITIAL_HEAD"
  assert publish "$operation" ${extra[@]+"${extra[@]}"} --feature-branch candidate
  git -C "$REPO" tag -d candidate >/dev/null
  assert grep -Eq "^pr $operation " "$GH_LOG"
  : > "$GH_LOG"
  git -C "$REPO" update-ref refs/heads/candidate "$INITIAL_HEAD"
  reject_publish "$operation" ${extra[@]+"${extra[@]}"} --feature-branch candidate; no_gh
  git -C "$REPO" update-ref refs/heads/candidate "$PR_HEAD"
  export REMOTE_HEAD="$INITIAL_HEAD"
  reject_publish "$operation" ${extra[@]+"${extra[@]}"} --feature-branch candidate; no_gh
  unset REMOTE_HEAD
  export REMOTE_REF=refs/heads/foreign
  reject_publish "$operation" ${extra[@]+"${extra[@]}"} --feature-branch candidate; no_gh
  unset REMOTE_REF
done
export PR_BRANCH=foreign
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42 --feature-branch candidate; no_mutation
unset PR_BRANCH
: > "$GH_LOG"
export MOVE_BRANCH_TO="$INITIAL_HEAD"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42 --feature-branch candidate; no_mutation
assert grep -Fq 'local feature branch missing or differs' "$TMP/rejected.out"
unset MOVE_BRANCH_TO
git -C "$REPO" update-ref refs/heads/candidate "$PR_HEAD"
assert cmp "$READINESS" "$TMP/retained-readiness.json"
assert cmp "$RUN_ROOT/review/request.json" "$TMP/retained-request.json"
assert cmp "$RUN_ROOT/review/authoritative-receipts.json" "$TMP/retained-receipts.json"
assert test "$(cat "$STATE/retained")" = 'retained owner state'
assert test "$(git -C "$REPO" rev-parse HEAD)" = "$PR_HEAD"
assert test "$(git -C "$CANONICAL" symbolic-ref --short HEAD)" = candidate
# The serving checkout cannot adopt the original owner's state.
SAVED_REPO="$REPO"; REPO="$CANONICAL"
: > "$GH_LOG"
reject_publish create --feature-branch candidate; no_gh
REPO="$SAVED_REPO"
git -C "$CANONICAL" checkout -q --detach HEAD
git -C "$REPO" checkout -q candidate
git -C "$REPO" worktree remove "$CANONICAL"

# Preserve original source-bound base/head while publishing to the approved
# branch. Resolve local and origin naming without guessing GitHub's default.
for base in release/reviewed refs/heads/release/reviewed origin/release/reviewed refs/remotes/origin/release/reviewed; do
  fixture "base-${pass}"
  cp "$RUN_ROOT/review/request.json" "$TMP/request-before.json"
  change_readiness ".approvedBase=\"$base\""
  assert publish create
  assert grep -Fq -- '--base release/reviewed --draft' "$GH_LOG"
  assert cmp "$RUN_ROOT/review/request.json" "$TMP/request-before.json"
done
git -C "$REPO" tag release/reviewed
fixture ambiguous-approved-base
change_readiness '.approvedBase="release/reviewed"'
reject_publish create; no_gh
fixture explicit-approved-base
change_readiness '.approvedBase="refs/heads/release/reviewed"'
assert publish create
assert grep -Fq -- '--base release/reviewed --draft' "$GH_LOG"
git -C "$REPO" tag -d release/reviewed >/dev/null
git -C "$REPO" tag not-a-branch
git -C "$REPO" update-ref refs/remotes/foreign/main "$INITIAL_HEAD"
for base in '' '-main' missing HEAD "$INITIAL_HEAD" refs/tags/not-a-branch refs/remotes/foreign/main; do
  fixture "invalid-base-${pass}"
  change_readiness ".approvedBase=\"$base\""
  reject_publish create; no_gh
done
fixture missing-approved-base
change_readiness 'del(.approvedBase)'
reject_publish create; no_gh
fixture pr-only-candidate
change_readiness '.readiness.checks=[{name:"actual CI",stage:"pr",status:"pass",link:null}]'
reject_publish create; no_gh
assert grep -Fxq '## Not ready' "$TMP/rejected.out"
assert grep -Fq 'Candidate verification results are missing.' "$TMP/rejected.out"
assert grep -Fq '**Agent next action:** Run the required source/build/verification checks' "$TMP/rejected.out"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_gh
assert grep -Fxq '## Not ready' "$TMP/rejected.out"
assert grep -Fq 'Candidate verification results are missing.' "$TMP/rejected.out"
assert grep -Fq '**Agent next action:** Run the required source/build/verification checks' "$TMP/rejected.out"
for candidate_status in fail pending; do
  fixture "candidate-blocked-$candidate_status"
  change_readiness ".readiness.checks[0].status=\"$candidate_status\""
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_gh
  assert grep -Fxq '## Not ready' "$TMP/rejected.out"
done
fixture wrong-approved-base
change_readiness '.approvedBase="release/reviewed"'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
assert grep -Fq 'actual PR base differs from approved base' "$TMP/rejected.out"
fixture approved-ready-base
change_readiness '.approvedBase="origin/release/reviewed"'
export PR_BASE=release/reviewed
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
unset PR_BASE

fixture ready
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
assert grep -Fxq 'pr ready https://github.com/Fixture/consumer/pull/42 --repo Fixture/consumer' "$GH_LOG"
# Actual GitHub results replace caller PR projections while candidate rows stay.
for caller_status in fail pending pass; do
  fixture "pr-refresh-$caller_status"
  change_readiness ".readiness.checks += [{name:\"actual CI\",stage:\"pr\",status:\"$caller_status\",link:null}] | .readiness.feedbackSettled=false"
  publish ready --pr https://github.com/Fixture/consumer/pull/42 > "$TMP/ready.out" || {
    cat "$TMP/ready.out"
    echo "FAIL: $caller_status PR projection was not replaced by actual passing CI" >&2
    exit 1
  }
  assert grep -Fxq '## Ready to merge' "$TMP/ready.out"
  assert test "$(grep -Fxc -- '- actual CI passed.' "$TMP/ready.out")" = 1
  assert test "$(grep -Fxc -- '- candidate tests passed.' "$TMP/ready.out")" = 1
  assert sh -c '! grep -Fq "is still running" "$1"' sh "$TMP/ready.out"
  assert grep -Fxq 'pr ready https://github.com/Fixture/consumer/pull/42 --repo Fixture/consumer' "$GH_LOG"
done
fixture pr-stale
export PR_HEAD="$(printf 'c%.0s' {1..40})"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
fixture pr-pending
export PR_BUCKET=pending
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset PR_BUCKET
fixture pr-failed
export PR_BUCKET=fail
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset PR_BUCKET
# Optional skipped checks remain visible without being called passed. Both
# classic protection and every applicable rules page must verify no requirements.
fixture optional-skipped
export PR_BUCKET=skipping REQUIRED_MODE=none CLASSIC_MODE=none
publish ready --pr https://github.com/Fixture/consumer/pull/42 > "$TMP/optional.out"
assert grep -Fxq '## Ready to merge' "$TMP/optional.out"
assert grep -Fxq -- '- actual CI: optional check skipped.' "$TMP/optional.out"
assert grep -Fxq -- '- Required PR checks: not applicable (no required PR checks).' "$TMP/optional.out"
assert sh -c '! grep -Fq "actual CI passed" "$1"' sh "$TMP/optional.out"
assert grep -Fxq 'pr ready https://github.com/Fixture/consumer/pull/42 --repo Fixture/consumer' "$GH_LOG"
# Caller-declared required checks stay strict even if GitHub marks them optional.
fixture declared-required-skip
change_readiness '.readiness.checks += [{name:"actual CI",stage:"pr",status:"pending",link:null}]'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset REQUIRED_MODE CLASSIC_MODE
fixture required-skipped
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset PR_BUCKET
fixture no-required
export REQUIRED_MODE=none CLASSIC_MODE=empty
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
export REQUIRED_MODE=empty-success
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
unset REQUIRED_MODE CLASSIC_MODE
# An absent required workflow alongside an optional skip can never become ready,
# even with empty classic protection and no caller-declared PR rows.
fixture absent-workflow-optional-skip
export PR_BUCKET=skipping REQUIRED_MODE=none CLASSIC_MODE=none RULES_MODE=workflow
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
cat "$TMP/rejected.out"
assert grep -Fq 'base main: unmappable applicable requirement' "$TMP/rejected.out"
assert grep -Fq '.github/workflows/required.yml' "$TMP/rejected.out"
assert test "$(grep -o 'Next action:' "$TMP/rejected.out" | wc -l | tr -d ' ')" = 1
unset PR_BUCKET REQUIRED_MODE RULES_MODE CLASSIC_MODE
for classic in lookup-failure malformed incomplete partial-error wrong-base app-bound absent; do
  fixture "classic-$classic"
  export CLASSIC_MODE="$classic" REQUIRED_MODE=none PR_BUCKET=skipping
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
  assert grep -Fq 'Next action:' "$TMP/rejected.out"
  unset CLASSIC_MODE REQUIRED_MODE PR_BUCKET
done
for rules in lookup-failure malformed incomplete missing-parameters unknown app-bound absent second-page; do
  fixture "rules-$rules"
  export CLASSIC_MODE=none RULES_MODE="$rules" REQUIRED_MODE=none PR_BUCKET=skipping
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
  assert grep -Fq 'Next action:' "$TMP/rejected.out"
  unset CLASSIC_MODE RULES_MODE REQUIRED_MODE PR_BUCKET
done
# Reported passing required results must cover configuration, not just each
# other. A passing classic check cannot hide an absent organization requirement.
fixture missing-rules-required-with-reported-check
export RULES_MODE=second-page
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset RULES_MODE
fixture rules-reported-required
change_readiness '.approvedBase="release/topic"'
export CLASSIC_MODE=none RULES_MODE=checks PR_BASE=release/topic
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
assert grep -Fq 'rules/branches/release%2Ftopic?per_page=100' "$GH_LOG"
unset CLASSIC_MODE RULES_MODE PR_BASE
for lookup in missing lookup-failure empty-error empty-success diagnostic-extra wrong-branch; do
  fixture "required-$lookup"
  export REQUIRED_MODE="$lookup"
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
  unset REQUIRED_MODE
done
for lookup in missing lookup-failure; do
  fixture "all-$lookup"
  export ALL_CHECKS_MODE="$lookup"
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
  unset ALL_CHECKS_MODE
done
fixture feedback
export UNRESOLVED=true
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset UNRESOLVED
fixture feedback-page
export MORE_THREADS=true
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset MORE_THREADS
fixture requested-changes
export REVIEW_DECISION=CHANGES_REQUESTED
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
unset REVIEW_DECISION
fixture required-approval
export REVIEW_DECISION=REVIEW_REQUIRED
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
assert grep -Fq 'required approving PR reviews are missing' "$TMP/rejected.out"
assert sh -c '! grep -Fxq "## Ready to merge" "$1"' sh "$TMP/rejected.out"
unset REVIEW_DECISION
fixture absent-ci
change_readiness '.readiness.checks += [{name:"missing required CI",stage:"pr",status:"pass",link:null}]'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
# Complete full-surface judgments, source identity and one fresh intake are
# mandatory; empty threads and a caller true flag cannot replace them.
fixture feedback-missing-intake
change_readiness 'del(.feedback)'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
for field in FEEDBACK_COMMENT FEEDBACK_REVIEW_BODY FEEDBACK_PR_BODY; do
  fixture "feedback-new-$pass"
  export "$field=Actionable new defect needs current-code evaluation."
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
  assert grep -Fq 'external feedback changed' "$TMP/rejected.out"
  unset "$field"
done
fixture feedback-unprocessed
jq '.source_evidence_index |= map(select(.source_id!="github:conversation-comment:82"))' "$RUN_ROOT/review/external-finding-decisions.json" > "$TMP/update.json"
mv "$TMP/update.json" "$RUN_ROOT/review/external-finding-decisions.json"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
fixture feedback-stale
jq '.inspected_head="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"' "$RUN_ROOT/review/external-finding-intake.json" > "$TMP/update.json"
mv "$TMP/update.json" "$RUN_ROOT/review/external-finding-intake.json"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
fixture feedback-stale-cutoff
jq '.collection_cutoff="2026-01-01T00:00:00Z"' "$RUN_ROOT/review/external-finding-decisions.json" > "$TMP/update.json"
mv "$TMP/update.json" "$RUN_ROOT/review/external-finding-decisions.json"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
for mode in partial unavailable; do
  fixture "feedback-intake-$mode"
  export INTAKE_MODE="$mode"
  reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
  unset INTAKE_MODE
done
fixture feedback-settled
export FEEDBACK_COMMENT='Prior claim is contradicted by current source.' FEEDBACK_REVIEW_BODY='Review claim already repaired at this head.'
settle_feedback
jq '.source_evidence_index |= map(if (.source_id|IN("github:conversation-comment:82","github:submitted-review:81")) then .candidate_source_finding_ids=[.source_id+":claim"] else . end) |
  .decisions=[.source_evidence_index[]|select(.candidate_source_finding_ids|length>0)|{
    source_finding_id:.candidate_source_finding_ids[0],source_ids:[.source_id],finding_id:("finding-v1:sha256("+("a"*64)+")"),
    finding_disposition:"discarded",decision_reason_code:"superseded-by-stronger-evidence",evidence_ref:"source.txt:1",current_head_evidence_ref:"source.txt:1",rationale:"Disposable fixture current source establishes repair."}]' "$RUN_ROOT/review/external-finding-decisions.json" > "$TMP/update.json"
mv "$TMP/update.json" "$RUN_ROOT/review/external-finding-decisions.json"
change_readiness '.readiness.feedbackSettled=false'
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
assert test -f "$RUN_ROOT/review/external-finding-intake.json.pull-request-body.md"
assert sh -c 'find "$1/review" -path "*/publication-feedback-*/decisions.json" | read -r file' sh "$RUN_ROOT"
unset FEEDBACK_COMMENT FEEDBACK_REVIEW_BODY
fixture ui
change_readiness '.readiness.ui={changed:true,preview:"https://preview.test",tasks:["Check proposal confirmation."],acceptance:null}'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
change_readiness '.readiness.ui.acceptance={head:.readiness.finalHead,unchangedSince:false}'
: > "$GH_LOG"
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
fixture ui-stale
change_readiness '.readiness.ui={changed:true,preview:"https://preview.test",tasks:["Check proposal confirmation."],acceptance:{head:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",unchangedSince:true}}'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_gh
# Same UI bytes permit explicit unaffected acceptance after backend changes.
fixture ui-unaffected
change_readiness ".readiness.ui={changed:true,preview:\"https://preview.test\",tasks:[\"Check proposal confirmation.\"],acceptance:{head:\"$INITIAL_HEAD\",unchangedSince:true}} | .uiNonImpact={fromHead:\"$INITIAL_HEAD\",toHead:.readiness.finalHead,paths:[\"ui.html\"],evidence:\"$RUN_ROOT/review/ui-non-impact.json\"}"
jq '.uiNonImpact | del(.evidence) | .reason="The complete UI surface is ui.html; backend source change has no UI impact."' "$READINESS" > "$RUN_ROOT/review/ui-non-impact.json"
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
printf 'UI behavior changed\n' >> "$REPO/ui.html"
git -C "$REPO" add ui.html; git -C "$REPO" commit -qm ui-change
fixture ui-changed
change_readiness ".readiness.ui={changed:true,preview:\"https://preview.test\",tasks:[\"Check proposal confirmation.\"],acceptance:{head:\"$INITIAL_HEAD\",unchangedSince:true}} | .uiNonImpact={fromHead:\"$INITIAL_HEAD\",toHead:.readiness.finalHead,paths:[\"ui.html\"],evidence:\"$RUN_ROOT/review/ui-non-impact.json\"}"
jq '.uiNonImpact | del(.evidence) | .reason="Owner non-impact claim (contradicted by source)."' "$READINESS" > "$RUN_ROOT/review/ui-non-impact.json"
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_gh
# Exercise the actual host-discovery preamble with gh outside the fixed PATH.
# The remaining tests exercise the complete producer/publication flow. This
# isolated preamble avoids replacing canonical Git identity with a local URL.
sed '/^HERE=/,$d' "$PUBLISH" > "$TMP/host-discovery.sh"
printf '\ngh pr create\n' >> "$TMP/host-discovery.sh"
: > "$GH_LOG"
assert env PATH="$TMP/bin:$PATH" "$HELPER_BASH" "$TMP/host-discovery.sh"
assert grep -Fxq 'pr create' "$GH_LOG"
# Without a discovered host CLI the same call fails, rather than selecting an
# executable from the reviewed repository or retained evidence.
if env PATH=/nonexistent "$HELPER_BASH" "$TMP/host-discovery.sh" > "$TMP/missing-host-gh.out" 2>&1; then
  printf 'FAIL: missing host gh accepted\n' >&2; exit 1
fi
pass=$((pass+1))
printf 'publish-reviewed-pr: %d assertions passed (real Kernel producer, disposable production-shaped fixtures, mocked gh; no live/installed proof)\n' "$pass"
