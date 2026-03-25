---
status: pending
priority: p2
issue_id: "006"
tags: [review, documentation]
source_agents: [doc-sync-reviewer]
review_date: 2026-03-25
---

# CLAUDE.md sections don't mention capabilities field

## Problem

Plugin Anatomy and Conventions sections in CLAUDE.md don't list `capabilities` as a plugin.json field. Future plugin authors won't know to add it.

## Location

- `CLAUDE.md:30` — Plugin Anatomy bullet for plugin.json
- `CLAUDE.md:134` — Conventions section listing plugin.json fields

## Fix

1. Plugin Anatomy: change "Contains `name`, `description`, `version`, and `author`" to also mention `capabilities`
2. Conventions: add `capabilities` to the optional fields list
3. Add `capabilities_summary` schema example to the Plugin Discovery section
4. Add `description-evals/` to Repository Structure diagram

## Acceptance Criteria

- [ ] Plugin Anatomy mentions capabilities
- [ ] Conventions lists capabilities as optional field
- [ ] capabilities_summary schema shown in Plugin Discovery section
- [ ] description-evals/ appears in Repository Structure
