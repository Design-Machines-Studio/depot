---
status: done
priority: p2
issue_id: "168"
---

# Same-run and same-lane OpenRouter receipts could cross attempts

Resolved by requiring the caller-held preparation-manifest request digest for
interim `record-attempt` calls and comparing it exactly with the wrapper
receipt before the atomic ledger append. Regressions reject a different valid
digest and malformed digest shapes without creating the receipt stream, while
the exact run, lane, and envelope identity succeeds.
