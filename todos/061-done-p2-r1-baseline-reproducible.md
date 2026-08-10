---
status: done
priority: p2
issue_id: "061"
tags: [review, documentation, provenance]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# R1 notice falsely says baseline is irreproducible

The deleted baseline is byte-identical to run4's summary. Exclude it because
implementation-chunk bytes are incomparable to review-loop lane bytes, not
because a separate observation-only prediction differed.
