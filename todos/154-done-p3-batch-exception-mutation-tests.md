---
status: done
priority: p3
issue_id: "154"
---

# Approval lifecycle tests missed exceptional post-persistence failures

Resolved with denial-only injected failures for TTY output, directory creation,
temporary-file creation, final batch reads, and transient cleanup errors, plus
a malformed second real snapshot. Every case asserts no envelope or batch is
retained.
