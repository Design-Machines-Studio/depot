---
status: done
priority: p2
issue_id: "095"
tags: [review, workflow-kernel, receipts, selective-rerun]
source_agents: [architecture-reviewer]
review_date: 2026-08-09
---

# Review iteration accepted contradictory fallback provenance

## Resolution

Fallback text and `selection_fail_open` reasons now require one another and a
non-selective pass. Iteration-only fields are rejected on every other stage,
with mutation-sensitive regressions.
