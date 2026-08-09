---
status: done
priority: p2
issue_id: "006"
tags: [review, workflow-kernel, tests]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# Matrix regressions are untested

## Problem

The chunk acceptance criteria require a regression proving that omission of
`--matrix` is byte-identical to pre-chunk output and that emitted digest
recomputation matches. The new tests cover pure-function determinism and schema
validation of an in-memory summary, but they do not compare no-matrix output to
the old behavior, invoke either CLI with valid events, exercise unreadable
matrix fallback, or recompute the emitted digest.

## Location

- `tests/test_imputed_cost.py:68` -- determinism test covers only the pure row function
- `tests/test_imputed_cost.py:76` -- summary test does not finalize or recompute a digest
- `tools/validate-workflow-kernel.py:753` -- CLI fixture adds the flag but does not assert imputed output or fallback behavior

## Evidence

The test file contains seven cases, none invoking `run-cost-summary` or
`emit-cost-summary`. There is no assertion comparing a matrix-omitted artifact
with the pre-chunk contract, and no call to `compute_cost_summary_digest` over
an emitted matrix-backed artifact.

## Fix

1. Add a no-matrix regression fixture pinned to pre-chunk semantic output
   (excluding declared volatile fields only).
2. Add valid-matrix and unreadable-matrix CLI tests for both commands.
3. Recompute and assert the digest of the emitted matrix-backed artifact.
4. Use production-shaped native and billed-cost fixtures in those tests.

## Acceptance Criteria

- [x] No-matrix behavior is explicitly regression-tested
- [x] Both CLI surfaces are tested with valid and unreadable matrices
- [x] Emitted digest recomputation matches
- [x] Billed-cost precedence is covered through the CLI path

## Resolution

Regression coverage now exercises both commands, trusted/unreadable matrices,
digest recomputation, no-matrix bytes, native aliases, and billed precedence.
