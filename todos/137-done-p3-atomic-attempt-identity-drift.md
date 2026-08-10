---
status: done
priority: p3
issue_id: "137"
---

# Atomic attempt receipts could disagree on routing identity

Resolved by deriving the usage row's routing identity from the lane executor
fields and treating legacy provider flags only as equality assertions.
