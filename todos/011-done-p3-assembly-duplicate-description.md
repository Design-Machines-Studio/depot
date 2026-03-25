---
status: pending
priority: p3
issue_id: "011"
tags: [review, simplicity]
source_agents: [code-simplicity-reviewer]
review_date: 2026-03-25
---

# assembly skill description duplicates plugin description

## Problem

Skill `development` description is identical to the plugin-level description. Skills should be more specific.

## Location

- `plugins/assembly/.claude-plugin/plugin.json`

## Fix

Differentiate skill description: "Go, Templ, and Datastar patterns — handlers, migrations, CRUD flows, SSE endpoints, and Docker ops"

## Acceptance Criteria

- [ ] Skill description is distinct from plugin description
