---
status: done
priority: p1
issue_id: "036"
tags: [review, workflow-kernel, cost-imputation]
source_agents: [final-review]
review_date: 2026-08-09
---

# Native byte estimate applies to direct OpenRouter rows

## Acceptance Criteria

- [x] byte-to-token estimation requires an explicit native alias
- [x] native provider and implementer identity remain required
- [x] a direct OpenRouter byte-only row stays unpriced
- [x] supported Codex and Claude aliases remain priceable

## Resolution

Restricted byte estimation to resolved native aliases and preserved the existing
native provider/implementer identity gate. Added a direct OpenRouter negative
regression while retaining native alias coverage in `tests/test_imputed_cost.py`.
The focused 176-test suite and full workflow-kernel validator pass.
