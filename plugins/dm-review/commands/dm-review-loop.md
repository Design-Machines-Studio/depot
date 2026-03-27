---
name: dm-review-loop
description: Run dm-review then dm-review-fix in a convergence loop until zero findings remain or max iterations reached
argument-hint: "[optional: --full, --max-iterations N, PR number, branch, or path]"
---

# Review-Fix Convergence Loop

Automates the cycle of reviewing code, fixing all findings, and re-reviewing until clean.

## Zero-Deferral Policy

This command treats ALL findings as blockers -- P1, P2, AND P3. Unlike standalone `/dm-review` where P3s may be triaged as "nice-to-have," the loop fixes everything. P3s (tech debt, band-aid solutions, simplification opportunities) are just as important to fix when encountered -- deferring them is how tech debt compounds.

## Arguments

Parse the argument string for flags and pass-through values:

- `--full` -- Use full dm-review (all agents) instead of quick (5 core agents)
- `--max-iterations N` -- Maximum review-fix cycles (default: 3)
- Everything else -- Passed through to dm-review as the review target (PR number, branch, path)

## Process

### 1. Initialize

```
iteration = 0
max_iterations = 3 (or from --max-iterations)
mode = "quick" (or "full" if --full flag present)
target = remaining arguments after flag parsing
```

### 2. Review-Fix Loop

```
while iteration < max_iterations:
  iteration += 1

  # Run review
  if mode == "quick":
    Run /dm-review-quick {target}
  else:
    Run /dm-review {target}

  # Check for findings
  Count findings in todos/*-pending-*.md

  if findings == 0:
    Report: "Clean after {iteration} iteration(s). Zero findings."
    STOP -- success

  # Fix all findings (all severities -- P1, P2, AND P3)
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
