---
status: done
priority: p1
issue_id: "093"
tags: [review, dependencies, workflow-kernel, receipts]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# dm-review allowed kernels without iteration receipt support

## Resolution

dm-review now requires Workflow Kernel 0.13.3, the first release containing
the closed `review_iteration` receipt stage, and dependency validation pins
that consumer floor.
