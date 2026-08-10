---
status: done
priority: p3
issue_id: "160"
---

# Canonical-validation failure test bypassed the real validator

Resolved by mutating the persisted batch with an unexpected field immediately
before the actual recursive `validate-batch` call. Removing that call now turns
the fixture into a retained successful batch and fails the test.
