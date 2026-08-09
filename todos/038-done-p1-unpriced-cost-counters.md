---
status: done
priority: p1
issue_id: "038"
tags: [review, workflow-kernel, cost-imputation]
source_agents: [final-review]
review_date: 2026-08-09
---

# Unpriced counters can produce a falsely complete imputed total

## Acceptance Criteria

- [x] cache-write and reasoning counters are explicitly identified as unpriced
- [x] affected rows retain null cost without trusted prices
- [x] affected totals retain missing coverage and null cost provenance
- [x] existing billed costs remain authoritative

## Resolution

Rows containing cache-write or reasoning usage now record explicit unpriced
counter provenance and remain unpriced. Coverage only moves to estimated when a
cost was actually imputed, so affected totals remain incomplete. Existing billed
costs retain precedence. The focused 176-test suite and full validator pass.
