---
status: done
priority: p1
issue_id: "024"
tags: [review, documentation, workflow-kernel]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Measurement reference publishes an unsafe bare fallback

## Problem

The measurement reference first requires a status-gated fallback, then shows a
bare `|| printf` example that also fires after exit 2 or 6.

## Fix

Remove the contradictory bare fallback and retain one exact gated pattern.

## Acceptance Criteria

- [x] no bare `emit-cost-summary ... || printf` example remains
- [x] the documented fallback covers only launcher failure
- [x] workflow contract validation passes

## Resolution

Removed the contradictory bare fallback and retained the status-gated chain,
with an explicit warning never to replace it with bare `|| printf`.
`validate-workflow-contracts.sh` passed, including all run-cost-summary emission
checks across the 11 synced consumers.
