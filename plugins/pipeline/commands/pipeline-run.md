---
name: pipeline-run
description: Execute generated prompts in worktrees with risk-tiered review gates
argument-hint: "[path to manifest.json or prompts directory]"
---

# Pipeline Run

Execute a set of generated prompts autonomously in worktrees with focused Codex
review for ordinary chunks, sensitive-path escalation, and the approved final
review mode. This is the execution engine -- it creates or reuses branches, runs
subagents, reviews, fixes, merges, and delivers a clean feature branch.

## Human-Facing Completion

Present the orchestrator's compact summary, not its durable ledgers. Start with
exactly `Done`, `Needs fixes`, or `Blocked`; state what changed or stopped, the
verification result, branch or PR, and one recommended next action. Link the
existing `receipt.md`, `final-requirements-crosscheck.md`,
`run-postmortem.md`, and detailed review when present. For blocked work, name
the exact blocker, the smallest operator action, and the preserved resumable
location. Normally stay within roughly 250 words, except for required P1/P2
findings or a real blocker.

Do not repeat `Steps Completed`, provider accounting, cleanup inventory, every
evaluation receipt, raw review output, or a default action menu in visible chat.
Those facts remain in the established artifacts. Put one recommended action
before any genuinely live alternatives.

## Input

<manifest_path> #$ARGUMENTS </manifest_path>

If the path above is empty, check for `manifest.json` files matching `plans/*/manifest.json`. If found, ask which manifest to execute. If none found, ask: "Provide a path to manifest.json, or run `/pipeline-prompts` first to generate one."

If a directory was provided instead of a manifest file, look for `manifest.json` inside it.

## Pre-Flight Checks

Before executing, verify:

1. **Manifest exists and is valid JSON**
2. **All prompt files referenced in manifest exist and resolve within `plans/`** -- reject any path that escapes the project's `plans/<feature>/prompts/` directory after canonical resolution
3. **Branch names are safe** -- `featureBranch` and all chunk IDs match `^[a-z0-9][a-z0-9\-\/]*$`
4. **Git working tree has no blocking user-file changes** -- classify dirty paths as pipeline-owned artifacts (`plans/<feature>/`, generated prompts/manifests/receipts) versus unrelated user files. Commit/gitignore/force-add pipeline-owned artifacts as directed by the orchestrator; block only on unrelated user files.
5. **Branch setup is valid** -- New manifests require `branchMode:
   create|reuse`. `create` uses `manifest.baseBranch` (default `main`) and
   requires `expectedFeatureHead` to be null/absent. `reuse` requires an exact
   lowercase 40- or 64-hex `expectedFeatureHead`; fetch
   `origin/<featureBranch>`, require its tip to match, select only that existing
   branch, and perform no initial push. Legacy manifests default to `create`
   with `branch_mode_defaulted=true`.
6. **Bypass permissions active** -- If not, warn: "Autonomous execution requires bypass permissions mode. Enable it and re-run."
7. **Workflow class is valid** -- Accept only `chore|bug|feature|hotfix|security|investigation|migration`. For a legacy manifest with no `workflowClass`, use `feature` and record `workflow_class_defaulted=true`. Never infer the class. Pass the validated value unchanged to the orchestrator, shadow translator, receipts, and metrics.
8. **Decision profile is valid** -- New manifests require exactly one closed
   object with exactly `uncertainty`, `consequence`, and `rationale`;
   uncertainty/consequence are `low|medium|high`, and rationale is a non-empty
   string. Reject extra keys, malformed/multiple values, or a conflict with the
   approved plan. Keep it separate from workflow class, risk, overlap,
   complexity, kind/executor, and routing overrides. For a legacy manifest with
   no profile, retain the current standard path and record
   `decision_profile_defaulted=true`; absence is not low/low evidence.
9. **Rendered-surface applicability is valid** -- New manifests require both
   `renderedSurface: required|not_applicable` and a non-empty
   `renderedSurfaceRationale` on every chunk. Reject one-sided, unknown, empty,
   or contradictory declarations. `not_applicable` must account for every
   UI/integration syntactic trigger and must not coexist with a served route,
   rendered output, browser interaction, visual claim, or mixed surface scope.
   Legacy manifests missing both fields default UI/Integration to `required`
   and Logic/Trivial to `not_applicable`, recording
   `rendered_surface_defaulted=true` in every receipt. This field never changes
   `kind`, provider routing, or review depth.
10. **Final review mode is valid** -- New manifests require
    `finalReviewMode: full|quick` and a non-empty `finalReviewRationale` copied
    from the approved plan. `quick` is invalid for
    `decisionProfile.consequence: high`; a security-sensitive final diff
    escalates it to full and records the escalation. Legacy manifests default
    to `full` with `final_review_mode_defaulted=true`. This field never weakens
    per-chunk sensitive review, repository/browser evidence, P1/P2 resolution,
    or cleanup.

If any check fails, report the issue and stop.

## Shadow Workflow Kernel Preflight

The Markdown manifest, this command, routing policy, orchestrator, and receipts remain authoritative. Workflow Kernel prediction, observation, comparison, and
metrics commands are shadow-only: they may not select ready nodes, block a
merge, change fallback routing, invoke cleanup, or convert a review result.
Repository-verification commands are a separate authoritative fail-closed
capability on profile-aware repositories.

Resolve `$WORKFLOW_KERNEL` -- the workflow-kernel launcher script -- once per run, following the single fail-closed resolution contract in the workflow-kernel plugin's `references/runtime-resolution.md` (launcher discovery snippet, repo-vs-cache trust boundaries, semver compatibility, symlink and scope fail-closed rules, and stable exit codes all live there; do not restate them here). Store observation and parity artifacts beneath `plans/<feature>/` and initialize every run at `.workflow-kernel/runs/<run-id>`.

The kernel has two distinct roles:

- shadow observation is optional and may record `shadow unavailable` without
  changing the canonical workflow; and
- repository verification is authoritative on profile-aware repositories.
  Missing/incompatible runtime, a stale/invalid exact-ref plan, or a required
  pending/failed lane stops with
  `human_help_required`. Never downgrade this verification failure to shadow
  unavailability.

Invoke only stable launcher subcommands documented by the kernel; inline Python source is forbidden. Observation, comparison, and metrics are side-effect free. Interpret stable exits exactly: `0` success, `2` invalid input/schema, `3` unsafe or blocked plan or required repository verification failed/pending, `4` runtime unavailable/incompatible, `5` parity gap, and `6` write/state conflict. No non-zero exit is translated into authoritative success; shadow failures preserve the canonical result, while cleanup blocks remain honestly blocked.

The canonical shadow inputs are `plans/<feature>/manifest.json` plus the cumulative ordered redacted array `plans/<feature>/authoritative-receipts.json`. Produce the independent prediction before corresponding authoritative actions and seal it first:

```text
"$WORKFLOW_KERNEL" init .workflow-kernel/runs/<run-id> --run-id <run-id> --mode shadow --occurred-at <timezone-aware-ISO-8601>
"$WORKFLOW_KERNEL" bind-prediction --type pipeline --manifest plans/<feature>/manifest.json --prediction-receipts plans/<feature>/independent-prediction-receipts.json --state-dir plans/<feature>
```

After the canonical `run.started` transition and before the first builder
dispatch, generate `plans/<feature>/verification-contract.json` only from the
approved requirements and final acceptance criteria. Resolve persona/browser
case IDs against authoritative project declarations for chunks whose
`renderedSurface` is `required` and block unresolved IDs. When at least one
chunk is required, materialize and bind the authoritative verification profile
for that union. When every chunk is `not_applicable`, use null profile
ID/digest, empty arrays, no profile artifact/flag, and preserve the validated
rationales in manifest and receipts. Never fabricate cases. Validate and bind
the initial contract exactly once, adding `--verification-profile
plans/<feature>/verification-profile.json` only for the required-surface form:

```text
"$WORKFLOW_KERNEL" bind-verification-contract --state-dir .workflow-kernel/runs/<run-id> --contract plans/<feature>/verification-contract.json > plans/<feature>/verification-contract-binding.json
```

The binding receipt's `contract_digest` and `revision` identify the contract for dispatch.
Every builder dispatch and completion must name those exact current values; a
missing or mismatched claim is deterministic validation failure, never success.
The kernel seals/validates this artifact but never schedules a builder or gate.

Append every later authoritative receipt to the cumulative ledger. Observe only
at the `all-chunks-complete` checkpoint before the approved final review and at the
terminal checkpoint. Each observation uses:

```text
"$WORKFLOW_KERNEL" observe-pipeline --manifest plans/<feature>/manifest.json --receipts plans/<feature>/authoritative-receipts.json --state-dir plans/<feature>
```

## Codex Native Execution Adapter

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

**Protocol source:** Read `plugins/pipeline/agents/workflow/execution-orchestrator.md` as the execution contract. The current Codex agent acts as the orchestrator in-process because Codex does not expose Claude's generic agent runner. All orchestrator steps remain mandatory: branch create/reuse semantics, worktree isolation or the documented `sequential-on-branch` isolation strategy (recorded as `isolationStrategy`, never as `executionMode`) for container-mounted test harnesses, input guardrails, chunk dispatch, validation, evaluation gates, merge-back, the approved final review mode, memory capture, cleanup, and summary.

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

- For ordinary non-sensitive chunks, run one focused read-only Codex review against the chunk diff and allow at most one P1/P2 repair/recheck pass. Preserve pending/done todo receipts.
- For sensitive-path chunks, run the full inline `plugins/dm-review/skills/review/SKILL.md` protocol against the chunk worktree, with at most two passes.
- For the final gate, read `finalReviewMode`. `full` runs the review skill's
  full-mode protocol. `quick` loads and executes the installed
  `dm-review-quick` protocol against the feature branch; if that protocol finds
  a bounded security-sensitive path, escalate to full and receipt the effective
  mode.
- Use `multi_agent_v1.spawn_agent` for the focused Codex reviewer or for review agents selected by the chosen dm-review protocol when available.
- Fix P1/P2 findings and retain complete P3 advisory evidence. Verify repairs with affected lanes; repeat the full fan-out only if its coverage was incomplete or a repair changed a security-sensitive boundary.
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

## Rail-Exhaustion Ask Gate

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

## After Execution

Immediately after the execution-orchestrator returns and before presenting its
human summary, consume the single `Memory observation handoff:` field from the
agent result. Keep the raw observation internal. Validate that it is the dated
Pipeline format for exact entity `DepotPlugin:pipeline` and is under 300
characters, then use the caller's ai-memory capability to:

1. `search_entities` for `DepotPlugin:pipeline`; create it as type `Tool` with
   `add_entity` only when missing.
2. Read the entity and check its same-day observations for the exact handoff.
3. If absent, call `add_observation`, then `save`.

Record exactly one outcome: `written`, `already-present`, or
`skipped -- <reason>`. Memory capture is non-blocking, but never silent. Append
`Memory capture: <outcome>` to `plans/<feature>/receipt.md` and retain the same
outcome in the existing internal summary evidence before presentation. Do not show the raw handoff in ordinary human-facing chat.

After the authoritative terminal receipt is appended to the cumulative receipt array, run exactly:

```text
"$WORKFLOW_KERNEL" observe-pipeline --manifest plans/<feature>/manifest.json --receipts plans/<feature>/authoritative-receipts.json --state-dir plans/<feature>
"$WORKFLOW_KERNEL" compare --state-dir plans/<feature> --authoritative-receipts plans/<feature>/authoritative-receipts.json --output plans/<feature>/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events plans/<feature>/authoritative-receipts.json --output plans/<feature>/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events plans/<feature>/authoritative-receipts.json --output plans/<feature>/run-cost-summary.json --receipt plans/<feature>/receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> plans/<feature>/receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> plans/<feature>/receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file left there by an earlier run, writes a schema-bound `run-cost-summary.json` beside that run's own `authoritative-receipts.json`, and appends exactly one inventory line to the run receipt naming what actually happened -- the artifact path on success, or `run-cost-summary: skipped (<reason>)` on any internal failure. It exits 0 for every measurement outcome, because the artifact is observation-only: it never gates, blocks, waives, or alters a review, lane, or phase outcome, and its absence never fails one. It exits 6 in exactly one case -- the receipt path was accepted but the write failed -- because a receipt naming neither an artifact nor a skip is the silence the failure-modes checklist forbids, and reporting that it could not report is the command's last obligation. A *refused* receipt path is the deliberate exception and still exits 0: exiting non-zero would fire the caller's `||` fallback, which appends through the very symlink the command just rejected, so the refusal is reported on stderr alone. Exit 2 is the other non-zero outcome and means the invocation was wrong -- bad flags, or `--output` and `--receipt` pointing at one path -- so nothing ran and nothing is recorded. The `||` fallback beside it must be status-aware: exit 6 triggers one final append of `skipped (receipt-write-failed)`, exit 2 is explicitly propagated as an invalid invocation, and every other non-zero status appends `skipped (kernel-unresolvable)`. If the final append also fails, its non-zero status remains visible instead of being erased. Receipt paths are fixed for a given receipt directory, so two concurrent runs sharing one directory overwrite each other: serialize them, or give each run its own directory. The command refuses a symlinked artifact or receipt path, and when the *receipt* path is the one refused it records nothing rather than writing the refusal through the symlink it just rejected. The caller resolves a coherent installed-plugin bundle and passes its model-matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; the kernel validates both bundle containment and matrix structure without owning a provider dependency. An unreadable or invalid matrix emits one stderr line, skips imputation, and never fails this observation-only emission. It does not inspect the working tree: the caller passes `--dirty-state`, and that flag is the artifact's only source of that fact. Populate the events it reads through `record-attempt` as each lane settles; that one atomic call appends the lane outcome and exactly one `attempt_usage` row under the same lock. Pass the OpenRouter wrapper receipt when present, otherwise pass the exact Codex/Claude input files for deterministic byte measurement; when neither exists, the paired row explicitly records `attempt_unmeasured`. Do not also call a standalone translator with `--append-to` for that attempt, because doing both double-counts it. A `lanes: 0` artifact after a run that executed lanes means this boundary is not wired; a structurally valid artifact with zero measured lanes proves the command ran, never that lanes were measured. Full command reference, when the workflow-kernel plugin is installed alongside this one: `plugins/workflow-kernel/skills/workflow-kernel/references/cli-measurement-commands.md`; if that path is not readable from this cache, the flags named above are the complete required set.

`bind-prediction` runs before corresponding authoritative actions, atomically seals the source, translated events, event digest, and RunSpec context, and appends exact binding authority to the canonical lifecycle ledger before `run.started`. `observe-pipeline` runs only after authoritative receipts exist and requires that ordered authority plus bound `pipeline-shadow-prediction.json`; direct comparison rechecks the same authority, and byte-identical predicted and authoritative receipts are valid only with the pre-start binding. It writes a separate `authoritative_observation` and never creates or changes the prediction. Without matching independent prediction evidence, observation and comparison fail closed. Keep the source and bound artifact until comparison completes. Write the shadow report and reliability metrics without changing the merge recommendation, cleanup disposition, or provider result. Never auto-delete the repository-lifetime `.workflow-kernel/repository-scope.json`; retain the terminal run directory or a durable tombstone until fresh exact-scope Docker inventory proves zero exact-run objects and no uninspectable matches, regardless of parity `match`.

Present the compact summary from the orchestrator. If an operator decision is
still needed, ask for it after `Recommended next action`; mention additional
choices only when they are genuinely live. Do not emit a standing five-option
menu.

If feedback given, suggest re-running `/pipeline-prompts` with the feedback to generate revision prompts, then `/pipeline-run` again on the same feature branch.
