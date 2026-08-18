# Codex native adapter parity

Loaded by the execution orchestrator only when the run executes from a Codex
host (`executionMode: codex_native`). A Claude-hosted run never loads it.

When executed from Codex via `/pipeline-run`, Claude's generic `Agent` tool and nested `Skill(skill="dm-review:review", ...)` calls may not exist. In that host the caller MUST use the Codex Native Execution Adapter from `plugins/pipeline/references/codex-native-execution-adapter.md` and record `executionMode: codex_native`.

Parity requirements:

- The current Codex agent is the orchestrator and follows this file as the execution contract.
- Implementation chunks are dispatched with `multi_agent_v1.spawn_agent` after the worktree is created; worker prompts inline the complete chunk prompt and restrict writes to the chunk worktree.
- Ordinary per-chunk gates use one native focused Codex reviewer; sensitive chunks use the dm-review inline protocol from `plugins/dm-review/skills/review/SKILL.md` in full mode.
- The final gate uses the validated full-or-quick dm-review inline protocol against the feature branch; quick security matches escalate to full.
- Zero-deferral, convergence limits, pending/done todo receipts, final requirements cross-check, cleanup, and summary reporting remain mandatory. Personal-memory enrichment is optional.

Do not stop merely because Codex lacks Claude's `Agent` or `Skill` tool names when the Codex adapter tools are available. Stop only if neither native tool invocation nor the Codex adapter can provide isolated worker dispatch and review gates.

---
