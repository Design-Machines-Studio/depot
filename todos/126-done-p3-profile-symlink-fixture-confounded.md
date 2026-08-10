---
status: done
priority: p3
issue_id: "126"
---

# Operator-profile symlink fixture had two rejection causes

Resolved by tracking only the redirecting `.dm` symlink while leaving the
destination profile untracked, isolating the physical-parent guard.
