#!/usr/bin/env bash
#
# validate-workflow-contracts.sh -- Guard the two prose contracts that pipeline
# and dm-review depend on but that nothing else enforces:
#
#   1. Repository cleanup contract -- worktree/branch registry, safe-to-delete
#      decision table, feature-branch protection, honest inventory reporting.
#   2. Datastar-first contract -- Datastar/Datastar Pro before hand-rolled JS,
#      plus the bundle-presence rule that keeps agents from emitting inert
#      Pro attributes.
#
# Both are Markdown. Markdown rots silently. These grep assertions fail loudly
# when a required anchor disappears from a workflow file.
#
# Wired into tools/validate-composition.sh (section "Workflow contracts").

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

failures=0

require_text() {
  local file="$1"
  local pattern="$2"
  local label="$3"

  if [ ! -f "$file" ]; then
    printf "  FAIL  %s (missing file: %s)\n" "$label" "${file#$REPO_ROOT/}"
    failures=1
    return
  fi

  if grep -Fq "$pattern" "$file"; then
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

  if [ ! -f "$file" ]; then
    printf "  FAIL  %s (missing file: %s)\n" "$label" "${file#$REPO_ROOT/}"
    failures=1
    return
  fi

  if grep -Fq "$pattern" "$file"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
}

# --------------------------------------------------------------------------
# Group 1: Repository cleanup contract
# --------------------------------------------------------------------------

contract="$REPO_ROOT/plugins/dm-review/skills/review/references/repo-cleanup-contract.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
pipeline_cmd="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
pipeline_run="$REPO_ROOT/plugins/pipeline/commands/pipeline-run.md"
pipeline_fix="$REPO_ROOT/plugins/pipeline/commands/pipeline-fix.md"
lifecycle="$REPO_ROOT/plugins/pipeline/references/artifact-lifecycle.md"
review_skill="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
review_loop="$REPO_ROOT/plugins/dm-review/commands/dm-review-loop.md"
review_fix="$REPO_ROOT/plugins/dm-review/commands/dm-review-fix.md"
output_format="$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md"

printf "Repository cleanup contract:\n"

# The contract itself carries its five load-bearing anchors.
require_text "$contract" "## Branch & Worktree Inventory" "contract defines the inventory block"
require_text "$contract" "merge-base --is-ancestor" "contract uses ancestor test as merge proof"
require_text "$contract" "git worktree prune" "contract prunes stale registrations"
require_text "$contract" "Feature-branch protection" "contract protects the feature branch"
require_text "$contract" "Blocked-removal reporting" "contract requires blocked-removal reporting"

# Pipeline honors it.
require_text "$orchestrator" "Step 0e" "orchestrator initializes the ref registry"
require_text "$orchestrator" "merge-base --is-ancestor" "orchestrator proves merge before deleting a branch"
require_text "$orchestrator" "git worktree prune" "orchestrator prunes stale worktree registrations"
require_text "$orchestrator" "## Branch & Worktree Inventory" "orchestrator receipt carries the inventory"
require_text "$orchestrator" "Never delete the feature branch without merge proof" "orchestrator forbids unproven feature-branch deletion"
require_text "$orchestrator" "Always run the repository cleanup phase" "orchestrator makes cleanup unconditional"
require_text "$lifecycle" "Repository-lifetime durable identity; never Tier 2 and never auto-deleted" "repository scope is durable, not run-scoped"
require_text "$lifecycle" 'Semantic parity `match` alone never authorizes its deletion' "parity cannot delete terminal run state"
require_text "$lifecycle" 'exact `(scope_id, run_id)`' "terminal run deletion requires exact scope and run absence"
require_text "$lifecycle" "no uninspectable match remains" "terminal run deletion blocks on uninspectable Docker matches"
require_text "$orchestrator" 'Never auto-delete `.workflow-kernel/repository-scope.json`' "orchestrator preserves repository scope identity"
require_absent "$orchestrator" '`.workflow-kernel/runs/<run-id>/`, `shadow-report.json`' "orchestrator does not delete run state on parity match alone"

# The old fragile sweep must stay gone: `grep -o` on porcelain output breaks on
# feature slugs containing regex metacharacters.
require_absent "$orchestrator" "grep -o '\\.worktrees/pipeline" "orchestrator no longer regex-greps porcelain output"

# `2>/dev/null` on a worktree dirtiness check turns a git failure into "clean"
# and routes an unreadable worktree to removal.
require_absent "$orchestrator" 'status --porcelain 2>/dev/null)" ]' "orchestrator does not mask git status failures as clean"
require_absent "$contract" 'status --porcelain 2>/dev/null)" ]' "contract does not mask git status failures as clean"

# Piping into `while` runs the loop in a subshell, silently discarding every
# BLOCKED_REFS mutation -- blocked refs then vanish from the receipt.
require_absent "$orchestrator" "| while IFS= read -r WT" "orchestrator sweep avoids the subshell-losing-state pipe"

# Shell state does not persist across orchestrator steps. Step 3j and Step 5b are
# separate invocations, so EACH must define `block` before using it. Two
# definitions is the floor; one means a snippet dies with `command not found`
# and its blocked refs never reach the inventory.
block_defs="$(grep -c '^block() {' "$orchestrator" 2>/dev/null || echo 0)"
if [ "${block_defs:-0}" -ge 2 ]; then
  printf "  OK    orchestrator defines block() in each cleanup step (%s definitions)\n" "$block_defs"
else
  printf "  FAIL  orchestrator defines block() only %s time(s) -- Step 3j and Step 5b are separate shells\n" "${block_defs:-0}"
  failures=1
fi

require_text "$pipeline_cmd" "repo-cleanup-contract.md" "pipeline command references the cleanup contract"
require_text "$pipeline_cmd" "repository cleanup phase runs on all three answers" "pipeline gate runs cleanup on every answer"
require_text "$pipeline_run" "repo-cleanup-contract.md" "pipeline-run references the cleanup contract"
require_text "$pipeline_run" "Repository cleanup is host-independent" "Codex adapter gets the same cleanup gate"
require_text "$pipeline_fix" "repo-cleanup-contract.md" "pipeline-fix references the cleanup contract"
require_text "$lifecycle" "repo-cleanup-contract.md" "artifact lifecycle defers refs to the cleanup contract"
require_text "$lifecycle" "## Branch & Worktree Inventory" "artifact lifecycle receipt carries the inventory"

# dm-review honors it.
require_text "$review_skill" "Phase 8: Repository Cleanup" "dm-review runs a repository cleanup phase"
require_text "$review_skill" "Phase 1b: Evidence Source Fallback" "dm-review falls back when PR threads are empty"
require_text "$review_skill" "repo-cleanup-contract.md" "dm-review review skill references the cleanup contract"
require_text "$review_loop" "repo-cleanup-contract.md" "dm-review-loop runs the cleanup phase"
require_text "$review_fix" "repo-cleanup-contract.md" "dm-review-fix runs the cleanup phase"
require_text "$output_format" "### Repository Cleanup" "review report carries the cleanup inventory"
require_text "$output_format" "**Lanes:**" "review report names which lanes ran"
require_text "$output_format" "**Evidence source:**" "review report names its evidence source"

# --------------------------------------------------------------------------
# Group 2: Datastar-first contract
# --------------------------------------------------------------------------

ds_assembly="$REPO_ROOT/plugins/assembly/skills/development/datastar-pro.md"
ds_review="$REPO_ROOT/plugins/dm-review/skills/review/references/datastar-pro.md"
datastar_sse="$REPO_ROOT/plugins/assembly/agents/workflow/datastar-sse.md"
promptcraft="$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
adversary="$REPO_ROOT/plugins/pipeline/agents/workflow/plan-adversary.md"
ui_standards="$REPO_ROOT/plugins/dm-review/agents/review/ui-standards-reviewer.md"

printf "\nDatastar-first contract:\n"

# All 10 Pro attributes and all 3 Pro actions are documented. An agent that
# cannot see an attribute will hand-roll the JS it replaces.
for attr in data-animate data-custom-validity data-match-media data-on-raf \
            data-on-resize data-persist data-query-string data-replace-url \
            data-scroll-into-view data-view-transition; do
  require_text "$ds_assembly" "$attr" "assembly datastar-pro documents $attr"
done

for act in "@clipboard" "@fit" "@intl"; do
  require_text "$ds_assembly" "$act" "assembly datastar-pro documents $act"
done

require_text "$ds_assembly" "Verified against:" "assembly datastar-pro records the verified version"
require_text "$ds_assembly" "inert" "assembly datastar-pro warns that a missing plugin is inert"

require_text "$ds_review" "plugins/assembly/skills/development/datastar-pro.md" "dm-review datastar-pro names its upstream source"
require_text "$ds_review" "Verified against:" "dm-review datastar-pro records the verified version"
require_text "$ds_review" "Inert Pro Attribute" "dm-review datastar-pro defines the inert-attribute finding"
require_text "$ds_review" "Hand-Rolled JS Where Datastar Suffices" "dm-review datastar-pro defines the hand-rolled-JS finding"

require_text "$datastar_sse" "## Datastar Pro" "datastar-sse agent teaches the Pro surface"
require_text "$promptcraft" "Phase 3o: Datastar-First Gate" "promptcraft gates UI chunks on Datastar-first"
require_text "$adversary" "Datastar-first" "plan-adversary checks for hand-rolled JS"
require_text "$ui_standards" "Inert Pro Attribute" "ui-standards-reviewer detects inert Pro attributes"

# The Datastar Pro facts are duplicated across three files by design (dm-review
# must not depend on assembly; the agent inlines its own copy). Duplication is
# only acceptable while something detects drift. These two checks are that
# something: an unenforced "keep these in sync" comment is a lie waiting to
# happen.
#
# Canonical source: plugins/assembly/skills/development/datastar-pro.md

# The hash is backticked in prose (``0f86778``), so capture version and hash
# separately and require BOTH in each dependent. Matching only "vX.Y.Z, commit "
# with an empty hash would let a rehashed same-version copy pass silently.
canonical_ver="$(grep -m1 -oE 'v[0-9]+\.[0-9]+\.[0-9]+' "$ds_assembly" 2>/dev/null || true)"
canonical_sha="$(grep -m1 -oE 'commit `[0-9a-f]{7,40}`' "$ds_assembly" 2>/dev/null | tr -d '`' | awk '{print $2}' || true)"
if [ -z "$canonical_ver" ] || [ -z "$canonical_sha" ]; then
  printf "  FAIL  canonical datastar-pro.md has no parseable 'Verified against:' version+commit\n"
  failures=1
else
  for dep in "$ds_review" "$datastar_sse"; do
    rel="${dep#$REPO_ROOT/}"
    if grep -Fq "$canonical_ver" "$dep" && grep -Fq "$canonical_sha" "$dep"; then
      printf "  OK    %s pinned to canonical Pro %s (%s)\n" "$rel" "$canonical_ver" "$canonical_sha"
    else
      printf "  FAIL  %s drifted from canonical Pro %s (%s)\n" "$rel" "$canonical_ver" "$canonical_sha"
      failures=1
    fi
  done
fi

# All 13 registered plugin names must appear in every file that tells an agent
# to grep the bundle for them. A missing name means an agent cannot detect that
# attribute's plugin, and silently ships an inert attribute.
registered="animate custom-validity match-media on-raf on-resize persist query-string replace-url scroll-into-view view-transition clipboard fit intl"
for dep in "$ds_assembly" "$ds_review" "$ui_standards" "$datastar_sse"; do
  rel="${dep#$REPO_ROOT/}"
  missing=""
  for n in $registered; do
    grep -Fq "\`$n\`" "$dep" || missing="$missing $n"
  done
  if [ -z "$missing" ]; then
    printf "  OK    %s lists all 13 registered plugin names\n" "$rel"
  else
    printf "  FAIL  %s missing registered name(s):%s\n" "$rel" "$missing"
    failures=1
  fi
done

# --------------------------------------------------------------------------
# Group 3: Baseplate evidence gates
# --------------------------------------------------------------------------

arch="$REPO_ROOT/plugins/dm-review/agents/review/architecture-reviewer.md"
sec="$REPO_ROOT/plugins/dm-review/agents/review/security-auditor.md"

printf "\nBaseplate evidence gates:\n"

require_text "$promptcraft" "Phase 3m: Fixture SDK Conformance Gate" "promptcraft gates fixture SDK conformance"
require_text "$promptcraft" "Phase 3n: Production Readiness Preflight Gate" "promptcraft gates production preflight"
require_text "$arch" "Fixture SDK Conformance Gap (P2)" "architecture-reviewer flags fixture conformance gaps"
require_text "$arch" "Missing Auth Boundary Map Receipt (P2)" "Auth Boundary Map receipt is a finding, not advisory"
require_absent "$arch" "This is advisory, not a finding" "Auth Boundary Map advisory language removed"
require_text "$sec" "Public/Private URL Boundary" "security-auditor guards the public/private URL boundary"
require_text "$sec" "Update / Release Preflight" "security-auditor checks update/release preflight"
require_text "$sec" "Responder-side share transport" "security-auditor reviews the federation responder side"

printf "\n"
if [ "$failures" -ne 0 ]; then
  printf "FIX  restore the missing workflow-contract anchors (see docs and plugin sources above)\n"
  exit 1
fi

printf "OK    Workflow contracts intact (repository cleanup, Datastar-first, Baseplate gates)\n"
