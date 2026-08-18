# Codex native execution adapter

Loaded by `/pipeline-run` only when the run executes from a Codex host --
Claude's generic `Agent` tool and nested `Skill(...)` calls are absent there. A
Claude-hosted run never loads it.

When this command runs in Codex and the session exposes `multi_agent_v1.spawn_agent`, use this adapter instead of stopping on Claude-only `Agent` or nested `Skill(...)` availability. This is the supported Codex execution path, not a manual workaround.

**Mode label:** Set `executionMode: codex_native` in the progress ledger, every chunk receipt, `plans/<feature>/receipt.md`, and the final summary.

The adapter also preserves `workflowClass` and provider evidence across hosts. Every dispatch receipt names `requestedProvider`, `attemptedProvider`, `implementedBy`, boolean `fallback`, and `fallbackReason`. `fallback` is strictly `true|false`, never a transition string or null; the requested, attempted, and implemented provider fields carry the transition. An unavailable or misrouted lane is evidence, not permission to silently relabel an inline implementation.

It also preserves `decisionProfile` and
`decision_profile_defaulted`. Read `decisionLeverage` from the routing policy as
depth-only: low/low optimized; high uncertainty one independent planning
opinion plus bounded synthesis; high consequence the stronger existing
independent verification seam; high/high both. Never use it to select a
provider/model/executor, alter security or workflow class, override
browser/persona cases, weaken cleanup, or change economics. High consequence
does not add full review to every ordinary chunk.

Measure orchestration pauses with authoritative `progress` receipts carrying a
nonnegative `duration_seconds` and exactly one `wait_category` from
`human_gate`, `external_dependency`, `capacity`, or `ci`. Emit one receipt for
the non-overlapping orchestrator-level interval, not one per parallel worker.
Never estimate an interval or classify active implementation/review as waiting.

**Protocol source:** Read `plugins/pipeline/agents/workflow/execution-orchestrator.md` as the execution contract. The current Codex agent acts as the orchestrator in-process because Codex does not expose Claude's generic agent runner. All orchestrator steps remain mandatory: branch create/reuse semantics, worktree isolation or the documented `sequential-on-branch` isolation strategy (recorded as `isolationStrategy`, never as `executionMode`) for container-mounted test harnesses, input guardrails, chunk dispatch, validation, evaluation gates, merge-back, the approved final review mode, cleanup, and summary. Personal-memory enrichment remains optional.

**Implementation dispatch:** For each chunk, create the worktree first, inline the full prompt content, then call `multi_agent_v1.spawn_agent` with `agent_type: "worker"`. The worker prompt MUST include:

- The worktree path as the only allowed write scope.
- The complete chunk prompt content, not a path to the prompt.
- The pipeline Fix Philosophy and ambiguity-trailer requirements.
- A reminder that other workers may be active and the worker must not revert unrelated changes.
- A requirement to commit its chunk changes before reporting completion.

Wait for the worker result before validating that chunk. Do not dispatch overlapping chunks in parallel unless the manifest level grouping and file ownership are disjoint.

On eligible deterministic validation failure, the adapter follows the
orchestrator's canonical feedback receipt and invokes exactly:

```text
$WORKFLOW_KERNEL decide-validation-retry --state-dir .workflow-kernel/runs/<run-id> --reason deterministic_validation_failure --signature <stable-signature>
```

Reject non-zero or malformed output and consume exactly `allowed`,
`reason_code`, `budget`, `attempt_count`, and `prior_signature`. Pipeline does
not duplicate retry limits in prose. Resume the same builder only with durable
host/session/repository/chunk/current-contract continuity; otherwise dispatch an
explicitly receipted replacement. Project rich feedback into kernel
`ValidationFeedback` using exactly `node_id`,
`reason_code: deterministic_validation_failure`, and safe receipt evidence
references.

**Review adapter:** Codex sessions do not expose a generic nested `Skill(skill="dm-review:review", ...)` callable. Use this risk-tiered contract in the current orchestrator context:

- For ordinary non-sensitive chunks, run one focused read-only Codex review against the chunk diff and allow at most one P1/P2/P3 repair/recheck pass. Preserve pending/done todo receipts.
- For sensitive-path chunks, run the full inline `plugins/dm-review/skills/review/SKILL.md` protocol against the chunk worktree, with at most two passes.
- For the final gate, read `finalReviewMode`. `full` runs the review skill's
  full-mode protocol. `quick` loads and executes the installed
  `dm-review-quick` protocol against the feature branch; if that protocol finds
  a bounded security-sensitive path, escalate to full and receipt the effective
  mode.
- Use `multi_agent_v1.spawn_agent` for the focused Codex reviewer or for review agents selected by the chosen dm-review protocol when available.
- Fix every retained P1/P2/P3 finding and verify repairs with affected lanes; repeat the full fan-out only if its coverage was incomplete or a repair changed a security-sensitive boundary. Reject unsupported preference-only suggestions during consolidation instead of deferring them.
- Write/read the same `todos/*-pending-*.md` and `todos/*-done-*.md` receipts that dm-review uses.

Do not report "Skill tool unavailable" in Codex when this adapter can run. That message is only valid if the session lacks both nested skill invocation and enough local access to execute the dm-review inline protocol.

**Repository verification adapter:** Resolve Workflow Kernel `>=0.15.0` once
and use its `plan-verification` and `run-verification` subcommands whenever the
target repository supplies `.dm/verification.json`.

- `chunk`: doctor, fast, and changed-package/dependent checks only.
- `revision_batch`: apply the complete finding set from one review pass, then
  perform one affected recheck.
- `execution_level`: after all sibling chunks merge, run one integrated full
  non-race pass.
- `merge_candidate`: run once for the exact candidate tree; preserve remote
  race/security/container/harness lanes explicitly.

Do not execute a full or race suite after each chunk or each individual finding
fix. For an
Assembly target without `.dm/verification.json`, stop for project
configuration rather than restoring hardcoded Go/Docker commands.

**Repository cleanup is host-independent.** The Codex adapter runs the same cleanup contract as the Claude path, at the same points (Step 0e registry init, Step 3j per chunk, Step 5b sweep + inventory) -- see `plugins/dm-review/skills/review/references/repo-cleanup-contract.md`. Cleanup is deterministic git executed by the orchestrator in-process. It is never delegated to a `multi_agent_v1.spawn_agent` worker and never routed through `openrouter-exec.sh` or `openrouter-wrapper.sh`. Deleting refs is not a judgment task, and a worker sandbox cannot be trusted to report honestly which refs survived.

The Codex adapter does not get a weaker gate than the Claude path. If `codex_native` cannot execute the cleanup phase, that is a pipeline-blocking failure, not a degradation.
