#!/usr/bin/env bash
# Disposable source fixtures for dm-review's bounded completion hook. This is
# source proof only; it does not show native Claude, Codex or T3 delivery.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REFS="$ROOT/plugins/dm-review/skills/review/references"
HOOK="$REFS/review-completion-hook.sh"
CONTEXT="$REFS/review-owner-context.sh"
HOOKS_JSON="$ROOT/plugins/dm-review/hooks/hooks.json"
KERNEL="$ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow-kernel-launcher.sh"
TMP="$(cd "$(mktemp -d "${TMPDIR:-/tmp}/review-completion-hook.XXXXXX")" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT
pass=0
assert() { "$@" >/dev/null || { printf 'FAIL: %s\n' "$*" >&2; exit 1; }; pass=$((pass + 1)); }
REASON='Resume this exact owner, validate current producer coverage and perform only the missing supported review action; never approve the plan/UI/merge gate.'

# Run the hook; stdout goes to $TMP/out. Every case must exit zero.
hook() { "$HOOK" "$1" < "$2" > "$TMP/out"; }
silent() { hook "$1" "$2" || return; test ! -s "$TMP/out"; }
blocks() { hook stop "$1" || return; jq -e --arg reason "$REASON" '. == {decision:"block",reason:$reason}' "$TMP/out"; }
diagnoses() { hook "$1" "$2" || return; jq -e --arg text "$3" '(keys == ["systemMessage"]) and (.systemMessage | contains($text))' "$TMP/out"; }
boundary() { bash -c 'source "$1"; review_change_boundary "$2"' bash "$CONTEXT" "$REPO"; }
phase() { "$CONTEXT" phase --repository-root "$REPO" --context "$POINTER" --phase "$1" --change-boundary "$(boundary)" < "$TMP/start.json" >/dev/null; }
recorded_phase() { jq -r .phase "$POINTER"; }
commit_change() { printf '%s\n' "$1" >> "$REPO/source.txt"; git -C "$REPO" commit -qam "$1"; }

make_repo() {
  mkdir "$1"
  git -C "$1" init -q
  git -C "$1" config user.name Fixture
  git -C "$1" config user.email fixture@example.test
  [ -z "$2" ] || git -C "$1" remote add origin "$2"
  printf '.workflow-kernel/\n' > "$1/.gitignore"
  printf 'fixture\n' > "$1/source.txt"
  git -C "$1" add .
  git -C "$1" commit -qm fixture
}
native() { # event session cwd [stop_hook_active]
  if [ "$1" = SessionStart ]; then
    jq -cn --arg s "$2" --arg cwd "$3" '{hook_event_name:"SessionStart",session_id:$s,cwd:$cwd,source:"startup"}'
  else
    jq -cn --arg s "$2" --arg cwd "$3" --argjson active "$4" \
      '{hook_event_name:"Stop",session_id:$s,cwd:$cwd,stop_hook_active:$active,last_assistant_message:"Done."}'
  fi
}

# The packaged hook config points both events at this bundle's executable.
assert jq -e '(.hooks | keys) == ["SessionStart","Stop"]' "$HOOKS_JSON"
assert jq -e '[.hooks[][].hooks[].command] ==
  ["\"${CLAUDE_PLUGIN_ROOT}/skills/review/references/review-completion-hook.sh\" session-start",
   "\"${CLAUDE_PLUGIN_ROOT}/skills/review/references/review-completion-hook.sh\" stop"]' "$HOOKS_JSON"
assert test -x "$HOOK"

export TMPDIR="$TMP"
REPO="$TMP/repository"
make_repo "$REPO" https://github.com/Fixture/consumer.git
native SessionStart native-session "$REPO" > "$TMP/start.json"
native Stop native-session "$REPO" false > "$TMP/stop.json"
native Stop native-session "$REPO" true > "$TMP/stop-active.json"

# A hook that exits nonzero fails every wrapper, even with matching output.
fails() { ! "$@"; }
REAL_HOOK="$HOOK"; HOOK="$TMP/crashing-hook"
printf '#!/usr/bin/env bash\ncat %q\nexit 7\n' "$TMP/crash.out" > "$HOOK"; chmod +x "$HOOK"
: > "$TMP/crash.out"
assert fails silent stop "$TMP/stop.json"
jq -cn --arg reason "$REASON" '{decision:"block",reason:$reason}' > "$TMP/crash.out"
assert fails blocks "$TMP/stop.json"
jq -cn '{systemMessage:"Not ready: crashed"}' > "$TMP/crash.out"
assert fails diagnoses stop "$TMP/stop.json" 'Not ready'
HOOK="$REAL_HOOK"

# Malformed input, wrong events, bad modes and missing assets are precise diagnostics.
printf 'not json' > "$TMP/malformed.json"
assert diagnoses stop "$TMP/malformed.json" 'malformed or unsupported native Stop input'
assert diagnoses session-start "$TMP/stop.json" 'malformed or unsupported native SessionStart input'
jq 'del(.stop_hook_active)' "$TMP/stop.json" > "$TMP/no-active.json"
assert diagnoses stop "$TMP/no-active.json" 'malformed or unsupported native Stop input'
assert diagnoses unknown "$TMP/stop.json" 'unsupported mode'
mkdir "$TMP/partial-bundle"; cp "$HOOK" "$TMP/partial-bundle/"
"$TMP/partial-bundle/review-completion-hook.sh" stop < "$TMP/stop.json" > "$TMP/out"
assert jq -e '.systemMessage | contains("review-owner-context.sh is missing")' "$TMP/out"
assert sh -c '! grep -q enabled "$1"' sh "$TMP/out"

# Missing SessionStart context is silent here; binding reports unavailability.
assert silent stop "$TMP/stop.json"
if "$CONTEXT" bind --repository-root "$REPO" --context "$TMP/none.json" < "$TMP/stop.json" > "$TMP/bind.out" 2>&1; then
  printf '%s\n' 'FAIL: bind accepted a missing SessionStart context' >&2; exit 1
fi
assert grep -q 'hook activation unavailable' "$TMP/bind.out"

# SessionStart supplies only the exact current-session pointer.
hook session-start "$TMP/start.json"
assert jq -e '.hookSpecificOutput.hookEventName == "SessionStart"' "$TMP/out"
POINTER="$(jq -r '.hookSpecificOutput.additionalContext | split(" ")[3] | rtrimstr(".")' "$TMP/out")"
assert jq -e '.phase == "planning" and .run_id == null and .session_id == "native-session"' "$POINTER"
# The Stop key derivation is pinned to the helper's.
KEY="$(printf '%s\0%s\0%s' Fixture/consumer "$REPO" native-session | sha256sum | awk '{print $1}')"
assert test "$POINTER" = "$TMP/claude-hook-state/review-$KEY/review-owner.json"

# Planning in a dirty checkout and plan approval waits are silent.
printf 'dirty planning note\n' >> "$REPO/source.txt"
assert silent stop "$TMP/stop.json"
assert phase awaiting_plan_approval
assert silent stop "$TMP/stop.json"
git -C "$REPO" checkout -q -- source.txt

# Bind the real owner after approval. Resume preserves the bound pointer.
RUN_ROOT="$("$KERNEL" owned-run-start --workflow pipeline --run-id parent --base "$TMP/runs" | jq -r .path)"
STATE="$REPO/.workflow-kernel/runs/parent"; mkdir -p "$STATE"
"$CONTEXT" bind --repository-root "$REPO" --context "$POINTER" --workflow pipeline --run-id parent \
  --run-root "$RUN_ROOT" --state-dir "$STATE" --change-boundary "$(boundary)" < "$TMP/start.json" >/dev/null
cp "$POINTER" "$TMP/bound.json"
jq '.source="resume"' "$TMP/start.json" > "$TMP/resume.json"
hook session-start "$TMP/resume.json"
assert cmp "$POINTER" "$TMP/bound.json"

# Foreign sessions, workers, other checkouts and unrelated repositories are silent.
native Stop other-session "$REPO" false > "$TMP/other-session.json"
assert silent stop "$TMP/other-session.json"
jq '.agent_id="worker" | .agent_type="builder"' "$TMP/stop.json" > "$TMP/worker.json"
assert silent stop "$TMP/worker.json"
mkdir "$REPO/nested"
native Stop native-session "$REPO/nested" false > "$TMP/nested.json"
assert silent stop "$TMP/nested.json"
make_repo "$TMP/foreign" https://github.com/Fixture/foreign.git
printf 'dirty foreign work\n' >> "$TMP/foreign/source.txt"
native Stop native-session "$TMP/foreign" false > "$TMP/foreign.json"
assert silent stop "$TMP/foreign.json"
make_repo "$TMP/unrelated" ""
native Stop native-session "$TMP/unrelated" false > "$TMP/unrelated.json"
assert silent stop "$TMP/unrelated.json"
jq '.session_id="forged-session"' "$TMP/bound.json" > "$POINTER"
assert silent stop "$TMP/stop.json"
cp "$TMP/bound.json" "$POINTER"; chmod 644 "$POINTER"
assert silent stop "$TMP/stop.json"
chmod 600 "$POINTER"

# Clean committed implementation in executing gets exactly one continuation.
commit_change 'implemented change'
assert test -z "$(git -C "$REPO" status --short)"
assert blocks "$TMP/stop.json"
# A question or repeated stop at the same boundary is silent.
assert silent stop "$TMP/stop.json"
# The marker is dedupe state only and never feeds publication.
assert test -n "$(find "$(dirname "$POINTER")" -name 'continued-*' -print -quit)"
assert sh -c '! grep -Eq "continued-|review-completion-hook" "$1"' sh "$REFS/publish-reviewed-pr.sh"
assert sh -c '! grep -Eq "role-dispatch|dm-review-loop|codex exec|claude -p" "$1"' sh "$HOOK"

# A successful continuation advances the owner; its recursive Stop is silent.
assert phase checking
assert phase awaiting_ui
assert silent stop "$TMP/stop-active.json"
assert silent stop "$TMP/stop.json"
assert phase awaiting_merge
assert silent stop "$TMP/stop.json"

# Changed source gets its own bounded check; a repeated failure ends Not ready.
assert phase checking
commit_change 'repair after feedback'
assert blocks "$TMP/stop.json"
assert diagnoses stop "$TMP/stop-active.json" 'Not ready: the bounded review continuation ended'
assert test "$(recorded_phase)" = blocked
assert silent stop "$TMP/stop.json"
assert silent stop "$TMP/stop-active.json"

# Another hook's continuation never starts this hook's loop.
assert phase executing
commit_change 'resumed owner work'
rm -f "$(dirname "$POINTER")"/continued-*
assert silent stop "$TMP/stop-active.json"
assert test "$(recorded_phase)" = executing
assert blocks "$TMP/stop.json"

# A bound owner whose exact-owned metadata no longer matches is not adopted.
cp "$RUN_ROOT/.depot-owned-run.json" "$TMP/meta.json"
jq '.run_id="foreign"' "$TMP/meta.json" > "$RUN_ROOT/.depot-owned-run.json"
commit_change 'unvalidated owner work'
assert diagnoses stop "$TMP/stop.json" 'bound review owner cannot be validated'
cp "$TMP/meta.json" "$RUN_ROOT/.depot-owned-run.json"

# Terminal phases are silent; clear removes only the root's completed binding.
assert phase checking
assert phase complete
assert silent stop "$TMP/stop.json"
"$CONTEXT" clear --repository-root "$REPO" --context "$POINTER" --run-id parent --run-root "$RUN_ROOT" < "$TMP/start.json"
assert test ! -e "$POINTER"
assert silent stop "$TMP/stop.json"

printf 'review completion hook fixtures: %s assertions passed (source proof; native delivery not exercised)\n' "$pass"
