---
status: pending
priority: p2
issue_id: "008"
tags: [review, documentation]
source_agents: [architecture-reviewer, pattern-recognition-specialist]
review_date: 2026-03-25
---

# capabilities_summary.tags aggregation rule undocumented

## Problem

CLAUDE.md says "aggregated tags" but doesn't define whether marketplace tags are a computed union or a curated shortlist. Current implementation is a curated subset — will cause confusion.

## Location

- `CLAUDE.md:71` — capabilities_summary mention

## Fix

1. Add clarifying sentence: "Tags in `capabilities_summary` are a curated representative subset, not a computed union of all skill/agent tags."

## Acceptance Criteria

- [ ] CLAUDE.md explicitly documents tags as curated subset
