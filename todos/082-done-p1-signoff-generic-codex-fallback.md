---
status: done
priority: p1
issue_id: "082"
tags: [review, security, fallback, architecture]
source_agents: [security-auditor-codex-signoff, architecture-reviewer]
review_date: 2026-08-09
---

# Generic Codex fallback overrides sign-off independence

Make failure, full-decline, and partial-coverage fallback lane-aware so the
mandatory sign-off never returns to the implementing family.

## Resolution

All fallback decision points now resolve the lane before the provider. The
machine policy maps all three failure shapes to another non-implementing family
or `REVIEW INCOMPLETE`, and focused policy gates enforce the mapping.
