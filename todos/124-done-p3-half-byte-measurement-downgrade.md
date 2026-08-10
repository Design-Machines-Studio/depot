---
status: done
priority: p3
issue_id: "124"
---

# A half-supplied byte measurement became unmeasured

Resolved by rejecting `--agent-definition` or `--diff` unless its paired flag
is present and proving the atomic receipt stream remains absent in both cases.
