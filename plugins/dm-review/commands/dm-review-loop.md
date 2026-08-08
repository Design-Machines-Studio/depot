---
name: dm-review-loop
description: Run dm-review then dm-review-fix in a convergence loop until zero findings remain or max iterations reached
argument-hint: "[optional: --full, --max-iterations N, PR number, branch, or path]"
---

# Review-Fix Convergence Loop

Automates the cycle of reviewing code, fixing all findings, and re-reviewing until clean.

## Zero-Deferral Policy (default)

All dm-review commands default to zero-deferral: P1, P2, AND P3 findings MUST be fixed. P3s fix band-aid solutions and tech debt -- deferring them is how debt compounds silently. The loop automates fix-until-clean; `/dm-review` and `/dm-review-fix` follow the same policy.

**When triage IS warranted** (rare): use `--allow-defer-p3`. This flag is the explicit opt-in for cases where a P3 is truly out of scope for this branch AND the deferred items will be tracked elsewhere (an issue tracker, a follow-up TODO with a ticket ID, a scheduled fix-pass pipeline run). Generic reasons like "not enough time" or "will do later" are not valid -- the point of zero-deferral is that "later" never comes.

## Arguments

Parse the argument string for flags and pass-through values:

- `--full` -- Use full dm-review (all agents) instead of quick (5 core criteria; 6 logical lanes when OpenRouter adds its security lens)
- `--max-iterations N` -- Maximum review-fix cycles (default: 3)
- `--allow-defer-p3` -- Opt out of zero-deferral for P3 findings. Requires each deferred finding to carry an explicit justification and a tracking destination. Default OFF.
- `DM_REVIEW_LOOP_FULL_FANOUT=1` -- Kill switch that disables selective re-runs and uses the original full fan-out on every review pass. Default OFF. Selection fails open: if lane selection errors or prior-iteration lane attribution is unavailable, use a full fan-out and record the reason.
- Everything else -- Passed through to dm-review as the review target (PR number, branch, path)

## Evaluation Depth

Out-of-the-box, Claude tends toward shallow testing that misses subtle bugs (per Anthropic's harness design research). The review-fix loop MUST push for depth:

- **Do not accept surface-level "looks fine" reviews.** The dm-review agents must read the actual code, not just scan file names.
- **Test edge cases, not just happy paths.** What happens with empty data? Missing permissions? Concurrent access?
- **Verify behavior, not just structure.** "The function exists" is not the same as "the function handles errors correctly."
- **Check integration points.** Does the new code actually connect to what it's supposed to connect to?

When invoking dm-review within the loop, pass this context to the review: "This is an automated review-fix loop. Be thorough. Check edge cases. Do not rubber-stamp."

## Process

### 1. Initialize

```text
iteration = 0
max_iterations = 3 (or from --max-iterations)
mode = "quick" (or "full" if --full flag present)
allow_defer_p3 = true if --allow-defer-p3 flag present, else false
force_full_fanout = true if DM_REVIEW_LOOP_FULL_FANOUT == "1", else false
target = remaining arguments after flag parsing
prior_findings_signature = null  # for stalled-convergence detection
prior_review_head = null
prior_unresolved_finding_owners = null
workflowClass = explicit request value, else "feature" with workflow_class_defaulted=true
shadow_state = trusted runtime state directory, or "shadow unavailable"
```

The canonical loop state and todo files remain authoritative. Pass the exact `workflowClass` and `workflow_class_defaulted` values into every nested `/dm-review-quick` or `/dm-review`, every `/dm-review-fix`, every final re-review, every iteration receipt, and the terminal receipt. Nested commands MUST NOT re-default, infer, or change the class. Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per run, following the fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md`. Initialize this run under `.workflow-kernel/runs/<run-id>`; the kernel derives and verifies the immutable repository scope from the state directory, and no caller-selected lease root is accepted. Append lifecycle transitions there. Materialize the validated request at `.claude/ux-review/workflow-kernel/request.json`. Before corresponding authoritative actions, produce and seal the independent prediction exactly once:

```text
"$WORKFLOW_KERNEL" bind-prediction --type review --request .claude/ux-review/workflow-kernel/request.json --prediction-receipts .claude/ux-review/workflow-kernel/independent-prediction-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

Rewrite `.claude/ux-review/workflow-kernel/authoritative-receipts.json` as the complete ordered redacted receipt array after each iteration. After each complete review/fix iteration receipt, invoke exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
```

Shadow prediction never advances the loop, declares convergence, changes a finding, or converts the terminal result. Record every requested, attempted, implemented-by, fallback, and reason field; do not silently drop unavailable lanes.

### 2. Review-Fix Loop

```text
while iteration < max_iterations:
  iteration += 1

  # Iteration 1 uses the original full fan-out in the selected mode. On
  # iteration 2+, limit the review to lanes that the fixes could affect.
  selected_mode_lanes = null
  review_is_full_fanout = false
  selective_rerun = false
  review_lane_allowlist = null
  rerun_lanes = null
  skipped_lanes = []
  rerun_reasons = {}
  selection_fallback_reason = null

  # Lane discovery and every selective-input derivation are one guarded
  # operation. Any error invokes the original review command unfiltered.
  Try:
    selected_mode_lanes = the unique exact logical lane IDs Phase 3 of review/SKILL.md selects for mode and target
    Require selected_mode_lanes is non-empty and contains no aliases or criterion-level IDs
    rerun_lanes = selected_mode_lanes
    rerun_reasons = every selected lane -> ["initial_full_fanout"]

    if iteration == 1 or force_full_fanout:
      if force_full_fanout:
        rerun_reasons = every selected lane -> ["DM_REVIEW_LOOP_FULL_FANOUT=1"]
    else:
      Require prior_unresolved_finding_owners captured every prior pending finding and its source_agents
      for finding in prior_unresolved_finding_owners:
        Require finding.source_agents is a non-empty list
        Require every owner is one exact logical lane ID in selected_mode_lanes
        Require no owner is unknown, an alias, or a criterion-level ID shared by multiple logical lanes

      Require git status --porcelain is empty
      fix_head = git rev-parse HEAD
      Require prior_review_head is non-null and fix_head != prior_review_head
      Require git merge-base --is-ancestor {prior_review_head} {fix_head} succeeds
      fix_files = git diff --name-only {prior_review_head}..{fix_head}
      Require fix_files is non-empty
      rerun_lanes = []
      rerun_reasons = {}
      for lane in selected_mode_lanes:
        if lane is an exact source_agents owner of any prior unresolved finding:
          Add lane to rerun_lanes with reason "a_prior_unresolved_finding"
        if lane has a file-trigger in the Phase 3 conditional table and that trigger matches any fix_files entry:
          Add lane to rerun_lanes with reason "b_fix_file_trigger"
        # Always-run criteria have no implicit all-files trigger. They re-run
        # only through (a), unless a Phase 3 trigger is explicitly declared.
        if lane == "security-auditor-codex-signoff" and fix_files is not empty:
          Add lane to rerun_lanes with reason "security_signoff_fix_commit"
      skipped_lanes = selected_mode_lanes - rerun_lanes
      selective_rerun = true
      review_lane_allowlist = {
        selected_full_set: selected_mode_lanes,
        lanes: rerun_lanes,
      }
  On any lane-discovery, attribution, repository-boundary, or selection error:
    # Fail open to review coverage, never to a narrower or clean result.
    selective_rerun = false
    review_lane_allowlist = null
    rerun_lanes = null
    skipped_lanes = []
    rerun_reasons = {"*": ["selection_fail_open"]}
    selection_fallback_reason = exact error, dirty/unchanged/ambiguous repository state, or missing attribution reason

  if review_lane_allowlist != null:
    Run the review command for mode and target with internal input review_lane_allowlist,
    plus workflowClass and workflow_class_defaulted forwarded unchanged
    In review Phase 3, recompute the selected full set and consume the allowlist only if
    selected_full_set exactly equals that set and lanes is a unique subset of exact logical lane IDs
    Otherwise discard the invalid selective input, run the original review command unfiltered,
    and return the exact fallback reason in the coverage receipt
  else:
    Run the original review command for mode and target unfiltered,
    with workflowClass and workflow_class_defaulted forwarded unchanged

  Consume the nested review's authoritative coverage receipt and merge recommendation
  If it reports that selective input was absent, invalid, or not applied:
    selective_rerun = false
    selection_fallback_reason = its exact fallback reason when review_lane_allowlist was non-null
  review_is_full_fanout = true only if selective input was not applied, the coverage receipt's
  selected lanes exactly equal its completed lanes, and the nested review did not return REVIEW INCOMPLETE

  iteration_receipt = .workflow-kernel/runs/<run-id>/dm-review-loop/iterations/<iteration>/iteration-receipt.json
  Atomically emit iteration_receipt after the coverage receipt is validated, then append the same
  receipt to authoritative-receipts.json before observe-review. It records `selective_rerun`,
  `lanes_rerun`, `lanes_skipped`, `rerun_reasons`, and `selection_fallback_reason`.
  `lanes_rerun` is derived from attempted coverage rows; `lanes_skipped` is the selected full set
  minus those rows. Each re-run lane records (a), (b), security-signoff, full-fan-out, or fallback
  reasons; each skipped lane records "no_rule_a_or_b_match". Skipped lanes get no record-attempt call.

  # Check for findings
  Count findings in todos/*-pending-*.md
  current_signature = sorted list of pending todo filenames

  if findings == 0 and selective_rerun == true:
    Run an immediate full fan-out review in the original mode with workflowClass and workflow_class_defaulted forwarded unchanged
    Validate its coverage receipt, then atomically emit clean-confirmation-receipt.json beside iteration_receipt
    with the same required receipt fields, selective_rerun: false, no skipped lanes, and reason "clean_confirmation_full_fanout";
    append that receipt to authoritative-receipts.json before observe-review
    Count findings in todos/*-pending-*.md
    current_signature = sorted list of pending todo filenames
    review_is_full_fanout = true only if its exact selected lane set completed and it did not return REVIEW INCOMPLETE

  if findings == 0:
    if review_is_full_fanout == false:
      Report the nested review's REVIEW INCOMPLETE or coverage failure
      STOP -- needs attention
    Report: "Clean after {iteration} iteration(s). Zero findings."
    STOP -- success

  # Stalled-convergence short-circuit (token saver):
  # if this iteration produced the same findings as the prior one,
  # further fix-review loops will not resolve them -- stop and escalate.
  if prior_findings_signature != null and current_signature == prior_findings_signature:
    Report: "Convergence stalled at iteration {iteration}. Same {findings} finding(s) remain as prior pass. Manual review required."
    List remaining todo files
    STOP -- needs attention

  prior_findings_signature = current_signature
  prior_review_head = git rev-parse HEAD
  Capture prior_unresolved_finding_owners as every pending finding ID and its literal source_agents before dm-review-fix cleans completed todos

  # Fix all findings (all severities -- P1, P2, AND P3)
  # Under zero-deferral (default), dm-review-fix addresses every pending finding.
  # Under --allow-defer-p3, P3s may be triaged; P1/P2 still mandatory.
  if allow_defer_p3:
    Run /dm-review-fix --allow-defer-p3 with workflowClass and workflow_class_defaulted forwarded unchanged
  else:
    Run /dm-review-fix with workflowClass and workflow_class_defaulted forwarded unchanged
  # dm-review-fix resolves and cleans up todo files

  # If this was the last iteration, run one final review to verify
  if iteration == max_iterations:
    Run one full fan-out review in the original mode with workflowClass and workflow_class_defaulted forwarded unchanged
    Validate its coverage receipt, then atomically emit max-iterations-verification-receipt.json beside iteration_receipt
    with the same required receipt fields, selective_rerun: false, no skipped lanes, and reason "max_iterations_full_fanout";
    append that receipt to authoritative-receipts.json before observe-review
    Count remaining findings
    if findings == 0:
      Assert its exact selected lane set completed and it did not return REVIEW INCOMPLETE
      Report: "Clean after {iteration} iteration(s) with fixes."
      STOP -- success
    else:
      Report: "{findings} finding(s) remain after {iteration} iteration(s)."
      List remaining todo files
      STOP -- needs attention
```

The selection rule applies to both security lanes, architecture-reviewer, pattern-recognition-specialist, code-simplicity-reviewer, and doc-sync-reviewer: each re-runs only for rule (a) or a declared Phase 3 rule (b) match. `security-auditor-codex-signoff` is the sole exception and re-runs whenever any fix commit exists, even without an (a) or (b) match.

`review_lane_allowlist` is an internal loop-to-review input, not a public flag. Review Phase 3 is its sole consumer. An absent or invalid input always means the original unfiltered review, never an empty or partially inferred lane set.

A CLEAN verdict may only ever be issued by a full fan-out in the original mode. Selective re-runs reduce repeated work but never provide CLEAN evidence by themselves.

### 3. Repository Cleanup

Runs on **all three terminal paths** -- clean, findings remaining, and stalled convergence. A loop that gives up on convergence still owes the next run a clean repository.

Follow `plugins/dm-review/skills/review/references/repo-cleanup-contract.md`: `git worktree prune`, delete only branches this loop created and that are provably merged, leave foreign refs alone with a follow-up command, assert a clean tree, emit the inventory. Never delete the branch under review.

Also reconcile only Docker resources explicitly registered as created by this loop/review. Follow the exact executable Docker interfaces in `plugins/dm-review/skills/review/SKILL.md`: creation includes `--dependent-node-ids-json`; cleanup/reconcile planning and every guarded execute include the bound freshly rewritten `--node-statuses`; terminal `plan-reconcile` produces independently sealed current-run and stale-sweep artifacts that are iterated and recorded separately. Never execute proposed argv separately or cross-use plan authorities. Existing project containers, unsupported instrumentation, incomplete ownership labels, in-use resources, and incomplete-dependent resources are retained and reported. Broad Docker prune and name-based ownership are forbidden.

### 4. Report

After authoritative cleanup receipts are appended, invoke exactly:

```text
"$WORKFLOW_KERNEL" observe-review --request .claude/ux-review/workflow-kernel/request.json --receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir .claude/ux-review/workflow-kernel --authoritative-receipts .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/metrics.json
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; [ "$s" -eq 2 ] || [ "$s" -eq 6 ]; } || printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be gated on the status (`|| { s=$?; [ "$s" -eq 2 ] || [ "$s" -eq 6 ]; } || printf ...`), because a bare `||` fires on every non-zero exit: after an exit 6 whose receipt line was already written it appends a second, contradicting skip line, and after an exit 2 it blames a launcher that demonstrably ran. Gated, the fallback covers only what no process inside the kernel can report -- the launcher itself failing to run. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads: after each lane attempt, translate that attempt's OpenRouter wrapper receipt with `openrouter-usage`, or that lane's Codex/Claude input files with `lane-input-bytes`, passing `--append-to <authoritative-receipts.json> --run-id <id> --occurred-at <ISO-8601> --authoritative-receipt <path>` so the translator wraps the payload as an `attempt_usage` receipt and appends it under an exclusive lock in one validated step. Emit a row for every attempt including failed ones -- an attempt missing from the receipt stream is indistinguishable from one that never ran, and its spend disappears with it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

The pre-action bind seals `review-shadow-prediction.json`; later authoritative observation only consumes it and cannot create or overwrite it. Keep the prediction source and bound artifact through comparison, and delete them only after semantic `match`. Missing or reused prediction evidence fails closed without changing convergence. The repository-lifetime scope file is never auto-deleted, and parity match alone never deletes terminal run state; retain the run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches.

Output one of:

**Success:**
```
dm-review-loop: Clean after N iteration(s).
Mode: quick|full
Iterations: N of M max
```

**Needs attention:**
```
dm-review-loop: N finding(s) remain after M iteration(s).
Mode: quick|full
Remaining:
- 001-pending-p2-description
- 002-pending-p3-description

These findings could not be auto-resolved. Manual review needed.
```

Both paths append the inventory:

```
Repository cleanup: worktrees N->M (pruned K), branches deleted J, blocked L.
Remaining: <ref> -- <reason> -- follow-up: <command>
git status --porcelain: clean | <residue>
```

## Integration

This command composes existing dm-review commands -- it does not reimplement review or fix logic. It simply runs them in a loop with a convergence check.

Used by the pipeline plugin's execution-orchestrator agent for post-chunk review-fix loops, but useful standalone for any "fix it until it's clean" workflow.
