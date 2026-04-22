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

- `--full` -- Use full dm-review (all agents) instead of quick (5 core agents)
- `--max-iterations N` -- Maximum review-fix cycles (default: 3)
- `--allow-defer-p3` -- Opt out of zero-deferral for P3 findings. Requires each deferred finding to carry an explicit justification and a tracking destination. Default OFF.
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
target = remaining arguments after flag parsing
prior_findings_signature = null  # for stalled-convergence detection
```

### 2. Review-Fix Loop

```text
while iteration < max_iterations:
  iteration += 1

  # Run review
  if mode == "quick":
    Run /dm-review-quick {target}
  else:
    Run /dm-review {target}

  # Check for findings
  Count findings in todos/*-pending-*.md
  current_signature = sorted list of pending todo filenames

  if findings == 0:
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

  # Fix all findings (all severities -- P1, P2, AND P3)
  # Under zero-deferral (default), dm-review-fix addresses every pending finding.
  # Under --allow-defer-p3, P3s may be triaged; P1/P2 still mandatory.
  if allow_defer_p3:
    Run /dm-review-fix --allow-defer-p3
  else:
    Run /dm-review-fix
  # dm-review-fix resolves and cleans up todo files

  # If this was the last iteration, run one final review to verify
  if iteration == max_iterations:
    Run review one more time (same mode)
    Count remaining findings
    if findings == 0:
      Report: "Clean after {iteration} iteration(s) with fixes."
      STOP -- success
    else:
      Report: "{findings} finding(s) remain after {iteration} iteration(s)."
      List remaining todo files
      STOP -- needs attention
```

### 3. Report

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

## Integration

This command composes existing dm-review commands -- it does not reimplement review or fix logic. It simply runs them in a loop with a convergence check.

Used by the pipeline plugin's execution-orchestrator agent for post-chunk review-fix loops, but useful standalone for any "fix it until it's clean" workflow.
