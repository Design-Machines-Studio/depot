---
name: dm-review-fix
description: Resolve pending review findings from todos/ directory
argument-hint: "[optional: specific todo ID, priority like p1, or --allow-defer-p3]"
---

# Resolve Review Findings

Fix pending review findings tracked in `todos/` from a previous `/dm-review` run.

## Zero-Deferral Policy (default)

This command fixes ALL pending findings -- P1, P2, AND P3. Do not mark the run complete while pending P3s remain.

To opt out for a specific P3 (rare), pass `--allow-defer-p3`. Skipping requires:

1. A written justification recorded in the finding's todo file under a `Deferred:` heading explaining why this P3 cannot be fixed in this branch.
2. A tracking destination: an issue tracker ID, a scheduled fix-pass pipeline run, or a TODO comment in code with the ticket ID. "Will do later" is not valid.
3. Rename the todo file: `pending` -> `deferred` (NOT `done`).

Generic reasons ("not enough time", "out of scope") are not valid. Zero-deferral exists because those reasons never translate into later fixes.

## Process

### 1. Find Pending Findings

```bash
ls todos/*-pending-*.md 2>/dev/null
```

If no pending findings exist, tell the user and stop.

If an argument was provided:
- Number (e.g., `001`) — resolve only that finding
- Priority (e.g., `p1`) — resolve all findings of that priority
- No argument — resolve all pending findings, P1 first

### 2. Plan Fixes

For each pending finding:
1. Read the todo file
2. Understand the problem and location
3. Read the affected source file(s)
4. Plan the fix

Group related findings that touch the same files — fix them together.

### 3. Implement Fixes

Fix all findings in priority order: P1 first, then P2, then P3. Do not mark the run complete while pending P3s remain (zero-deferral default).

For each finding:

1. Implement the fix described in the todo file
2. Follow the Fix Philosophy (see dm-review skill). Never apply band-aid fixes.
3. Verify the acceptance criteria
4. Rename the todo file: `pending` -> `done`

If `--allow-defer-p3` is passed and a P3 cannot be fixed in this branch, the deferral process is:

1. Add a `Deferred:` heading to the todo file with the written justification.
2. Record the tracking destination (ticket ID, follow-up pipeline run slug, etc.).
3. Rename the todo file: `pending` -> `deferred` (NOT `done`).

The Summary (step 4) distinguishes `done` from `deferred`. Deferred todos persist in `todos/` so the tracking loop is closed explicitly.

```bash
mv todos/001-pending-p1-description.md todos/001-done-p1-description.md
```

### 4. Summary

After resolving all findings:

```text
Resolved N of M findings:
- [done] 001-p1-description
- [done] 002-p2-description
- [done] 003-p3-description
- [deferred] 004-p3-description -- justification: <reason>. Tracked: <ticket-or-fix-pass-slug>

Remaining: X pending findings
```

If any `[deferred]` entries appear WITHOUT `--allow-defer-p3` having been passed, the run is invalid -- re-run with the flag if deferral was intentional, or fix the P3 if it was not.

If all findings are resolved, suggest committing:
```
All review findings resolved. Commit the fixes?
```

### 5. Cleanup Completed Todos

Clean up completed todo files. This runs unconditionally -- do not gate on whether fixes were committed. Stale done files accumulate across sessions when this step is skipped.

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

Always clean up after fixes are committed — don't leave completed todo files accumulating.
