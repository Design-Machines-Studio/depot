---
status: done
priority: p3
issue_id: "146"
---

# Durable batch lane validation was weaker than production

Resolved by enforcing exact nested lane types and keys and by sending every
newly produced batch through the same canonical typed validator used by later
validation and redispatch.
