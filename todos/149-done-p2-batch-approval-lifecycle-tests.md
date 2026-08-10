---
status: done
priority: p2
issue_id: "149"
---

# Operator-visible batch approval lacked behavioral coverage

Resolved with a real PTY fixture that executes `batch-approve`, checks every
lane/model/provider/role-byte/inspection summary, validates the persisted lane
mapping, and covers success, decline, no-TTY, interruption, and partial lanes.
