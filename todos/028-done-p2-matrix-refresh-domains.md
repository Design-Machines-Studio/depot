---
status: done
priority: p2
issue_id: "028"
tags: [review, documentation, openrouter, freshness]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Routing and native-cost refresh domains are conflated

## Problem

The model-selection refresh procedure says every refresh moves the top-level
and every model date, but the matrix intentionally carries independent routing
and native API-equivalent cost snapshots.

## Fix

Split the procedures and state exactly which snapshot and entries each refresh
owns without restamping unrelated evidence.

## Acceptance Criteria

- [x] routing refresh updates only the routing snapshot domain
- [x] native-cost refresh updates only the native cost snapshot domain
- [x] both procedures name their evidence and no-restamping rule

## Resolution

Split the routing and native API-equivalent cost procedures. Each now names its
owned snapshots, entries, and evidence sources, and explicitly forbids
restamping the other domain when its evidence was not refreshed.
