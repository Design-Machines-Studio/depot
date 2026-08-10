---
status: done
priority: p2
issue_id: "140"
---

# Bounded verifier crashed when host denied process-group signalling

Resolved by falling back to signalling the owned child leader when `killpg`
raises `PermissionError`, while retaining the failed outcome and bounded drain.
A deterministic regression injects the host-policy denial during output-limit
termination.
