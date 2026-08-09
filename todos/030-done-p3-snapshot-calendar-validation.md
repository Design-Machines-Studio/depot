---
status: done
priority: p3
issue_id: "030"
tags: [review, workflow-kernel, validation]
source_agents: [pattern-recognition-specialist]
review_date: 2026-08-09
---

# Snapshot validation accepts impossible calendar dates

## Acceptance Criteria

- [x] Snapshot parsing validates real calendar dates centrally.
- [x] Impossible dates fail while a real leap day passes.
- [x] Focused imputation tests pass.

## Resolution

`_valid_snapshot_date` now combines the strict `YYYY-MM-DD` shape with
`datetime.date.fromisoformat`, and both routing and native snapshots use that
single boundary. The regression rejects `2026-02-30`, accepts `2028-02-29`, and
the combined imputation/preflight suite passed 43 tests.
