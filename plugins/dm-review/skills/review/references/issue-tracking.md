# Issue Tracking Reference

Template and conventions for tracking review findings as todo files or GitHub Issues.

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

- `path/to/file.ext:line` — specific location
- `path/to/related-file.ext:line` — related code (if applicable)

## Evidence

What the agent found — include code snippets, patterns, or data that demonstrate the issue.

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
003-pending-p2-heading-hierarchy-broken.md
```

---

## Severity to Priority Mapping

| Review Severity | Todo Priority | Tracked? |
|----------------|---------------|----------|
| P1 — Critical | `p1` | Yes — always |
| P2 — Should Fix | `p2` | Yes — always |
| P3 -- Fix Before Merge | `p3` | Yes -- always |

---

## Status Lifecycle

```
pending → done → (deleted after commit)
```

Rename the file when the fix is complete:
```bash
mv todos/001-pending-p1-sql-injection.md todos/001-done-p1-sql-injection.md
```

After fixes are committed, delete completed todo files:
```bash
rm todos/*-done-*.md
```

Don't leave completed todo files accumulating. Clean up after every fix session.

---

## GitHub Issue Template

When tracking via GitHub Issues instead of text files:

**Title format:** `[P1] Finding title` or `[P2] Finding title`

**Labels:** `review` + `p1` or `p2`

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

## Promoting a Finding to a Durable GitHub Issue

The zero-deferral policy (see `severity-mapping.md`) governs findings **in scope for the current branch**: those are fixed before merge, not deferred. A separate case is a valid finding whose fix is a **structural refactor larger than the change under review** (a domain-model change, or splitting oversized files) -- new, durable work to track as a GitHub issue rather than smuggle into the branch or drop into an ephemeral todo file. This is not a deferral loophole: it applies only when the fix is out-of-scope work newly surfaced, never to in-scope work owed.

Promote a finding to a GitHub issue (instead of a `todos/` file) when **all** of these hold:

- The fix touches a data model, public interface, or file structure beyond the diff under review.
- Implementing it in the current branch would expand scope past the branch's stated purpose.
- The finding is concrete enough to act on later without re-deriving it.

Do **not** promote a finding just to avoid fixing it. If the fix fits the current change, fix it now.

**Examples from Assembly Baseplate review history:**

- **#233** -- "measurable membership requirements store a target but completion is boolean." Correcting the model (track progress toward the target, not a boolean done-flag) is a schema + service change wider than the membership UI polish branch that surfaced it. Tracked as an open P2 issue, not forced into the polish PR.
- **#234** -- "split oversized membership service + admin handler files." A multi-file decomposition (triggered by the architecture-reviewer File Size Limits check) that is its own unit of work. Tracked as an open P2 issue.

The polish branch (PR #238) closed the in-scope membership findings (#235, #236) and left #233/#234 as tracked issues -- correct application of this rule.

## Batch Cleanup PR Pattern

Tracked review-finding issues accumulate. Clear them in a **dedicated cleanup PR** rather than smuggling unrelated fixes into feature branches. One cleanup pass can close many issues at once.

**Precedent:** PR #247/#248 (a pre-federation cleanup/review pass) merged the fixes and closed review-finding issues #106, #109, #110, #184, #207, #216, #217, #225, and #243-#246 together.

Conventions for a batch cleanup PR:

- Reference every closed issue in the PR body (`Closes #106, Closes #109, ...`) so the tracker stays accurate.
- Group the commits by finding or by surface, the same way feature PRs group by concern.
- Run `/dm-review-loop` on the cleanup branch -- a cleanup PR is still subject to zero-deferral on any *new* findings it introduces.
- Schedule cleanup passes around natural milestones (here: before federation work) so debt does not cross a major boundary.
