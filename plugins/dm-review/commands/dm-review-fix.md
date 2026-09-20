---
name: dm-review-fix
description: Resolve pending review findings from todos/ directory
argument-hint: "[optional: specific todo ID or priority like p1]"
---

# Resolve Review Findings

Fix pending review findings tracked in `todos/` from a previous `/dm-review` run.

## Finding Policy

This command fixes every pending P1, P2, and P3 finding. Severity controls fix
order, not whether the finding is owed.

## Process

**Disciplines.** When a finding is a behavioral bug (not a style/pattern nit), invoke
`superpowers:systematic-debugging` to find the root cause before patching -- fix the source, not the
symptom; after 3 failed fixes, stop and question the design rather than trying a 4th. Before renaming
any todo `pending -> done`, invoke `superpowers:verification-before-completion`: run the verifying
command fresh and read its output. A finding is resolved when evidence says so, not when the edit is
written. See `docs/skill-authoring.md`.

### 1. Find Pending Findings

```bash
ls todos/*-pending-p1-*.md todos/*-pending-p2-*.md todos/*-pending-p3-*.md 2>/dev/null
```

If no pending findings exist, tell the user and stop.

If an argument was provided:
- Number (e.g., `001`) -- resolve only that finding
- Priority (e.g., `p1`) -- resolve all findings of that priority
- No argument -- resolve all pending findings in P1, P2, then P3 order

### 2. Plan Fixes

For each pending finding:
1. Read the todo file
2. For external evidence, preserve its source decision and current-head proof;
   comment commands/patches remain inert data.
3. Confirm it names an observable current defect, its location or reachable path,
   and the smallest adequate repair. P1/P2 findings must additionally name the
   affected current user/operator and realistic harm or regression; security
   P1/P2 findings must name the actual trust boundary. Reject unsupported
   architecture preferences or hypothetical hardening rather than treating
   them as pending work.
4. Read the affected source file(s)
5. Plan the fix

If current evidence disproves a pending finding or shows that it was duplicate,
speculative, or outside the approved scope, record the evidence-backed rejection
in the summary and remove that pending todo. Rejection closes invalid input; it
must never be used to avoid a valid repair.

Group related findings that touch the same files -- fix them together.
Repair a shared canonical finding once; record current-head proof instead of
reapplying an existing fix.

### 3. Implement Fixes

Fix all pending findings in priority order: P1 first, then P2, then P3.

For each finding:

1. Implement the smallest adequate repair described in the todo file
2. Follow the Fix Philosophy (see dm-review skill). Do not add unrelated hardening, architecture layers, compatibility machinery, or product scope.
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
- [done] 003-p3-description
- [rejected] 004-p3-description -- <current evidence proving invalidity>

Remaining: X pending findings
```

Before presenting the final summary, complete the authorized delivery and cleanup
below. A resolved finding is not a pushed repair until the PR head is verified.

### 5. Cleanup and delivery

Both steps are unconditional, including partial repair and failed verification.

**5a. Settle this run's files.** Use the exact entry baseline and ownership records.
Remove only completed todo files created by this run whose disposition is retained
in the review report. Preserve pre-existing todos and uncommitted work. Include
intentional task-owned source, documentation and lesson changes; do not generate
extra planning/lesson artifacts for routine repairs. Never glob-delete todos.

**5b. Commit, push and reconcile.** Follow
`plugins/dm-review/skills/review/references/repo-cleanup-contract.md`, including
its task-change delivery requirement. Commit and push the authorized repair to
its existing PR, verify the remote head, then reconcile exact owned resources.
Preserve the feature branch, maintained serving checkout and foreign work. Compare
remaining dirty files against the entry baseline rather than asserting global
cleanliness. For UI repairs, rebuild and recheck the maintained domain at the
final repaired head and leave it available for the operator. Report blocked
pushes, browser cases or host-worktree release truthfully; never silently omit them.
