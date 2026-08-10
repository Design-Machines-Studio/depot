---
status: done
priority: p1
issue_id: "057"
tags: [review, routing, openrouter]
source_agents: [second-perspective]
review_date: 2026-08-09
---

# OpenRouter live headroom is always unavailable

The generic conservative predicate requires `remaining_pct`, while the live
OpenRouter probe reports `balance_usd`. Make the predicate rail-specific and
test the production probe schema without reintroducing the obsolete low-balance
threshold for the auto-reloading account.
