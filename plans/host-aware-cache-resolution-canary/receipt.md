# Issue #28 cheap-path canary receipt

Status: **FAILED CANARY — paid output rejected before application**

- Requested route/model: OpenRouter `openrouter_exec` / `deepseek/deepseek-v4-flash-0731`
- Initial executable policy result: Codex selected by `codex-20x` deficit-round-robin pressure (`0.65` Codex deficit vs `0.35` OpenRouter deficit on the first eligible chunk)
- User correction: direct configured-key OpenRouter execution was authorized after the initial policy-only stop
- Provider calls: one; no retry and no fallback model
- Served model: unavailable because the bounded adapter removes its temporary wrapper receipt after output rejection
- Live catalog: unavailable, not required for normal execution
- Matrix snapshot: checked-in `2026-08-12` planning snapshot; not live telemetry
- Input/output tokens: unavailable; the temporary wrapper receipt was not preserved
- Billed cost: unavailable; not estimated
- Worker elapsed time: 137 seconds
- Total measured execution time: 239 seconds (102-second initial gate plus 137-second paid worker)
- Worker disposition: one whole output rejected as `headerless-diff`; accepted 0, rejected 1 output with no parseable hunks, rewritten 0
- Retries/fallback: 0 / none
- Validation: Pipeline rejected the model output before application because it was not a parseable unified diff. The two focused resolver tests passed (2/2); manifest and command-alias checks, dual compatibility, workflow contracts, OpenRouter resolution, full composition, and `git diff --check` passed on the unchanged base. No Issue #28 implementation exists to validate.
- Recommendation: **reject this DeepSeek cheap execution route for this task shape**. The single call did not satisfy the executor's minimum unified-diff contract, leaving no inspectable or repairable worker hunks.

No source files, routing policy, model matrix, Workflow Kernel runtime, release preflight, caches, or tags were changed by execution. The evidence-only branch head before this receipt update remains `6a92adb235d3a284d62c55b291072b015f0773e1`.
run-cost-summary: plans/host-aware-cache-resolution-canary/run-cost-summary.json (usage measured 0/0)
