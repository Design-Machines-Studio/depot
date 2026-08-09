---
status: done
priority: p1
issue_id: "010"
tags: [review, release-preflight, codex-cache, fail-closed]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# Cache checker crashes can disappear from the receipt

## Problem

The cache-report Python subprocess assumes both decoded JSON roots are objects
and the shell never checks its exit status. A valid JSON document with an
unexpected top-level type (for example `[]`) raises `AttributeError` at
`installed_doc.get(...)`; command substitution records an empty report, the
receipt prints neither FAIL nor SKIP for gate 6, and the overall preflight can
still report READY.

## Location

- `tools/check-release-preflight.sh:219` -- captures checker output but not its return code
- `tools/check-release-preflight.sh:232` -- calls `.get` before validating the JSON root type

## Root Cause

The checker handles JSON parse errors and nested-field shape errors, but not
top-level shape errors or any other unexpected Python failure. Unlike the
existing version-sync checker, its subprocess status is discarded.

## Suggested Fix

Validate that `installed_doc` and `canonical_doc` are dictionaries before any
`.get` call, and capture/check the Python command's exit status. Emit an
explicit SKIP for unsupported input shape and a blocking FAIL if the checker
itself exits unexpectedly so this gate can never vanish from the receipt.

## Acceptance Criteria

- [x] Object, array, scalar, and malformed JSON inputs each produce an explicit gate receipt
- [x] An unexpected checker exception makes the preflight non-zero rather than READY
- [x] Existing stale, fresh, and unavailable-Codex behavior remains unchanged

## Resolution

Gate 6 now validates both decoded roots before `.get`, captures the Python
checker status, and emits a blocking FAIL on unexpected non-zero exit. An
ephemeral fake-Codex harness exercised fresh and stale objects, array, scalar,
malformed JSON, and an in-memory forced `RuntimeError`; every case produced an
explicit OK, FAIL, or SKIP receipt. The unavailable-Codex branches were not
changed by this repair.
