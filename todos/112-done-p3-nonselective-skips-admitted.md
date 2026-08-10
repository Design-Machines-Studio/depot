---
status: done
priority: p3
issue_id: "112"
---

# Kernel admitted skipped lanes on non-selective passes

Resolved by rejecting every non-empty skip set when `selective_rerun` is false,
with a mutation regression.
