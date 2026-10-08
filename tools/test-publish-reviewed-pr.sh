#!/usr/bin/env bash
# Production-shaped disposable fixtures exercise the real supported producer.
# No participant ran; this is source development proof, not live review proof.
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLISH="$ROOT/plugins/dm-review/skills/review/references/publish-reviewed-pr.sh"
export WORKFLOW_KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/publish-reviewed-pr-test.XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
trap 'rm -rf -- "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }
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
export REAL_GIT="$(command -v git)" GH_LOG="$TMP/gh.log"
cat > "$TMP/bin/git" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [ "${3:-}" = ls-remote ]; then
  printf '%s\trefs/heads/candidate\n' "${REMOTE_HEAD:-$("$REAL_GIT" -C "$2" rev-parse HEAD)}"
else exec "$REAL_GIT" "$@"; fi
SH
cat > "$TMP/bin/gh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$GH_LOG"
case "$1 ${2:-}" in
  'pr create') printf 'https://github.com/Fixture/consumer/pull/42\n' ;;
  'pr ready') ;;
  'pr view') jq -cn --arg head "$PR_HEAD" '{headRefOid:$head,headRefName:"candidate",state:"OPEN",isDraft:true,reviewDecision:env.REVIEW_DECISION}' ;;
  'pr checks') jq -cn --arg bucket "${PR_BUCKET:-pass}" '[{name:"actual CI",bucket:$bucket,link:"https://example.test/ci"}]' ;;
  'api graphql') jq -cn --arg head "$PR_HEAD" '{data:{repository:{pullRequest:{headRefOid:$head,reviewThreads:{nodes:[{isResolved:(env.UNRESOLVED!="true")}],pageInfo:{hasNextPage:(env.MORE_THREADS=="true")}}}}}}' ;;
  *) exit 2 ;;
esac
SH
chmod +x "$TMP/bin/git" "$TMP/bin/gh"
export DM_REVIEW_DEVELOPMENT_TEST_ROOT="$TMP"

fixture() {
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
  jq -cn --arg id "$id" --arg root "$RUN_ROOT" --arg state "$STATE" --arg head "$PR_HEAD" '{owner:{repository:"Fixture/consumer",workflow:"pipeline",run_id:$id,run_root:$root,state_dir:$state},uiNonImpact:null,
    readiness:{target:"Vetted candidate",detail:"https://example.test/report",finalHead:$head,dirty:false,feedbackSettled:true,
      coverage:{status:"missing",head:null,gaps:[],requiredBrowserCases:[],evidence:null},
      lanes:(["Architecture","Simplicity","Security","Testing","Fixture/distribution"]|map({area:.,status:(if .=="Security" then "covered" else "exempt" end),note:(if .=="Security" then null else "Not selected in this bounded fixture." end),evidence:(if .=="Security" then "https://example.test/security" else null end)})),
      findings:[],checks:[{name:"candidate tests",stage:"candidate",status:"pass",link:null}],ui:{changed:false,preview:null,tasks:[],acceptance:null}}}' > "$READINESS"
  : > "$GH_LOG"
}
publish() { "$PUBLISH" --operation "$1" --repository-root "$REPO" --run-root "$RUN_ROOT" --producer-input "$PRODUCER" --readiness-input "$READINESS" "${@:2}"; }
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
change_readiness '.readiness.checks += [{name:"PR-only CI",stage:"pr",status:"pending",link:null}] | .readiness.feedbackSettled=false'
assert publish create
assert grep -Fq 'pr create --repo Fixture/consumer --head candidate --draft' "$GH_LOG"
assert test "$(find "$RUN_ROOT/diagnostic/review" -name report.md | wc -l | tr -d ' ')" = 1
# PATH cannot select executable dependencies. Only the bounded source fixture
# mechanism above activates mocks, and never replaces the real producer.
: > "$GH_LOG"
assert env PATH="$TMP/bin" /bin/bash "$PUBLISH" --operation create --repository-root "$REPO" --run-root "$RUN_ROOT" --producer-input "$PRODUCER" --readiness-input "$READINESS"
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

fixture ready
assert publish ready --pr https://github.com/Fixture/consumer/pull/42
assert grep -Fxq 'pr ready https://github.com/Fixture/consumer/pull/42 --repo Fixture/consumer' "$GH_LOG"
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
fixture absent-ci
change_readiness '.readiness.checks += [{name:"missing required CI",stage:"pr",status:"pass",link:null}]'
reject_publish ready --pr https://github.com/Fixture/consumer/pull/42; no_mutation
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
printf 'publish-reviewed-pr: %d assertions passed (real Kernel producer, disposable production-shaped fixtures, mocked gh; no live/installed proof)\n' "$pass"
