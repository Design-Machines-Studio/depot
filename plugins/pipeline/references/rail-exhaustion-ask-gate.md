# Rail-exhaustion ask gate

Loaded by `/pipeline-run` only when the cascade reports every configured rail
for a chunk exhausted or gated (`CASCADE_RC` 76). A run whose rails have
headroom never loads it.

When every configured rail for a chunk is exhausted or gated (cascade RC 76),
the run pauses instead of terminating. Capacity is recoverable. The ask shows
live rail status and offers “wait until reset” or “park this run.” Any context
that cannot reach the operator parks resumable.
There is no dormant or
operator-authorized coding rail outside the configured Codex and OpenRouter
paths.

Ask-then-default-park is the only headless behavior: a non-interactive session, an ask that errors, an ask answered by a non-operator, or one that exceeds the caller's stated timeout parks resumable. `PIPELINE_EXHAUSTION_ASK=0` selects the same resumable park directly for headless CI. The ask cannot broaden configured-key OpenRouter workload, disclosure, path, or output boundaries; the approved final dm-review gate is never waived, required family independence remains, and sensitive-path chunks are never rerouted. The routing policy object is `exhaustionFallback` in `plugins/pipeline/references/routing-policy.json`.

## Process

1. Read the manifest
2. If running in Codex with `multi_agent_v1.spawn_agent`, run the **Codex Native Execution Adapter** above
3. Otherwise, launch the execution-orchestrator agent from `plugins/pipeline/agents/workflow/execution-orchestrator.md`
4. Pass the manifest path, prompts directory, and feature branch name
5. The orchestrator handles everything autonomously:
   - Branch creation or exact-head existing-branch reuse
   - Worktree creation per chunk
   - Subagent dispatch with inlined prompt content
   - focused Codex review after ordinary chunks; full review for sensitive paths
   - Merge back to feature branch
   - Approved final dm-review mode, with security escalation
   - preparation of one compact memory observation for the capable caller
   - cumulative shadow observation after all chunks and at terminal, when the trusted runtime is available
6. Apply the caller-side memory handoff below
7. Present the execution summary
