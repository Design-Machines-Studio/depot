---
status: done
priority: p2
issue_id: "159"
---

# Digest publication occurred after rollback was disarmed

Resolved by publishing and flushing the caller-visible digest directly from
the lifecycle-owning Python process. There is no post-success shell output
handoff where interruption or a broken pipe can retain authority silently.
