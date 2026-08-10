---
status: done
priority: p2
issue_id: "152"
---

# Unexpected approval exceptions bypassed cleanup and rollback

Resolved with one process-exit lifecycle owner that attempts removal of every
registered private envelope and rollback of a persisted batch on every
unsuccessful exit, reporting any filesystem refusal. Success is armed only
after canonical validation and digest output are complete.
