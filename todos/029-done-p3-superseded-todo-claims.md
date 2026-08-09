---
status: done
priority: p3
issue_id: "029"
tags: [review, documentation, todos]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Earlier done ledgers contradict the final native-cost contract

## Problem

Todo 004 says no byte estimate was added and Todo 008 names a nonexistent
`native_api_equivalent_aliases` field, although later repairs established the
four-byte estimate and `native_api_equivalent_cost` object.

## Fix

Mark Todo 004's superseded assertions explicitly and correct Todo 008's exact
field name without erasing the historical review sequence.

## Acceptance Criteria

- [x] Todo 004 points to Todo 007 and states the final byte-estimate outcome
- [x] Todo 008 consistently names `native_api_equivalent_cost`
- [x] historical problem/resolution sequencing remains clear

## Resolution

Todo 004 now labels its original no-byte-estimate result as an intermediate
state and points to Todo 007's final four-byte estimate. Todo 008 consistently
uses the exact `native_api_equivalent_cost` field name while retaining its
original problem and evidence sequence.
