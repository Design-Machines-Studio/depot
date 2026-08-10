---
status: done
priority: p2
issue_id: "170"
---

# One OpenRouter receipt could be counted as multiple attempts

Resolved by adding a content-free per-invocation identity to every wrapper
receipt, including failures, carrying the canonical receipt digest into atomic
OpenRouter usage rows, and rejecting reuse under the same receipt-stream lock
that appends the lane/usage pair. Identical request bytes and identical failure
kinds may be retried with distinct receipts; replay appends neither row.
