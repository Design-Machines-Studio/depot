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

## Shadow Workflow Kernel Lifecycle

The review skill, selected lanes, findings, coverage receipt, merge recommendation, and repository-cleanup report remain authoritative. Resolve the workflow kernel from the real path of the currently executing canonical Depot dm-review plugin; accept an in-repository runtime only beneath that same canonical Depot repository realpath, otherwise search versioned cache entries under `~/.claude/plugins/cache/depot/` and then `~/.codex/plugins/cache/depot/`. Reject symlink escapes, project-cwd/PATH discovery, and incompatible plugin metadata.

After the authoritative consolidated review and coverage receipt exist, run the stable `python3 -m workflow_kernel observe-review` command. At terminal cleanup, run `compare` and `metrics`; inline Python source is forbidden. Missing/incompatible runtime records `shadow unavailable` and preserves the review result. A parity gap cannot convert `CLEAN`, `APPROVE WITH FIXES`, `BLOCKS MERGE`, or `REVIEW INCOMPLETE`; it is proposal-only evidence.

When a review request has no explicit `workflowClass`, translate it as `feature` with `workflow_class_defaulted=true`; never infer it from findings, diff kinds, or severity. Preserve requested/attempted/implemented-by/fallback/reason evidence for every provider lane.
