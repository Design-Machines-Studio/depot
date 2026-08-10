---
status: done
priority: p2
issue_id: "100"
---

# OpenRouter probe treated missing balances as zero

Resolved by requiring an object with numeric credit and usage fields before
subtraction. Missing or error-shaped authenticated responses now remain unknown.
