# Issue Tracking Reference

Repair is the default, not a tracking choice. Standalone `/dm-review` and
`/dm-review-quick` delegate to `/dm-review-loop` before dispatch, preserving the
requested mode and target. A nested review owned by Pipeline or dm-review-loop
returns findings to that owner instead of starting a recursive loop. Explicit
read-only or local-only user instructions override mutation or push defaults.

Fix every retained P1/P2/P3 in the current feature branch, verify affected lanes,
commit and push to its PR, and verify the remote head. Do not ask whether to
create todos, file issues, or begin repairs. Todo files are temporary repair
inputs, not deferred debt; allocate noncolliding IDs and preserve foreign files.
No findings means no repair dispatch. Never merge or release by implication.

## External blockers

Create or reuse a GitHub issue only when a concrete external dependency prevents
the repair here, such as an unavailable Baseplate SDK release or an upstream
service/access failure. Search the owning repository for the same blocker
first. Record the reviewed head, finding evidence, dependency/owner, why local
repair cannot resolve it, exact unblock condition, and acceptance check. Link
the issue in the review report and keep the finding pending and review non-clean.
Continue all independent local repairs. Do not move a local repair to an issue
because it is P3, inconvenient, or needs another focused attempt. Repeated local
repair failure is unresolved work, not evidence of an external dependency.

Issue creation is part of this default repair workflow, subject to explicit
read-only scope and available GitHub permission. If creation fails, preserve the
finding and prepared issue details in the report; report the failure, never a
fabricated issue URL. Do not modify or close unrelated existing issues.

---

## Todo File Template

```markdown
---
status: pending
priority: p1
issue_id: "001"
tags: [review, security]
source_agents: [security-auditor]
review_date: YYYY-MM-DD
---

# Finding Title

## Problem

Clear description of what's wrong and why it matters.

## Location

- `path/to/file.ext:line` -- specific location
- `path/to/related-file.ext:line` -- related code (if applicable)

## Evidence

What the agent found -- include code snippets, patterns, or data that demonstrate the issue.

## Fix

Specific steps to remediate:
1. Step one
2. Step two
3. Verify by...

## Reference

- Standard: OWASP A03:2021 / WCAG 2.4.7 / pattern name
- Documentation: link if applicable

## Acceptance Criteria

- [ ] Criterion one
- [ ] Criterion two
- [ ] Review agent passes on re-run
```

---

## File Naming

```
{id}-{status}-{priority}-{slug}.md
```

| Field | Values |
|-------|--------|
| `id` | 3-digit sequential: `001`, `002`, `003` |
| `status` | `pending`, `done` |
| `priority` | `p1`, `p2`, `p3` |
| `slug` | Lowercase kebab-case summary (max 5 words) |

Examples:
```
001-pending-p1-sql-injection-in-search.md
002-pending-p2-missing-csrf-protection.md
003-pending-p3-heading-rhythm.md
```

---

## Severity to Priority Mapping

| Review Severity | Todo Priority | Tracked? |
|----------------|---------------|----------|
| P1 -- Critical | `p1` | Yes -- always |
| P2 -- Should Fix | `p2` | Yes -- always |
| P3 -- Required Fix | `p3` | Yes -- always |

---

## Status Lifecycle

```
pending -> done -> (deleted after commit)
```

Rename the file when the fix is complete:
```bash
mv todos/001-pending-p1-sql-injection.md todos/001-done-p1-sql-injection.md
```

Remove only this run's completed todo files whose dispositions are preserved in
the report. Include tracked removals in the repair commit; never glob-delete
pre-existing todos. Preserve pending blockers and other owners' work.

---

## GitHub Issue Template

For a verified external blocker only (search for an existing issue first):

**Title format:** `[P1] Finding title`, `[P2] Finding title`, or `[P3] Finding title`

**Labels:** reuse applicable existing repository labels; absent labels must not
block issue creation or cause a new label taxonomy.

**Body structure:**

```markdown
## Problem
Description from the review finding.

## Location
`path/to/file.ext:line`

## Fix
Remediation steps.

## Reference
OWASP/WCAG/pattern reference.

## Source Agents
- agent-name-1
- agent-name-2

---
*From dm-review ([Full/Quick] mode, YYYY-MM-DD)*
```

---

## Batch Cleanup PR Pattern

Historical review-finding issues may already exist. Clear them in a **dedicated cleanup PR** rather than smuggling unrelated fixes into feature branches. New dm-review runs do not create another deferred backlog.

**Precedent:** PR #247/#248 (a pre-federation cleanup/review pass) merged the fixes and closed review-finding issues #106, #109, #110, #184, #207, #216, #217, #225, and #243-#246 together.

Conventions for a batch cleanup PR:

- Reference every closed issue in the PR body (`Closes #106, Closes #109, ...`) so the tracker stays accurate.
- Group the commits by finding or by surface, the same way feature PRs group by concern.
- Run `/dm-review-loop` on the cleanup branch -- every new P1/P2/P3 finding still requires resolution.
- Schedule cleanup passes around natural milestones (here: before federation work) so debt does not cross a major boundary.
- Dispose of the cleanup branch under `repo-cleanup-contract.md`. It is the one branch dm-review creates, so it is the one branch dm-review may delete -- and only once `git merge-base --is-ancestor <branch> main` exits 0. An unmerged cleanup branch is kept and reported, never force-deleted.

## Closure Reconciliation

Before claiming any finding closed -- in a review report, a session summary, or a cleanup PR -- reconcile every artifact that carries review state. On Assembly Baseplate, formal GitHub PR review threads are mostly empty; the durable review signal lives in **PR bodies, issue state, and `review-finding` issues**. A PR review thread with no comments tells you nothing about whether findings were addressed -- never treat it as the source of truth.

Reconcile all eight before declaring closure:

1. **PR body `Closes #X` references** -- the claim of closure.
2. **Actual issue open/closed state** -- the verification. `gh issue view <n> --json state`. A `Closes` reference in an unmerged or reverted PR closes nothing.
3. **Merge commits** -- confirm the PR that claims the closure actually merged (`gh pr view <n> --json state,mergedAt`).
4. **Labels** -- `review-finding` / `p1` / `p2` labels must match the issue's real state; stale labels mislead the next cleanup pass.
5. **`review-finding` issues** -- sweep for open ones the PR body never referenced (`gh issue list --label review-finding --state open`). An open finding the PR forgot to reference is still owed.
6. **PR receipts** -- the evidence the PR claims it produced (browser screenshots, JSON receipts, Auth Boundary Map receipt, two-install proof) actually exist and match the claim. A PR body that says "verified via two-install proof" or "screenshot attached" with no artifact is an unverified claim, not a closure.
7. **Changed-files vs claimed scope** -- diff the actual changed files (`gh pr view <n> --json files`) against what the PR body says it did. A "federation trust hardening" PR whose diff never touches `federation/` did not do what it claims; a reorg-only PR with logic edits in the diff broke its own contract.
8. **Open-issue sweep on the surface** -- before claiming a *surface* (federation, install, membership) is done, list every open issue touching it, not just the ones this PR named. Closing the PR's three issues while five surface issues stay open is "this PR merged," not "this surface is done."

**Worked example (federation):** Baseplate PR #252 (Session 2.9a federation backend) merged with green checks, but #253, #254, #255, #258, and #259 remained open follow-on issues. PR #271 (federation trust hardening / delivery repair) then merged but left #255 (key-rotation detection), #258 (federation file decomposition), and #270 (a user-owned historical P3 rollup) open. "Federation trust hardening merged" was true; "federation review findings closed" was false. Existing user-owned trackers remain owner-managed, but new retained findings cannot use that history as permission to defer.
