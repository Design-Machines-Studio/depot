---
status: done
priority: p1
issue_id: "032"
tags: [review, documentation, release-preflight]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Release runbook overclaims Codex cache verification after an explicit SKIP

## Problem

REQ-CODEX-CACHE-GATE intentionally emits an explicit SKIP when Codex or its
installed-cache evidence is unavailable, but CLAUDE previously said every
passing preflight verified installed Codex versions.

## Acceptance Criteria

- [x] CLAUDE preserves the explicit SKIP contract
- [x] a Codex-cache SKIP is documented as a coverage gap
- [x] operators are forbidden from claiming installed-cache verification after a SKIP

## Resolution

CLAUDE now distinguishes a passing preflight from the evidence-specific Codex
cache result: `REQ-CODEX-CACHE-GATE` keeps its explicit `SKIP`, the skip must be
reported as a coverage gap, and installed-cache verification may be claimed
only when the receipt contains the corresponding `OK`. Verified by direct text
inspection and `./tools/validate-workflow-contracts.sh`.
