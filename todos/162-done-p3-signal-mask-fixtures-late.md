---
status: done
priority: p3
issue_id: "162"
---

# Signal-mask fixtures fired after rollback ownership

Resolved by moving the denial-only signal injections into the actual masked
windows: after temporary-file creation but before temp-path ownership, and
after replacement but before persisted-batch ownership. The existing absence
assertions now fail if either production mask is removed.
