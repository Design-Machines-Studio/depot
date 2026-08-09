---
status: done
priority: p1
issue_id: "007"
tags: [review, workflow-kernel, cost-accounting]
source_agents: [codex-focused-recheck]
review_date: 2026-08-09
---

# Native production remains unpriceable

## Problem

The repair adds explicit aliases and tests a fabricated native receipt carrying
token counters, but the real native measurement producer still emits only
`input_bytes` and no token counters. The new aliases also do not cover any of
the native model identities present in committed baseline receipts. As a
result, the production rows that motivated the chunk remain null-cost.

## Location

- `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/lane_bytes.py:77` -- native measurement contract explicitly omits token counters
- `plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json:5` -- aliases cover only `gpt-5.6-terra` and `gpt-5.6-luna`
- `tests/test_imputed_cost.py:44` -- the production-shaped fixture invents `native_token_usage` counters no producer emits
- `tests/test_imputed_cost.py:170` -- the test explicitly accepts current `gpt-5.6-sol` rows remaining null

## Evidence

Replaying the repaired imputer over every null-cost native lane in the committed
cost baselines still reports 12 candidate rows and 0 imputed rows. Their models
are `gpt-5.6`, `gpt-5.6-sol`, `opus`, `fable`, and `not_reported`. Repository
search finds `native_token_usage` only in the new test fixture.

## Fix

1. Wire real native token counters from the harness into attempt receipts, or
   introduce an explicitly labeled and reviewed byte-to-token estimate.
2. Add trusted aliases for the actual supported native model identities whose
   API-equivalent mapping is known; leave genuinely unknown aliases null.
3. Replace the invented fixture with a captured production-shaped receipt and
   prove at least one current Codex lane becomes priceable.

## Acceptance Criteria

- [x] A current real Codex receipt gains labeled API-equivalent cost
- [x] The native producer supplies the measurement used by imputation
- [x] Replaying committed or freshly captured native receipts imputes at least one row
- [x] Unknown Claude and model identities remain honestly null

## Resolution

The reviewed native-cost contract prices `gpt-5.6-sol` from its authoritative
catalog entry. Native `input_bytes` uses the explicit four-bytes-per-input-token
estimate without populating token fields; generic GPT-5.6 and bare Opus remain
null because their exact API pricing identities are not established.
