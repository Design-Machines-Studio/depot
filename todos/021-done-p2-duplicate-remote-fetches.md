---
status: done
priority: p2
issue_id: "021"
tags: [review, release-preflight, boundedness]
source_agents: [review-consolidator]
review_date: 2026-08-09
---

# Remote SHAs are fetched once per changed plugin

## Problem

The plugin-outer/branch-inner loop fetches the same advertised remote SHA again
for every changed plugin, making network calls grow as plugins times branches.

## Acceptance Criteria

- [x] Each unique advertised SHA is fetched at most once per preflight run
- [x] Fetch failures remain blocking for every affected plugin inspection
- [x] Memoization uses Bash 3.2-compatible constructs

## Resolution

A newline-delimited `SHA|rc` cache replaces associative arrays, preserving Bash
3.2 support. The harness records one fetch for a SHA shared by two changed
plugins; an injected rc 42 is likewise fetched once while producing blocking
FAIL receipts for both plugins.
