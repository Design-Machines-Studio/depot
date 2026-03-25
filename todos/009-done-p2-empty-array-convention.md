---
status: pending
priority: p2
issue_id: "009"
tags: [review, conventions]
source_agents: [code-simplicity-reviewer, architecture-reviewer, pattern-recognition-specialist]
review_date: 2026-03-25
---

# Empty arrays vs omitted keys — inconsistent convention

## Problem

`mcpDependencies` and `argumentHint` are omitted when absent, but `agents: []` and `commands: []` are included as empty arrays. Convention is split.

## Location

- Multiple plugin.json files (ned, project-manager, project-scaffolder, design-machines, live-wires, design-practice)

## Fix

Pick one convention and apply consistently:
- Option A: Always include empty arrays (consumer-friendly, `.length` works)
- Option B: Omit empty arrays (consistent with mcpDependencies pattern)

Document the choice in CLAUDE.md Plugin Discovery section.

## Acceptance Criteria

- [ ] Convention documented in CLAUDE.md
- [ ] All 14 plugin.json files follow the chosen convention
