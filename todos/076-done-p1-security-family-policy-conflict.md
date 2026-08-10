---
status: done
priority: p1
issue_id: "076"
tags: [review, security, architecture, routing]
source_agents: [security-auditor-codex-signoff, architecture-reviewer]
review_date: 2026-08-09
---

# Security sign-off policy conflicts with family independence

Make the stable sign-off lane implementer-aware and require the reviewer family
to differ from the implementation family across policy and consumers.

## Resolution

The machine policy now treats the lane ID as stable compatibility metadata and
resolves an independent provider from the implementer family. Routing and
workflow-contract validators enforce the non-implementing-family constraint.
