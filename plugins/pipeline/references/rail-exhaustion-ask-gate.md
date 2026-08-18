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

Record the measured pause with `wait_category: human_gate`; a `wait` receipt carries the named reset time and the resume instruction. A `park` records resumable state with the exact chunk left pending.

This gate governs scheduling only (wait or park) at RC 76; it never launches or relaunches the orchestrator. The run-launch sequence lives in the `/pipeline-run` command's `## Process` section.
