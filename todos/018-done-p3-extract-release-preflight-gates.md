---
status: done
priority: p3
issue_id: "018"
tags: [review, release-preflight, simplicity]
source_agents: [code-simplicity-reviewer]
review_date: 2026-08-09
---

# Extract release-preflight gates from the top-level flow

## Problem

The Codex-cache and cross-lane gates add roughly 200 lines of deeply nested
logic directly to the script body, making their independent contracts and
failure paths difficult to reason about.

## Acceptance Criteria

- [x] Cache freshness lives in one named function
- [x] Cross-lane equal-bump inspection lives in one named function
- [x] Existing receipt text, exit status, and Bash 3.2 compatibility remain intact

## Resolution

The gates now run through `check_codex_cache_freshness` and
`check_cross_lane_bumps`. The focused behavioral suite passes under the system
Bash path, and `bash -n` plus ShellCheck are clean.
