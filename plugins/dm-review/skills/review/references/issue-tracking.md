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
| `status` | `pending`, `in-progress`, `done` |
| `priority` | `p1`, `p2` |
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
| P2 — Important | `p2` | Yes — always |
| P3 — Nice-to-Have | — | No — stays in report only |

---

## Status Lifecycle

```
pending → in-progress → done
```

Rename the file when status changes:
```bash
mv todos/001-pending-p1-sql-injection.md todos/001-in-progress-p1-sql-injection.md
mv todos/001-in-progress-p1-sql-injection.md todos/001-done-p1-sql-injection.md
```

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
