---
status: done
priority: p2
issue_id: "059"
tags: [review, contracts, openrouter]
source_agents: [pattern-recognition-specialist]
review_date: 2026-08-09
---

# Canonical batch consumers still prescribe schema v1

dm-review and routing policy still document content-only snapshots and
`payload_digests`. Migrate them to the schema-v2 exact request-envelope flow and
regenerate mirrors.
