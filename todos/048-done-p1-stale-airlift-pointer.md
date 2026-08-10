---
status: done
priority: p1
issue_id: "048"
tags: [review, documentation]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# CLAUDE points to a missing mandatory handoff

CLAUDE.md requires reading `.airlift/HANDOFF.md`, but that file is absent.
Remove the stale generated pointer or restore a valid handoff.
