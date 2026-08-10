---
status: done
priority: p2
issue_id: "107"
---

# Zero-attempt selection fail-open was unrepresentable

Resolved by treating the non-null fallback field as the pass-level fail-open
signal while requiring every attempted lane, when present, to carry its closed
`selection_fail_open` reason. A positive zero-attempt regression is included.
