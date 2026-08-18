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

require_count() {
  local file="$1"
  local pattern="$2"
  local expected="$3"
  local label="$4"
  local actual

  if [ ! -f "$file" ]; then
    printf "  FAIL  %s (missing file: %s)\n" "$label" "${file#$REPO_ROOT/}"
    failures=1
    return
  fi
  actual="$(grep -Fc -- "$pattern" "$file" || true)"
  if [ "$actual" -eq "$expected" ]; then
    printf "  OK    %s\n" "$label"
  else
    printf "  FAIL  %s (expected %s, found %s)\n" "$label" "$expected" "$actual"
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
persona_verification_runtime="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification.py"
verification_execution="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/verification_execution.py"
repository_verification="$REPO_ROOT/plugins/workflow-kernel/skills/workflow-kernel/references/repository-verification.md"
assembly_build="$REPO_ROOT/plugins/assembly/commands/assembly-build.md"
assembly_release="$REPO_ROOT/plugins/assembly/commands/assembly-release.md"
assembly_release_skill="$REPO_ROOT/plugins/assembly/skills/assembly-release/SKILL.md"
assembly_test_runner="$REPO_ROOT/plugins/assembly/agents/workflow/go-test-runner.md"
assembly_go_tests="$REPO_ROOT/plugins/assembly/agents/workflow/go-test-runner.md"
assembly_verification_profile="$REPO_ROOT/plugins/assembly/references/repository-verification-profile.example.json"
assembly_development="$REPO_ROOT/plugins/assembly/skills/development/SKILL.md"
assembly_nats_reviewer="$REPO_ROOT/plugins/assembly/agents/review/nats-reviewer.md"
assembly_nats_skill="$REPO_ROOT/plugins/assembly/skills/nats-jetstream/SKILL.md"
assembly_workflows="$REPO_ROOT/plugins/assembly/skills/development/workflows.md"
promptcraft="$REPO_ROOT/plugins/pipeline/skills/promptcraft/SKILL.md"
promptcraft_contract="$REPO_ROOT/plugins/pipeline/references/promptcraft-behavioral-contract.md"
assess_skill="$REPO_ROOT/plugins/pipeline/skills/assess/SKILL.md"
research_skill="$REPO_ROOT/plugins/pipeline/skills/research/SKILL.md"
prompt_template="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/prompt-template.md"
assessment_template="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/templates/sections/assessment.html"
plan_template="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/templates/sections/plan.html"
html_templates_readme="$REPO_ROOT/plugins/pipeline/skills/promptcraft/references/templates/README.md"
html_artifacts="$REPO_ROOT/docs/html-artifacts.md"
plan_adversary="$REPO_ROOT/plugins/pipeline/agents/workflow/plan-adversary.md"
security_mapping="$REPO_ROOT/plugins/dm-review/skills/review/references/severity-mapping.md"
simplicity="$REPO_ROOT/plugins/dm-review/agents/review/code-simplicity-reviewer.md"
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
worktree_cleanup="$REPO_ROOT/plugins/pipeline/references/execution-worktree-cleanup.md"
require_text "$worktree_cleanup" 'block() {' "worktree-cleanup reference owns the block helper"
require_text "$worktree_cleanup" 'Define `block` at the top of **each shell invocation**' "worktree-cleanup reference states the per-shell rule"
orchestrator_loads="$(grep -c 'references/execution-worktree-cleanup.md' "$orchestrator" 2>/dev/null || echo 0)"
if [ "${orchestrator_loads:-0}" -ge 2 ]; then
  printf "  OK    orchestrator loads the worktree-cleanup reference in each cleanup step (%s load sites)\n" "$orchestrator_loads"
else
  printf "  FAIL  orchestrator loads the worktree-cleanup reference only %s time(s) -- Step 3j and Step 5b are separate shells\n" "${orchestrator_loads:-0}"
  failures=1
fi

require_text "$pipeline_cmd" "repo-cleanup-contract.md" "pipeline command references the cleanup contract"
require_text "$pipeline_cmd" "repository cleanup phase runs on all three answers" "pipeline gate runs cleanup on every answer"
codex_native_adapter="$REPO_ROOT/plugins/pipeline/references/codex-native-execution-adapter.md"
rail_exhaustion_gate="$REPO_ROOT/plugins/pipeline/references/rail-exhaustion-ask-gate.md"
cascade_descent="$REPO_ROOT/plugins/pipeline/references/execution-cascade-descent.md"
caller_memory="$REPO_ROOT/plugins/pipeline/references/caller-memory-enrichment.md"
run_memory="$REPO_ROOT/plugins/pipeline/references/run-memory-enrichment.md"
selective_rerun_ref="$REPO_ROOT/plugins/dm-review/skills/review/references/selective-lane-rerun.md"
require_text "$pipeline_run" "codex-native-execution-adapter.md" "pipeline-run loads the Codex adapter on a Codex host"
require_text "$pipeline_run" "rail-exhaustion-ask-gate.md" "pipeline-run loads the ask gate only on rail exhaustion"
require_text "$codex_native_adapter" "repo-cleanup-contract.md" "Codex adapter references the cleanup contract"
require_text "$codex_native_adapter" "Repository cleanup is host-independent" "Codex adapter gets the same cleanup gate"
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

assembly_arch_checks="$REPO_ROOT/plugins/dm-review/skills/review/references/assembly-architecture-checks.md"
assembly_sec_checks="$REPO_ROOT/plugins/dm-review/skills/review/references/assembly-security-checks.md"
plan_visual_readiness="$REPO_ROOT/plugins/pipeline/references/plan-visual-verification-readiness.md"
plan_assembly_standards="$REPO_ROOT/plugins/pipeline/references/plan-assembly-standards.md"
codex_native_parity="$REPO_ROOT/plugins/pipeline/references/execution-codex-native-parity.md"
verification_planner="$REPO_ROOT/plugins/pipeline/references/execution-verification-planner.md"
verification_profile="$REPO_ROOT/plugins/pipeline/references/execution-verification-profile.md"
consolidator_gaps="$REPO_ROOT/plugins/dm-review/skills/review/references/consolidator-coverage-gaps.md"
require_text "$arch" "assembly-architecture-checks.md" "architecture-reviewer loads the Assembly checks on an Assembly project"
require_text "$sec" "assembly-security-checks.md" "security-auditor loads the Assembly federation/release checks on those surfaces"
require_text "$plan_adversary" "plan-visual-verification-readiness.md" "plan adversary loads rendered-surface readiness when a surface renders"
require_text "$plan_adversary" "plan-assembly-standards.md" "plan adversary loads Assembly standards on an Assembly project"
require_text "$orchestrator" "execution-codex-native-parity.md" "orchestrator loads Codex native parity on a Codex host"
require_text "$orchestrator" "execution-verification-planner.md" "orchestrator loads the verification planner on a profile-aware repository"
require_text "$promptcraft" "Phase 3m: Fixture SDK Conformance Gate" "promptcraft gates fixture SDK conformance"
require_text "$promptcraft" "Phase 3n: Production Readiness Preflight Gate" "promptcraft gates production preflight"
require_text "$assembly_arch_checks" "Fixture SDK Conformance Gap" "architecture-reviewer checks reachable fixture conformance gaps"
require_text "$assembly_arch_checks" "Its absence is a coverage note, not a product finding" "Auth Boundary Map absence is a coverage note without a reachable defect"
require_absent "$assembly_arch_checks" "Missing Auth Boundary Map Receipt (P2)" "Auth Boundary Map absence is not automatically blocking"
require_text "$assembly_sec_checks" "Public/Private URL Boundary" "security-auditor guards the public/private URL boundary"
require_text "$assembly_sec_checks" "Update / Release Preflight" "security-auditor checks update/release preflight"
require_text "$assembly_sec_checks" "Responder-side share transport" "security-auditor reviews the federation responder side"

printf "\nAssembly release invocation-authority contract:\n"
for release_surface in "$assembly_release" "$assembly_release_skill"; do
  release_rel="${release_surface#$REPO_ROOT/}"
  require_text "$release_surface" "The invocation is the operator authorization." "$release_rel treats the exact invocation as authorization"
  require_text "$release_surface" "second confirmation before mutation" "$release_rel removes redundant confirmation prompts"
  require_text "$release_surface" "exact tag and channel" "$release_rel requires bounded mutating input"
  require_text "$release_surface" "execute every currently valid incomplete transition" "$release_rel resumes all valid incomplete work"
  require_text "$release_surface" "Do not artificially limit a resume invocation to one transition." "$release_rel rejects one-step resume churn"
  require_text "$release_surface" "stable-promotion approval; do not ask" "$release_rel makes stable intent explicit once"
  require_text "$release_surface" "Before the first mutation, mechanically bind and validate:" "$release_rel keeps deterministic pre-mutation validation"
  require_text "$release_surface" "Do not turn machine-checkable facts into a human review checklist." "$release_rel prefers code validation"
  require_text "$release_surface" 'return `BLOCKED` with the exact missing decision and one corrected invocation' "$release_rel blocks only on a concrete unresolved decision"
  require_text "$release_surface" "GitHub environment wait or other repository-owned approval" "$release_rel preserves repository-owned external gates"
  require_absent "$release_surface" "## Exact authorization gate" "$release_rel removes the Depot authorization gate"
  require_absent "$release_surface" "PAUSED FOR APPROVAL" "$release_rel removes the paused-for-approval state"
  require_absent "$release_surface" "Present the authorization envelope once" "$release_rel removes the authorization envelope"
  require_absent "$release_surface" "at most the one smallest valid next transition" "$release_rel removes the one-transition resume cap"
done

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
require_before "$orchestrator" 'execution-verification-profile.md' '### 3d: Dispatch Implementation Subagent' "orchestrator resolves the verification profile before dispatch"
require_text "$verification_profile" 'bind-verification-contract --state-dir' "verification profile binds the contract"
require_before "$pipeline_run" 'bind-verification-contract --state-dir' 'codex-native-execution-adapter.md' "pipeline-run binds contract before the adapter dispatches"
require_text "$verification_profile" 'bind-verification-contract --state-dir .workflow-kernel/runs/<run-id>' "orchestrator binds contracts in the canonical run directory"
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
require_text "$codex_native_adapter" "For ordinary non-sensitive chunks, run one focused read-only Codex review" "Codex adapter uses one focused ordinary-chunk reviewer"
require_text "$orchestrator" "Do not dispatch a multi-agent quick dm-review" "orchestrator avoids per-chunk review fanout"
require_text "$orchestrator" '`all-chunks-complete` boundary' "orchestrator batches intermediate shadow observation"
require_text "$orchestrator" "Empty-plan fast path" "orchestrator skips no-op cleanup commands"
require_text "$promptcraft" "Do not create an orchestrator-owned closeout chunk" "promptcraft excludes closeout-only chunks"
require_text "$promptcraft" "no more than 8 total chunks" "promptcraft enforces the default run-size budget"
require_text "$manifest_schema" "scope: newly discovered desirable work" "manifest contract freezes approved scope"

printf "\nExisting-branch and final-review-mode contract:\n"
require_text "$manifest_schema" '`branchMode` | enum' "manifest schema defines branch setup mode"
require_text "$manifest_schema" '`expectedFeatureHead` | string or null' "manifest schema binds the expected existing branch head"
require_text "$manifest_schema" '`finalReviewMode` | enum' "manifest schema defines final review mode"
require_text "$manifest_schema" '`finalReviewRationale` | string' "manifest schema requires final review rationale"
require_text "$pipeline_run" 'perform no initial push' "pipeline-run forbids an initial push in reuse mode"
require_text "$orchestrator" 'REMOTE_REF="refs/remotes/origin/$FEATURE_BRANCH"' "orchestrator resolves the remote feature branch explicitly"
require_text "$orchestrator" 'REMOTE_HEAD="$(git rev-parse --verify "$REMOTE_REF^{commit}")"' "orchestrator resolves the exact remote feature head"
require_text "$orchestrator" 'Do not push during reuse setup.' "orchestrator forbids reuse setup publication"
require_text "$orchestrator" 'installed `dm-review-quick` command-skill protocol' "orchestrator owns quick closeout execution"
require_text "$orchestrator" 'A match changes only the effective mode to full' "orchestrator escalates security-sensitive quick closeout"
require_text "$orchestrator" '`final_review_effective_mode: full`' "orchestrator emits the kernel-owned effective review field"
require_absent "$orchestrator" '`final_review_mode_requested:' "orchestrator rejects the non-canonical requested review field"
require_absent "$orchestrator" '`final_review_mode_effective:' "orchestrator rejects the non-canonical effective review field"
require_text "$kernel_skill" '`branch_mode`' "kernel preserves branch setup mode"
require_text "$kernel_skill" '`final_review_effective_mode`' "kernel preserves effective final review mode"

printf "\nRendered-surface applicability contract:\n"
require_text "$manifest_schema" '## Rendered-Surface Applicability' "manifest schema separates rendered-surface applicability"
require_text "$manifest_schema" '`renderedSurface` | enum' "manifest schema defines the closed applicability field"
require_text "$manifest_schema" '`renderedSurfaceRationale` | string' "manifest schema requires an applicability rationale"
require_text "$manifest_schema" 'Mixed or uncertain scope must use `required`.' "manifest schema fails closed on mixed or uncertain scope"
require_text "$manifest_schema" 'a planning/report `.html` artifact that is never mounted by the product' "manifest schema covers unserved HTML artifacts"
require_text "$manifest_schema" 'a non-HTTP CLI `main.go`' "manifest schema covers non-rendering CLI entry points"
require_text "$promptcraft" 'MUST carry `renderedSurface: required|not_applicable`' "promptcraft emits explicit applicability"
require_text "$promptcraft" 'Mixed or uncertain chunks are `required`.' "promptcraft fails closed during generation"
require_text "$promptcraft_contract" 'contribute no persona or' "promptcraft keeps N/A browser cases empty"
require_text "$plan_visual_readiness" 'Apply the mode-specific rendered-surface audit' "plan adversary audits applicability independently"
require_text "$plan_adversary" 'Mixed or uncertain scope is `required`.' "plan adversary rejects unsupported N/A"
require_text "$orchestrator" 'Count rendered-surface chunks' "orchestrator browser preflight uses applicability"
require_text "$orchestrator" 'Do not derive it' "orchestrator does not recompute applicability from kind"
require_text "$orchestrator" 'Do not emit `BROWSER_VERIFIED`, fabricate empty' "orchestrator avoids fabricated browser evidence"
require_text "$pipeline_cmd" 'ANY `renderedSurface: required` chunk' "pipeline caller verification uses applicability"
require_text "$pipeline_prompts" 'For `not_applicable`, keep persona/browser arrays empty' "pipeline-prompts avoids invented browser cases"
require_text "$pipeline_run" 'Rendered-surface applicability is valid' "pipeline-run validates applicability"
require_text "$verification_contract" '`rendered_surface=required` blocks' "kernel persona contract uses independent applicability"
require_text "$persona_verification_runtime" 'rendered_surface=None' "kernel gate accepts independent applicability"
require_text "$persona_verification_runtime" 'rendered_surface == "not_applicable"' "kernel gate honors validated N/A"
require_text "$verification_profile" 'When every chunk is `not_applicable`, do not discover or materialize a browser' "orchestrator binds zero-surface runs without a profile"
require_absent "$orchestrator" '### 1. Count UI/Integration chunks' "orchestrator removes kind-only browser preflight"
require_absent "$orchestrator" 'Visual Verification Protocol (UI and Integration chunks only)' "orchestrator removes kind-only visual gate"
require_absent "$plan_adversary" 'For each chunk classified as UI or Integration' "plan adversary removes kind-only visual readiness"
require_absent "$pipeline_cmd" 'mandatory when ANY UI/Integration chunk was executed' "pipeline removes kind-only caller browser gate"
require_line_mutation_sensitive "$manifest_schema" \
  '| `renderedSurface` | enum | Required on new manifests. Closed values: `"required"` or `"not_applicable"`. Controls visual references, rendered-impression criteria, browser/persona cases, Datastar gates, browser preflight, browser smoke, and final visual verification. It never changes `kind`, executor routing, or code-review depth. |' \
  '| `renderedSurface` | enum | Optional. |' \
  "rendered-surface enum anchor is mutation-sensitive"

require_text "$pipeline_prompts" 'exact closed `decisionProfile`' "pipeline-prompts requires an approved decision profile"
require_text "$pipeline_prompts" '`bind-verification-contract`' "pipeline-prompts publishes contract binding"
require_text "$pipeline_prompts" '`decide-validation-retry`' "pipeline-prompts publishes bounded validation feedback"
require_text "$pipeline_prompts" "primary process/session quit" "pipeline-prompts publishes primary browser recovery"
require_text "$cascade_descent" 'The ask is scheduling only.' "orchestrator keeps RC76 as a scheduling decision"
require_text "$cascade_descent" 'offer exactly `wait` or `park`' "orchestrator closes the current ask action vocabulary"
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
  require_text "$loop_contract" '**Convergence requires no open P1/P2/P3 findings and complete required coverage for the verification pass.**' "$loop_contract_relative defines zero-deferral convergence"
  require_text "$loop_contract" 'Every retained finding triggers repair and affected-lane verification.' "$loop_contract_relative includes every retained severity in convergence"
  require_text "$loop_contract" "selective-lane-rerun.md" "$loop_contract_relative loads the selective re-run contract from iteration 2"
  require_text "$loop_contract" "iteration-receipt.json" "$loop_contract_relative names the iteration receipt artifact"
  require_text "$loop_contract" 'Repeat the whole full fan-out only when the prior full review was incomplete or a repair changed a security-sensitive boundary.' "$loop_contract_relative limits repeated full fan-out"
  require_text "$loop_contract" 'prior_finding_owner_lanes = union of validated exact source_agents' "$loop_contract_relative preserves repaired finding ownership"
  require_text "$loop_contract" 'required_finding_files = todos/*-pending-p1-*.md plus todos/*-pending-p2-*.md plus todos/*-pending-p3-*.md' "$loop_contract_relative includes P3 artifacts in convergence"
  require_text "$loop_contract" 'security_boundary_changed: security_boundary_changed' "$loop_contract_relative binds security repair classification"
  require_line "$loop_contract" '          rerun_lanes = lanes_a union lanes_b' "$loop_contract_relative keeps affected-lane assignment inside the non-promotion branch"
  require_line "$loop_contract" '          promoted_to_full = true' "$loop_contract_relative records ordinary full-review promotion"
done
require_text "$review_skill" '`review_lane_allowlist`' "review receiver names the selective lane allowlist"
selective_allowlist="$REPO_ROOT/plugins/dm-review/skills/review/references/selective-lane-allowlist.md"
require_text "$review_skill" "references/selective-lane-allowlist.md" "review receiver loads the allowlist contract only when the input is present"
require_text "$selective_allowlist" "never relax this equality check to a subset check" "allowlist contract requires exact selected_full_set equality"
require_text "$selective_allowlist" "Any validation failure discards the entire selective input and dispatches the unfiltered recomputed selected full set. Never drop invalid members and honor the remainder." "allowlist contract fails open without partially honoring invalid input"
require_text "$REPO_ROOT/plugins/dm-review/.claude-plugin/plugin.json" '"workflow-kernel": ">=0.14.0"' "dm-review requires the simplified verification kernel release"
require_text "$REPO_ROOT/plugins/pipeline/.claude-plugin/plugin.json" '"dm-review": ">=1.64.0"' "pipeline requires zero-deferral dm-review release"
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
require_text "$selective_allowlist" "never relax this equality check to a subset check" "review receiver requires exact selected_full_set equality"
require_text "$selective_allowlist" "Any validation failure discards the entire selective input and dispatches the unfiltered recomputed selected full set. Never drop invalid members and honor the remainder." "review receiver fails open without partially honoring invalid input"
require_text "$review_skill" 'It records the exact set of logical lanes actually `DISPATCHED` on this pass' "review receipt reports actually dispatched lanes"
require_text "$selective_allowlist" 'A selective affected-lane repair verification can support `CLEAN` only after an earlier complete full review' "selective repair verification can complete proportional convergence"
require_text "$selective_allowlist" 'mandatory for the initial full review, incomplete full-review recovery, and' "allowlist contract retains security sign-off at required boundaries"
require_text "$selective_allowlist" '`prior_full_review_complete: true`' "allowlist contract requires completed full baseline before security omission"
require_text "$selective_allowlist" '`security_boundary_changed: false`' "allowlist contract requires non-security repair before security omission"
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
require_text "$codex_native_adapter" 'Workflow Kernel `>=0.15.0`' "pipeline resolves the exact-ref verification runtime floor"
require_text "$verification_planner" 'Workflow Kernel `>=0.15.0`' "orchestrator resolves the exact-ref verification runtime floor"
require_text "$assembly_test_runner" 'Workflow Kernel `>=0.14.0`' "assembly runner resolves the exact-ref verification runtime floor"
require_text "$verification_planner" 'rather than importing it into the local result.' "pipeline keeps remote evidence outside the local kernel"
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
require_text "$assembly_arch_checks" 'not flag a one-use handler merely for one low-consequence `ScopedDB` statement' "architecture review follows the conditional service boundary"
require_text "$assembly_sec_checks" "internal maintenance must instead name and enforce an explicit trust boundary" "security review recognizes trusted maintenance boundaries"
require_text "$assembly_workflows" 's.auth.Authorize(ctx, actorID, "proposal.submit"' "workflow example authorizes the protected proposal transition"
require_text "$orchestrator" "Raw passing stdout/stderr and repeated result copies must not enter" "passing verification output stays out of later model prompts"
require_text "$orchestrator" '"reproduction_instruction": "<trusted profile-derived bounded instruction>"' "failed verification carries a trusted bounded reproduction instruction before review"
require_text "$promptcraft_contract" "A passing current-invocation result appears once as selected check IDs" "promptcraft bounds passing verification evidence"
require_text "$promptcraft_contract" "Never include raw logs, secrets, environment, arbitrary host paths, or unbounded output" "promptcraft rejects raw or unbounded failure evidence"
require_text "$orchestrator" "Resolve and validate the referenced feedback receipt before every repair" "orchestrator validates feedback before repair"
require_text "$orchestrator" 'mode (`resume` or `replacement`); require it before accepting either repair' "orchestrator proves feedback delivery to resumed and replacement builders"
require_text "$orchestrator" "A replacement-dispatch receipt by itself is not proof of" "replacement dispatch alone cannot satisfy feedback delivery"
require_absent "$orchestrator" "A mutation handler without authorization is a P1 security violation." "orchestrator rejects unconditional mutation authorization findings"
require_text "$orchestrator" "protected user/operator write or trusted internal maintenance" "orchestrator classifies the authorization boundary"

printf "\nProportional-scope regression specimens (Publish Preview and FIX-01):\n"
# Publish Preview: a requested mechanism stays visible but is not promoted into
# approved scope before the user sees the smaller usable publication workflow.
require_text "$pipeline_cmd" "not an automatically approved implementation contract" "proposed mechanisms are not automatically approved scope"
require_text "$assess_skill" "Never silently discard an explicit request" "explicit user requests cannot disappear during intake"
require_text "$pipeline_cmd" 'Apply the response to the assessment Scope Intake and Project Alignment' "Publish Preview mechanism choice is persisted after combined discovery"
require_text "$pipeline_cmd" "verify the extracted requirements" "downstream coverage reads the user's selected scope"
require_text "$assessment_template" "provisional until the combined discovery response is persisted" "pre-discovery assessment does not masquerade as approved scope"
require_text "$promptcraft" "total scope and the smaller usable alternative" "oversized campaign decomposition exposes the minimum adequate alternative first"

printf "\nPipeline two-gate planning and alignment contract:\n"
require_absent "$pipeline_cmd" "Phase 1 GATE" "retired assessment gate is absent"
require_absent "$pipeline_cmd" "Phase 2 GATE" "retired research gate is absent"
require_absent "$pipeline_cmd" "Phase 3 GATE" "retired standalone plan gate is absent"
require_absent "$pipeline_cmd" "Assessment complete. Any corrections or context to add before I research?" "retired assessment question cannot return"
require_absent "$pipeline_cmd" "Research complete. Ready to plan, or want to adjust the scope?" "retired research question cannot return"
require_absent "$pipeline_cmd" 'Plan ready at `plans/<feature-slug>/plan.html`' "retired plan question cannot return"
require_before "$pipeline_cmd" "## Phase 2: Research" "## Combined Discovery Gate" "research precedes combined discovery gate"
require_before "$pipeline_cmd" "## Combined Discovery Gate" "## Phase 3: Plan" "combined discovery precedes planning"
require_text "$pipeline_cmd" "Only this combined discovery response makes the Key Requirements authoritative" "only discovery approval makes requirements authoritative"
require_text "$pipeline_cmd" 'recommended `workflowClass`, `decisionProfile`, `baseBranch`' "discovery resolves workflow, decision, and branch controls"
require_text "$pipeline_cmd" '`expectedFeatureHead`, `finalReviewMode`, and `finalReviewRationale`' "discovery resolves expected head and final review controls"
require_text "$pipeline_cmd" 'non-empty `baseBranch` and `featureBranch`' "approved plan carries branch identities"
require_text "$pipeline_cmd" '`branchMode: create|reuse`, and `expectedFeatureHead`' "approved plan carries branch mode and expected head"
require_before "$pipeline_cmd" "## Phase 5: Adversarial Scope Review" "## Final Planning Gate" "bounded adversarial review precedes final planning gate"
require_before "$pipeline_cmd" "## Final Planning Gate" "## Phase 6: Execute" "final planning gate precedes execution"
require_text "$pipeline_cmd" "Execution MUST NOT begin without explicit approval of this final package" "execution requires explicit final planning approval"
require_text "$pipeline_cmd" 'plans/<feature-slug>/manifest.json' "full final gate presents the manifest"
require_text "$pipeline_cmd" 'plans/<feature-slug>/prompts/' "full final gate presents the prompt directory"
require_text "$pipeline_cmd" "no manifest or prompt directory exists by design" "lean final gate does not fabricate artifacts"
require_text "$pipeline_cmd" '**Full-mode branch preflight:** Read `baseBranch`, `featureBranch`' "full preflight reads branch controls from manifest"
require_text "$pipeline_cmd" '**Lean-mode branch preflight:** Extract the approved data island from' "lean preflight reads branch controls from plan"
require_absent "$pipeline_cmd" 'Confirm branch authority according to `manifest.branchMode`' "shared preflight no longer assumes a manifest"
lean_preflight_block="$(awk '
  /\*\*Lean-mode branch preflight:\*\*/ { capture=1 }
  capture && /^4\. / { exit }
  capture { print }
' "$pipeline_cmd")"
if grep -Eq 'manifest|prompts/' <<<"$lean_preflight_block"; then
  printf "  FAIL  lean preflight has no manifest or prompt-directory dependency\n"
  failures=1
else
  printf "  OK    lean preflight has no manifest or prompt-directory dependency\n"
fi
require_count "$html_artifacts" '"baseBranch":"<base>", "featureBranch":"<feature>",' 2 "canonical feature and epic plan schemas carry branch identities"
require_count "$html_artifacts" '"branchMode":"create|reuse", "expectedFeatureHead":"<sha>|null",' 2 "canonical feature and epic plan schemas carry branch mode and expected head"
require_line "$plan_template" '  <h2 id="execution-scope">{{EXECUTION_SCOPE_HEADING}}</h2>' "rendered plan uses a mode-aware execution-scope heading"
require_line "$plan_template" '  {{EXECUTION_SCOPE_BODY}}' "rendered plan uses mode-aware execution-scope content"
require_line "$plan_template" '  <p>Maps each approved Key Requirement (from <a href="assessment.html">assessment.html</a>) to the applicable execution scope that satisfies it.</p>' "rendered requirements wording is mode-neutral"
require_absent "$plan_template" '<h2 id="chunks">Chunk Decomposition</h2>' "rendered plan no longer hard-codes chunk decomposition"
require_absent "$plan_template" 'Each row becomes <code>prompts/' "rendered plan no longer hard-codes prompt generation"
require_text "$html_templates_readme" 'For a **full-mode plan**, set `EXECUTION_SCOPE_HEADING` to `Chunk' "full plan rendering selects chunk decomposition"
require_text "$html_templates_readme" '`data-island-key="chunks"` wrapper containing the chunk table' "full plan rendering emits the chunk table"
require_text "$html_templates_readme" 'For a **Lean-mode plan**, set `EXECUTION_SCOPE_HEADING` to `Single-pass' "lean plan rendering selects single-pass scope"
require_text "$html_templates_readme" 'Do not emit a chunk' "lean plan rendering omits the chunk table"
require_text "$html_templates_readme" 'A Lean-mode plan links `assessment.html` and' "lean navigation omits full-mode artifacts"
require_text "$html_templates_readme" 'A full-mode plan links `assessment.html`' "full navigation includes its generated artifacts"
require_text "$html_templates_readme" '`research.html`, and `prompts/`. A Lean-mode plan links' "full navigation includes prompts before the lean branch"
require_text "$html_templates_readme" 'it MUST NOT link `prompts/` or `manifest.json`' "lean navigation forbids nonexistent artifact links"
require_absent "$html_templates_readme" 'print(len(json.load(sys.stdin)["chunks"]))' "template extractor example works without lean chunks"
require_text "$promptcraft" 'Validate exact plan/manifest equality for `baseBranch`, `featureBranch`' "full manifest copies approved plan branch controls"
require_text "$plan_adversary" 'In lean mode, does execution consume them' "plan adversary checks lean branch-control authority"
require_text "$plan_adversary" '## Mode Applicability (apply before every perspective)' "plan adversary defines mode applicability once"
require_text "$plan_adversary" 'Skip every `[Full only]` check' "lean adversary skips full-only artifact checks"
require_text "$plan_adversary" 'their absence is expected and MUST' "lean artifact absence is not a blocker"
require_text "$plan_adversary" 'In Lean mode, read the rendered single-pass scope; `chunks` may be absent.' "lean adversary reviews plan single-pass scope"
require_text "$plan_visual_readiness" '**[Full only]** Does the manifest carry `renderedSurface`' "manifest applicability check is full-only"
require_text "$plan_visual_readiness" '**[Lean only]** Does the plan' "lean visual readiness reads the plan"
require_absent "$plan_adversary" 'Read its structured `chunks`/`decisions`/`requirementsCoverage`' "plan adversary no longer requires chunks in every mode"
require_absent "$plan_adversary" 'During prototyping, do prompts' "lean minimum-scope review does not require prompts"
require_absent "$plan_adversary" 'Does the chunk have a `## Visual References`' "lean visual review does not require chunk sections"
require_text "$plan_visual_readiness" 'In full mode, inspect the planned `filesToModify`; in Lean mode, inspect the files named in the single-pass scope.' "visual parity review uses mode-appropriate source"
require_text "$assessment_template" '<h2 id="project-alignment">Project Alignment</h2>' "assessment renders compact project alignment"
require_text "$research_skill" "Does it advance the current project goal?" "research tests project-goal alignment"
require_text "$research_skill" "Do not perform a generic organization-wide GitHub survey" "research keeps GitHub discovery proportional"
require_text "$prompt_template" "the larger approved project goal this chunk serves" "chunk context carries the larger project goal"
require_text "$prompt_template" "the relevant non-goals and ownership boundary" "chunk context carries compact boundaries"
require_text "$plan_adversary" "Project-Goal Alignment and Ownership" "plan adversary reviews project alignment"
require_text "$plan_adversary" "another repository, owner, or active branch already own the work" "plan adversary checks duplicated ownership"
require_text "$plan_adversary" "stale-context assumptions" "plan adversary checks stale context"
require_text "$orchestrator" "approved scope cached after the combined discovery gate" "execution carries discovery-approved requirements"
require_text "$orchestrator" "correct work that misses the chunk's approved outcome" "per-chunk review checks outcome alignment"
require_text "$orchestrator" "final-requirements-crosscheck.md" "final delivery retains requirements cross-check"
require_text "$orchestrator" "A branch that passes tests but fails an approved" "tests cannot override a missed project outcome"
# FIX-01: trusted first-party Fixture code must not be reviewed as a hypothetical
# hostile marketplace, while real reachable trust boundaries remain blocking.
require_text "$plan_assembly_standards" "Do not model trusted Fixture authors as hostile third parties" "plan adversary uses the approved current Fixture trust model"
require_text "$plan_assembly_standards" "Mere raw-DB use by trusted first-party code is not automatically a P1" "FIX-01 does not turn trusted Fixture database access into an automatic blocker"
require_absent "$plan_adversary" "sprint contract addendum" "plan adversary does not require per-chunk addenda"
require_absent "$plan_adversary" "priced in the extra round" "plan adversary does not presume extra review rounds"
require_text "$plan_adversary" "Run one complete adversarial pass" "adversarial review is bounded to one pass"
require_text "$plan_adversary" "targeted recheck of only those revised blocker scopes" "adversarial review permits at most one targeted blocker recheck"
require_text "$sec" "reachable actor, input, and path" "security P1/P2 evidence requires a reachable threat"
require_text "$sec" "realistic harm or regression" "security P1/P2 evidence requires realistic current harm"
require_text "$sec" "actual trust boundary crossed" "security P1/P2 evidence names the actual trust boundary"
require_text "$arch" "not findings by themselves" "architecture preferences are heuristic rather than blocking"
require_absent "$arch" "Layer violations are P1 when they create circular dependencies, P2 otherwise" "architecture review rejects automatic layer-violation severity"
require_text "$arch" "Report a layer violation only when it causes a concrete current failure" "architecture layer findings require current evidence"
require_text "$arch" "Direct one-use handlers and concrete implementations are valid" "direct clear implementations remain valid"
require_text "$assembly_arch_checks" "Mere direct access in trusted first-party Fixture code is not automatically a finding" "architecture review requires a reachable Fixture boundary defect"
require_text "$simplicity" "the number alone is not a finding" "numeric simplicity thresholds are not automatically blocking"
require_text "$review_consolidator" "Discard unrelated hardening, new product scope" "review repairs cannot introduce unrelated hardening or product scope"
require_text "$review_fix" "Do not add unrelated hardening, architecture layers, compatibility machinery, or product scope" "dm-review-fix keeps repairs inside evidenced approved scope"
require_text "$security_mapping" "authentication or authorization bypass, credential disclosure, unsafe destructive operations, corruptible state or backups, public untrusted input, release/update integrity failures, and false verification claims remain blocking" "real sensitive boundaries and verification integrity remain blocking"
require_text "$selective_rerun_ref" 'the touched-file set is the union of `git diff --name-only <prior-review-head>..HEAD` and the paths reported by `git status --porcelain`' "selective re-run contract unions committed and uncommitted changed paths"
require_text "$selective_rerun_ref" "An empty computed lane set is never dispatched." "selective re-run contract never dispatches an empty selection"
require_text "$selective_rerun_ref" 'selection fails open to a full fan-out with `fallback_reason: empty selection`' "selective re-run contract fails open on an empty selection"
require_text "$selective_rerun_ref" '`max-iterations-verification-receipt.json`' "selective re-run contract names the max-iterations receipt artifact"
require_text "$review_loop" "one repair batch followed by one" "default review convergence uses one repair batch"
require_text "$review_loop" "affected-lane recheck" "default review convergence keeps the affected-lane recheck"
require_absent "$promptcraft" "mechanical_path.py" "promptcraft adds no mechanical classifier"
require_absent "$orchestrator" "mechanical_globs" "orchestrator adds no caller-supplied mechanical globs"
require_absent "$orchestrator" 'eligibleProviderSplit:** `{claude:' "orchestrator excludes Claude from the eligible provider split"
require_text "$verification_planner" '| `revision_batch` | All fixes from one review pass are applied |' "orchestrator batches review-fix verification"
require_text "$verification_planner" '| `execution_level` | Every chunk in one dependency level is merged |' "orchestrator runs integrated full verification once per level"
require_text "$verification_planner" '| `merge_candidate` | All levels are merged and before final review |' "orchestrator binds exact candidate evidence"
require_text "$orchestrator" "Do not test after every" "final review fixes are batched before re-verification"
require_text "$orchestrator" "[FULL PROMPT CONTENT INLINED HERE]" "legacy Codex worker receives the complete chunk prompt"
require_before "$orchestrator" "[INLINE ONLY THE APPROVED KEY REQUIREMENTS MAPPED TO THIS CHUNK HERE]" "[FULL PROMPT CONTENT INLINED HERE]" "legacy Codex worker places chunk-relevant approved requirements before the complete prompt"
require_before "$orchestrator" "[FULL PROMPT CONTENT INLINED HERE]" "When done:" "legacy Codex worker places the complete chunk prompt before closeout instructions"
require_text "$codex_native_adapter" "Do not execute a full or race suite after each chunk" "Codex adapter forbids repeated full-suite execution"
require_text "$assembly_build" "Planner modes never fall back to the legacy" "assembly planner modes reject legacy hardcoded fallback"
require_text "$assembly_go_tests" "Batch all fixes from one review pass" "assembly runner batches review revisions"
require_text "$assembly_go_tests" "Preserve full race," "assembly runner keeps expensive remote lanes explicit"
require_text "$assembly_verification_profile" '"argv": [' "assembly publishes argv-array profile examples"
require_text "$assembly_verification_profile" '"id": "go-full-race"' "assembly profile retains candidate race coverage"
require_text "$cascade_descent" "Otherwise park resumably" "orchestrator parks rather than assuming yes on rail exhaustion"
require_text "$cascade_descent" "broadens configured-key OpenRouter eligibility" "orchestrator keeps configured-key boundaries non-overridable by the exhaustion ask"
require_text "$cascade_descent" "weakens sensitive-path" "orchestrator excludes sensitive-path chunks from fallback"
require_text "$cascade_descent" "waives the final independent review" "orchestrator never waives the final review for capacity"
require_absent "$orchestrator" "Future receipt design" "orchestrator has no dormant fallback receipt design"
require_absent "$orchestrator" "ask_evidence_ref" "orchestrator has no authorization receipt exchange"
require_text "$routing_policy" '"exhaustionFallback"' "routing policy declares the exhaustion fallback object"
require_text "$routing_policy" '"headlessDefault": "park"' "routing policy defaults headless exhaustion to park"
require_text "$routing_policy" '"neverOfferable"' "routing policy pins the never-offerable rails"
require_text "$pipeline_run_skill" "Rail-Exhaustion Ask Gate" "generated pipeline-run alias carries the ask gate section"
require_text "$rail_exhaustion_gate" "There is no dormant or" "pipeline-run has no hidden fallback rail"
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
    and $lane.reviewerFamilyConstraint == "must-differ-from-every-implementer-family"
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
  "$REPO_ROOT/plugins/dm-review/skills/dm-review-loop/SKILL.md" \
  "$selective_rerun_ref"; do
  rel="${f#$REPO_ROOT/}"
  require_absent "$f" "\`codex-perspective\`" \
    "$rel rejects the retired perspective lane token while allowing its .md filename"
done
require_text "$selective_rerun_ref" "\`second-perspective\`" \
  "selective re-run contract preserves the exact provider-neutral full-mode perspective lane"
for f in "$selective_rerun_ref"; do
  rel="${f#$REPO_ROOT/}"
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
  require_text "$f" "security review role requires Kimi K3 primary and Grok 4.6 fallback" \
    "$rel binds security review routing to the approved model pair"
done

# ---------------------------------------------------------------------------
# Group 10: compact human output with durable evidence
# ---------------------------------------------------------------------------
printf "\nGroup 10: compact human output with durable evidence\n"

voice_check="$REPO_ROOT/plugins/ghostwriter/commands/voice-check.md"
voice_check_alias="$REPO_ROOT/plugins/ghostwriter/skills/voice-check/SKILL.md"
review_output="$REPO_ROOT/plugins/dm-review/skills/review/references/output-format.md"
review_consolidator="$REPO_ROOT/plugins/dm-review/agents/workflow/review-consolidator.md"
review_command="$REPO_ROOT/plugins/dm-review/commands/dm-review.md"
review_alias="$REPO_ROOT/plugins/dm-review/skills/dm-review/SKILL.md"
pipeline_alias="$REPO_ROOT/plugins/pipeline/skills/pipeline/SKILL.md"

for f in "$voice_check" "$voice_check_alias"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" 'Puffery, promotional filler, vague attribution, and generic conclusions' \
    "$rel audits promotional and vague language"
  require_text "$f" 'Sentences that express a feeling but provide no fact, instruction, example, or decision' \
    "$rel requires concrete information"
  require_text "$f" 'Dense sentences that require rereading' \
    "$rel catches dense sentences"
  require_text "$f" 'Sterile rewrites that remove the writer' \
    "$rel preserves deliberate voice"
  require_text "$f" '## Verdict' "$rel starts the compact result shape with Verdict"
  require_text "$f" '## Fix now' "$rel includes impact-ordered fixes"
  require_text "$f" '## Suggested rewrite' "$rel includes direct replacement text"
  require_text "$f" '## What remains' "$rel limits residual commentary"
done
require_absent "$voice_check" 'Provide 2-3 rewritten passages' \
  "voice-check no longer forces a fixed rewrite count"

require_before "$review_output" '## Compact Human Handoff' '## Complete Report Template' \
  "dm-review leads with compact handoff before complete evidence"
require_text "$review_output" 'path:anchor -- problem -- smallest adequate fix' \
  "dm-review handoff has the compact P1/P2/P3 row shape"
require_text "$review_output" 'findings` with the exact remaining count' \
  "dm-review discloses the exact overflow count"
require_text "$review_output" 'Chat keeps P3' \
  "dm-review keeps P3 compact while preserving its required fix path"
require_text "$review_output" '### Synthesis Decisions' \
  "dm-review retains the complete synthesis ledger"
require_text "$review_output" '### Repository Cleanup' \
  "dm-review retains cleanup truth"
require_text "$review_output" '### Detailed Agent Reports' \
  "dm-review retains raw reviewer evidence"
require_text "$review_skill" 'Preserve the complete unified report and all' \
  "dm-review preserves complete report evidence"
require_text "$review_skill" 'write the complete report to `.claude/ux-review/report.md`' \
  "dm-review always writes the complete report"
require_before "$review_skill" '### Phase 8: Repository Cleanup' '### Finalize Report and Deliver Handoff' \
  "dm-review finalizes the report only after mandatory cleanup"
require_before "$review_skill" '### Phase 8: Repository Cleanup' 'write the complete report to `.claude/ux-review/report.md`' \
  "dm-review writes the complete report only after cleanup truth exists"
require_before "$review_skill" 'write the complete report to `.claude/ux-review/report.md`' 'Deliver the compact human handoff' \
  "dm-review delivers the compact handoff only after the complete report write"
require_text "$review_skill" 'Do not write `.claude/ux-review/report.md` or deliver the compact human handoff' \
  "dm-review consolidation explicitly forbids early final delivery"
require_text "$lifecycle" '| `.claude/ux-review/report.md` | 3 |' \
  "dm-review complete report uses the existing artifact lifecycle"
require_text "$review_consolidator" 'Coverage Gaps' \
  "dm-review consolidator retains coverage gaps"
require_text "$review_consolidator" 'provisional report body preserving' \
  "dm-review consolidator produces only a provisional report body"
require_text "$review_consolidator" 'Do not write `.claude/ux-review/report.md` and do not deliver or project the' \
  "dm-review consolidator forbids delegated publication"
require_before "$review_consolidator" '### Step 5.5: Coverage Gaps' 'Return the provisional report body only after this Coverage Gaps section' \
  "dm-review consolidator completes coverage gaps before returning its provisional body"
require_text "$consolidator_gaps" 'Coverage Gaps' "coverage-gap contract owns the gap section"
require_absent "$review_consolidator" 'Write that report to `.claude/ux-review/report.md`' \
  "dm-review consolidator does not write the final report early"
require_absent "$review_consolidator" 'then project its compact' \
  "dm-review consolidator does not project the handoff early"
require_text "$review_skill" 'After consolidation, determine tracking method automatically:' \
  "dm-review issue tracking follows consolidation rather than publication"
require_absent "$review_skill" 'After outputting the report' \
  "dm-review removes the stale early-publication Phase 6 phrase"
require_absent "$review_skill" 'Output the full report to the user.' \
  "dm-review rejects the old visible full-report dump"
for f in "$review_command" "$review_alias"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" '**P3 only:** `APPROVE WITH FIXES`. Must fix.' \
    "$rel rejects a clean result with retained P3 findings"
  require_absent "$f" 'retain every P3 as a visible advisory' \
    "$rel rejects expanded P3 delivery"
done
require_text "$review_output" 'Clean review:' \
  "dm-review carries a clean-review specimen"
require_text "$review_output" 'Review with actionable findings:' \
  "dm-review carries an actionable-review specimen"

for f in "$pipeline_cmd" "$pipeline_alias" "$pipeline_run" "$pipeline_run_skill"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" 'Done' "$rel includes the successful outcome token"
  require_text "$f" 'Needs fixes' "$rel includes the repair outcome token"
  require_text "$f" 'Blocked' "$rel includes the blocked outcome token"
  require_text "$f" 'Recommended next action' "$rel requires one recommended next action"
done
require_text "$orchestrator" 'Memory observation handoff: <observation>' \
  "Pipeline orchestrator returns the compact caller handoff"
require_text "$orchestrator" 'Keep the observation under 300 characters.' \
  "Pipeline orchestrator bounds the memory handoff"
require_text "$codex_native_parity" 'Personal-memory enrichment is optional.' \
  "Codex native parity treats personal memory as optional enrichment"
require_absent "$orchestrator" '`search_entities`' \
  "restricted Pipeline orchestrator does not call ai-memory"
for f in "$caller_memory" "$run_memory"; do
  rel="${f#$REPO_ROOT/}"
  require_text "$f" 'Read the entity and check its same-day observations for the exact handoff.' \
    "$rel deduplicates the caller memory handoff"
  require_text "$f" 'If absent, call `add_observation`, then `save`.' \
    "$rel writes and saves the caller memory handoff"
  require_text "$f" '`Memory capture: written`' \
    "$rel records successful memory capture"
  require_text "$f" '`Memory capture: already-present`' \
    "$rel records deduplicated memory capture"
  require_absent "$f" '`skipped -- <reason>`' \
    "$rel omits incidental memory-unavailable status"
  require_text "$f" 'omit the write and every' \
    "$rel silently omits unavailable incidental memory"
  require_text "$f" 'Do not show the raw handoff in ordinary human-facing' \
    "$rel keeps the internal memory handoff out of chat"
done
require_before "$pipeline_cmd" 'caller-memory-enrichment.md' '### Caller Verification Checklist' \
  "Pipeline resolves available memory enrichment before human delivery"
require_text "$caller_memory" 'retain that outcome in internal summary evidence before Phase 7' \
  "caller memory enrichment lands before human delivery"
require_before "$pipeline_run" 'run-memory-enrichment.md' 'Present the compact summary from the orchestrator.' \
  "pipeline-run resolves available memory enrichment before human presentation"
require_text "$run_memory" 'After a successful write or exact duplicate' \
  "run memory enrichment lands before human presentation"
require_before "$lifecycle" 'Step 5b writes the base' 'A capable caller that successfully consumes the handoff' \
  "artifact lifecycle orders the base receipt before optional caller memory status"
require_count "$lifecycle" 'exactly one terminal `- Memory capture:' 1 \
  "artifact lifecycle has one caller-owned terminal append instruction"
require_count "$lifecycle" '- Memory capture:' 2 \
  "artifact lifecycle limits memory-status syntax to the two-stage instructions"
require_before "$orchestrator" 'This Step 5b base receipt MUST omit the caller-owned `- Memory capture:` field.' 'After the compact report, return the optional internal line prepared in Step 5.1:' \
  "orchestrator completes the base receipt before returning the memory handoff"
require_count "$orchestrator" 'may append exactly one terminal memory-capture field' 1 \
  "orchestrator permits one optional memory-status append"
require_count "$orchestrator" '- Memory capture:' 1 \
  "orchestrator keeps caller-owned memory syntax out of the Step 5b template"
require_text "$orchestrator" '## <Done | Needs fixes | Blocked>' \
  "Pipeline final summary leads with the outcome"
require_text "$orchestrator" '**Recommended next action:** <one action; for blocked work, the smallest operator action>' \
  "Pipeline final summary has one recommended action"
require_text "$orchestrator" 'Successful-run specimen:' \
  "Pipeline carries a successful-run specimen"
require_text "$orchestrator" 'Blocked-run specimen:' \
  "Pipeline carries a blocked-run specimen"
require_text "$orchestrator" 'Required Safari evidence for `member-form-mobile` could not run' \
  "blocked specimen exposes exact browser evidence"
require_text "$orchestrator" 'plans/<feature-slug>/receipt.md' \
  "Pipeline keeps the durable receipt path"
require_text "$orchestrator" 'plans/<feature-slug>/final-requirements-crosscheck.md' \
  "Pipeline keeps the durable requirements crosscheck"
require_text "$orchestrator" 'plans/<feature-slug>/run-postmortem.md' \
  "Pipeline keeps the durable postmortem"
require_text "$orchestrator" 'write both under `## Codify Proposals` in the mandatory' \
  "Pipeline preserves approval-ready codify proposals in the postmortem"
require_text "$orchestrator" 'Detailed review: `.claude/ux-review/report.md`' \
  "Pipeline links the mandatory detailed review artifact"
require_before "$orchestrator" '## Step 4c: Merge Policy Check' '## Step 6: Summary Report' \
  "Pipeline records merge policy before final human delivery"
require_text "$orchestrator" 'state `noMergeOnCompletion=true` in **Branch or PR** and make manual branch review the single **Recommended next action**' \
  "Pipeline routes no-merge disposition into live compact-summary fields"
require_absent "$orchestrator" 'Summary Report'"'"'s "Next Steps" section' \
  "Pipeline no longer points no-merge runs at the deleted Next Steps section"
require_text "$orchestrator" 'providerSplit: {claude: N, codex: N, openrouter: N}' \
  "Pipeline receipt retains provider provenance"
require_text "$orchestrator" 'retained/blocked <J>' \
  "Pipeline receipt retains cleanup truth"
require_text "$orchestrator" 'P1/P2/P3' \
  "Pipeline preserves every actionable finding severity"
require_text "$orchestrator" 'human_help_required' \
  "Pipeline still preserves blocked browser evidence"
require_absent "$orchestrator" '# Pipeline Execution Complete' \
  "Pipeline rejects the old giant visible completion template"
require_absent "$pipeline_run" 'Feature branch `<branch>` is ready. Options:' \
  "pipeline-run rejects the old standing action menu"
require_text "$pipeline_cmd" 'Keep the complete coverage map in the existing plan/manifest artifacts' \
  "Pipeline phase gate keeps detailed coverage durable"
require_text "$pipeline_cmd" 'State the approved project goal, smallest usable implementation, chunk count,' \
  "Pipeline final planning gate stays compact and decision-focused"
require_absent "$pipeline_cmd" 'Then reproduce the inventory' \
  "Pipeline cleanup delivery does not dump the complete inventory"

printf "\ncontext budget:\n"

context_budget="$REPO_ROOT/tools/fixtures/workflow-context-budget.json"
if [ ! -f "$context_budget" ]; then
  printf "  FAIL  missing %s\n" "${context_budget#$REPO_ROOT/}"
  failures=1
else
  context_report=$(python3 - "$REPO_ROOT" "$context_budget" <<'PY'
import json, math, re, sys
from pathlib import Path
root = Path(sys.argv[1])
budget = json.loads(Path(sys.argv[2]).read_text())
fail = 0

def words(rel):
    p = root / rel
    if not p.is_file():
        return None
    return len(p.read_text().split())

# Hot entries: the ceiling can never authorize growth over the recorded
# baseline, so the effective cap is the tighter of the two.
for rel, spec in budget["hot_entries"].items():
    w = words(rel)
    if w is None:
        print(f"FAIL  missing hot entry {rel}")
        fail = 1
        continue
    cap = min(spec["max_words"], spec["baseline_words"])
    if w > cap:
        print(f"FAIL  {rel} is {w} words (cap {cap}; baseline {spec['baseline_words']}, ceiling {spec['max_words']})")
        fail = 1
    else:
        print(f"OK    {rel} {w} words (cap {cap})")

agg = 0
base_agg = 0
path_totals = {}
for name, spec in budget["paths"].items():
    total = 0
    missing = False
    for rel in spec["always"]:
        w = words(rel)
        if w is None:
            print(f"FAIL  {name} missing {rel}")
            fail = 1
            missing = True
            continue
        total += w
    if missing:
        continue
    path_totals[name] = total
    agg += total
    base_agg += spec["baseline_words"]
    cap = min(spec["max_words"], spec["baseline_words"])
    if total > cap:
        print(f"FAIL  {name} path is {total} words (cap {cap}; baseline {spec['baseline_words']}, ceiling {spec['max_words']})")
        fail = 1
    else:
        print(f"OK    {name} path {total} words (cap {cap})")

# Aggregate: the fixture names the required reduction and the validator
# computes the threshold from the recorded baseline. A missing reduction
# field fails closed rather than silently accepting any aggregate.
pct = budget.get("required_aggregate_reduction_pct")
if pct is None:
    print("FAIL  fixture omits required_aggregate_reduction_pct")
    fail = 1
else:
    agg_cap = math.floor(base_agg * (100 - pct) / 100)
    reduction = 100.0 * (base_agg - agg) / base_agg if base_agg else 0.0
    if agg > agg_cap:
        print(f"FAIL  aggregate {agg} exceeds {agg_cap} (baseline {base_agg}, required reduction {pct}%, actual {reduction:.1f}%)")
        fail = 1
    else:
        print(f"OK    aggregate {agg} <= {agg_cap} (baseline {base_agg}, reduction {reduction:.1f}% >= {pct}%)")

# Load-map audit: a reference omitted from the always-set may only be cited
# with an explicit named condition at its load site, and every measured
# always-file must actually be named by the entry that loads it.
condition_re = re.compile(r"\b(only when|only if|when|if|unless)\b", re.I)
entries = {
    "plugins/pipeline/commands/pipeline.md": root / "plugins/pipeline/references",
    "plugins/pipeline/agents/workflow/execution-orchestrator.md": root / "plugins/pipeline/references",
    "plugins/dm-review/skills/review/SKILL.md": root / "plugins/dm-review/skills/review/references",
    "plugins/dm-review/agents/review/security-auditor.md": root / "plugins/dm-review/skills/review/references",
    "plugins/dm-review/agents/review/architecture-reviewer.md": root / "plugins/dm-review/skills/review/references",
    "plugins/pipeline/agents/workflow/plan-adversary.md": root / "plugins/pipeline/references",
    "plugins/pipeline/skills/promptcraft/SKILL.md": root / "plugins/pipeline/references",
}
# Every measured always-file under a references dir must be named by at least
# one entry that loads from that dir; a conditional citation must carry an
# explicit named condition in the paragraph that cites it.
always_measured = set()
for spec in budget["paths"].values():
    always_measured.update(spec["always"])
entry_text = {rel: (root / rel).read_text() for rel in entries}
refdir_entries = {}
for rel, refdir in entries.items():
    refdir_entries.setdefault(refdir.relative_to(root).as_posix(), []).append(rel)
for refdir_rel, owners in refdir_entries.items():
    for measured in sorted(m for m in always_measured if m.startswith(refdir_rel + "/")):
        name = measured.rsplit("/", 1)[-1]
        if not any(name in entry_text[o] for o in owners):
            print(f"FAIL  no entry loads measured always-file {measured}")
            fail = 1
for rel, refdir in entries.items():
    text = entry_text[rel]
    paras = re.split(r"\n\s*\n", text)
    refs = sorted(p.name for p in refdir.glob("*.md"))
    cited = [name for name in refs if name in text]
    if refs and len(cited) == len(refs):
        print(f"FAIL  {rel} unconditionally names every {refdir.relative_to(root)} file")
        fail = 1
    else:
        print(f"OK    {rel} does not bulk-load {refdir.name} ({len(cited)}/{len(refs)} named)")
    for name in cited:
        ref_rel = f"{refdir.relative_to(root).as_posix()}/{name}"
        if ref_rel in always_measured:
            continue
        citing = [b for b in paras if name in b]
        if not any(condition_re.search(b) for b in citing):
            print(f"FAIL  {rel} cites omitted reference {name} without an explicit named condition")
            fail = 1

# Reachability: every reference must be named by a real load site (an entry
# surface or another reachable reference), so an added conditional reference
# cannot sit orphaned unnoticed.
def closure(seeds, refdir):
    seen = set()
    frontier = [(root / s).read_text() for s in seeds]
    names = {p.name: p for p in refdir.glob("*.md")}
    while frontier:
        text = frontier.pop()
        for name, p in names.items():
            if name not in seen and name in text:
                seen.add(name)
                frontier.append(p.read_text())
    return seen

review_refs = root / "plugins/dm-review/skills/review/references"
review_reachable = closure(
    ["plugins/dm-review/skills/review/SKILL.md",
     "plugins/dm-review/skills/review/references/full-lane-dispatch.md"]
    + [str(p.relative_to(root)) for p in sorted(
        (root / "plugins/dm-review/agents").glob("*/*.md"))]
    + [str(p.relative_to(root)) for p in sorted(
        (root / "plugins/dm-review/commands").glob("*.md"))],
    review_refs)
for p in sorted(review_refs.glob("*.md")):
    if p.name not in review_reachable:
        print(f"FAIL  orphaned dm-review reference {p.name} (not reachable from the review skill)")
        fail = 1

pipeline_refs = root / "plugins/pipeline/references"
pipeline_seeds = [str(p.relative_to(root)) for p in sorted(
    (root / "plugins/pipeline").glob("commands/*.md")) + sorted(
    (root / "plugins/pipeline").glob("skills/*/SKILL.md")) + sorted(
    (root / "plugins/pipeline").glob("agents/workflow/*.md"))]
pipeline_reachable = closure(pipeline_seeds, pipeline_refs)
for p in sorted(pipeline_refs.glob("*.md")):
    if p.name not in pipeline_reachable:
        print(f"FAIL  orphaned pipeline reference {p.name} (not reachable from any pipeline surface)")
        fail = 1

# Reviewer prompt contract: one common contract reachable from both modes,
# visual rules bound to rendered UI lanes, and no truncated fenced block.
prompt_contract = root / "plugins/dm-review/skills/review/references/reviewer-prompt-template.md"
full_dispatch = root / "plugins/dm-review/skills/review/references/full-lane-dispatch.md"
review_skill_text = (root / "plugins/dm-review/skills/review/SKILL.md").read_text()
if not prompt_contract.is_file():
    print("FAIL  reviewer-prompt-template.md missing")
    fail = 1
else:
    pc_text = prompt_contract.read_text()
    # Scope this to the dispatch phase itself. A "both modes" mention in the
    # Reference Files index is documentation, not a load site, and must not
    # satisfy the contract when Phase 4 has narrowed the load to one mode.
    dispatch_section = ""
    m = re.search(r"^### Phase 4: Parallel Agent Launch$(.*?)^### ",
                  review_skill_text, re.M | re.S)
    if m:
        dispatch_section = m.group(1)
    load_sites = [l for l in dispatch_section.splitlines()
                  if "reviewer-prompt-template.md" in l
                  and re.search(r"\bload\b", l, re.I)]
    if load_sites and any(re.search(r"both modes|quick and full", l, re.I)
                          for l in load_sites):
        print("OK    common prompt contract loads before dispatch in both modes")
    else:
        print("FAIL  review skill does not load the common prompt contract for both modes")
        fail = 1
    if "reviewer-prompt-template.md" in full_dispatch.read_text():
        print("OK    full-mode dispatch builds prompts from the common contract")
    else:
        print("FAIL  full-mode dispatch does not name the common prompt contract")
        fail = 1
    # Judge the citation by its paragraph, not its wrapped line: the guard
    # ("If a rendered UI lane is selected ...") sits above the path itself.
    visual_paras = [b for b in re.split(r"\n\s*\n", pc_text)
                    if "visual-finding-rules.md" in b]
    ui_lane_re = re.compile(r"(if|only when|when)\b[^.]*rendered UI lane", re.I | re.S)
    if visual_paras and all(ui_lane_re.search(b) for b in visual_paras) \
            and re.search(r"Non-UI lanes never receive", pc_text):
        print("OK    visual finding rules are conditional on a rendered UI lane")
    else:
        print("FAIL  visual finding rules are not conditional on a rendered UI lane")
        fail = 1
    for anchor in ["untrusted input", "## Project Context", "## Fix Philosophy",
                   "## Caller-Provided Context",
                   "When callable, preserve the existing RAG lookup and ai-memory write behavior."]:
        if anchor in pc_text:
            print(f"OK    common prompt contract preserves '{anchor}'")
        else:
            print(f"FAIL  common prompt contract lost '{anchor}'")
            fail = 1
    fence_lines = [l for l in pc_text.splitlines() if l.startswith("```")]
    if len(fence_lines) % 2 == 0 and not pc_text.rstrip().endswith("```text") and pc_text.rstrip():
        print("OK    common prompt contract has no truncated fenced block")
    else:
        print("FAIL  common prompt contract has an unbalanced or truncated fence")
        fail = 1

# Forbid "read every file in references/"
for rel in list(budget["hot_entries"]) + [
    "plugins/pipeline/skills/promptcraft/SKILL.md",
    "plugins/dm-review/commands/dm-review-loop.md",
]:
    text = (root / rel).read_text()
    if re.search(r"every file in .*references|read all .*references/", text, re.I):
        print(f"FAIL  {rel} bulk-loads references")
        fail = 1

print(f"AGGREGATE {agg} baseline {base_agg}")
sys.exit(fail)
PY
)
  context_rc=$?
  printf "%s\n" "$context_report" | sed 's/^/  /'
  if [ "$context_rc" -ne 0 ]; then
    failures=1
  fi
fi

printf "\n"
if [ "$failures" -ne 0 ]; then
  printf "FIX  restore the missing workflow-contract anchors (see docs and plugin sources above)\n"
  exit 1
fi

printf "OK    Workflow contracts intact (repository cleanup, two-gate Pipeline planning/alignment, Datastar-first, Baseplate gates, workflow kernel, pipeline performance, cost-summary emission, routing invariants, configured-key OpenRouter authorization)\n"
