---
status: done
priority: p2
issue_id: "019"
tags: [review, release-preflight, tests]
source_agents: [test-coverage-reviewer]
review_date: 2026-08-09
---

# Release-preflight scenarios are not durable

## Problem

Cache parsing and remote equal-bump behavior were proved only by ephemeral
harnesses, leaving no repeatable repository regression suite.

## Acceptance Criteria

- [x] Fresh, stale, malformed, and unavailable Codex cases are repeatable
- [x] `--no-net`, equal/greater, same-name divergent/contained cases are repeatable
- [x] Fatal merge-base and diff predicate statuses are repeatable and fail closed

## Resolution

`tests/test_release_preflight.py` runs the real script in temporary repositories
against a local bare remote. Fifteen tests cover cache JSON, no-network behavior,
equal/greater bumps, same-name ancestry, Git predicate failures, and fetch
failure handling; all pass.
