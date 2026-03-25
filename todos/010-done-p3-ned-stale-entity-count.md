---
status: pending
priority: p3
issue_id: "010"
tags: [review, staleness]
source_agents: [architecture-reviewer, security-auditor, pattern-recognition-specialist]
review_date: 2026-03-25
---

# ned AI Memory description contains stale entity count

## Problem

Description says "~5,850 entities" which will immediately go stale. Also discloses "finances" category unnecessarily.

## Location

- `plugins/ned/.claude-plugin/plugin.json:13`

## Fix

Replace with static description: "Personal knowledge graph tracking projects, people, and decisions"

## Acceptance Criteria

- [ ] No live counts in plugin.json descriptions
