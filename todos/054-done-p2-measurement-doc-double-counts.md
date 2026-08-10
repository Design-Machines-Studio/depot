---
status: done
priority: p2
issue_id: "054"
tags: [review, documentation, workflow-kernel]
source_agents: [code-simplicity-reviewer]
review_date: 2026-08-09
---

# Measurement guide instructs double counting

The guide warns against pairing `record-attempt` with a standalone append and
then instructs exactly that. Remove the obsolete two-call emission boundary and
state the atomic recording contract once.
