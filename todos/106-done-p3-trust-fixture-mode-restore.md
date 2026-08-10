---
status: done
priority: p3
issue_id: "106"
---

# Trust fixture restore skipped chmod

Resolved by using a two-statement restoration helper that always writes the
original trust bytes and restores mode 0644.
