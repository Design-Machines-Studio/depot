#!/usr/bin/env bash
#
# validate-codex-native-pipeline.sh -- Ensure /pipeline-run has a real Codex
# execution adapter instead of relying on Claude-only Agent/Skill tools.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

failures=0

require_text() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if grep -Fq -- "$pattern" "$file"; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

require_absent() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if grep -Fq -- "$pattern" "$file"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
}

pipeline_run="$REPO_ROOT/plugins/pipeline/commands/pipeline-run.md"
pipeline_command="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
generated_alias="$REPO_ROOT/plugins/pipeline/skills/pipeline-run/SKILL.md"

require_text "$pipeline_run" "## Codex Native Execution Adapter" "pipeline-run documents Codex-native execution"
codex_adapter="$REPO_ROOT/plugins/pipeline/references/codex-native-execution-adapter.md"
browser_preflight="$REPO_ROOT/plugins/pipeline/references/execution-browser-preflight.md"
require_text "$pipeline_run" "codex-native-execution-adapter.md" "pipeline-run loads the Codex native adapter on a Codex host"
require_text "$codex_adapter" "role-dispatch.sh" "Codex host adapter sends implementation through model-router"
require_absent "$codex_adapter" 'call `multi_agent_v1.spawn_agent`' "Codex host adapter does not select a participant transport"
require_text "$codex_adapter" "dm-review inline protocol" "Codex adapter replaces nested Skill calls with inline review protocol"
require_text "$pipeline_run" "executionMode: codex_native" "pipeline-run records codex_native receipts"

require_text "$pipeline_command" "Codex Native Execution Adapter" "full pipeline Phase 6 links to Codex-native adapter"
require_text "$pipeline_command" "Mandatory regardless of resolved participant" "full pipeline keeps the required adversarial lens participant-neutral"
require_text "$pipeline_command" "role-level planning coverage receipt" "full pipeline records role-level planning coverage"

require_text "$orchestrator" "codex_native" "orchestrator accepts codex_native execution mode"
require_text "$orchestrator" "Host Adapter Parity" "orchestrator documents participant-neutral host parity"
require_text "$orchestrator" 'BASE_BRANCH="${manifest.baseBranch:-main}"' "orchestrator branches from manifest.baseBranch with main fallback"
require_text "$orchestrator" "pipeline-owned artifacts" "orchestrator distinguishes pipeline artifacts from user changes"
require_text "$orchestrator" "sequential-on-branch" "orchestrator documents container-mounted sequential execution mode"
require_text "$browser_preflight" "manifest.devServerURL" "browser preflight accepts manifest.devServerURL for browser proof"
require_text "$browser_preflight" "Never infer a port" "browser preflight forbids inferred targets"
require_absent "$browser_preflight" "http://localhost:3000" "browser preflight does not scan guessed localhost ports"
require_text "$orchestrator" "git add -A --" "orchestrator stages pathspecs without aborting on missing renamed files"
require_text "$orchestrator" "git commit -F" "orchestrator writes commit messages from files"
require_text "$orchestrator" "git check-ignore -q plans/" "orchestrator detects ignored plans receipts"

require_text "$generated_alias" "## Codex Native Execution Adapter" "generated pipeline-run skill contains adapter section"
promptcraft="$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
require_text "$promptcraft" "There is no minimum prompt-line or general acceptance-criterion count" "promptcraft rejects count floors"
require_text "$promptcraft" 'Every `renderedSurface: required` chunk gets at least two rendered-impression criteria' "promptcraft retains two visual criteria for rendered-surface chunks"
require_text "$promptcraft" "Relative size alone is never under-specification or a blocker" "prompt size parity is advisory only"
require_absent "$promptcraft" "Classification floors:" "promptcraft removes classification floors"
require_absent "$promptcraft" "below Logic floor" "promptcraft removes below-floor blockers"
require_absent "$promptcraft" "floors are non-negotiable" "promptcraft removes non-negotiable floors"
require_text "$promptcraft" "module build/tests pass in Docker" "promptcraft avoids bare Go command phrases in commit text"

# Execute the sequential commit gate from the instructions themselves. A
# disconnected fixture implementation would not catch a regressed command.
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pipeline-sequential.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
sed -n '/^# sequential-commit-check:start$/,/^# sequential-commit-check:end$/p' \
  "$orchestrator" > "$TMP/check.sh"
test -s "$TMP/check.sh" || { printf 'FAIL: missing sequential commit gate\n' >&2; exit 1; }
CHUNK_ROOT="$TMP/repository"
git init -q "$CHUNK_ROOT"
git -C "$CHUNK_ROOT" config user.name fixture
git -C "$CHUNK_ROOT" config user.email fixture@example.invalid
git -C "$CHUNK_ROOT" commit --allow-empty -qm base
FEATURE_BRANCH=fixture-feature
git -C "$CHUNK_ROOT" checkout -qb "$FEATURE_BRANCH"
CHUNK_START_HEAD="$(git -C "$CHUNK_ROOT" rev-parse HEAD)"
export CHUNK_ROOT FEATURE_BRANCH CHUNK_START_HEAD
expect_rejected() {
  if bash "$TMP/check.sh" >/dev/null 2>&1; then
    printf 'FAIL: sequential gate accepted %s\n' "$1" >&2
    exit 1
  fi
}
expect_rejected 'a chunk without a new commit'
git -C "$CHUNK_ROOT" commit --allow-empty -qm chunk-one
bash "$TMP/check.sh"
if git -C "$CHUNK_ROOT" show-ref --verify --quiet refs/heads/pipeline/fixture/chunk-one; then
  printf 'FAIL: sequential fixture unexpectedly has a chunk branch\n' >&2
  exit 1
fi
printf 'dirty\n' > "$CHUNK_ROOT/untracked.txt"
expect_rejected 'uncommitted work'
rm "$CHUNK_ROOT/untracked.txt"
CHUNK_START_HEAD="$(git -C "$CHUNK_ROOT" rev-parse HEAD)"
export CHUNK_START_HEAD
expect_rejected 'the preceding chunk as new work'
git -C "$CHUNK_ROOT" commit --allow-empty -qm chunk-two
bash "$TMP/check.sh"
printf 'repair\n' > "$CHUNK_ROOT/repair.txt"
expect_rejected 'a repair before its commit'
git -C "$CHUNK_ROOT" add repair.txt
git -C "$CHUNK_ROOT" commit -qm repair-two
bash "$TMP/check.sh"
test "$(git -C "$CHUNK_ROOT" rev-list --count "$CHUNK_START_HEAD..HEAD")" -eq 2
test "$(git -C "$CHUNK_ROOT" diff --name-only "$CHUNK_START_HEAD..HEAD")" = repair.txt
require_text "$orchestrator" 'stage and commit the complete repair batch in <review-root>' "review repairs commit before the sequential gate"
require_text "$orchestrator" 'Final feature review uses the existing physical checkout of' "final repair binds the integrated feature checkout"
require_text "$orchestrator" 'pending = ls <review-root>/todos/' "finding lookup uses the bound review root"
require_text "$orchestrator" 'apply the fix to the cited file in <review-root>' "repairs use the bound review root"
require_text "$orchestrator" 'Supply both heads, that inventory and that diff as' "per-chunk review receives the explicit commit boundary"
require_text "$orchestrator" 'Every Step 3g repair batch, including focused UI/Logic, Integration and Trivial' "ordinary review repairs use the commit protocol"
require_text "$orchestrator" 'args=review_args' "nested review consumes its selected arguments"
require_text "$orchestrator" '--base-commit <CHUNK_START_HEAD> --head-commit <CHUNK_END_HEAD>' "nested chunk review passes the supported commit range"

sed -n '/^# chunk-end-head:start$/,/^# chunk-end-head:end$/p' \
  "$orchestrator" > "$TMP/capture-head.sh"
test -s "$TMP/capture-head.sh"
git -C "$CHUNK_ROOT" worktree add -qb fixture-chunk "$TMP/chunk-worktree"
git -C "$TMP/chunk-worktree" commit --allow-empty -qm worktree-chunk
captured_head="$(CHUNK_ROOT="$TMP/chunk-worktree" bash -c 'source "$1"; printf "%s\n" "$CHUNK_END_HEAD"' -- "$TMP/capture-head.sh")"
test "$captured_head" = "$(git -C "$TMP/chunk-worktree" rev-parse HEAD)"

# The receiving review skill, not a parallel fixture algorithm, selects the
# second chunk's diff and rejects stale, malformed and dirty inputs.
review_skill="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
sed -n '/^# exact-review-range:start$/,/^# exact-review-range:end$/p' \
  "$review_skill" > "$TMP/review-range.sh"
test -s "$TMP/review-range.sh"
REVIEW_ROOT="$CHUNK_ROOT"
REVIEW_BASE_COMMIT="$CHUNK_START_HEAD"
REVIEW_HEAD_COMMIT="$(git -C "$CHUNK_ROOT" rev-parse HEAD)"
REVIEW_DIFF_FILE="$TMP/review.patch"
REVIEW_FILES_FILE="$TMP/review-files.txt"
export REVIEW_ROOT REVIEW_BASE_COMMIT REVIEW_HEAD_COMMIT REVIEW_DIFF_FILE REVIEW_FILES_FILE
bash "$TMP/review-range.sh"
test "$(cat "$REVIEW_FILES_FILE")" = repair.txt
grep -Fq '+repair' "$REVIEW_DIFF_FILE"
expect_range_rejected() {
  if bash "$TMP/review-range.sh" >/dev/null 2>&1; then
    printf 'FAIL: exact review accepted %s\n' "$1" >&2
    exit 1
  fi
}
REVIEW_BASE_COMMIT=main expect_range_rejected 'a branch name instead of an exact commit'
REVIEW_HEAD_COMMIT="$CHUNK_START_HEAD" expect_range_rejected 'a stale end head'
REVIEW_BASE_COMMIT= expect_range_rejected 'a missing base'
printf 'dirty\n' > "$CHUNK_ROOT/dirty.txt"
expect_range_rejected 'uncommitted changes'
rm "$CHUNK_ROOT/dirty.txt"
require_text "$review_skill" 'First parse optional paired `--base-commit <sha>` and `--head-commit <sha>`' "review target detection accepts the chunk range"
require_text "$review_skill" 'Use those exact files for changed-file discovery, lane triggers, reviewer' "range evidence drives actual review selection"
require_text "$codex_adapter" 'Forward the orchestrator' "Codex inline adapter forwards the selected target"
require_text "$codex_adapter" '--base-commit <CHUNK_START_HEAD> --head-commit <CHUNK_END_HEAD>' "Codex inline adapter uses the tested exact-range receiver"
require_text "$codex_adapter" 'Final review keeps complete feature/PR scope without the per-chunk range.' "Codex final review restores full scope"

# Execute the documented dispatch from the wrong parent directory and prove
# that its child receives the selected worktree and absolute prompt path.
sed -n '/^# selected-root-dispatch:start$/,/^# selected-root-dispatch:end$/p' \
  "$orchestrator" > "$TMP/dispatch.sh"
test -s "$TMP/dispatch.sh"
cat > "$TMP/role-dispatch.sh" <<'STUB'
#!/usr/bin/env bash
test "$(pwd -P)" = "$CHUNK_ROOT" || exit 81
test "$1" = --prompt-file && test "$2" = "$WORKER_PROMPT" && test -f "$2"
STUB
chmod +x "$TMP/role-dispatch.sh"
ROLE_DISPATCH="$TMP/role-dispatch.sh"
WORKER_PROMPT="$TMP/prompt.md"
OWNED_PATHS=repair.txt
printf 'fixture\n' > "$WORKER_PROMPT"
export ROLE_DISPATCH WORKER_PROMPT OWNED_PATHS
(cd "$TMP" && bash -c 'ROLE_ARGS=(--prompt-file "$WORKER_PROMPT"); source "$1"' -- "$TMP/dispatch.sh")
git -C "$CHUNK_ROOT" checkout -qb wrong-branch
expect_rejected 'a different branch'
git -C "$CHUNK_ROOT" checkout -q "$FEATURE_BRANCH"
CHUNK_START_HEAD="$(git -C "$CHUNK_ROOT" hash-object -t commit -w --stdin <<EOF
tree $(git -C "$CHUNK_ROOT" rev-parse HEAD^{tree})
author Fixture <fixture@example.invalid> 0 +0000
committer Fixture <fixture@example.invalid> 0 +0000

unrelated root
EOF
)"
export CHUNK_START_HEAD
expect_rejected 'a non-ancestor starting commit'
require_text "$orchestrator" 'Record `already-integrated`' "sequential mode skips nonexistent chunk merge"
require_text "$orchestrator" 'Only under `per-chunk-worktree`, run:' "merge commands are worktree-only"
require_text "$orchestrator" 'or branch was created: record Git cleanup as `not-applicable`' "sequential mode skips nonexistent Git cleanup"
require_text "$orchestrator" 'Only under `per-chunk-worktree`, load' "cleanup script is worktree-only"
require_absent "$orchestrator" '<worktree-path>' "review and repair use the selected chunk root"
printf 'OK    sequential commit gate accepts direct commits and rejects invalid boundaries\n'

if [ "$failures" -ne 0 ]; then
  printf "FIX  add the Codex-native pipeline execution adapter and regenerate command skill aliases\n"
  exit 1
fi

printf "OK    Codex-native pipeline execution adapter documented and generated\n"
