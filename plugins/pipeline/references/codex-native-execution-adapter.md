# Codex native execution adapter

Loaded by `/pipeline-run` only when the run executes from a Codex host --
Claude's generic `Agent` tool and nested `Skill(...)` calls are absent there. A
Claude-hosted run never loads it.

When this command runs in Codex and the session exposes `multi_agent_v1.spawn_agent`, use this adapter instead of stopping on Claude-only `Agent` or nested `Skill(...)` availability. This is the supported Codex execution path, not a manual workaround.

**Mode label:** Set `executionMode: codex_native` in the progress ledger, every chunk receipt, `plans/<feature>/receipt.md`, and the final summary.

The adapter preserves `workflowClass` and role evidence across hosts. Every
public dispatch receipt names requested role/capabilities/effort, effective
effort, anonymous participant, boolean `fallback`, and `fallbackReason`.
Concrete identity and billing stay in the referenced private model-router
receipt. An unavailable lane is evidence, not permission to relabel inline
implementation.

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

**Implementation dispatch:** For each chunk, create the worktree first and
materialize the complete prompt. Invoke model-router's `role-dispatch.sh` from
that worktree with the manifest's `executorRole`, repeated
`executorCapabilities`, and `executorEffort`, plus fresh output and private
receipt destinations, the complete repository-evidence file, and the current
behavioral contract digest/revision. Pass the exact invocation-local validated
Kernel launcher as `--workflow-kernel "$WORKFLOW_KERNEL"`. Build argv as an array. Never call a host
worker/model transport directly. The materialized prompt MUST include:

- The worktree path as the only allowed write scope.
- The complete chunk prompt content, not a path to the prompt.
- The pipeline Fix Philosophy and ambiguity-trailer requirements.
- A reminder that other workers may be active and the worker must not revert unrelated changes.
- A requirement to commit its chunk changes before reporting completion.

Wait for the role result before validating that chunk. Do not dispatch
overlapping chunks in parallel unless the manifest level grouping and file
ownership are disjoint.

Append every successful live implementation and repair receipt ID to the
run-private terminal-report set. Do not pass implementation receipts or author
origin into final dm-review or affected-lane eligibility. These are receipts
produced internally by this run; never ask the operator to provide them.
Preserve them until terminal reporting and the final review disposition settle.

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

- For ordinary non-sensitive chunks, request one focused read-only
  `review-fast` or `review-deep` role against the chunk diff and allow at most
  one P1/P2/P3 repair/recheck pass. Preserve pending/done todo receipts.
- For sensitive-path chunks, run the full inline `plugins/dm-review/skills/review/SKILL.md` protocol against the chunk worktree, with at most two passes.
- For the final gate, read `finalReviewMode`. `full` runs the review skill's
  full-mode protocol. `quick` loads and executes the installed
  `dm-review-quick` protocol against the feature branch; if that protocol finds
  a bounded security-sensitive path, escalate to full and receipt the effective
  mode.
- Dispatch every selected review lane through model-router using dm-review's
  role mapping. Never attach implementation or repair receipts, author-origin
  claims, family exclusions, or independence inputs to a review request.
- Keep every implementation and repair receipt produced earlier in this
  Codex-native run only in the caller-owned terminal-report set.
- Fix every retained P1/P2/P3 finding and verify repairs with affected lanes; repeat the full fan-out only if its coverage was incomplete or a repair changed a security-sensitive boundary. Reject unsupported preference-only suggestions during consolidation instead of deferring them.
- Write/read the same `todos/*-pending-*.md` and `todos/*-done-*.md` receipts that dm-review uses.

Do not report "Skill tool unavailable" in Codex when this adapter can run. That message is only valid if the session lacks both nested skill invocation and enough local access to execute the dm-review inline protocol.

**Repository verification adapter:** First distinguish an absent profile from a
declared profile. Resolve Workflow Kernel `>=0.15.0` once and use its
`plan-verification` and `run-verification` subcommands whenever the target
repository declares `.dm/verification.json` or an equivalent profile. A valid
profile remains authoritative for planning, cadence, and evidence. A malformed
or unsafe declaration stops with `human_help_required`, preserving the exact
validation evidence; never fall back.

- `chunk`: doctor, fast, and changed-package/dependent checks only.
- `revision_batch`: apply the complete finding set from one review pass, then
  perform one affected recheck.
- `execution_level`: after all sibling chunks merge, run one integrated full
  non-race pass.
- `merge_candidate`: run once for the exact candidate tree; preserve remote
  race/security/container/harness lanes explicitly.

Do not execute a full or race suite after each chunk or each individual finding
fix. With no profile, apply the same repository-native policy as the Claude
orchestrator regardless of repository type. Applicable root instructions must
designate exactly one canonical full repository-owned verification entrypoint
and may delegate to the other root instruction file. Separately scoped focused
or pre-push commands do not conflict with that designation; different canonical
full designations do conflict and block. The canonical entrypoint's directly
named checked-in target or script must exist and must not depend on missing
repository configuration. Otherwise stop narrowly with `human_help_required`
and preserve the failed policy evidence. Never invent raw Go, Docker, package,
build-tag, race, service, remote-CI, or other commands, and never synthesize or
commit `.dm/verification.json`.

Contract specimen: root `AGENTS.md` designates `make verify` as canonical full
verification and names `make conformance` as narrower and `make survivor` as
pre-push; root `CLAUDE.md` delegates to `AGENTS.md`; checked-in `Makefile` owns
`verify:`, `conformance:`, and `survivor:`. The narrower commands do not conflict,
so with no missing configuration repository-native verification is available.

When the native policy passes, record `verificationPlanner: unavailable` and
preserve the exact command and root policy-source path in existing verification
evidence where supported; add no schema. Per chunk and review batch, run only
focused checks explicitly approved by the prompt. Do not run the canonical
native command per chunk, finding, or execution level. Run it exactly once on
the integrated candidate before final review. After a repair batch, rerun it
once and bind it to the new SHA when relevant verification inputs changed or
relevance is uncertain. After an irrelevant repair, prior canonical-command
evidence may be carried forward only with bounded diff proof that no relevant
verification input changed since its tested SHA.

**Repository cleanup is host-independent.** The adapter runs the same cleanup
contract at the same points (Step 0e registry init, Step 3j per chunk, Step 5b
exact-record reconciliation + inventory) -- see
`plugins/dm-review/skills/review/references/repo-cleanup-contract.md`. Cleanup
is deterministic Git executed by the orchestrator in-process. It is never
delegated to model-router or any participant. Deleting refs is not a judgment
task, and a worker sandbox cannot be trusted to report honestly which refs
survived.

The Codex adapter does not get a weaker gate than the Claude path. If `codex_native` cannot execute the cleanup phase, that is a pipeline-blocking failure, not a degradation.
