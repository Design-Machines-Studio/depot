---
status: done
priority: p1
issue_id: "090"
tags: [review, workflow-kernel, receipts, selective-rerun]
source_agents: [kimi-k3]
review_date: 2026-08-09
---

# Selective iteration receipts are outside the kernel schema

Add the documented review-iteration stage and selection fields to the closed
receipt vocabulary, validate their shapes, and prove downstream translation.

## Resolution

Workflow Kernel 0.13.3 admits `review_iteration`, preserves every documented
selection field, rejects incoherent shapes, and tests the same stream through
atomic `record-attempt`, review translation, and cost-summary validation.
