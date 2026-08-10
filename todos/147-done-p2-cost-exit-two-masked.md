---
status: done
priority: p2
issue_id: "147"
---

# Cost-summary invalid invocation exit was converted to success

Resolved by explicitly propagating exit 2 in all eleven consumers and adding a
behavioral test that executes each copied status handler for exit 2, exit 6,
another nonzero status, and an append failure.
