---
status: done
priority: p3
issue_id: "050"
tags: [review, documentation, measurement]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Baseline README names a nonexistent run date

The README says the run date is in `run_identity`, but the schema records the
first event at `invocation.first_event_at`. Correct the operator guidance.
