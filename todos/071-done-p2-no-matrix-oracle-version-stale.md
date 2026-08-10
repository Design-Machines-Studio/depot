---
status: done
priority: p2
issue_id: "071"
tags: [review, workflow-kernel, tests]
source_agents: [test-coverage-reviewer]
review_date: 2026-08-09
---

# Frozen no-matrix oracle retained the old kernel version

The 0.13.2 runtime bump left the frozen no-matrix artifact at 0.13.1, changing
its canonical digest and failing the full suite. Refresh the version and digest
without changing no-matrix behavior.
