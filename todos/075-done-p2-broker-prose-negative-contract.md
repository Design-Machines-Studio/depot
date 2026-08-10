---
status: done
priority: p2
issue_id: "075"
tags: [review, tests, contracts]
source_agents: [test-coverage-reviewer]
review_date: 2026-08-09
---

# Workflow contracts permit contradictory broker prose

Add negative contract assertions that reject executable broker-mode claims in
dm-review consumers until broker-owned transport is implemented.

## Resolution

The workflow contract validator now rejects the stale availability and routing
enum phrases across the canonical command, generated alias, and review skill.
