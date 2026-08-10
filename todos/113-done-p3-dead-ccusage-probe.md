---
status: done
priority: p3
issue_id: "113"
---

# Claude ccusage fallback could never satisfy required windows

Resolved by removing the misleading production-dead fallback and retaining
conservative unknown behavior outside explicit statusLine test input.
