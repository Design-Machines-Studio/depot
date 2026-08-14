# Issue #28 cheap-path canary receipt

Status: **INCONCLUSIVE — paid route not selected**

- Requested route/model: OpenRouter `openrouter_exec` / `deepseek/deepseek-v4-flash-0731`
- Executable policy result: Codex selected by `codex-20x` deficit-round-robin pressure (`0.65` Codex deficit vs `0.35` OpenRouter deficit on the first eligible chunk)
- Provider calls: none
- Served model: unavailable
- Live catalog: unavailable, not required for normal execution
- Matrix snapshot: checked-in `2026-08-12` planning snapshot; not live telemetry
- Input/output tokens: unavailable because no call occurred
- Billed cost: unavailable because no call occurred; not estimated
- Worker elapsed time: unavailable because no worker ran
- Total execution-gate elapsed time: 102 seconds
- Worker hunks: accepted 0, rejected 0, rewritten 0
- Retries/fallback: 0 / none
- Validation: the two focused resolver tests passed (2/2); manifest and command-alias checks, dual compatibility, workflow contracts, OpenRouter resolution, full composition, and `git diff --check` all passed on the unchanged base. The first focused-test command omitted the repository-required `PYTHONPATH`; the corrected exact invocation passed. No Issue #28 implementation exists to validate.
- Recommendation: **reject this single-chunk cheap-route canary under the current run-level target-pressure algorithm**. It cannot reach OpenRouter as the first eligible chunk without forcing the provider, which policy forbids. Revisit only with an approved canary mechanism that preserves routing authority while making experimental route eligibility explicit.

No source files, routing policy, model matrix, Workflow Kernel runtime, release preflight, caches, tags, Issues, or PRs were changed by execution. The unchanged feature branch remains anchored at `a1094889b0461579a744d2ba159a41c6e394d081`.
run-cost-summary: plans/host-aware-cache-resolution-canary/run-cost-summary.json (usage measured 0/0)
