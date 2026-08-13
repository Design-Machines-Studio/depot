---
name: dm-review-loop
description: Run one review, one repair batch, and one affected-lane recheck by default, with required verification
argument-hint: "[optional: --full, --max-iterations N, PR number, branch, or path]"
---

# Review-Fix Convergence Loop

Automates the cycle of reviewing code, fixing required findings, and re-reviewing affected lanes until clean.

## Finding Policy

P1 blocks merge and P2 must be fixed before merge. P3 remains fully visible advisory evidence but never enters the fix queue, triggers another iteration, or blocks convergence. The loop is clean when no P1/P2 findings remain and all required verification and coverage gates are complete.

The default convergence path is one repair batch followed by one affected-lane recheck. Repeat broad review only when the original required review was incomplete or the repair changed a real sensitive boundary.

## Arguments

Parse the argument string for flags and pass-through values:

- `--full` -- Use full dm-review instead of the applicability-driven quick roster
- `--max-iterations N` -- Maximum review/fix passes (default: 2: one review and, when needed, one affected-lane recheck)
- Everything else -- Passed through to dm-review as the review target (PR number, branch, path)

## Environment Flags

- `DM_REVIEW_LOOP_FULL_FANOUT=1` -- Disable selective lane re-run entirely. Every iteration runs a full fan-out in the selected mode, exactly as the loop behaved before selection existed. Default OFF, which means selection is active from iteration 2 onward. The switch fails OPEN: if the selection logic errors, or the prior iteration's lane attribution is unavailable, that iteration falls back to a full fan-out and records `fallback_reason` in its receipt. Narrowing is only ever done on evidence; uncertainty always widens the fan-out.

## Evaluation Depth

Out-of-the-box, Claude tends toward shallow testing that misses subtle bugs (per Anthropic's harness design research). The review-fix loop MUST push for depth:

- **Do not accept surface-level "looks fine" reviews.** The dm-review agents must read the actual code, not just scan file names.
- **Test edge cases, not just happy paths.** What happens with empty data? Missing permissions? Concurrent access?
- **Verify behavior, not just structure.** "The function exists" is not the same as "the function handles errors correctly."
- **Check integration points.** Does the new code actually connect to what it's supposed to connect to?

When invoking dm-review within the loop, pass this context to the review: "This is an automated review-fix loop. Verify reachable failures and approved-scope regressions. Required fixes must be the smallest adequate repair; reject unrelated hardening and new product scope."

## Process

### 1. Initialize

```text
iteration = 0
max_iterations = 2 (or from --max-iterations)
explicit_iteration_override = true only when --max-iterations was provided
mode = "quick" (or "full" if --full flag present)
target = remaining arguments after flag parsing
prior_findings_signature = null  # for stalled-convergence detection
prior_review_head = null  # HEAD commit the prior iteration reviewed
prior_finding_owner_lanes = empty set  # owners of P1/P2 findings just repaired
rerun_lanes = null  # null = full fan-out; a set = narrowed lane selection
selective_rerun = false
review_is_full_fanout = false
full_review_baseline_complete = false
full_fanout_override = true if DM_REVIEW_LOOP_FULL_FANOUT=1 in the environment, else false
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

  # Lane selection (token saver). Iteration 1 is always a full fan-out;
  # iteration 2+ re-reviews only what the fixes could have affected.
  fallback_reason = null    # reset EVERY iteration -- never leak a stale reason
  promoted_to_full = false  # set only when a narrowed pass is promoted below
  review_lane_allowlist = null
  review_is_full_fanout = false
  rerun_reasons = {}
  try:
    selected_full_set = the non-empty set of unique exact logical lane IDs
                        Phase 3 selects for this mode, target, and current diff
    Require every member of selected_full_set is an exact logical lane ID --
      no aliases and no criterion-level ID shared by multiple logical lanes

    if iteration == 1 or full_fanout_override:
      rerun_lanes = null  # full fan-out in the selected mode
      selective_rerun = false
      rerun_reasons = every lane in selected_full_set -> ["initial_full_fanout"]
    else:
      # (a) every lane that owned a P1/P2 finding repaired in the prior fix
      #     step, plus every lane owning a finding that remains pending. Capture
      #     repaired owners before dm-review-fix removes their todo files.
      For every repaired or pending P1/P2 finding, require source_agents is a non-empty list and
        every named owner resolves to exactly one member of selected_full_set.
        An unknown owner, alias, or criterion-level ID shared by multiple
        logical lanes is a selection error. In particular, bare
        security-auditor is ambiguous because security-auditor-codex-signoff
        and security-auditor-openrouter are separate logical lanes.
      lanes_a = prior_finding_owner_lanes union the validated exact source_agents
                lane IDs from remaining pending P1/P2 findings
      # (b) every lane whose file-trigger set matches a file the fixes touched.
      #     dm-review-fix does not commit, so a committed-range diff alone
      #     would silently miss every uncommitted fix. Consult both.
      Require prior_review_head is non-null.
      fix_head = git rev-parse HEAD
      uncommitted_changed_files = paths from git status --porcelain
      if fix_head != prior_review_head:
        Require git merge-base --is-ancestor {prior_review_head} {fix_head}
          succeeds; rewritten or reset history is a selection error.
        committed_changed_files = git diff --name-only {prior_review_head}..{fix_head}
      else if uncommitted_changed_files is not empty:
        # The committed half did not advance, which is normal when
        # dm-review-fix made only uncommitted edits. Do not interpret that as
        # proof that no files changed; use the porcelain paths as the boundary.
        committed_changed_files = empty
      else:
        Fail selection: "non-advancing fix boundary with no uncommitted fix paths"
      Remove self-authored review artifacts under `todos/`, `.workflow-kernel/`,
        and `.claude/ux-review/` from both changed-file sets before trigger
        matching or slicing. These are evidence about the review, not product
        files changed by the fix.
      changed_files = filtered committed_changed_files union filtered uncommitted_changed_files
      security_boundary_changed = changed_files matches the bounded escalation
                                  set in review skill Phase 3
      lanes_b = lanes whose MODE-APPROPRIATE file triggers match changed_files
                (see "Selective Lane Re-run" below for which trigger source
                 applies in quick mode vs full mode)
      if lanes_a is empty and lanes_b is empty:
        # Nothing the fixes could have affected. Fail OPEN rather than run a
        # near-empty pass that must be promoted to full anyway.
        rerun_lanes = null
        selective_rerun = false
        fallback_reason = "empty selection -- no unresolved findings, no touched triggers"
        rerun_reasons = every lane in selected_full_set -> ["selection_fail_open"]
      else:
        if mode == "full" and
           (full_review_baseline_complete == false or security_boundary_changed):
          rerun_lanes = null
          selective_rerun = false
          review_lane_allowlist = null
          promoted_to_full = true
          rerun_reasons = every lane in selected_full_set -> ["initial_full_fanout"]
        else:
          rerun_lanes = lanes_a union lanes_b
          Require rerun_lanes is non-empty and is a unique subset containing only
            exact logical lane IDs from selected_full_set. Never dispatch an
            empty, aliased, criterion-level, unknown, or ambiguous allowlist.
          if rerun_lanes equals selected_full_set:
            # Equality is not a narrowed pass. Collapse it before dispatch so the
            # receipt truthfully describes the full fan-out.
            rerun_lanes = null
            selective_rerun = false
            review_lane_allowlist = null
            rerun_reasons = every lane in selected_full_set -> ["initial_full_fanout"]
          else:
            for lane in rerun_lanes:
              rerun_reasons[lane] includes "a_prior_unresolved_finding" if rule (a) selected it
              rerun_reasons[lane] includes "b_fix_file_trigger" if rule (b) selected it
            selective_rerun = true
            review_lane_allowlist = {
              selected_full_set: selected_full_set,
              lanes: rerun_lanes,
              verification_basis: "affected_lane_repair",
              prior_full_review_complete: full_review_baseline_complete,
              security_boundary_changed: security_boundary_changed,
            }
  except lane-discovery, lane-ID validation, attribution, repository-boundary,
         or selection error:
    rerun_lanes = null  # fail OPEN -- never narrow on uncertain evidence
    selective_rerun = false
    review_lane_allowlist = null
    rerun_reasons = {}  # rebuilt from authoritative ATTEMPTED rows below
    fallback_reason = "<exact unknown, alias, ambiguity, empty-set, null-boundary, non-advancing-boundary, non-ancestor, or other failure reason>"

  # Run review. review_lane_allowlist is an internal loop-to-review input, never
  # a public flag. The loop never assumes the receiver honored it.
  prior_review_head = git rev-parse HEAD
  if mode == "quick":
    Run /dm-review-quick {target} with review_lane_allowlist when non-null
      with workflowClass and workflow_class_defaulted forwarded unchanged
  else:
    Run /dm-review {target} with review_lane_allowlist when non-null
      with workflowClass and workflow_class_defaulted forwarded unchanged

  Consume and validate the nested review's authoritative coverage receipt: one
    row per selected lane with requested, attempted, implemented-by, status,
    finding count, and evidence reference, plus its REVIEW INCOMPLETE result.
  if review_lane_allowlist was non-null and the coverage receipt reports the
     selective input was absent, invalid, or not applied:
    selective_rerun = false
    fallback_reason = the coverage receipt's exact fallback reason
    rerun_reasons = every lane in selected_full_set -> ["selection_fail_open"]
  required_verification_complete = true ONLY IF every lane selected for this
    pass completed and the nested review did not return REVIEW INCOMPLETE.
  review_is_full_fanout = true only when selective input was not applied and
    coverage receipt selected lanes exactly equal completed lanes.
  if mode == "full" and review_is_full_fanout and required_verification_complete:
    full_review_baseline_complete = true

  coverage_selected_set = exact logical lane IDs selected by the coverage receipt
  lanes_rerun = exact logical lane IDs in the coverage receipt's ATTEMPTED rows;
    ATTEMPTED means dispatch began, regardless of success or failure
  if fallback_reason is non-null:
    rerun_reasons = every lane in lanes_rerun -> ["selection_fail_open"]
  else:
    Remove any rerun_reasons entry whose lane is not in lanes_rerun.
  if selective_rerun and the coverage receipt proves the allowlist was applied:
    lanes_skipped = coverage_selected_set minus the applied allowlist
  else:
    lanes_skipped = []
  A lane selected for a full fan-out or allowlisted for a selective pass that
    fails before dispatch is not "skipped". Its absence from ATTEMPTED makes the
    nested review REVIEW INCOMPLETE; it appears in neither lanes_rerun nor
    lanes_skipped. Therefore `full_fanout_override: true` and
    `promoted_to_full: true` receipts always carry an empty skip set.
  For each lane in lanes_skipped, record reason "no_rule_a_or_b_match".
  Do not issue a kernel record-attempt call for any lane in lanes_skipped.

  iteration_receipt = .workflow-kernel/runs/<run-id>/dm-review-loop/iterations/<iteration>/iteration-receipt.json
  After the coverage receipt validates, atomically emit iteration_receipt with
    explicit booleans `selective_rerun`, `promoted_to_full`, and
    `full_fanout_override` on every pass, plus `lanes_rerun`, `lanes_skipped`,
    `rerun_reasons`, and `selection_fallback_reason`, then append it to authoritative-receipts.json
    BEFORE invoking observe-review. The persisted receipt field
    `selection_fallback_reason` is the loop-local fallback_reason value.

  # Check for required findings. P3 advisories exist only in the report/receipts.
  required_finding_files = todos/*-pending-p1-*.md plus todos/*-pending-p2-*.md
  Count findings in required_finding_files

  current_signature = sorted list of required_finding_files

  if findings == 0:
    if required_verification_complete == false:
      Report the nested review's REVIEW INCOMPLETE or exact coverage failure
      STOP -- needs attention
    Report: "Clean after {iteration} iteration(s). No open P1/P2 findings; P3 advisories retained."
    STOP -- success

  # Stalled-convergence short-circuit (token saver):
  # if this iteration produced the same findings as the prior one,
  # further fix-review loops will not resolve them -- stop and escalate.
  if prior_findings_signature != null and current_signature == prior_findings_signature:
    Report: "Convergence stalled at iteration {iteration}. Same {findings} finding(s) remain as prior pass. Manual review required."
    List remaining todo files
    STOP -- needs attention

  prior_findings_signature = current_signature
  prior_finding_owner_lanes = union of validated exact source_agents from
                              required_finding_files

  # The default convergence contract is one repair batch followed by one
  # affected-lane recheck. Remaining or newly supported P1/P2 after that
  # recheck require operator attention, not an automatic second repair batch.
  if iteration > 1 and explicit_iteration_override == false:
    Report: "{findings} supported finding(s) remain after the targeted recheck. Manual decision required."
    List remaining todo files
    STOP -- needs attention

  # Fix required findings only (P1/P2).
  Run /dm-review-fix with workflowClass and workflow_class_defaulted forwarded unchanged
  # dm-review-fix resolves and cleans up todo files

  # If this was the last iteration, run one final review to verify.
  # Verify affected lanes on the new tested SHA. Repeat a full fan-out only if
  # the prior full review was incomplete or the repair changed a security-sensitive boundary.
  if iteration == max_iterations:
    Compute the affected-lane allowlist from finding ownership and touched-file
      triggers. If mode is full and the prior full review was incomplete or a
      security-sensitive boundary changed, set review_lane_allowlist = null and
      promoted_to_full = true.
    Run review one more time (same mode) with the resulting selective input
      and workflowClass and workflow_class_defaulted forwarded unchanged
    Consume and validate the verification pass's authoritative coverage receipt.
    Atomically emit max-iterations-verification-receipt.json beside
      iteration_receipt, with the same required receipt fields,
      the truthful selective_rerun value and reason
      "max_iterations_affected_lane_verification", after coverage validates; append it to
      authoritative-receipts.json BEFORE observe-review.
    Count remaining todos/*-pending-p1-*.md and todos/*-pending-p2-*.md
    if findings == 0:
      if required_verification_complete == false:
        Report the nested review's REVIEW INCOMPLETE or exact coverage failure
        STOP -- needs attention
      Report: "Clean after {iteration} iteration(s) with fixes."
      STOP -- success
    else:
      Report: "{findings} finding(s) remain after {iteration} iteration(s)."
      List remaining todo files
      STOP -- needs attention
```

#### Selective Lane Re-run (iteration 2+)

Iteration 1 is always a full fan-out in the selected mode. From iteration 2 onward the loop re-reviews only what the fixes could have affected. Before each fix step, preserve the exact owner lanes of every pending P1/P2 finding so deleting a resolved todo cannot erase its verification obligation. The re-run lane set is the union of:

- **(a) Finding-owning lanes** -- every lane named in the `source_agents` frontmatter of a P1/P2 finding repaired by the prior fix step, plus every lane owning a P1/P2 finding that remains pending. The loop snapshots repaired owners before `dm-review-fix` deletes completed todos.
- **(b) File-trigger lanes** -- every lane whose file-trigger set matches any file the fixes touched since the prior review. `dm-review-fix` does not commit, so the touched-file set is the union of `git diff --name-only <prior-review-head>..HEAD` and the paths reported by `git status --porcelain`. A committed-range diff alone would report an empty change set for a perfectly normal uncommitted fix pass, and would then narrow on false evidence.

Before either rule may narrow coverage, recompute a non-empty `selected_full_set` containing only unique exact logical lane IDs. Every owner in every pending finding's `source_agents` must resolve to exactly one member of that set. Unknown owners, aliases, and criterion-level IDs shared by more than one logical lane are not narrowing signals; each fails open to full coverage with an explicit `fallback_reason`. The naming trap is deliberate: `security-auditor-codex-signoff` and `security-auditor-openrouter` are two logical lanes sharing one criterion, so bare `security-auditor` is ambiguous and fails open. An empty computed lane set is never dispatched.

The committed half of changed-file discovery is boundary-guarded. `prior_review_head` must be non-null. When `HEAD` advanced, `fix_head` must differ from `prior_review_head` and `git merge-base --is-ancestor <prior_review_head> <fix_head>` must succeed before the committed diff is trusted. A reset, rewritten history, null boundary, or advanced non-ancestor boundary fails open with an explicit `fallback_reason`; it must never be read as "no files changed." When `HEAD` did not advance but `git status --porcelain` reports fix paths, the committed half contributes no paths and the uncommitted half remains valid narrowing evidence. When neither half advances, selection fails open. This preserves ordinary uncommitted-only `dm-review-fix` passes while applying the ancestry guard only to the committed half.

**Which trigger source applies depends on the mode**, because the two modes run different rosters:

- **quick mode** (the default): the eligible roster is `pattern-recognition-specialist`, `code-simplicity-reviewer`, and only the applicable existing UI/build/domain verification lanes from the quick-mode contract. Security-sensitive changes escalate to full mode.
- **full mode**: the trigger sets are the Phase 3 conditional-agents table in `plugins/dm-review/skills/review/SKILL.md`, plus the quick-mode UI trigger above.

Full-mode lanes follow the same affected-lane rule. A selective full-mode input
may omit `security-auditor-codex-signoff` only when the loop records an earlier
complete full review and the touched-file set does not match the bounded
security escalation set. It passes those facts as
`verification_basis: "affected_lane_repair"`,
`prior_full_review_complete: true`, and
`security_boundary_changed: false`; the receiver validates them. If the prior
full review was incomplete or a repair changes a security-sensitive boundary,
repeat the full fan-out so independent-family full-diff security sign-off, the
authorized external security lens, `second-perspective`, and all applicable
conditionals are complete on the new tested SHA.

When both (a) and (b) come back empty there is nothing the fixes could have affected, so selection fails open to a full fan-out with `fallback_reason: empty selection` rather than running a near-empty pass that would have to be promoted to full anyway.

The restriction is passed as the internal loop-to-review input `review_lane_allowlist`, carrying both `selected_full_set` (the loop's recomputed full lane set) and `lanes` (the narrowed subset). It is not a public flag. Review Phase 3 recomputes its own selected full set and consumes the input only when that set exactly equals `selected_full_set` and `lanes` is a unique subset of exact logical lane IDs. Otherwise the receiver discards the input, runs the original unfiltered review, and returns the exact fallback reason in its authoritative coverage receipt. An absent or invalid input always means the original unfiltered review, never an empty or partially inferred lane set.

**Current state of the receiving interface -- read this before claiming a saving.** Review Phase 3 now receives `review_lane_allowlist` under the validation contract above. The loop still never assumes that a restriction was honored: after every pass it consumes the authoritative coverage receipt and derives attempted and skipped lanes from that evidence. If the receiver reports the input absent, invalid, or not applied, the loop sets `selective_rerun` to false and persists the receiver's exact fallback reason. Input-byte savings may be claimed only from a receipt proving the narrowed input was applied.

**Convergence requires no open P1/P2 findings and complete required coverage for the verification pass.** P3 advisories never trigger another pass. A selective affected-lane pass may establish convergence when every required selected lane completes; missing required coverage reports `REVIEW INCOMPLETE`. Repeat the whole full fan-out only when the prior full review was incomplete or a repair changed a security-sensitive boundary.

#### Selective Re-run Receipt

Skipped lanes get no kernel `record-attempt` call, because nothing ran. That is exactly why every iteration report must name them: without the skip list, a `lanes: m/n` coverage delta in `run-cost-summary.json` is indistinguishable from a lane that silently failed. These fields are additions beside per-lane recording, not replacements for it.

Receipts are **per pass, not per iteration**. If an incomplete prior full review or a security-boundary repair requires a new full fan-out, report that pass separately so the affected-lane verification history remains recoverable.

The ordinary pass artifact is `.workflow-kernel/runs/<run-id>/dm-review-loop/iterations/<iteration>/iteration-receipt.json`. The last-iteration verification atomically emits `max-iterations-verification-receipt.json` beside it with artifact reason `max_iterations_affected_lane_verification`. Emit each artifact only AFTER its nested coverage receipt validates, then append it to `authoritative-receipts.json` BEFORE the corresponding `observe-review` invocation.

Each pass report carries:

- `selective_rerun: true` on a pass whose coverage receipt proves a narrowed lane set was applied; `selective_rerun: false` on iteration 1, on any full fan-out, on any fail-open fallback, and whenever a passed selective input was absent, invalid, or not applied. The value describes the pass that emitted it, never a sibling pass.
- `promoted_to_full` and `full_fanout_override` are explicit booleans on every pass, including `false`; they are never omitted as present-when-true fields.
- `promoted_to_full: true` only when an incomplete prior full review or a security-boundary repair requires another full fan-out.
- `lanes_rerun` -- the exact logical lane IDs from the coverage receipt's ATTEMPTED rows, not the loop's intended set. A receiver that silently drops an intended lane therefore cannot falsely report it as re-run.
- `lanes_skipped` -- for a proven selective pass only, `coverage_selected_set` minus the applied allowlist: the lanes deliberately omitted by narrowing. Each skipped lane records `no_rule_a_or_b_match` and receives no kernel `record-attempt` call. Every non-selective full fan-out reports an empty skip set. A lane selected or allowlisted but missing from ATTEMPTED because dispatch never began is neither re-run nor skipped; the nested review reports `REVIEW INCOMPLETE`.
- `rerun_reasons` -- a per-lane map using only `a_prior_unresolved_finding`, `b_fix_file_trigger`, `initial_full_fanout`, and `selection_fail_open`. The stable `a_prior_unresolved_finding` receipt value covers a prior P1/P2 finding owner whether the finding was repaired or remains unresolved. A lane selected by more than one rule records every applicable reason. Full fan-outs use `initial_full_fanout`; fail-open full fan-outs use `selection_fail_open`.
- `selection_fallback_reason: <reason>` whenever selection failed open to a full fan-out or the receiver rejected or ignored selective input, and `full_fanout_override: true` whenever `DM_REVIEW_LOOP_FULL_FANOUT=1` disabled selection. `selection_fallback_reason` is the persisted receipt field for the loop-local `fallback_reason`. The local variable resets at the start of every iteration so a fail-open on one iteration never leaks into the next iteration's receipt.

Example (affected-lane verification):

```
Iteration 2, pass 1: selective_rerun: true
Lanes re-run:
- code-simplicity-reviewer -- a_prior_unresolved_finding
- a11y-css-reviewer -- b_fix_file_trigger
Lanes skipped (no_rule_a_or_b_match):
- architecture-reviewer, second-perspective, doc-sync-reviewer, pattern-recognition-specialist, security-auditor-openrouter
```

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
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events .claude/ux-review/workflow-kernel/authoritative-receipts.json --output .claude/ux-review/workflow-kernel/run-cost-summary.json --receipt .claude/ux-review/workflow-kernel/run-receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> .claude/ux-review/workflow-kernel/run-receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be status-aware: exit 6 triggers one final append of `skipped (receipt-write-failed)`, exit 2 is explicitly propagated as an invalid invocation, and every other non-zero status appends `skipped (kernel-unresolvable)`. If the final append also fails, its non-zero status remains visible instead of being erased. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. The caller resolves a coherent installed-plugin bundle and passes its model-matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; the kernel validates both bundle containment and matrix structure without owning a provider dependency. An unreadable or invalid matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads through `record-attempt` as each lane settles; that one atomic call appends the lane outcome and exactly one `attempt_usage` row under the same lock. Pass the OpenRouter wrapper receipt when present, otherwise pass the exact Codex/Claude input files for deterministic byte measurement; when neither exists, the paired row explicitly records `attempt_unmeasured`. Do not also call a standalone translator with `--append-to` for that attempt, because doing both double-counts it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

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
