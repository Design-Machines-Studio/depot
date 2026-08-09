---
status: done
priority: p2
issue_id: "009"
tags: [review, workflow-kernel, tests]
source_agents: [codex-focused-recheck]
review_date: 2026-08-09
---

# No-matrix compatibility oracle is missing

## Problem

The required no-matrix regression test compares `build_run_cost_summary(events)`
with `build_run_cost_summary(events, matrix=None)`. Both calls execute the same
new implementation, so the test remains green if default output drifts from the
pre-chunk contract in both paths. It does not establish the requested
byte-identical compatibility with the old behavior.

## Location

- `tests/test_imputed_cost.py:205` -- compares two spellings of the new default

## Evidence

No golden pre-chunk artifact, base-implementation oracle, or pinned semantic
fixture is used by `test_no_matrix_default_is_byte_identical_to_explicit_none`.
The valid/unreadable matrix CLI and digest tests are otherwise present.

## Fix

1. Pin a representative pre-chunk no-matrix artifact or canonical serialization
   fixture with declared volatile fields normalized.
2. Run the current no-matrix CLI path against that oracle.
3. Keep the explicit-`None` comparison as an additional API-default check if useful.

## Acceptance Criteria

- [x] No-matrix CLI output matches a pre-chunk compatibility oracle
- [x] Only declared volatile fields are normalized
- [x] The test fails on any non-volatile schema-v1 output drift

## Resolution

A frozen schema-v1 oracle now covers the production-shaped Sol byte row. The
CLI test removes only `invocation.emitted_at`; digest and all other fields stay
bound to the expected artifact.
