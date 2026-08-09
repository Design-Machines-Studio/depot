---
status: done
priority: p3
issue_id: "039"
tags: [review, documentation, workflow-kernel]
source_agents: [final-review]
review_date: 2026-08-09
---

# CLAUDE names Workflow Kernel 0.12.0 as current

## Acceptance Criteria

- [x] CLAUDE names the 0.13.0 behavior milestone
- [x] Workflow Kernel canonical and generated versions remain synchronized

## Resolution

Corrected the stale behavior milestone to 0.13.0 and released the runtime fix as
Workflow Kernel 0.13.1 across the canonical manifest, generated Codex manifest,
marketplace, runtime tuple, and frozen fixture. Manifest generation and the full
workflow-kernel validator pass.
