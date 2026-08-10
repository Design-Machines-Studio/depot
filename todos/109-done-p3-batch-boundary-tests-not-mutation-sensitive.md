---
status: done
priority: p3
issue_id: "109"
---

# Batch boundary repairs lacked mutation-sensitive tests

Resolved with direct ready/degraded broker tests for typed batch validation and
a shipped-helper fixture that mutates the original batch after snapshotting and
requires digest plus verification to use the private snapshot.
