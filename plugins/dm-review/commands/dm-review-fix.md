---
name: dm-review-fix
description: Resolve pending review findings from todos/ directory
argument-hint: "[optional: specific todo ID or priority like p1]"
---

# Resolve Review Findings

Fix pending review findings tracked in `todos/` from a previous `/dm-review` run.

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

Fix findings in priority order: P1 first, then P2.

For each finding:
1. Implement the fix described in the todo file
2. Verify the acceptance criteria
3. Rename the todo file: `pending` → `done`

```bash
mv todos/001-pending-p1-description.md todos/001-done-p1-description.md
```

### 4. Summary

After resolving all findings:

```
Resolved N of M findings:
- [done] 001-p1-description
- [done] 002-p2-description
- [skipped] 003-p2-description — reason

Remaining: X pending findings
```

If all findings are resolved, suggest committing:
```
All review findings resolved. Commit the fixes?
```
