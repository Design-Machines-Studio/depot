---
status: done
priority: p2
issue_id: "037"
tags: [review, workflow-kernel, cli]
source_agents: [final-review]
review_date: 2026-08-09
---

# Empty matrix selector emits an invalid-matrix diagnostic

## Acceptance Criteria

- [x] an omitted or empty selector is expected matrix absence
- [x] expected absence emits no invalid-matrix diagnostic
- [x] a provided invalid trusted matrix still emits one diagnostic

## Resolution

The CLI now treats an omitted or empty selector as expected absence without
stderr. Non-empty invalid trusted assets still use the existing diagnostic path.
Both cost-summary entry points are covered by the empty-selector regression, and
the focused 176-test suite passes.
