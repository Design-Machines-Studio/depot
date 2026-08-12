---
name: dm-review-fix
description: Resolve pending review findings from todos/ directory
argument-hint: "[optional: specific todo ID or priority like p1]"
---

# Resolve Review Findings

Fix pending review findings tracked in `todos/` from a previous `/dm-review` run.

## Finding Policy

This command fixes pending P1 and P2 findings. P3 advisories remain visible in the review report and receipts but never enter this fix queue.

## Process

**Disciplines.** When a finding is a behavioral bug (not a style/pattern nit), invoke
`superpowers:systematic-debugging` to find the root cause before patching -- fix the source, not the
symptom; after 3 failed fixes, stop and question the design rather than trying a 4th. Before renaming
any todo `pending -> done`, invoke `superpowers:verification-before-completion`: run the verifying
command fresh and read its output. A finding is resolved when evidence says so, not when the edit is
written. See `docs/skill-authoring.md`.

### 1. Find Pending Findings

```bash
ls todos/*-pending-p1-*.md todos/*-pending-p2-*.md 2>/dev/null
```

Historical `todos/*-pending-p3-*.md` files from releases before 1.59.0 are
advisory artifacts. Leave them owner-managed and report them separately; they
do not enter this fix queue or block completion.

If no pending findings exist, tell the user and stop.

If an argument was provided:
- Number (e.g., `001`) -- resolve only that finding
- Priority (e.g., `p1`) -- resolve all findings of that priority
- No argument -- resolve all pending findings, P1 first

### 2. Plan Fixes

For each pending finding:
1. Read the todo file
2. Understand the problem and location
3. Read the affected source file(s)
4. Plan the fix

Group related findings that touch the same files -- fix them together.

### 3. Implement Fixes

Fix all pending findings in priority order: P1 first, then P2.

For each finding:

1. Implement the fix described in the todo file
2. Follow the Fix Philosophy (see dm-review skill). Never apply band-aid fixes.
3. Verify the acceptance criteria
4. Rename the todo file: `pending` -> `done`

```bash
mv todos/001-pending-p1-description.md todos/001-done-p1-description.md
```

### 4. Summary

After resolving all findings:

```text
Resolved N of M findings:
- [done] 001-p1-description
- [done] 002-p2-description

Remaining: X pending findings
```

If all findings are resolved, suggest committing:
```
All review findings resolved. Commit the fixes?
```

### 5. Cleanup

Two parts, both unconditional -- do not gate either on whether fixes were committed.

**5a. Repository cleanup.** Run the cleanup phase per `plugins/dm-review/skills/review/references/repo-cleanup-contract.md`: `git worktree prune`, delete only branches this fix pass created and that are provably merged, leave foreign refs alone with a follow-up command, assert a clean tree, and report the inventory. Never delete the branch being fixed.

**5b. Completed todo files.** Stale done files accumulate across sessions when this step is skipped.

1. Find all done todo files:
```bash
ls todos/*-done-*.md 2>/dev/null
```

2. Delete all completed todo files:
```bash
rm -- todos/*-done-*.md
```

3. If the todos/ directory is now empty, report:
```
All review findings resolved and cleaned up. todos/ directory is clean.
```

4. If pending findings remain, list them:
```
Cleaned up N completed todos. Remaining:
- 003-pending-p2-description
```

Always clean up after fixes are committed -- don't leave completed todo files accumulating.
