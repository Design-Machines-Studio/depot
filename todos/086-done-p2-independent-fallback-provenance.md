---
status: done
priority: p2
issue_id: "086"
tags: [review, architecture, receipts, fallback]
source_agents: [architecture-reviewer]
review_date: 2026-08-09
---

# Independent fallback is mislabeled as Codex

Make fallback tags and attempt bounds lane-aware so receipts identify the real
reviewer family and never imply one generic Codex retry.

## Resolution

Independent fallback uses a reviewer-family tag and tries each eligible
non-implementing family once; ordinary Codex fallback keeps its existing tag
and single-retry bound.
