---
status: done
priority: p2
issue_id: "060"
tags: [review, test-coverage, openrouter]
source_agents: [test-coverage-reviewer]
review_date: 2026-08-09
---

# Approval and transport render different envelope bytes

The positive fixture reconstructs compact JSON separately from the wrapper, so
exact-byte authorization rejects the supposedly approved request. Use one
canonical renderer or immutable approved envelope for approval and transport.
