---
name: dm-review
description: Full code review with all applicable agents including visual browser testing
argument-hint: "[optional: PR number, branch name, or file path]"
---

# Full Code Review

Run a comprehensive code review using all applicable agents for the current project stack.

## Zero-Deferral Policy (default)

All dm-review commands default to zero-deferral: P1, P2, AND P3 findings MUST be fixed before the branch is considered ready to merge. P3s fix band-aid solutions and tech debt -- deferring them is how debt compounds silently. `/dm-review` surfaces findings; `/dm-review-fix` resolves them; `/dm-review-loop` automates fix-until-clean.

The merge recommendation reflects this policy:

- **Zero findings:** `CLEAN` -- safe to merge.
- **P3 only (no P1/P2):** `APPROVE WITH FIXES -- P3s mandatory under zero-deferral.` NOT clean. Run `/dm-review-fix` (or `/dm-review-loop`) to resolve before merging.
- **P2 present:** `APPROVE WITH FIXES`. Must fix.
- **P1 present:** `BLOCKS MERGE`. Must fix.

To explicitly opt out of zero-deferral for a specific run (rare -- e.g. a P3 genuinely belongs in a different branch), pass `--allow-defer-p3`. Each deferred P3 must carry a written justification and a tracking destination.

## Process

1. Load the review skill from `plugins/dm-review/skills/review/SKILL.md`
2. Execute in **Full** mode with the provided argument:
   - No argument: review uncommitted changes or current branch vs main
   - PR number or URL: review that pull request
   - Branch name: review that branch vs main
   - File path: review that specific file or directory
3. Output the unified review report with merge recommendation (per the zero-deferral policy above)
