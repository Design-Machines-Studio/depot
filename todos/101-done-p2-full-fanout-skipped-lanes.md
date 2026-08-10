---
status: done
priority: p2
issue_id: "101"
---

# Full-fanout failures were misclassified as skipped lanes

Resolved by reserving `lanes_skipped` for deliberate allowlist omissions.
Full-fanout and promotion failures flow through REVIEW INCOMPLETE with an empty
skip set.
