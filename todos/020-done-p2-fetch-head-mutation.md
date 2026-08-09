---
status: done
priority: p2
issue_id: "020"
tags: [review, release-preflight, read-only]
source_agents: [review-consolidator]
review_date: 2026-08-09
---

# Remote inspection mutates FETCH_HEAD

## Problem

The equal-bump probe uses `git fetch` without suppressing FETCH_HEAD writes,
contradicting the release preflight's read-only promise.

## Acceptance Criteria

- [x] Remote inspection uses Git's no-write-FETCH_HEAD mode
- [x] A pre-existing FETCH_HEAD remains byte-identical after the probe
- [x] Equal-bump behavior and receipt semantics remain unchanged

## Resolution

Remote object probes now pass `--no-write-fetch-head`. The regression plants a
literal sentinel in `.git/FETCH_HEAD`, executes a real equal-bump inspection,
and proves the bytes remain unchanged while the expected equal-bump FAIL stays
intact.
