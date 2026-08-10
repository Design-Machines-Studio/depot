---
status: done
priority: p1
issue_id: "051"
tags: [review, workflow-kernel, routing]
source_agents: [second-perspective]
review_date: 2026-08-09
---

# Routing receipts omit matrix decision evidence

Policy requires matrix snapshot date and rung rationale on every routing
decision, but `record-attempt` cannot bind or validate them. Add closed CLI
fields, schema validation, storage, and negative tests.
