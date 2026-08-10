---
status: done
priority: p2
issue_id: "158"
---

# Overlapping PTY teardown signals re-entered cleanup

Resolved by ignoring all handled signals as soon as the first signal begins,
running idempotent lifecycle cleanup synchronously, and asserting exactly one
interruption receipt under the process-group fixture.
