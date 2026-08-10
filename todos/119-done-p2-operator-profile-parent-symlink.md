---
status: done
priority: p2
issue_id: "119"
---

# Operator profile admitted a tracked parent-directory symlink

Resolved by comparing the physical profile parent with the literal repository
`.dm` directory and exercising a tracked `.dm` symlink through the production
probe.
