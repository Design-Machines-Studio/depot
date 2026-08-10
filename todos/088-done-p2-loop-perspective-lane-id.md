---
status: done
priority: p2
issue_id: "088"
tags: [review, routing, selective-rerun, documentation]
source_agents: [pattern-recognition-specialist, test-coverage-reviewer]
review_date: 2026-08-09
---

# dm-review-loop uses a retired perspective lane ID

Replace the compatibility filename stem with the exact `second-perspective`
logical lane in selective rosters and receipts, then regenerate the alias.

## Resolution

Canonical and generated loop surfaces now use `second-perspective`; workflow
contracts reject the retired token while permitting the compatibility filename.
