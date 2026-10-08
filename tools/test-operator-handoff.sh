#!/usr/bin/env bash
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HANDOFF="$ROOT/plugins/dm-review/skills/review/references/operator-handoff.sh"
HANDOFF_BASH="${BASH32:-/bin/bash}"
handoff() { "$HANDOFF_BASH" "$HANDOFF" "$@"; }
CONTEXT="$ROOT/plugins/dm-review/skills/review/references/review-owner-context.sh"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/operator-handoff.XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
trap 'rm -rf -- "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }
reject() { local code=0; "$@" > "$TMP/rejected.out" 2>&1 || code=$?; [ "$code" -ne 0 ] || { echo "FAIL: accepted $*" >&2; exit 1; }; pass=$((pass+1)); }
HEAD="$(printf 'a%.0s' {1..40})"; OLD="$(printf 'b%.0s' {1..40})"
jq -cn --arg head "$HEAD" '{target:"PR #42",detail:"https://example.test/report",finalHead:$head,dirty:false,
  feedbackSettled:true,coverage:{status:"complete",head:$head,gaps:[],requiredBrowserCases:[],evidence:"https://example.test/evidence"},
  lanes:(["Architecture","Simplicity","Security","Testing","Fixture/distribution"]|map({area:.,status:"covered",note:null,evidence:"https://example.test/lane"})),
  findings:[],checks:[{name:"Tests",stage:"candidate",status:"pass",link:"https://example.test/tests"},{name:"CI",stage:"pr",status:"pass",link:"https://example.test/ci"}],
  ui:{changed:false,preview:null,tasks:[],acceptance:null}}' > "$TMP/base.json"
handoff --gate merge "$TMP/base.json" > "$TMP/base.out"
assert grep -Fxq '## Ready to merge' "$TMP/base.out"
assert grep -Fxq '**Your action:** Merge PR #42.' "$TMP/base.out"
assert sh -c '! grep -E "dm-review|inspect.*code|review.*backend" "$1"' sh "$TMP/base.out"
jq '.ui={changed:true,preview:"https://preview.test",tasks:["Open the proposal and check the vote confirmation.","Check the member list at phone width."],acceptance:null} | .coverage.requiredBrowserCases=["vote-confirmation"]' "$TMP/base.json" > "$TMP/ui.json"
handoff "$TMP/ui.json" > "$TMP/ui.out"
assert grep -Fxq '## UI check needed' "$TMP/ui.out"
assert grep -Fq 'https://preview.test' "$TMP/ui.out"
assert grep -Fq '1. Open the proposal' "$TMP/ui.out"
reject handoff --gate merge "$TMP/ui.json"
assert handoff --gate candidate "$TMP/ui.json"
jq --arg head "$HEAD" '.ui.acceptance={head:$head,unchangedSince:false}' "$TMP/ui.json" > "$TMP/accepted.json"
assert handoff --gate merge "$TMP/accepted.json"
jq --arg old "$OLD" '.ui.acceptance.head=$old' "$TMP/accepted.json" > "$TMP/stale-ui.json"
reject handoff --gate merge "$TMP/stale-ui.json"
assert grep -Fxq '## UI check needed' "$TMP/rejected.out"
jq '.ui.acceptance.unchangedSince=true' "$TMP/stale-ui.json" > "$TMP/unaffected-ui.json"
assert handoff --gate merge "$TMP/unaffected-ui.json"

for expression in \
  '.dirty=true' \
  '.coverage.status="missing" | .coverage.head=null' \
  '.coverage.head="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"' \
  '.coverage.status="incomplete" | .coverage.gaps=["required browser case vote-confirmation missing"]' \
  '.coverage.gaps=["security inspection missing"]' \
  '.findings=[{severity:"P3",location:"a.sh:12",problem:"wrong exit status"}]' \
  '.checks[1].status="pending"' \
  '.checks[1].status="fail"' \
  '.feedbackSettled=false' \
  '.lanes[0].status="omitted"' \
  '.coverage.evidence=null'; do
  jq "$expression" "$TMP/base.json" > "$TMP/gap.json"
  reject handoff --gate merge "$TMP/gap.json"
  assert grep -Fxq '## Not ready' "$TMP/rejected.out"
done
jq '.checks[1].status="pending" | .feedbackSettled=false' "$TMP/base.json" > "$TMP/pending-pr.json"
assert handoff --gate candidate "$TMP/pending-pr.json"
# PR-stage rows alone do not establish candidate source/build verification.
for expression in '.checks |= map(select(.stage=="pr"))' '.checks=[]'; do
  jq "$expression" "$TMP/base.json" > "$TMP/no-candidate.json"
  reject handoff --gate candidate "$TMP/no-candidate.json"
  assert grep -Fxq '## Not ready' "$TMP/rejected.out"
  assert grep -Fq 'Candidate verification results are missing.' "$TMP/rejected.out"
  assert grep -Fq '**Agent next action:** Run the required source/build/verification checks' "$TMP/rejected.out"
  assert test "$(grep -Fc '**Agent next action:**' "$TMP/rejected.out")" = 1
  reject handoff --gate merge "$TMP/no-candidate.json"
done
jq '.checks[0].status="pending"' "$TMP/base.json" > "$TMP/pending-tests.json"
reject handoff --gate candidate "$TMP/pending-tests.json"
jq '.lanes[4]={area:"Fixture/distribution",status:"exempt",note:"No Fixture or distribution behavior changed.",evidence:null}' "$TMP/base.json" > "$TMP/exempt.json"
assert handoff --gate merge "$TMP/exempt.json"
jq '.lanes[4].note=null' "$TMP/exempt.json" > "$TMP/false-exemption.json"
reject handoff "$TMP/false-exemption.json"
# Narrative CLEAN and CI green cannot repair missing lane/case coverage.
jq '.target="CLEAN, CI green" | .coverage.status="incomplete" | .coverage.gaps=["required browser case settings missing"]' "$TMP/base.json" > "$TMP/misleading.json"
reject handoff --gate candidate "$TMP/misleading.json"
assert grep -Fq 'required browser case settings missing' "$TMP/rejected.out"
jq '.verdict="CLEAN"' "$TMP/base.json" > "$TMP/shortcut.json"
reject handoff "$TMP/shortcut.json"
jq '.coverage.status="incomplete" | .coverage.gaps=["required automated UI case missing"]' "$TMP/accepted.json" > "$TMP/approval-gap.json"
reject handoff --gate merge "$TMP/approval-gap.json"

# Optional GitHub outcomes are separate from passed required checks.
for status in skipped not_applicable; do
  jq --arg status "$status" '.checks[1] += {status:$status,required:false}' "$TMP/base.json" > "$TMP/optional.json"
  handoff --gate merge "$TMP/optional.json" > "$TMP/optional.out"
  assert grep -Fxq '## Ready to merge' "$TMP/optional.out"
  assert sh -c '! grep -Fq "CI passed" "$1"' sh "$TMP/optional.out"
  jq '.checks[1].required=true' "$TMP/optional.json" > "$TMP/required-skipped.json"
  reject handoff --gate merge "$TMP/required-skipped.json"
  assert grep -Fq 'it has not passed' "$TMP/rejected.out"
  jq 'del(.checks[1].required)' "$TMP/optional.json" > "$TMP/unknown-required.json"
  reject handoff --gate merge "$TMP/unknown-required.json"
done
# Skipped/not-applicable have closed PR-stage/link requirements; required
# defaults apply to both omitted and null values.
for status in skipped not_applicable; do
  for expression in '.checks[1].stage="candidate"' '.checks[1].link=null'; do
    jq --arg status "$status" '.checks[1]+={status:$status,required:false}' "$TMP/base.json" | jq "$expression" > "$TMP/invalid-check.json"
    reject handoff "$TMP/invalid-check.json"
  done
  jq --arg status "$status" '.checks[1]+={status:$status,required:null}' "$TMP/base.json" > "$TMP/default-required.json"
  reject handoff --gate merge "$TMP/default-required.json"
  assert grep -Fq 'it has not passed' "$TMP/rejected.out"
done
# Final artifact writes can leave cleanup pending while code coverage is clean.
assert grep -Fxq 'Workspace: clean' "$TMP/base.out"
jq '.workspace={clean:false,paths:["/safe/checkout/final report.md"],nextAction:"Preserve report bytes in the retained root, remove the exact owned copy, and recheck both checkouts."}' "$TMP/base.json" > "$TMP/workspace.json"
reject handoff --gate candidate "$TMP/workspace.json"
assert grep -Fxq '## Not ready' "$TMP/rejected.out"
assert grep -Fxq 'Workspace: Not ready' "$TMP/rejected.out"
assert grep -Fq '/safe/checkout/final report.md' "$TMP/rejected.out"
assert grep -Fq '**Agent next action:** Preserve report bytes' "$TMP/rejected.out"
assert sh -c '! grep -E "exact-owned|producer" "$1"' sh "$TMP/rejected.out"
jq '.dirty=true | .coverage.status="incomplete"' "$TMP/base.json" > "$TMP/plain.json"
reject handoff --gate candidate "$TMP/plain.json"
assert sh -c '! grep -E "exact-owned|producer" "$1"' sh "$TMP/rejected.out"
jq '.workspace={clean:true,paths:[],nextAction:null}' "$TMP/base.json" > "$TMP/workspace-clean.json"
assert handoff --gate merge "$TMP/workspace-clean.json"
jq '.workspace.paths=["unremoved"]' "$TMP/workspace-clean.json" > "$TMP/false-clean.json"
reject handoff "$TMP/false-clean.json"
jq '.workspace.clean="true"' "$TMP/workspace-clean.json" > "$TMP/malformed-workspace.json"
reject handoff "$TMP/malformed-workspace.json"

# Native session/owner lifecycle. Disposable supported Kernel root only.
REPO="$TMP/repository"; mkdir "$REPO"
git -C "$REPO" init -q
git -C "$REPO" config user.name Fixture
git -C "$REPO" config user.email fixture@example.test
git -C "$REPO" remote add origin https://github.com/Fixture/consumer.git
printf '.workflow-kernel/\n' > "$REPO/.gitignore"
printf 'fixture\n' > "$REPO/source.txt"
git -C "$REPO" add .
git -C "$REPO" commit -qm fixture
export TMPDIR="$TMP"
jq -cn --arg cwd "$REPO" '{hook_event_name:"SessionStart",session_id:"native-parent-session",cwd:$cwd}' > "$TMP/native.json"
init_context() { "$CONTEXT" init --repository-root "$REPO" < "$TMP/native.json" > "$TMP/init.json"; }
init_context
POINTER="$(jq -r '.hookSpecificOutput.additionalContext | split(" ")[3] | rtrimstr(".")' "$TMP/init.json")"
assert test -f "$POINTER"
assert jq -e '.phase=="planning" and .run_id==null and (keys|length)==8' "$POINTER"
assert test "$(bash -c 'source "$1"; review_stat mode "$2"' bash "$CONTEXT" "$POINTER")" = 600
cp "$POINTER" "$TMP/original.json"
init_context
assert cmp "$POINTER" "$TMP/original.json"
ln -s "$TMP" "$TMP/temporary-alias"
assert env TMPDIR="$TMP/temporary-alias" bash -c '"$1" init --repository-root "$2" < "$3" > "$4"' bash "$CONTEXT" "$REPO" "$TMP/native.json" "$TMP/alias-init.json"
assert cmp "$TMP/init.json" "$TMP/alias-init.json"
rm "$TMP/temporary-alias"
RUN_ROOT="$("$KERNEL" owned-run-start --workflow pipeline --run-id parent --base "$TMP/runs" | jq -r .path)"
STATE="$REPO/.workflow-kernel/runs/parent"; mkdir -p "$STATE"
BOUNDARY="$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
printf 'untracked content\n' > "$REPO/untracked file.txt"
UNTRACKED_BOUNDARY="$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
assert test "$BOUNDARY" != "$UNTRACKED_BOUNDARY"
printf 'changed content\n' >> "$REPO/untracked file.txt"
assert test "$UNTRACKED_BOUNDARY" != "$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
rm "$REPO/untracked file.txt"
assert test "$BOUNDARY" = "$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
# Staging different bytes while retaining HEAD working bytes changes ownership.
printf 'index-only repair\n' > "$REPO/source.txt"
git -C "$REPO" add -- source.txt
git -C "$REPO" show HEAD:source.txt > "$REPO/source.txt"
assert test "$BOUNDARY" != "$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
git -C "$REPO" restore --source=HEAD --staged -- source.txt
assert test "$BOUNDARY" = "$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
# A hostile inherited PATH is discarded even when the library is sourced.
assert env PATH=/unavailable /bin/bash -c 'source "$1"; test "$PATH" = /opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin; review_private "$2"' bash "$CONTEXT" "$POINTER"
# Exercise BSD stat and shasum fallbacks on Linux with function-local mocks.
# This proves branch behavior, not actual macOS execution.
if stat -c %u -- "$TMP" >/dev/null 2>&1; then
assert bash -c '
  source "$1"
  stat() {
    [ "$1" = -f ] || return 1
    local format="$2"
    case "$format" in %Lp) format=%a ;; %l) format=%h ;; esac
    command stat -c "$format" -- "$3"
  }
  command() {
    if [ "${1:-}" = -v ] && [ "${2:-}" = sha256sum ]; then return 1; fi
    builtin command "$@"
  }
  review_private "$2"
  test "$(review_stat identity "$3")" = "$(builtin command stat -c "[%d,%i]" -- "$3")"
  test "$(printf fixture | review_sha256)" = "$(printf fixture | shasum -a 256 | awk "{print \$1}")"
' bash "$CONTEXT" "$POINTER" "$RUN_ROOT"
fi
reject bash -c 'source "$1"; id() { printf "0\n"; }; review_private "$2"' bash "$CONTEXT" "$POINTER"
for path in "$REPO/./source.txt" "$REPO/../repository/source.txt" "$REPO//source.txt" "$REPO/source.txt/"; do
  reject bash -c 'source "$1"; review_safe_path "$2"' bash "$CONTEXT" "$path"
done
assert bash -c 'source "$1"; review_safe_path "$2"' bash "$CONTEXT" "$REPO/not-created/file with spaces"
owner_bind() { "$CONTEXT" bind --repository-root "$REPO" --context "$POINTER" --workflow pipeline --run-id parent --run-root "$RUN_ROOT" --state-dir "$STATE" --change-boundary "$BOUNDARY" < "$TMP/native.json"; }
phase() { "$CONTEXT" phase --repository-root "$REPO" --context "$POINTER" --phase "$1" --change-boundary "$BOUNDARY" < "$TMP/native.json"; }
assert phase awaiting_plan_approval
assert owner_bind
assert jq -e '.phase=="executing" and .run_id=="parent"' "$POINTER"
cp "$POINTER" "$TMP/bound.json"
init_context
assert cmp "$POINTER" "$TMP/bound.json"
jq '.hook_event_name="Stop"' "$TMP/native.json" > "$TMP/stop.json"
mv "$TMP/stop.json" "$TMP/native.json"
reject owner_bind
assert phase checking
assert phase awaiting_ui
reject phase planning
assert phase checking
assert phase awaiting_merge
assert phase complete
# A completed owner can be rebound; active ones cannot. Native workers and
# foreign sessions cannot operate the parent's marker.
assert owner_bind
jq '.agent_id="worker"' "$TMP/native.json" > "$TMP/worker.json"
reject bash -c '"$1" bind --repository-root "$2" --context "$3" < "$4"' bash "$CONTEXT" "$REPO" "$POINTER" "$TMP/worker.json"
jq '.session_id="foreign-session"' "$TMP/native.json" > "$TMP/foreign.json"
reject bash -c '"$1" phase --repository-root "$2" --context "$3" --phase checking < "$4"' bash "$CONTEXT" "$REPO" "$POINTER" "$TMP/foreign.json"
jq --arg cwd "$TMP" '.cwd=$cwd' "$TMP/native.json" > "$TMP/foreign-cwd.json"
reject bash -c '"$1" phase --repository-root "$2" --context "$3" --phase checking < "$4"' bash "$CONTEXT" "$REPO" "$POINTER" "$TMP/foreign-cwd.json"
reject bash -c '"$1" clear --repository-root "$2" --context "$3" --run-id parent --run-root "$4" < "$5"' bash "$CONTEXT" "$REPO" "$POINTER" "$RUN_ROOT" "$TMP/native.json"
printf 'changed\n' >> "$REPO/source.txt"
reject phase checking
BOUNDARY="$(bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO")"
assert phase checking
cp "$POINTER" "$TMP/safe.json"
chmod 644 "$POINTER"
reject phase awaiting_merge
chmod 600 "$POINTER"
ln "$POINTER" "$TMP/hardlink"
reject phase awaiting_merge
rm "$TMP/hardlink"
rm "$POINTER"; ln -s "$TMP/safe.json" "$POINTER"
reject phase awaiting_merge
rm "$POINTER"; cp "$TMP/safe.json" "$POINTER"; chmod 600 "$POINTER"
# Exact run metadata cannot be adopted from a different root.
cp "$RUN_ROOT/.depot-owned-run.json" "$TMP/meta.json"
jq '.root_identity=[0,0]' "$TMP/meta.json" > "$RUN_ROOT/.depot-owned-run.json"
reject phase awaiting_merge
jq '.run_id="foreign"' "$TMP/meta.json" > "$RUN_ROOT/.depot-owned-run.json"
reject phase awaiting_merge
cp "$TMP/meta.json" "$RUN_ROOT/.depot-owned-run.json"
assert phase awaiting_merge
assert phase complete
rm -rf -- "$RUN_ROOT"
assert bash -c '"$1" clear --repository-root "$2" --context "$3" --run-id parent --run-root "$4" < "$5"' bash "$CONTEXT" "$REPO" "$POINTER" "$RUN_ROOT" "$TMP/native.json"
assert test ! -e "$POINTER"
reject phase checking
printf 'operator-handoff/context: %d assertions passed (disposable source fixtures; no installed hook proof)\n' "$pass"
