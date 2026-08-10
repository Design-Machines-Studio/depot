---
status: done
priority: p3
issue_id: "144"
---

# Cost-summary exit 6 was converted to success

Resolved by handling exit 6 separately with a `receipt-write-failed` inventory
append, leaving invalid invocation exit 2 alone, and reserving
`kernel-unresolvable` for launcher failures that the kernel could not report.
