---
status: done
priority: p2
issue_id: "052"
tags: [review, workflow-kernel, measurement]
source_agents: [second-perspective]
review_date: 2026-08-09
---

# Review diff scope is not bound to receipts

The review contract promises diff scope, override, and slice status, while the
kernel stores only an opaque path. Bind the three values through validated,
closed `record-attempt` fields and reject incoherent combinations.
