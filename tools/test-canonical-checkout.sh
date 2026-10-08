#!/usr/bin/env bash
# Disposable real Git/native-owner fixtures; no installed hook or live domain proof.
set -euo pipefail
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
export PATH
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/plugins/dm-review/skills/review/references/canonical-checkout.sh"
CONTEXT="$ROOT/plugins/dm-review/skills/review/references/review-owner-context.sh"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/canonical-checkout-test.XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"; export TMPDIR="$TMP"
umask 077
trap 'rm -rf -- "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass+1)); }
reject() { local rc=0; "$@" > "$TMP/rejected.out" 2>&1 || rc=$?; [ "$rc" -eq 3 ] || { printf 'FAIL expected blocked, rc=%s: %s\n' "$rc" "$*" >&2; cat "$TMP/rejected.out" >&2; exit 1; }; pass=$((pass+1)); }
REPO="$TMP/canonical folder"; mkdir "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" config user.name Fixture
git -C "$REPO" config user.email fixture@example.test
git -C "$REPO" remote add origin https://github.com/Design-Machines-Studio/assembly-fixture.git
printf '.workflow-kernel/\n.env\ninstall/\nevidence/\n' > "$REPO/.gitignore"
printf 'Assembly development source and existing dm006.asmbly.app service.\nProtect install, .env and evidence from actual service/runbook bindings.\n' > "$REPO/AGENTS.md"
printf 'original\n' > "$REPO/source with spaces"
printf 'original\n' > "$REPO/-leading"
NEWLINE=$'source\nwith newline'; printf 'original\n' > "$REPO/$NEWLINE"
printf 'original\n' > "$REPO/conflict"
mkdir -p "$REPO/nested"; printf 'tracked secret\n' > "$REPO/nested/secret"
git -C "$REPO" add .; git -C "$REPO" commit -qm baseline
BASE="$(git -C "$REPO" rev-parse HEAD)"
git -C "$REPO" checkout -qb reviewed
printf 'reviewed\n' > "$REPO/feature"; git -C "$REPO" add feature; git -C "$REPO" commit -qm reviewed
TARGET="$(git -C "$REPO" rev-parse HEAD)"
git -C "$REPO" checkout -q main
# Unique history is retained independently of source disposal.
git -C "$REPO" branch unique "$TARGET"
mkdir -p "$REPO/install/nested" "$REPO/evidence"
printf 'private secret\n' > "$REPO/.env"
printf 'database bytes\n' > "$REPO/install/nested/extensionless"
printf 'literal receipt bytes\n' > "$REPO/evidence/receipt"
cp "$REPO/.env" "$TMP/env-before"; cp "$REPO/install/nested/extensionless" "$TMP/data-before"; cp "$REPO/evidence/receipt" "$TMP/receipt-before"
BINDING="$TMP/binding.json"
jq -cn --arg repo "$REPO" '{kind:"assembly-development",repository:"Design-Machines-Studio/assembly-fixture",checkout:$repo,domain:"https://dm006.asmbly.app",sourceRanges:[{path:"AGENTS.md",startLine:1,endLine:2}],protectedPaths:[$repo+"/.env",$repo+"/install",$repo+"/evidence",$repo+"/nested/secret"]}' > "$BINDING"
boundary() { bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$1"; }
# Use the actual pointer API and supported owned-run producer, no invented lease store.
make_context() {
  local repo="$1" run="$2" terminal="$3" native root state pointer changed
  native="$TMP/native-$run.json"
  jq -cn --arg cwd "$repo" --arg session "$run" '{hook_event_name:"SessionStart",session_id:$session,cwd:$cwd}' > "$native"
  "$CONTEXT" init --repository-root "$repo" < "$native" > "$TMP/init-$run.json"
  pointer="$(jq -r '.hookSpecificOutput.additionalContext | split(" ")[3] | rtrimstr(".")' "$TMP/init-$run.json")"
  root="$("$KERNEL" owned-run-start --workflow pipeline --run-id "$run" --base "$TMP/runs" | jq -r .path)"
  state="$repo/.workflow-kernel/runs/$run"; mkdir -p "$state"
  changed="$(boundary "$repo")"
  "$CONTEXT" bind --repository-root "$repo" --context "$pointer" --workflow pipeline --run-id "$run" --run-root "$root" --state-dir "$state" --change-boundary "$changed" < "$native" >/dev/null
  "$CONTEXT" phase --repository-root "$repo" --context "$pointer" --phase checking --change-boundary "$changed" < "$native" >/dev/null
  if [ "$terminal" = complete ]; then
    "$CONTEXT" phase --repository-root "$repo" --context "$pointer" --phase complete --change-boundary "$changed" < "$native" >/dev/null
  fi
  printf '%s\n' "$pointer"
}
OLD="$(make_context "$REPO" old complete)"
# Abandoned source has no per-file historical creation records.
printf 'stale\n' > "$REPO/source with spaces"; printf 'stale\n' > "$REPO/-leading"; printf 'stale\n' > "$REPO/$NEWLINE"
printf 'discard\n' > "$REPO/untracked with spaces"; printf 'discard\n' > "$REPO/-untracked"; printf 'discard\n' > "$REPO/"$'untracked\nnewline'
printf 'staged abandonment\n' > "$REPO/staged new"
git -C "$REPO" add 'staged new'
CURRENT="$(make_context "$REPO" current checking)"
args=(--repository-root "$REPO" --repository Design-Machines-Studio/assembly-fixture --target-branch reviewed --binding-file "$BINDING" --current-context "$CURRENT" --owner-context "$OLD")
inspect() { "$HELPER" inspect "${args[@]}" "$@" > "$TMP/inspect.json"; }
prepare() { "$HELPER" prepare "${args[@]}" --inspection "$TMP/inspect.json" "$@"; }
inspect
assert jq -e --arg p "$NEWLINE" 'any(.paths[]; .path==$p and .classification=="disposable")' "$TMP/inspect.json"
assert jq -e 'any(.paths[]; .path=="install/nested/extensionless" and .classification=="retained")' "$TMP/inspect.json"
assert test "$(git -C "$REPO" rev-parse HEAD)" = "$BASE"
assert test -f "$REPO/untracked with spaces"
assert prepare
assert test "$(git -C "$REPO" symbolic-ref --short HEAD)" = reviewed
assert test "$(git -C "$REPO" rev-parse HEAD)" = "$TARGET"
assert test "$(cat "$REPO/source with spaces")" = original
assert test "$(cat "$REPO/-leading")" = original
assert test "$(cat "$REPO/$NEWLINE")" = original
assert test ! -e "$REPO/untracked with spaces"
assert test ! -e "$REPO/-untracked"
assert test ! -e "$REPO/"$'untracked\nnewline'
assert test ! -e "$REPO/staged new"
assert test "$(git -C "$REPO" rev-parse unique)" = "$TARGET"
assert cmp "$REPO/.env" "$TMP/env-before"
assert cmp "$REPO/install/nested/extensionless" "$TMP/data-before"
assert cmp "$REPO/evidence/receipt" "$TMP/receipt-before"
# Clean retry is safe and makes no alternate checkout.
inspect; assert prepare
assert "$HELPER" finish "${args[@]}"
git -C "$REPO" worktree list --porcelain -z > "$TMP/trees"
assert test "$(git -C "$REPO" worktree list --porcelain | grep -c '^worktree ')" = 1
# Post-report ignored residue is checked separately from Git's clean status.
printf 'final report\n' > "$REPO/evidence/final report"
reject "$HELPER" finish "${args[@]}" --residue-path "$REPO/evidence/final report"
assert grep -Fq 'preserve required evidence' "$TMP/rejected.out"
rm -- "$REPO/evidence/final report"
assert "$HELPER" finish "${args[@]}" --residue-path "$REPO/evidence/final report"
# Active ownership is an exact coordination blocker; no bytes change.
ACTIVE="$(make_context "$REPO" other checking)"
reject inspect --owner-context "$ACTIVE"
assert grep -Fq 'active owner at' "$TMP/rejected.out"
cp "$OLD" "$TMP/malformed.json"; printf '{invalid' > "$TMP/malformed.json"
reject inspect --owner-context "$TMP/malformed.json"
reject inspect --owner-context "$TMP/unavailable.json"
# No inactive proof cannot authorize source disposal.
no_prior=(--repository-root "$REPO" --repository Design-Machines-Studio/assembly-fixture --target-branch reviewed --binding-file "$BINDING" --current-context "$CURRENT")
printf 'unknown dirt\n' > "$REPO/unknown"
"$HELPER" inspect "${no_prior[@]}" > "$TMP/no-prior.json"
assert jq -e 'any(.paths[]; .path=="unknown" and .classification=="retained")' "$TMP/no-prior.json"
reject "$HELPER" prepare "${no_prior[@]}" --inspection "$TMP/no-prior.json"
rm -- "$REPO/unknown"
# New current-run changes do not become disposable without delivery.
printf 'current repair\n' > "$REPO/source with spaces"
inspect
assert jq -e 'any(.paths[]; .reason=="current-boundary-changed" and .classification=="retained")' "$TMP/inspect.json"
reject prepare
assert test "$(cat "$REPO/source with spaces")" = 'current repair'
# Also honor explicit current path ownership even if pointer was refreshed.
inspect --keep-path 'source with spaces'
reject prepare --keep-path 'source with spaces'
git -C "$REPO" restore -- 'source with spaces'
# Reject unsafe names and symlink components before source mutation.
reject inspect --keep-path ../escape
ln -s "$TMP/env-before" "$REPO/link"
inspect
assert jq -e 'any(.paths[]; .path=="link" and .classification=="blocked")' "$TMP/inspect.json"
reject prepare
assert test -L "$REPO/link"; rm -- "$REPO/link"
# Directory/file collision with ignored protected descendants stays intact.
rm -- "$REPO/conflict"; mkdir "$REPO/conflict"
printf 'protected nested state\n' > "$REPO/conflict/secret"
cp "$BINDING" "$TMP/binding-original.json"
jq --arg p "$REPO/conflict/secret" '.protectedPaths+=[$p]' "$BINDING" > "$TMP/binding-new.json"; mv "$TMP/binding-new.json" "$BINDING"
inspect
assert jq -e 'any(.paths[]; .path=="conflict" and .classification=="blocked")' "$TMP/inspect.json"
reject prepare
assert test "$(cat "$REPO/conflict/secret")" = 'protected nested state'
rm -- "$REPO/conflict/secret"; rmdir -- "$REPO/conflict"; git -C "$REPO" restore -- conflict
mv "$TMP/binding-original.json" "$BINDING"
# Tracked protected secrets cannot be restored to fabricate clean source.
printf 'protected edited bytes\n' > "$REPO/nested/secret"
inspect; reject prepare
assert test "$(cat "$REPO/nested/secret")" = 'protected edited bytes'
git -C "$REPO" restore -- nested/secret
# Inspect/prepare rejects a changed snapshot, including staged bytes.
inspect; printf 'late edit\n' > "$REPO/source with spaces"
reject prepare
assert grep -Fq 'inspection changed' "$TMP/rejected.out"
git -C "$REPO" restore -- 'source with spaces'
# Symlinked binding or owner files are refused.
ln -s "$BINDING" "$TMP/binding-link"
reject "$HELPER" inspect "${args[@]}" --binding-file "$TMP/binding-link"
# Foreign occupancy cannot be evaded with a fresh preview target.
git -C "$REPO" checkout -q main
FOREIGN="$TMP/foreign worktree"; git -C "$REPO" worktree add -q "$FOREIGN" reviewed
reject inspect
assert grep -Fq "$FOREIGN" "$TMP/rejected.out"
assert test "$(git -C "$FOREIGN" symbolic-ref --short HEAD)" = reviewed
# Target branch cannot replace a clean protected tracked binding.
git -C "$REPO" checkout -qb changes-install
printf 'wrong install state\n' > "$REPO/nested/secret"
git -C "$REPO" add nested/secret; git -C "$REPO" commit -qm protected-change
git -C "$REPO" checkout -q main
reject inspect --target-branch changes-install
assert grep -Fq 'target branch changes protected binding' "$TMP/rejected.out"
assert test "$(cat "$REPO/nested/secret")" = 'tracked secret'
# The existing current owner can bind its implementation worktree; normal
# detach frees only that owner, retains its checkout for later producer calls.
IMPL_OWNER="$(make_context "$FOREIGN" implementation checking)"
git init -q --bare "$TMP/remote.git"
git -C "$FOREIGN" remote set-url --push origin "$TMP/remote.git"
git -C "$FOREIGN" push -q origin reviewed
# A bounded preservation-result fixture exercises transfer preconditions only;
# actual coverage/retention authority remains the existing Kernel producer.
mkdir "$TMP/retained"; printf 'retained report\n' > "$TMP/retained/report.md"
jq -cn --arg p "$TMP/retained" '{status:"complete",evidence_path:$p}' > "$TMP/preserved.json"
release=(--current-context "$IMPL_OWNER" --implementation-root "$FOREIGN" --delivered-head "$TARGET" --preservation "$TMP/preserved.json")
reject inspect --current-context "$IMPL_OWNER" --implementation-root "$FOREIGN" --delivered-head "$BASE" --preservation "$TMP/preserved.json"
assert test "$(git -C "$FOREIGN" symbolic-ref --short HEAD)" = reviewed
jq '.status="incomplete"' "$TMP/preserved.json" > "$TMP/preservation-failed.json"
reject inspect "${release[@]}" --preservation "$TMP/preservation-failed.json"
assert test "$(git -C "$FOREIGN" symbolic-ref --short HEAD)" = reviewed
inspect "${release[@]}"
assert prepare "${release[@]}"
assert test "$(git -C "$REPO" symbolic-ref --short HEAD)" = reviewed
assert test "$(git -C "$FOREIGN" rev-parse HEAD)" = "$TARGET"
assert bash -c '! git -C "$1" symbolic-ref -q HEAD' bash "$FOREIGN"
assert test -d "$FOREIGN"
assert cmp "$REPO/evidence/receipt" "$TMP/receipt-before"
assert "$HELPER" finish "${args[@]}" "${release[@]}"
# A failing/interrupting caller uses the same read-only terminal checks.
printf 'abort residue\n' > "$FOREIGN/unfinished"
reject "$HELPER" finish "${args[@]}" "${release[@]}"
assert test "$(cat "$FOREIGN/unfinished")" = 'abort residue'
rm -- "$FOREIGN/unfinished"
assert "$HELPER" finish "${args[@]}" "${release[@]}"
# An actual SIGTERM during inspect leaves source/protected bytes untouched;
# retry uses the same exact contexts rather than guessing a latest owner.
(
  trap - EXIT
  printf 'started\n' > "$TMP/interruption-started"
  exec "$HELPER" inspect "${args[@]}" "${release[@]}"
) > "$TMP/interrupted.json" 2> "$TMP/interrupted.err" &
inspection_pid=$!
while [ ! -f "$TMP/interruption-started" ]; do sleep 0.01; done
sleep 0.05
kill -TERM "$inspection_pid"
interrupt_rc=0; wait "$inspection_pid" || interrupt_rc=$?
assert test "$interrupt_rc" = 143
assert cmp "$REPO/.env" "$TMP/env-before"
assert cmp "$REPO/install/nested/extensionless" "$TMP/data-before"
assert cmp "$REPO/evidence/receipt" "$TMP/receipt-before"
assert "$HELPER" finish "${args[@]}" "${release[@]}"
printf 'PASS: %s canonical checkout assertions (source/Git fixtures only; no live-domain proof)\n' "$pass"
