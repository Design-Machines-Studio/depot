---
status: done
priority: p2
issue_id: "026"
tags: [review, documentation, workflow-kernel]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Public cost-summary docs omit the 0.13 imputation contract

## Problem

The CLI reference omits the trusted matrix asset contract, while the Workflow
Kernel manual omits alias, byte-estimate, cost-provenance, coverage, and
fallback semantics introduced in 0.13.0.

## Fix

Document the caller-resolved installed-plugin asset boundary and the complete
observation-only imputation contract in both public references.

## Acceptance Criteria

- [x] both cost-summary CLI surfaces document the trusted matrix asset boundary
- [x] native alias and input-byte estimate provenance is documented
- [x] `imputed_subscription_equivalent` and estimated cost coverage are documented
- [x] invalid/unavailable matrix fallback is documented as non-gating

## Resolution

Both references now document the current caller-resolved
`--matrix "$MODEL_MATRIX_ASSET"` contract, coherent installed-plugin containment,
and the kernel's provider-independent validation boundary. They also cover
alias/byte-estimate provenance, estimated coverage, complete-total semantics,
and observation-only fallback. `validate-workflow-contracts.sh` passed the
caller-bound asset and consumer emission checks.
