---
status: done
priority: p3
issue_id: "150"
---

# Verify-batch usage omitted its mandatory lane identifier

Resolved by documenting the required `--lane-id` argument in the executable
helper's usage synopsis, matching its parser and fail-closed invocation check.
