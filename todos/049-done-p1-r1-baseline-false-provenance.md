---
status: done
priority: p1
issue_id: "049"
tags: [review, measurement, provenance]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# R1 baseline has false executor provenance

The R1 JSON calls five Claude Opus implementation chunks Codex attempts and
omits executed chunk 06 while claiming complete coverage. Remove it from the
usable baseline set and preserve a forensic invalidation notice.
