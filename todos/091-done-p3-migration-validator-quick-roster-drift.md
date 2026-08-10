---
status: done
priority: p3
issue_id: "091"
tags: [review, documentation, roster, migration]
source_agents: [kimi-k3]
review_date: 2026-08-09
---

# Migration validator registry overstates quick-mode coverage

Align the registry with the executable quick roster: migration validation is
conditional in full mode and is not added by quick mode.

## Resolution

The registry now states full mode only, and workflow contracts require the
correct statement while rejecting both retired quick-mode claims.
