---
status: done
priority: p1
issue_id: "089"
tags: [review, routing, authorization, cascade]
source_agents: [kimi-k3]
review_date: 2026-08-09
---

# Authorized native judgment remains unreachable

Make run-bound human authorization the sole availability gate for the
`native_judgment` rung and prove exhausted ordinary rails cannot mask it.

## Resolution

The review proved that the existing environment object was not valid human
authority at all. The rung is now explicitly unavailable until a trusted
single-use issuer/consumer exists; exhausted headroom reports the deadlock
honestly, and every caller-supplied grant shape fails closed.
