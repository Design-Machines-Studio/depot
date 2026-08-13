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

  # `--` before the pattern: a pattern that starts with a dash (a CLI flag, say)
  # is otherwise parsed as a grep option and the check silently fails.
  if grep -Fq -- "$pattern" "$file"; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

require_line() {
  local file="$1"
  local line="$2"
  local label="$3"

  if [ ! -f "$file" ]; then
    printf "  FAIL  %s (missing file: %s)\n" "$label" "${file#$REPO_ROOT/}"
    failures=1
    return
  fi
  if grep -Fxq -- "$line" "$file"; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

require_line_mutation_sensitive() {
  local file="$1"
  local exact="$2"
  local replacement="$3"
  local label="$4"
  local mutated

  mutated=$(mktemp) || {
    printf "  FAIL  %s (could not allocate fixture)\n" "$label"
    failures=1
    return
  }
  awk -v exact="$exact" -v replacement="$replacement" \
    '{ print ($0 == exact ? replacement : $0) }' "$file" > "$mutated"
  if cmp -s "$file" "$mutated" || grep -Fxq -- "$exact" "$mutated"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
  rm -f "$mutated"
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

  # `--` as above, and it matters more here: without it a dash-leading pattern
  # makes grep exit non-zero as an *error*, which this branch would then report
  # as the absence it was asked to prove. A check that fails open is worse than
  # no check, because the OK line says it ran.
  if grep -Fq -- "$pattern" "$file"; then
    printf "  FAIL  %s\n" "$label"
    failures=1
  else
    printf "  OK    %s\n" "$label"
  fi
}

require_before() {
  local file="$1"
  local first="$2"
  local second="$3"
  local label="$4"
  local first_line second_line

  first_line="$(grep -nF -m1 -- "$first" "$file" 2>/dev/null | cut -d: -f1 || true)"
  second_line="$(grep -nF -m1 -- "$second" "$file" 2>/dev/null | cut -d: -f1 || true)"
  if [ -n "$first_line" ] && [ -n "$second_line" ] && [ "$first_line" -lt "$second_line" ]; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s\n" "$label"
    failures=1
  fi
}

# --------------------------------------------------------------------------
# Group 1: Repository cleanup contract
# --------------------------------------------------------------------------

contract="$REPO_ROOT/plugins/dm-review/skills/review/references/repo-cleanup-contract.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
pipeline_cmd="$REPO_ROOT/plugins/pipeline/commands/pipeline.md"
pipeline_run="$REPO_ROOT/plugins/pipeline/commands/pipeline-run.md"
# Defined here, not at first use in Group 7: Group 5 anchors these too, and a
# variable assigned below its own use expands empty and reports "missing file".
pipeline_run_skill="$REPO_ROOT/plugins/pipeline/skills/pipeline-run/SKILL.md"
routing_policy="$REPO_ROOT/plugins/pipeline/references/routing-policy.json"
pipeline_prompts="$REPO_ROOT/plugins/pipeline/commands/pipeline-prompts.md"
pipeline_fix="$REPO_ROOT/plugins/pipeline/commands/pipeline-fix.md"
lifecycle="$REPO_ROOT/plugins/pipeline/references/artifact-lifecycle.md"
review_skill="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
review_cmd="$REPO_ROOT/plugins/dm-review/commands/dm-review.md"
review_consolidator="$REPO_ROOT/plugins/dm-review/agents/workflow/review-consolidator.md"
review_loop="$REPO_ROOT/plugins/dm-review/commands/dm-review-loop.md"
review_loop_skill="$REPO_ROOT/plugins/dm-review/skills/dm-review-loop/SKILL.md"
review_fix="$REPO_ROOT/plugins/dm-review/commands/dm-review-fix.md"
output_format="$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md"
kernel_skill="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/SKILL.md"
kernel_cli="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/cli.py"
kernel_promotion="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/promotion.py"
verification_planner="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_repository.py"
verification_contract_runtime="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_contract.py"
verification_execution="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_execution.py"
repository_verification="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md"
assembly_build="$REPO_ROOT/plugins/assembly/commands/assembly-build.md"
assembly_test_runner="$REPO_ROOT/plugins/assembly/agents/workflow/go-test-runner.md"
assembly_go_tests="$REPO_ROOT/plugins/assembly/agents/workflow/go-test-runner.md"
assembly_verification_profile="$REPO_ROOT/plugins/assembly/references/repository-verification-profile.example.json"
assembly_development="$REPO_ROOT/plugins/assembly/skills/development/SKILL.md"
assembly_nats_reviewer="$REPO_ROOT/plugins/assembly/agents/review/nats-reviewer.md"
assembly_nats_skill="$REPO_ROOT/plugins/assembly/skills/nats-jetstream/SKILL.md"
assembly_workflows="$REPO_ROOT/plugins/assembly/skills/development/workflows.md"
promptcraft="$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
plan_adversary="$REPO_ROOT/plugins/pipeline/agents/workflow/plan-adversary.md"
postmortem_schema="$REPO_ROOT/plugins/pipeline/references/run-postmortem-schema.md"
manifest_schema="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/manifest-schema.md"
verification_contract="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/verification-contract.md"
behavioral_schema="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/behavioral-verification-contract-schema.json"
quality_pulse_command="$REPO_ROOT/plugins/dm-review/commands/dm-review-quality-pulse.md"
quality_pulse_skill="$REPO_ROOT/plugins/dm-review/skills/quality-pulse/SKILL.md"
quality_pulse_profile="$REPO_ROOT/plugins/dm-review/skills/quality-pulse/references/profile-contract.md"
quality_pulse_output="$REPO_ROOT/plugins/dm-review/skills/quality-pulse/references/output-contract.md"
quality_pulse_trust="$REPO_ROOT/plugins/dm-review/skills/quality-pulse/references/trust-boundary.md"
quality_pulse_degradation="$REPO_ROOT/plugins/dm-review/skills/quality-pulse/references/graceful-degradation.md"

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
require_text "$review_loop" 'if rerun_lanes equals selected_full_set:' "dm-review-loop collapses equal-set selection to full fan-out"
require_text "$review_loop" 'rerun_reasons = every lane in selected_full_set -> ["initial_full_fanout"]' "dm-review-loop records equal-set collapse as full fan-out"
require_text "$review_loop" 'rerun_reasons = every lane in lanes_rerun -> ["selection_fail_open"]' "dm-review-loop rebuilds fail-open reasons from authoritative attempted lanes"
require_text "$review_loop" '`.workflow-kernel/`' "dm-review-loop excludes self-authored review artifacts from trigger matching"
require_text "$review_loop" '`full_fanout_override: true` and' "dm-review-loop keeps full-fanout skip sets empty"
require_text "$review_loop" 'explicit booleans `selective_rerun`, `promoted_to_full`, and' "dm-review-loop emits all required iteration booleans"
require_text "$review_skill" 'There is no additional authorization or fallback rail.' "dm-review has no hidden exhaustion rail"
require_absent "$review_skill" 'authorize one operator-selected fallback provider for THIS LANE' "dm-review removes executable exhaustion option b"
require_absent "$review_loop" '`lanes_skipped` -- `selected_full_set` minus those ATTEMPTED rows.' "dm-review-loop removes the retired attempted-complement skip formula"
require_absent "$review_loop_skill" '`lanes_skipped` -- `selected_full_set` minus those ATTEMPTED rows.' "generated dm-review-loop removes the retired attempted-complement skip formula"
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

# --------------------------------------------------------------------------
# Group 4: Workflow-kernel integration anchors
# --------------------------------------------------------------------------

printf "\nWorkflow-kernel integration anchors:\n"

require_text "$pipeline_run" "The Markdown manifest, this command, routing policy, orchestrator, and receipts remain authoritative." "pipeline preserves Markdown authority in shadow mode"
require_text "$pipeline_run" "runtime unavailable/incompatible" "pipeline preserves fallback when the kernel is unavailable"
require_text "$review_skill" "Kernel prediction is observation-only" "dm-review keeps shadow observation non-authoritative"
require_text "$review_skill" "human_help_required" "dm-review preserves required browser recovery escalation"
require_text "$verification_contract" "## Behavioral contract lifecycle" "shared verification contract defines the behavioral lifecycle"
require_text "$verification_contract" '`bind-verification-contract`' "shared verification contract binds before dispatch"
require_text "$verification_contract" 'The binding is immutable for that run.' "shared verification contract is immutable within a run"
require_text "$verification_contract" "quit the primary process or engine session" "shared verification contract requires primary quit"
require_text "$verification_contract" "fresh primary session" "shared verification contract requires primary restart"
require_text "$verification_contract" "different configured" "shared verification contract requires an alternate engine"
require_text "$verification_contract" '`human_help_required`' "shared verification contract ends exhausted recovery in human help"
require_text "$behavioral_schema" '"previous_contract_digest"' "behavioral schema binds revision ancestry"
require_text "$behavioral_schema" '"proves_regression_ids"' "behavioral schema requires executable regression proof links"
require_text "$verification_contract" 'Every prohibited regression has an' "shared verification contract requires regression coverage"
require_before "$orchestrator" 'bind-verification-contract --state-dir' '### 3d: Dispatch Implementation Subagent' "orchestrator binds contract before dispatch"
require_before "$pipeline_run" 'bind-verification-contract --state-dir' '**Implementation dispatch:**' "pipeline-run binds contract before dispatch"
require_text "$orchestrator" 'bind-verification-contract --state-dir .workflow-kernel/runs/<run-id>' "orchestrator binds contracts in the canonical run directory"
require_absent "$orchestrator" 'revise-verification-contract' "orchestrator has no contract-revision protocol"
require_text "$pipeline_run" 'bind-verification-contract --state-dir .workflow-kernel/runs/<run-id>' "pipeline-run binds contracts in the canonical run directory"
require_absent "$orchestrator" 'bind-verification-contract --state-dir plans/' "orchestrator never binds contracts in the observation directory"
require_absent "$pipeline_run" 'bind-verification-contract --state-dir plans/' "pipeline-run never binds contracts in the observation directory"
require_text "$orchestrator" "STEP5B_ORDER: docker_reconcile -> artifact_git_cleanup -> authoritative_terminal_receipt -> shadow_observe_compare_metrics" "orchestrator preserves terminal cleanup ordering"
require_text "$orchestrator" "Broad prune, wildcards, negative filters, and name-based ownership are forbidden." "orchestrator forbids broad Docker cleanup"
require_text "$kernel_skill" "Initialize every run in shadow mode" "kernel documents shadow default"
require_text "$kernel_cli" "default=RunMode.SHADOW.value" "kernel CLI defaults to shadow"
require_text "$kernel_promotion" "native_default_not_supported" "promotion keeps native default unsupported"

# --------------------------------------------------------------------------
# Group 5: Pipeline performance contract
# --------------------------------------------------------------------------

printf "\nPipeline performance contract:\n"

require_text "$pipeline_cmd" "focused Codex review for ordinary chunks" "pipeline command uses focused ordinary-chunk review"
require_text "$pipeline_run" "For ordinary non-sensitive chunks, run one focused read-only Codex review" "Codex adapter uses one focused ordinary-chunk reviewer"
require_text "$orchestrator" "Do not dispatch a multi-agent quick dm-review" "orchestrator avoids per-chunk review fanout"
require_text "$orchestrator" '`all-chunks-complete` boundary' "orchestrator batches intermediate shadow observation"
require_text "$orchestrator" "Empty-plan fast path" "orchestrator skips no-op cleanup commands"
require_text "$promptcraft" "Do not create an orchestrator-owned closeout chunk" "promptcraft excludes closeout-only chunks"
require_text "$promptcraft" "no more than 8 total chunks" "promptcraft enforces the default run-size budget"
require_text "$manifest_schema" "scope: newly discovered desirable work" "manifest contract freezes approved scope"
require_text "$pipeline_prompts" 'exact closed `decisionProfile`' "pipeline-prompts requires an approved decision profile"
require_text "$pipeline_prompts" '`bind-verification-contract`' "pipeline-prompts publishes contract binding"
require_text "$pipeline_prompts" '`decide-validation-retry`' "pipeline-prompts publishes bounded validation feedback"
require_text "$pipeline_prompts" "primary process/session quit" "pipeline-prompts publishes primary browser recovery"
require_text "$orchestrator" 'The ask is scheduling only.' "orchestrator keeps RC76 as a scheduling decision"
require_text "$orchestrator" 'offer exactly `wait` or `park`' "orchestrator closes the current ask action vocabulary"
if grep -Fq -- 'The answer must be an exact identifier from the derived list.' "$orchestrator"; then
  printf "  FAIL  orchestrator still requires a provider identifier for the wait/park ask\n"
  failures=1
else
  printf "  OK    orchestrator does not require a provider identifier for the wait/park ask\n"
fi
if grep -Fq -- '**(b) authorized fallback** -> proceed' "$orchestrator"; then
  printf "  FAIL  orchestrator still executes caller-owned authorized fallback\n"
  failures=1
else
  printf "  OK    orchestrator does not execute caller-owned authorized fallback\n"
fi
require_text "$pipeline_prompts" '`human_help_required`' "pipeline-prompts publishes human escalation"
require_text "$pipeline_prompts" "optimized ordinary path" "pipeline-prompts preserves the optimized ordinary path"
require_text "$review_cmd" "canonical finding IDs" "dm-review publishes stable finding identities"
require_text "$review_cmd" "disagreement is retained" "dm-review publishes disagreement preservation"
require_text "$review_cmd" "contribution receipts" "dm-review publishes contribution receipts"
require_text "$review_cmd" "raw evidence" "dm-review requires raw evidence"
require_text "$review_cmd" "finding-policy recommendation" "dm-review preserves proportional severity policy"
require_text "$review_cmd" "reported coverage gap" "dm-review preserves explicit coverage"
require_text "$review_cmd" "observation-only economics evidence" "dm-review contributions remain observation-only"
require_text "$review_consolidator" "stable ID" "review consolidator preserves stable IDs"
for loop_contract in "$review_loop" "$review_loop_skill"; do
  loop_contract_relative="${loop_contract#$REPO_ROOT/}"
  for receipt_field in selective_rerun lanes_rerun lanes_skipped rerun_reasons selection_fallback_reason; do
    require_text "$loop_contract" "\`$receipt_field\`" "$loop_contract_relative preserves $receipt_field receipt field"
  done
  require_text "$loop_contract" '**Convergence requires no open P1/P2 findings and complete required coverage for the verification pass.**' "$loop_contract_relative defines proportional convergence"
  require_text "$loop_contract" 'P3 advisories never trigger another pass.' "$loop_contract_relative excludes P3 from convergence"
  require_text "$loop_contract" 'the touched-file set is the union of `git diff --name-only <prior-review-head>..HEAD` and the paths reported by `git status --porcelain`' "$loop_contract_relative unions committed and uncommitted changed paths"
  require_text "$loop_contract" "An empty computed lane set is never dispatched." "$loop_contract_relative never dispatches an empty selection"
  require_text "$loop_contract" 'selection fails open to a full fan-out with `fallback_reason: empty selection`' "$loop_contract_relative fails open on an empty selection"
  require_text "$loop_contract" "iteration-receipt.json" "$loop_contract_relative names the iteration receipt artifact"
  require_text "$loop_contract" '`max-iterations-verification-receipt.json`' "$loop_contract_relative names the max-iterations receipt artifact"
  require_text "$loop_contract" 'Repeat the whole full fan-out only when the prior full review was incomplete or a repair changed a security-sensitive boundary.' "$loop_contract_relative limits repeated full fan-out"
  require_text "$loop_contract" 'prior_finding_owner_lanes = union of validated exact source_agents' "$loop_contract_relative preserves repaired finding ownership"
  require_text "$loop_contract" 'required_finding_files = todos/*-pending-p1-*.md plus todos/*-pending-p2-*.md' "$loop_contract_relative excludes P3 artifacts from convergence"
  require_text "$loop_contract" 'security_boundary_changed: security_boundary_changed' "$loop_contract_relative binds security repair classification"
  require_line "$loop_contract" '          rerun_lanes = lanes_a union lanes_b' "$loop_contract_relative keeps affected-lane assignment inside the non-promotion branch"
  require_line "$loop_contract" '          promoted_to_full = true' "$loop_contract_relative records ordinary full-review promotion"
done
require_text "$review_skill" '`review_lane_allowlist`' "review receiver names the selective lane allowlist"
require_text "$REPO_ROOT/plugins/dm-review/.claude-plugin/plugin.json" '"workflow-kernel": ">=0.14.0"' "dm-review requires the simplified verification kernel release"
require_text "$REPO_ROOT/plugins/pipeline/.claude-plugin/plugin.json" '"dm-review": ">=1.60.1"' "pipeline requires configured-key dm-review release"
require_text "$REPO_ROOT/plugins/dm-review/.claude-plugin/plugin.json" '"name": "Second Perspective Reviewer"' "dm-review manifest names the provider-neutral perspective lane"
require_text "$REPO_ROOT/plugins/dm-review/.claude-plugin/plugin.json" 'family-independent second-opinion review' "dm-review manifest describes family-independent perspective resolution"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md" 'Full mode only.' "migration-validator registry limits the lane to full mode"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md" 'quick mode does not add this lane' "migration-validator registry matches the executable quick roster"
for stale_migration_claim in 'Also dispatched in quick mode' 'dispatched in BOTH modes'; do
  if grep -Fq -- "$stale_migration_claim" "$REPO_ROOT/plugins/dm-review/skills/review/references/agent-registry.md"; then
    printf "  FAIL  migration-validator registry rejects stale quick-mode coverage\n"
    failures=1
  else
    printf "  OK    migration-validator registry rejects stale quick-mode coverage\n"
  fi
done
require_text "$review_skill" "never relax this equality check to a subset check" "review receiver requires exact selected_full_set equality"
require_text "$review_skill" "Any validation failure discards the entire selective input and dispatches the unfiltered recomputed selected full set. Never drop invalid members and honor the remainder." "review receiver fails open without partially honoring invalid input"
require_text "$review_skill" 'It records the exact set of logical lanes actually `DISPATCHED` on this pass' "review receipt reports actually dispatched lanes"
require_text "$review_skill" 'A selective affected-lane repair verification can support `CLEAN` only after an earlier complete full review' "selective repair verification can complete proportional convergence"
require_text "$review_skill" 'mandatory for the initial full review, incomplete full-review recovery, and' "review retains security sign-off at required boundaries"
require_text "$review_skill" '`prior_full_review_complete: true`' "review requires completed full baseline before security omission"
require_text "$review_skill" '`security_boundary_changed: false`' "review requires non-security repair before security omission"
require_text "$postmortem_schema" '`activeComputeSeconds`' "postmortem separates active compute from elapsed time"
require_text "$postmortem_schema" '`waitSecondsByCategory`' "postmortem records typed waits"
require_text "$orchestrator" "Measure the orchestrator-level non-overlapping interval" "orchestrator measures non-overlapping waits"
require_absent "$pipeline_run" "shadow observation after each authoritative receipt" "pipeline-run avoids per-receipt observation"
require_absent "$orchestrator" 'feed it to `observe-pipeline`' "orchestrator avoids intermediate observer invocations"
require_text "$verification_contract_runtime" '"chunk", "revision_batch", "execution_level", "merge_candidate"' "kernel owns the closed verification boundaries"
require_text "$verification_contract_runtime" '"doctor", "fast", "focused", "full", "race", "harness", "remote"' "kernel owns the closed verification tiers"
require_text "$verification_execution" "subprocess.Popen(" "kernel executes planned argv through the contained runner"
require_text "$verification_execution" "stdin=subprocess.DEVNULL" "kernel detaches caller stdin before repository execution"
require_text "$verification_execution" "start_new_session=True" "kernel isolates repository command process groups"
require_absent "$verification_execution" "shell=True" "kernel never delegates verification argv through a shell"
require_text "$repository_verification" "Selected local lanes always execute." "repository verification has no result reuse"
require_text "$repository_verification" "does not persist command output, environment values," "repository verification results remain bounded"
require_text "$assembly_build" 'Workflow Kernel `>=0.14.0`' "assembly resolves the exact-ref verification runtime floor"
require_text "$pipeline_run" 'Workflow Kernel `>=0.14.0`' "pipeline resolves the exact-ref verification runtime floor"
require_text "$orchestrator" 'Workflow Kernel `>=0.14.0`' "orchestrator resolves the exact-ref verification runtime floor"
require_text "$assembly_test_runner" 'Workflow Kernel `>=0.14.0`' "assembly runner resolves the exact-ref verification runtime floor"
require_text "$orchestrator" 'rather than importing it into the local result.' "pipeline keeps remote evidence outside the local kernel"
require_text "$assembly_test_runner" 'independently collected any required native CI or' "assembly separates remote evidence from local results"
require_absent "$orchestrator" 'validated and authenticated by the host integration' "pipeline removes authenticated provider completion"
require_absent "$assembly_test_runner" 'reused authenticated' "assembly removes authenticated receipt reuse"
require_text "$orchestrator" "### 1d: Repository Verification Planner" "orchestrator resolves repository-owned verification before dispatch"
require_text "$assembly_development" "4-50" "Assembly doctrine names the default member scale"
require_text "$assembly_development" "two-person development team" "Assembly doctrine names the default team scale"
require_text "$assembly_development" "## Mutation Applicability Matrix" "Assembly defines conditional mutation controls"
require_absent "$promptcraft" "Every mutation chunk" "promptcraft does not require blanket mutation ceremony"
require_absent "$promptcraft" "Classification floors:" "promptcraft rejects retired numeric floors"
require_absent "$promptcraft" "below Logic floor" "promptcraft rejects retired below-floor blockers"
require_absent "$promptcraft" "floors are non-negotiable" "promptcraft rejects retired non-negotiable floors"
require_absent "$plan_adversary" "every SQLite mutation" "plan adversary does not require blanket mutation events"
require_absent "$plan_adversary" "covering all 7 steps of the mutation invariant checklist" "plan adversary rejects the blanket seven-control rule"
require_text "$plan_adversary" "only for selected controls whose obligation" "plan adversary selects only applicable mutation controls"
require_text "$assembly_nats_reviewer" "named current event obligation" "NATS review requires current event evidence"
require_text "$assembly_nats_skill" "named current event obligation exists" "NATS skill requires a named current event obligation"
require_absent "$assembly_nats_skill" "Every mutation that changes persisted state" "NATS skill rejects universal mutation events"
require_text "$assembly_development" 'A one-use handler may call `ScopedDB` directly' "Assembly permits a narrow direct-handler boundary"
require_text "$arch" 'not flag a one-use handler merely for one low-consequence `ScopedDB` statement' "architecture review follows the conditional service boundary"
require_text "$sec" "internal maintenance must instead name and enforce an explicit trust boundary" "security review recognizes trusted maintenance boundaries"
require_text "$assembly_workflows" 's.auth.Authorize(ctx, actorID, "proposal.submit"' "workflow example authorizes the protected proposal transition"
require_text "$orchestrator" "Raw passing stdout/stderr and repeated result copies must not enter" "passing verification output stays out of later model prompts"
require_text "$orchestrator" '"reproduction_instruction": "<trusted profile-derived bounded instruction>"' "failed verification carries a trusted bounded reproduction instruction before review"
require_text "$promptcraft" "A passing current-invocation result appears once as selected check IDs" "promptcraft bounds passing verification evidence"
require_text "$promptcraft" "Never include raw logs, secrets, environment, arbitrary host paths, or unbounded output" "promptcraft rejects raw or unbounded failure evidence"
require_text "$orchestrator" "Resolve and validate the referenced feedback receipt before every repair" "orchestrator validates feedback before repair"
require_text "$orchestrator" 'mode (`resume` or `replacement`); require it before accepting either repair' "orchestrator proves feedback delivery to resumed and replacement builders"
require_text "$orchestrator" "A replacement-dispatch receipt by itself is not proof of" "replacement dispatch alone cannot satisfy feedback delivery"
require_absent "$orchestrator" "A mutation handler without authorization is a P1 security violation." "orchestrator rejects unconditional mutation authorization findings"
require_text "$orchestrator" "protected user/operator write or trusted internal maintenance" "orchestrator classifies the authorization boundary"
require_absent "$promptcraft" "mechanical_path.py" "promptcraft adds no mechanical classifier"
require_absent "$orchestrator" "mechanical_globs" "orchestrator adds no caller-supplied mechanical globs"
require_absent "$orchestrator" 'eligibleProviderSplit:** `{claude:' "orchestrator excludes Claude from the eligible provider split"
require_text "$orchestrator" '| `revision_batch` | All fixes from one review pass are applied |' "orchestrator batches review-fix verification"
require_text "$orchestrator" '| `execution_level` | Every chunk in one dependency level is merged |' "orchestrator runs integrated full verification once per level"
require_text "$orchestrator" '| `merge_candidate` | All levels are merged and before final review |' "orchestrator binds exact candidate evidence"
require_text "$orchestrator" "Do not test after every" "final review fixes are batched before re-verification"
require_text "$pipeline_run" "Do not execute a full or race suite after each chunk" "Codex adapter forbids repeated full-suite execution"
require_text "$assembly_build" "Planner modes never fall back to the legacy" "assembly planner modes reject legacy hardcoded fallback"
require_text "$assembly_go_tests" "Batch all fixes from one review pass" "assembly runner batches review revisions"
require_text "$assembly_go_tests" "Preserve full race," "assembly runner keeps expensive remote lanes explicit"
require_text "$assembly_verification_profile" '"argv": [' "assembly publishes argv-array profile examples"
require_text "$assembly_verification_profile" '"id": "go-full-race"' "assembly profile retains candidate race coverage"
require_text "$orchestrator" "Otherwise park resumably" "orchestrator parks rather than assuming yes on rail exhaustion"
require_text "$orchestrator" "broadens configured-key OpenRouter eligibility" "orchestrator keeps configured-key boundaries non-overridable by the exhaustion ask"
require_text "$orchestrator" "weakens sensitive-path" "orchestrator excludes sensitive-path chunks from fallback"
require_text "$orchestrator" "waives the final independent review" "orchestrator never waives the final review for capacity"
require_absent "$orchestrator" "Future receipt design" "orchestrator has no dormant fallback receipt design"
require_absent "$orchestrator" "ask_evidence_ref" "orchestrator has no authorization receipt exchange"
require_text "$routing_policy" '"exhaustionFallback"' "routing policy declares the exhaustion fallback object"
require_text "$routing_policy" '"headlessDefault": "park"' "routing policy defaults headless exhaustion to park"
require_text "$routing_policy" '"neverOfferable"' "routing policy pins the never-offerable rails"
require_text "$pipeline_run_skill" "Rail-Exhaustion Ask Gate" "generated pipeline-run alias carries the ask gate section"
require_text "$pipeline_run" "There is no dormant or" "pipeline-run has no hidden fallback rail"
require_text "$review_skill" "Ordinary in-policy OpenRouter/Codex routing remains unaffected" "dm-review keeps configured-key routing separate from exhaustion"
require_text "$review_skill" "“record the gap and continue” and the headless gap-and-continue default are unavailable" "dm-review cannot gap-and-continue the pipeline final review"

# --------------------------------------------------------------------------
# Group 6: dm-review quality-pulse contract
# --------------------------------------------------------------------------

printf "\ndm-review quality-pulse contract:\n"

require_text "$quality_pulse_command" "name: dm-review-quality-pulse" "quality-pulse command is canonical"
require_text "$quality_pulse_command" 'plugins/dm-review/skills/quality-pulse/SKILL.md' "quality-pulse command delegates to the shared skill"
require_text "$quality_pulse_command" "Codex command-skill alias is generated" "quality-pulse keeps the generated-alias source boundary"
require_text "$quality_pulse_skill" "name: quality-pulse" "quality-pulse skill frontmatter matches its folder"
require_absent "$quality_pulse_skill" "Codex Command Alias" "primary quality-pulse skill is not a generated command alias"
require_text "$quality_pulse_skill" '.dm-review/quality-pulse.json' "quality-pulse declares the canonical default profile"
require_text "$quality_pulse_skill" 'resolve-plugin-bundle' "quality-pulse uses coherent plugin-bundle resolution"
require_text "$quality_pulse_skill" 'inspection-validate' "quality-pulse delegates complete validation to the kernel"
require_text "$quality_pulse_skill" 'inspection-run' "quality-pulse delegates contained lane execution to the kernel"
require_text "$quality_pulse_skill" "Never invoke a fallback lane ID directly" "quality-pulse leaves fallback selection to the kernel"
require_text "$quality_pulse_skill" "Consume the complete returned receipt set" "quality-pulse consumes kernel primary and fallback receipts"
require_absent "$quality_pulse_skill" "and for a fallback only after" "quality-pulse never dispatches fallback lanes directly"
require_text "$quality_pulse_skill" 'inspection-classify' "quality-pulse delegates classification mechanics to the kernel"
require_text "$quality_pulse_skill" 'inspection-render' "quality-pulse renders only through kernel inputs"
require_text "$quality_pulse_skill" 'inspection-trend' "quality-pulse delegates compatibility comparison to the kernel"
require_text "$quality_pulse_skill" '"classification": "unknown"' "quality-pulse preserves unknown classification"
require_text "$quality_pulse_skill" '"actionability": "actionable"' "quality-pulse makes unknown evidence actionable"
require_text "$quality_pulse_skill" "A quality pulse is **not a merge recommendation**" "quality-pulse is separate from merge review"
require_before "$quality_pulse_skill" "### 2. Complete preflight" "### 4. Run requested primary lanes and consume fallback receipts" "quality-pulse validates before lane execution"
require_before "$quality_pulse_skill" "emit authoritative JSON" "render Markdown digest" "quality-pulse publishes JSON before Markdown"
require_before "$quality_pulse_skill" "bind compatible trend or baseline discontinuity" "render Markdown digest" "quality-pulse binds trend before Markdown rendering"

require_text "$quality_pulse_profile" "default: .dm-review/quality-pulse.json" "profile contract defines default discovery"
require_text "$quality_pulse_profile" "untrusted PR profile: validate and report, never execute lanes" "profile contract blocks untrusted execution"
require_text "$quality_pulse_profile" "catalog_id: live-wires-quality-rules" "profile contract binds the canonical catalog"
require_text "$quality_pulse_profile" "content_digest" "profile contract requires a computed catalog digest"
require_text "$quality_pulse_output" "Authoritative JSON is the sole source of truth" "output contract keeps Markdown non-authoritative"
require_text "$quality_pulse_output" "requested, attempted, and actual lane/tool identities" "output contract keeps literal lane provenance"
require_text "$quality_pulse_output" "baseline discontinuity" "output contract preserves incompatible trends"
require_text "$quality_pulse_trust" "construct a separate kernel trust attestation outside the canonical" "trust contract requires host-derived external authority"
require_text "$quality_pulse_trust" "No profile field, repository file" "trust contract rejects profile self-attestation"

for state in available unavailable failed fallback skipped; do
  require_text "$quality_pulse_degradation" "\`$state\`" "quality-pulse degradation distinguishes $state"
done
require_text "$quality_pulse_degradation" "Redaction refuses unsafe evidence" "quality-pulse reports redaction refusal"
require_text "$quality_pulse_degradation" "Partial evidence cannot become" "quality-pulse prevents partial success"

# --------------------------------------------------------------------------
# Group 7: run-cost-summary emission contract
# --------------------------------------------------------------------------

printf "\nrun-cost-summary emission contract:\n"

dm_review_skill_alias="$REPO_ROOT/plugins/dm-review/skills/dm-review/SKILL.md"
dm_review_loop_skill="$REPO_ROOT/plugins/dm-review/skills/dm-review-loop/SKILL.md"
dm_review_visual_cmd="$REPO_ROOT/plugins/dm-review/commands/dm-review-visual.md"
dm_review_visual_skill="$REPO_ROOT/plugins/dm-review/skills/dm-review-visual/SKILL.md"
pipeline_skill="$REPO_ROOT/plugins/pipeline/skills/pipeline/SKILL.md"
pipeline_run_skill="$REPO_ROOT/plugins/pipeline/skills/pipeline-run/SKILL.md"

contract_canonical="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/run-cost-summary-contract.md"
contract_sync="$REPO_ROOT/tools/sync-run-cost-summary-contract.sh"
kernel_doc="$REPO_ROOT/docs/workflow-kernel.md"

# The paragraph is generated into all eleven consumers from one canonical
# source. Presence anchors let wording drift file by file while still passing;
# byte-identity does not. Delegate to the generator's --check mode.
require_text "$contract_canonical" "CANONICAL-PARAGRAPH-START" "canonical contract exposes a generated paragraph block"
require_text "$contract_canonical" "CANONICAL-PARAGRAPH-END" "canonical contract closes the generated paragraph block"
require_text "$contract_canonical" 'CANONICAL-INVOCATION-FLAG: --matrix "$MODEL_MATRIX_ASSET"' "canonical contract owns the caller-bound matrix asset"
require_text "$contract_canonical" "CANONICAL-MATRIX-RESOLUTION:" "canonical contract owns coherent matrix resolution"
require_text "$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/runtime_resolution.py" "def resolve_trusted_plugin_asset" "kernel validates generic installed-plugin assets"

if [ -x "$contract_sync" ]; then
  if "$contract_sync" --check >/dev/null 2>&1; then
    printf "  ok    eleven consumers match the canonical run-cost-summary paragraph\n"
  else
    printf "  FAIL  run-cost-summary paragraph drifted from the canonical source\n"
    "$contract_sync" --check 2>&1 | sed 's/^/        /'
    failures=$((failures + 1))
  fi
else
  printf "  FAIL  tools/sync-run-cost-summary-contract.sh missing or not executable\n"
  failures=$((failures + 1))
fi

# The contract states the real concurrency property. The retired draft promised
# isolation the fixed paths do not provide; it must not come back.
for f in "$review_skill" "$review_cmd" "$dm_review_skill_alias" "$review_loop" \
         "$dm_review_loop_skill" "$dm_review_visual_cmd" "$dm_review_visual_skill" \
         "$pipeline_cmd" "$pipeline_skill" "$pipeline_run" "$pipeline_run_skill"; do
  rel="${f#$REPO_ROOT/}"
  require_absent "$f" "never collide" "$rel does not promise unbacked run isolation"
done

# "silent no-op" framing is retired everywhere the contract is stated --
# including the kernel's own contract document, which consumers defer to.
require_absent "$pipeline_run" "silent no-op" "pipeline-run command retires silent no-op"
require_absent "$pipeline_run_skill" "silent no-op" "pipeline-run skill retires silent no-op"
require_absent "$kernel_doc" "silent no-op" "kernel contract doc retires silent no-op"
require_absent "$kernel_doc" "run-cost-summary unavailable" "kernel contract doc uses the mandated skip line"
require_text "$kernel_doc" "run-cost-summary: skipped (<reason>)" "kernel contract doc mandates the literal skip line"

# The invocation remains path-specific, but its trusted matrix selector is
# generated beside the paragraph and checked here for every consumer.
for f in "$review_skill" "$review_cmd" "$dm_review_skill_alias" "$review_loop" \
         "$dm_review_loop_skill" "$dm_review_visual_cmd" "$dm_review_visual_skill" \
         "$pipeline_cmd" "$pipeline_skill" "$pipeline_run" "$pipeline_run_skill"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" "emit-cost-summary --events" "$rel invokes the transactional emission command"
  require_text "$f" '--matrix "$MODEL_MATRIX_ASSET"' "$rel passes the caller-bound matrix asset"
  require_text "$f" 'if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset' "$rel resolves the matrix through the coherent bundle boundary"
  require_text "$f" 'then :; else MODEL_MATRIX_ASSET=""; fi' "$rel makes matrix-resolution failure explicit"
  require_absent "$f" 'resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0 2>/dev/null' "$rel preserves matrix resolver stderr"
  require_absent "$f" 'minimum-version 1.11.0 || true' "$rel does not silently swallow matrix resolution failure"
  require_absent "$f" "--matrix trusted-openrouter-bundle" "$rel removes the kernel-owned provider selector"
  # --receipt is argparse-required, so the command cannot run without it; what
  # needs pinning is that the consumer names a receipt at all.
  require_text "$f" "run-cost-summary: skipped" "$rel names a receipt skip line"
  require_text "$f" "skipped (kernel-unresolvable)" "$rel handles an unresolvable launcher"
  require_text "$f" "skipped (receipt-write-failed)" "$rel preserves receipt-write failure evidence"
  # The retired multi-command block must not come back in any consumer.
  require_absent "$f" "run-cost-summary: skipped (%s)\\n' \"kernel-unavailable-or-failed\"" \
    "$rel does not carry the retired shell fallback chain"
done

# The kernel version lives in four places: two plugin manifests, the
# marketplace entry, and the runtime constant. A test that pinned the runtime
# literal kept a stale value green while the manifests moved. Compare them.
runtime_resolution="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/runtime_resolution.py"
runtime_tuple=$(sed -n 's/^KERNEL_VERSION = (\([0-9]*\), \([0-9]*\), \([0-9]*\))$/\1.\2.\3/p' "$runtime_resolution" | head -1)
# All four homes, not just the Claude manifest. Checking one of them let the
# other three drift from the runtime constant with nothing to catch it -- which
# is the exact failure this block was added to prevent, half-implemented.
for kernel_manifest in \
  "$REPO_ROOT/plugins/workflow-kernel/.claude-plugin/plugin.json" \
  "$REPO_ROOT/plugins/workflow-kernel/.codex-plugin/plugin.json"; do
  rel="${kernel_manifest#$REPO_ROOT/}"
  manifest_version=$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([0-9.]*\)".*/\1/p' "$kernel_manifest" | head -1)
  if [ -n "$manifest_version" ] && [ "$manifest_version" = "$runtime_tuple" ]; then
    printf "  ok    kernel runtime version %s matches %s\n" "$runtime_tuple" "$rel"
  else
    printf "  FAIL  kernel runtime version '%s' does not match %s '%s'\n" \
      "$runtime_tuple" "$rel" "$manifest_version"
    failures=$((failures + 1))
  fi
done
marketplace_version=$(python3 -c "
import json, sys
manifest = json.load(open(sys.argv[1]))
entry = next(
    (p for p in manifest['plugins'] if p.get('name') == 'workflow-kernel'), {}
)
sys.stdout.write(entry.get('version', ''))
" "$REPO_ROOT/.claude-plugin/marketplace.json" 2>/dev/null)
if [ -n "$marketplace_version" ] && [ "$marketplace_version" = "$runtime_tuple" ]; then
  printf "  ok    kernel runtime version %s matches the marketplace entry\n" "$runtime_tuple"
else
  printf "  FAIL  kernel runtime version '%s' does not match marketplace entry '%s'\n" \
    "$runtime_tuple" "$marketplace_version"
  failures=$((failures + 1))
fi

# The measurement producers must be documented, not just registered in the CLI.
measurement_doc="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md"
require_text "$measurement_doc" "openrouter-usage" "measurement CLI reference documents openrouter-usage"
require_text "$measurement_doc" "lane-input-bytes" "measurement CLI reference documents lane-input-bytes"
require_text "$measurement_doc" "input_bytes" "measurement CLI reference documents the byte-unit field"
require_text "$measurement_doc" "record-attempt" "measurement CLI reference documents record-attempt"
require_text "$measurement_doc" "attempt_unmeasured" "measurement CLI reference documents the explicit unmeasured claim"
require_text "$measurement_doc" "--request-envelope-sha256" \
  "measurement CLI reference documents request-envelope evidence binding"

# The emission boundary has to be wired at the DISPATCH site, not only described
# in the terminal emission paragraph. Six review lanes and four production runs
# established that an instruction living next to the last command in the run is
# an instruction nobody executes during the run. Assert that the two consumers
# that actually dispatch lanes name `record-attempt` where they dispatch them.
review_dispatch_skill="$REPO_ROOT/plugins/dm-review/skills/review/SKILL.md"
orchestrator="$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
for f in "$review_dispatch_skill" "$orchestrator"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" "record-attempt" "$rel records each attempt through the kernel"
  require_text "$f" "attempt_unmeasured" "$rel names the explicit unmeasured claim"
  require_text "$f" "--openrouter-receipt" "$rel names the provider-receipt evidence path"
  require_text "$f" "--request-envelope-sha256" \
    "$rel binds provider receipts to the attempted request envelope"
  require_text "$f" "--agent-definition" "$rel names the input-bytes evidence path"
done

# The per-chunk review tier is a burn control, so it has to be receipt-evidenced
# rather than advisory. Pin the required-field sentence: without it the
# orchestrator can quietly dispatch the multi-agent suite for ordinary chunks and
# leave no trace that the cheap default was skipped.
require_text "$orchestrator" \
  "MUST record \`review_tier:" \
  "execution orchestrator requires the review_tier chunk-receipt field"

# Implementation tool-call policy is a delivery checkpoint, not a hard stop.
# Pin both canonical injection surfaces, the legacy-prompt override, and the
# separate read-only/sweep caps that this repair must not broaden.
prompt_template="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/prompt-template.md"
eval_sweep="$REPO_ROOT/plugins/pipeline/skills/eval-sweep/SKILL.md"
for f in "$prompt_template" "$orchestrator"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" "approximately 40 tool calls as an exploration checkpoint" \
    "$rel defines the approximate exploration checkpoint"
  require_text "$f" "stop new research, broad exploration, speculative refactoring, scope expansion, and unrelated improvements" \
    "$rel stops scope growth at the exploration checkpoint"
  require_text "$f" "inspect the current diff and status" \
    "$rel permits closeout inspection calls"
  require_text "$f" "run proportionate focused verification" \
    "$rel permits focused verification calls"
  require_text "$f" "targeted repair" \
    "$rel permits targeted repair calls"
  require_text "$f" "commit coherent work" \
    "$rel permits commit calls"
  require_text "$f" "push the branch" \
    "$rel permits push calls"
  require_text "$f" "create or update the PR" \
    "$rel permits PR calls"
  require_text "$f" "final report" \
    "$rel permits final reporting calls"
  require_text "$f" "After at most two targeted repair-and-recheck cycles" \
    "$rel bounds repair churn"
  require_text "$f" "Reaching the exploration checkpoint is never, by itself, a valid reason to leave implemented work unverified, uncommitted, unpushed, or unreported." \
    "$rel preserves the delivery invariant"
  require_text "$f" 'NOT-COVERED:' \
    "$rel retains NOT-COVERED transparency"
  require_text "$f" 'COMMANDS-RUN:' \
    "$rel retains COMMANDS-RUN transparency"
  require_absent "$f" "Hard cap: 40 tool calls" \
    "$rel removes the hard implementation termination point"
  require_absent "$f" "stop at 80% of budget" \
    "$rel removes the early implementation stop rule"
done
require_text "$orchestrator" "Legacy generated prompts:" \
  "execution orchestrator overrides legacy generated hard-cap prompts"
require_text "$orchestrator" "Verification, targeted repair, commit, push, PR creation or update, and final reporting calls are exempt from the legacy cap." \
  "legacy prompt override exempts delivery calls"

for reviewer in \
  architecture-reviewer code-simplicity-reviewer codex-perspective \
  craft-reviewer doc-sync-reviewer go-build-verifier migration-validator \
  pattern-recognition-specialist security-auditor test-coverage-reviewer; do
  require_text "$REPO_ROOT/plugins/dm-review/agents/review/$reviewer.md" \
    "Hard cap: 40 tool calls." \
    "dm-review $reviewer retains its read-only hard cap"
done
require_text "$eval_sweep" "Hard cap: 40 tool calls" \
  "pipeline eval-sweep retains its ledger-oriented hard cap"

# --------------------------------------------------------------------------
# Group 8: subscription-first and family-independent routing
# --------------------------------------------------------------------------

printf "\nrouting invariants:\n"

require_text "$review_skill" \
  "The second-perspective reviewer model family MUST differ from the family that implemented the diff under review." \
  "dm-review requires a family-independent second perspective"
require_text "$review_skill" \
  "Unknown subscription headroom is treated as at-threshold, never as available." \
  "routing-policy consumers treat unknown subscription headroom conservatively"
if jq -e '
  .agentType["security-auditor-codex-signoff"] as $lane
  | $lane.provider == "implementer-aware-independent-family"
    and $lane.reviewerFamilyConstraint == "must-differ-from-implementer-family"
    and $lane.preferredProviderWhenIndependent == "codex"
    and $lane.codexImplementerProvider == "openrouter"
    and ($lane.failureResolution | [
      .runner_failure,
      .full_disclosure_decline,
      .partial_coverage
    ] | all(. == "remaining-non-implementing-family-or-review-incomplete"))
    and .security.reviewControls.highConsequenceSecuritySignoff
      == "independent-non-implementing-family-required"
' "$routing_policy" >/dev/null; then
  printf "  OK    security sign-off route is implementer-aware and family-independent\n"
else
  printf "  FAIL  security sign-off route is implementer-aware and family-independent\n"
  failures=1
fi

# ---------------------------------------------------------------------------
# Group 9: configured-key OpenRouter contract
# ---------------------------------------------------------------------------
printf "\nGroup 9: configured-key OpenRouter authorization\n"

openrouter_wrapper="$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/openrouter-wrapper.sh"
openrouter_agent_runner="$REPO_ROOT/plugins/openrouter/agents/workflow/openrouter-agent-runner.md"
review_alias="$REPO_ROOT/plugins/dm-review/skills/dm-review/SKILL.md"
authorization_contract="$REPO_ROOT/plugins/pipeline/references/openrouter-authorization-contract.md"
openrouter_exec="$REPO_ROOT/plugins/pipeline/references/openrouter-exec.sh"
cascade_dispatch="$REPO_ROOT/plugins/pipeline/references/cascade-dispatch.sh"
noninteractive_fixtures="$REPO_ROOT/tests/test_openrouter_noninteractive.py"

require_text "$authorization_contract" 'either `OPENROUTER_API_KEY` or the existing' \
  "configured-key contract accepts both supported key inputs"
require_text "$authorization_contract" 'delegation-boundary.sh --mode artifact-delegation' \
  "configured-key contract requires one automatic private-file scan"
require_text "$authorization_contract" 'configured-key path has no broker dependency' \
  "configured-key contract has no broker dependency"
require_text "$openrouter_exec" 'OPENROUTER_EXEC_ALLOWED_PATHS is required' \
  "bounded Pipeline adapter keeps the owned-path allowlist"
require_text "$openrouter_exec" '--mode artifact-delegation' \
  "bounded Pipeline adapter uses configured-key wrapper transport"
require_text "$review_skill" 'dispatch immediately' \
  "dm-review resolves eligible configured-key lanes non-interactively"
require_text "$review_skill" 'OPENROUTER_API_KEY_FILE' \
  "dm-review accepts the validated key-file input"
require_absent "$review_skill" 'OPENROUTER_INTERIM_PROGRAM_SUNSET' \
  "dm-review active path has no artificial sunset"
require_absent "$openrouter_wrapper" 'exact-digest' \
  "OpenRouter wrapper removes per-call digest approval"
require_absent "$openrouter_wrapper" 'interim-operator-batch' \
  "OpenRouter wrapper removes batch authorization"
if [ ! -e "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/payload-authorization.sh" ]; then
  printf "  OK    screening-manifest helper is deleted\n"
else
  printf "  FAIL  screening-manifest helper is deleted\n"
  failures=1
fi
if [ ! -e "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/runner-batch-authorization.sh" ]; then
  printf "  OK    batch runner helper is deleted\n"
else
  printf "  FAIL  batch runner helper is deleted\n"
  failures=1
fi
require_text "$openrouter_agent_runner" '--mode artifact-delegation' \
  "OpenRouter agent runner scans private exact outbound files once"
require_absent "$openrouter_agent_runner" 'RUNNER_BATCH_HELPER' \
  "OpenRouter agent runner does not enter the batch path"
require_text "$noninteractive_fixtures" 'test_direct_is_one_pass_and_receipt_is_content_free' \
  "loopback fixtures cover one-pass direct dispatch and receipt hygiene"
require_text "$noninteractive_fixtures" 'test_pipeline_rejects_disallowed_path_before_application' \
  "loopback fixtures cover pre-application path rejection"
require_text "$noninteractive_fixtures" 'test_active_surfaces_have_no_approval_machinery' \
  "fixtures cover active approval-machinery absence"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md" \
  '`implementer_family`, `reviewer_family`, `resolution_reason`' \
  "dm-review output contract requires family provenance on contribution decisions"
require_text "$review_skill" \
  'Every machine-readable contribution decision and lane companion also records normalized' \
  "dm-review review contract requires family provenance on every contribution surface"
family_surfaces=(
  "$REPO_ROOT/plugins/openrouter/commands/openrouter.md"
  "$REPO_ROOT/plugins/openrouter/skills/openrouter/SKILL.md"
  "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/SKILL.md"
  "$openrouter_agent_runner"
  "$REPO_ROOT/plugins/openrouter/skills/openrouter-delegate/references/model-selection.md"
  "$REPO_ROOT/plugins/dm-review/commands/dm-review-quick.md"
  "$REPO_ROOT/plugins/dm-review/skills/dm-review-quick/SKILL.md"
  "$REPO_ROOT/plugins/dm-review/skills/review/references/guardrails.md"
  "$REPO_ROOT/plugins/pipeline/agents/workflow/execution-orchestrator.md"
  "$REPO_ROOT/docs/superpowers/specs/2026-08-06-delivery-throughput-token-plan.md"
  "$REPO_ROOT/docs/cascade-migration.md"
)
for f in "${family_surfaces[@]}"; do
  rel="${f#$REPO_ROOT/}"
  for phrase in \
    "Codex sign-off remains mandatory" \
    "full-input Codex review" \
    "full-diff Codex security" \
    "required full-diff Codex lane" \
    "requires a Codex security sign-off" \
    "independent full-diff Codex sign-off" \
    "independent local Codex security sign-off"; do
    require_absent "$f" "$phrase" \
      "$rel does not hard-wire the implementing Codex family into security sign-off"
  done
done
require_text "$review_skill" "Resolve the lane before its provider." \
  "dm-review resolves independent-lane fallback before generic provider fallback"
require_text "$review_skill" "all three signals instead" \
  "dm-review applies the sign-off exception to failures and disclosure markers"
require_text "$review_skill" "do not complete the held" \
  "dm-review forbids same-family partial-coverage completion for the sign-off lane"
require_text "$openrouter_agent_runner" "continues only to a non-implementing family" \
  "OpenRouter runner keeps full-decline sign-off fallback independent"
require_text "$openrouter_agent_runner" "must use a non-implementing family for every held path" \
  "OpenRouter runner keeps partial sign-off fallback independent"
require_text "$review_skill" "[independent-family-fallback/{reviewer-family}/{agent-name}]" \
  "dm-review attributes independent fallback to its actual reviewer family"
require_text "$review_skill" "policy-derived non-implementing family at most once" \
  "dm-review bounds independent-family fallback without a same-family retry"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/graceful-degradation.md" \
  "Never same-family fallback completion" \
  "graceful degradation keeps sign-off exhaustion review-incomplete"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/graceful-degradation.md" \
  "| Second perspective |" \
  "graceful degradation uses the provider-neutral second-perspective lane"
require_absent "$REPO_ROOT/plugins/dm-review/skills/review/references/graceful-degradation.md" \
  "| Codex perspective |" \
  "graceful degradation removes the retired Codex-only perspective lane"
require_text "$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md" \
  "second-perspective: unavailable:no-independent-family" \
  "review output attributes perspective gaps to family resolution"
require_absent "$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md" \
  "codex-perspective: skipped:cli-absent" \
  "review output removes the retired Codex-only perspective example"
for f in \
  "$REPO_ROOT/plugins/dm-review/commands/dm-review-loop.md" \
  "$REPO_ROOT/plugins/dm-review/skills/dm-review-loop/SKILL.md"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" "\`second-perspective\`" \
    "$rel preserves the exact provider-neutral full-mode perspective lane"
  require_absent "$f" "\`codex-perspective\`" \
    "$rel rejects the retired perspective lane token while allowing its .md filename"
done
require_text "$REPO_ROOT/plugins/openrouter/README.md" \
  "required for every live wrapper transmission" \
  "OpenRouter README states the API-key requirement for automated live calls"
require_absent "$REPO_ROOT/docs/cascade-migration.md" \
  "future broker-ready host" \
  "cascade guidance does not treat readiness alone as transport authority"
require_text "$REPO_ROOT/docs/cascade-migration.md" \
  "configured-key" \
  "cascade guidance documents configured-key availability"
require_text "$REPO_ROOT/docs/cascade-migration.md" \
  "configured-key path has no broker dependency" \
  "cascade guidance has no broker dependency"
require_text "$REPO_ROOT/docs/cascade-migration.md" \
  "read-only independent review" \
  "cascade guidance preserves Claude's narrow independent review role"
require_absent "$REPO_ROOT/docs/cascade-migration.md" \
  "never for implementation or code review" \
  "cascade guidance does not forbid the shipped independent Claude review role"
for f in "$openrouter_agent_runner" "$openrouter_wrapper"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" "security review role requires Kimi K3 primary and GPT-5.6 Terra fallback" \
    "$rel binds security review routing to the approved model pair"
done

printf "\n"
if [ "$failures" -ne 0 ]; then
  printf "FIX  restore the missing workflow-contract anchors (see docs and plugin sources above)\n"
  exit 1
fi

printf "OK    Workflow contracts intact (repository cleanup, Datastar-first, Baseplate gates, workflow kernel, pipeline performance, cost-summary emission, routing invariants, configured-key OpenRouter authorization)\n"
