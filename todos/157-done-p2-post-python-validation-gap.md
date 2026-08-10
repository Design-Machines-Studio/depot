---
status: done
priority: p2
issue_id: "157"
---

# Batch rollback disarmed before canonical validation

Resolved by running canonical `validate-batch` inside the lifecycle-owning
Python process and arming success only after validation and digest output. A
denial-only validation failure proves the persisted batch is rolled back.
