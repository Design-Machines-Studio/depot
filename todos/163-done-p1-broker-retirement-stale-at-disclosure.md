---
status: done
priority: p1
issue_id: "163"
---

# Broker retirement was sampled only before prompt ingestion

Resolved by applying the same fail-closed broker-state gate at process start
and again after exact envelope membership, immediately before provider contact.
Behavioral fixtures transition absent to ready and degraded while stdin is
blocked and prove zero transport contact.
