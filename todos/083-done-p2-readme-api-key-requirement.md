---
status: done
priority: p2
issue_id: "083"
tags: [review, documentation, authorization]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# README understates the API-key requirement

Document that every live wrapper call needs the key while key presence alone
never grants automated authority.

## Resolution

The README now states both halves of the contract and the workflow validator
pins the live-transmission requirement.
