---
status: done
priority: p1
issue_id: "004"
tags: [review, workflow-kernel, cost-accounting]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# Native rows remain unpriceable

## Problem

The implementation cannot impute the real Codex and Claude attempt rows it was
introduced to measure. Native attempts are recorded by `lane-input-bytes` with
`input_bytes` and no token counters, while `impute_attempt_cost` prices only
`input_usage_count`, `output_usage_count`, and `cache_read_usage_count`.
Additionally, committed native receipts use bare aliases such as `gpt-5.6-sol`,
`gpt-5.6`, `opus`, and `fable`, while the selected OpenRouter matrix explicitly
excludes native Codex and Claude identities.

## Location

- `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/imputed_cost.py:8` -- only token-counter fields are priceable
- `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/imputed_cost.py:29` -- model lookup requires an exact matrix slug
- `plugins/workflow-kernel/skills/workflow-kernel/references/workflow_kernel/lane_bytes.py:88` -- native producer emits only `input_bytes`
- `plugins/openrouter/skills/openrouter-delegate/references/model-matrix.json:2` -- native identities are deliberately absent

## Evidence

Applying this branch's `impute_attempt_cost` to every null-cost native lane in
the committed cost baselines found 12 candidate rows and 0 imputed rows. Their
models were `gpt-5.6-sol`, `gpt-5.6`, `opus`, `fable`, and `not_reported`.
The new unit test instead invents `openai/gpt-test` plus token counters, a shape
that the native producer does not emit.

## Fix

1. Define a trusted native-model pricing identity/alias contract rather than
   guessing OpenRouter twins from string prefixes.
2. Capture real native token counters when the harness provides them, or define
   an explicitly labeled and reviewed bytes-to-token estimate before applying
   token prices. Do not silently treat bytes as tokens.
3. Exercise the implementation with production-shaped Codex and Claude
   attempt receipts and the real matrix data.

## Acceptance Criteria

- [x] A real-shaped Codex attempt gains visibly imputed API-equivalent cost
- [x] A supported Claude attempt gains cost when its trusted price is present
- [x] At this repair stage, unknown native aliases and byte-only rows remained
  honestly null; Todo 007 superseded the byte-only part of this criterion
- [x] Existing billed OpenRouter receipt costs remain authoritative

## Resolution

At this intermediate repair stage, the trusted matrix owned explicit native
API-equivalent aliases and no byte-to-token estimate had been added.

## Superseded by Todo 007

Todo 007 completed the production-shaped repair. The final contract uses an
explicit four-input-bytes-per-token estimate for supported `gpt-5.6-sol` rows,
records that estimate in provenance, and leaves unknown identities null.
