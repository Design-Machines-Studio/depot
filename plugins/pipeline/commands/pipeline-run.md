---
name: pipeline-run
description: Execute generated prompts in worktrees with risk-tiered review gates
argument-hint: "[path to manifest.json or prompts directory]"
---

# Pipeline Run

Execute a set of generated prompts autonomously in worktrees with focused role
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
location. Normally stay within roughly 250 words, except for required P1/P2/P3
findings or a real blocker.

Do not repeat `Steps Completed`, concrete routing accounting, cleanup inventory, every
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
   complexity, kind/role fields, and routing overrides. For a legacy manifest with
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
   `kind`, role routing, or review depth.
10. **Role request is valid** -- New manifests pass
    `plugins/pipeline/references/validate-role-manifest.sh`; they contain
    `executorRole`, `executorCapabilities`, and `executorEffort`, and contain no
    provider/model/transport selector. Approved legacy manifests are translated
    in memory with `translate-legacy-executor.sh`, receipt the translation, and
    remain byte-identical on disk.
11. **Final review mode is valid** -- New manifests require
    `finalReviewMode: full|quick` and a non-empty `finalReviewRationale` copied
    from the approved plan. `quick` is invalid for
    `decisionProfile.consequence: high`; a security-sensitive final diff
    escalates it to full and records the escalation. Legacy manifests default
    to `full` with `final_review_mode_defaulted=true`. This field never weakens
    per-chunk sensitive review, repository/browser evidence, P1/P2/P3 resolution,
    or cleanup.

Resolve and read Workflow Kernel's `exact-owned-cleanup.md` before creating any
run directory, worktree, temporary repository/cache, or Docker resource. Use
one unique run ID and one exact-owned disposable root for this invocation.
Pre-flight abort before execution finishes it with `review-aborted`; success,
failure, interruption, resume, and retry use the shared terminal sequence.

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

When an owner-approved retained ledger has the one historical noncanonical
`browser_recovery` shape, load
`plugins/pipeline/references/legacy-browser-reconciliation.md` and use its
canonical writer. Never rewrite or skip the target, and never apply the command
to any other invalid row.

Append every later authoritative receipt to the cumulative ledger. Observe only
at the `all-chunks-complete` checkpoint before the approved final review and at the
terminal checkpoint. Each observation uses:

```text
"$WORKFLOW_KERNEL" observe-pipeline --manifest plans/<feature>/manifest.json --receipts plans/<feature>/authoritative-receipts.json --state-dir plans/<feature>
```

## Codex Native Execution Adapter

When the run executes from a Codex host (no Claude `Agent` tool and no nested `Skill(...)` calls), load `plugins/pipeline/references/codex-native-execution-adapter.md` and follow it exactly, recording `executionMode: codex_native`. A Claude-hosted run does not load it and keeps `executionMode: full_cli`. (`claude_native` is a kernel mechanism, not a host execution mode; the closed vocabulary is `full_cli | codex_native | manual_walkthrough | generic | generic_host`.)

## Role-Unavailable Scheduling Gate

When model-router returns a closed `unavailable` disposition for a required
role, load `plugins/pipeline/references/rail-exhaustion-ask-gate.md`. This gate
schedules wait or park only after automatic role fallback is exhausted; it
never selects, approves, or reveals concrete routing. Do not load it while an
eligible candidate remains.

## Process

Once the pre-flight checks pass and the shadow-kernel preflight is initialized:

1. Read the manifest.
2. If running in Codex with `multi_agent_v1.spawn_agent`, run the **Codex Native Execution Adapter** above.
3. Otherwise, launch the execution-orchestrator agent from `plugins/pipeline/agents/workflow/execution-orchestrator.md`.
4. Pass the manifest path, prompts directory, feature branch name, and
   `terminalModelReportOwner: pipeline-run`.
5. The orchestrator handles everything autonomously:
   - Branch creation or exact-head existing-branch reuse
   - Exact registered worktree creation per chunk under the unique run ID
   - Subagent dispatch with inlined prompt content
   - focused Codex review after ordinary chunks; full review for sensitive paths
   - Merge back to feature branch
   - Approved final dm-review mode, with security escalation
   - preparation of one compact memory observation for the capable caller
   - cumulative shadow observation after all chunks and at terminal, when the trusted runtime is available
6. Apply the caller-side memory handoff below.
7. Present the execution summary.

## After Execution

Immediately after the execution-orchestrator returns and before presenting its
human summary, consume the single optional `Memory observation handoff:` field
from the agent result and keep the raw observation internal. Determine ai-memory
availability from the callable-tool inventory or tool search without making a
probe call; capability availability is the complete rule, never identity,
environment, or repository heuristics. When those tools are callable, load
`plugins/pipeline/references/run-memory-enrichment.md` and follow it. When they
are absent, omit the write and every receipt or summary mention silently, do not
mark execution or delivery incomplete, and do not load that file.

After the authoritative terminal receipt is appended to the cumulative receipt array, run exactly:

```text
"$WORKFLOW_KERNEL" observe-pipeline --manifest plans/<feature>/manifest.json --receipts plans/<feature>/authoritative-receipts.json --state-dir plans/<feature>
"$WORKFLOW_KERNEL" compare --state-dir plans/<feature> --authoritative-receipts plans/<feature>/authoritative-receipts.json --output plans/<feature>/shadow-report.json
"$WORKFLOW_KERNEL" metrics --events plans/<feature>/authoritative-receipts.json --output plans/<feature>/metrics.json
if MODEL_MATRIX_ASSET=$("$WORKFLOW_KERNEL" resolve-plugin-asset --plugin openrouter --asset skills/openrouter-delegate/references/model-matrix.json --minimum-version 1.11.0); then :; else MODEL_MATRIX_ASSET=""; fi
"$WORKFLOW_KERNEL" emit-cost-summary --events plans/<feature>/authoritative-receipts.json --output plans/<feature>/run-cost-summary.json --receipt plans/<feature>/receipt.md --matrix "$MODEL_MATRIX_ASSET" --repository-commit "$(git rev-parse HEAD)" $(test -n "$(git status --porcelain)" && echo --dirty-state) \
  || { s=$?; if [ "$s" -eq 6 ]; then printf 'run-cost-summary: skipped (receipt-write-failed)\n' >> plans/<feature>/receipt.md; elif [ "$s" -eq 2 ]; then exit "$s"; else printf 'run-cost-summary: skipped (kernel-unresolvable)\n' >> plans/<feature>/receipt.md; fi; }
```

The `emit-cost-summary` command is one transaction: it owns the artifact path, clears any stale file, writes a schema-bound `run-cost-summary.json` beside that run's `authoritative-receipts.json`, and appends exactly one receipt line -- the artifact path, or `run-cost-summary: skipped (<reason>)` on any internal failure. It is observation-only: it exits 0 for every measurement outcome, never gates or alters a review, lane, or phase outcome, and its absence never fails one. Exit 6 (receipt write failed after acceptance) appends `skipped (receipt-write-failed)` through the status-aware `||` fallback; exit 2 is an invalid invocation and propagates; any other non-zero status appends `skipped (kernel-unresolvable)`, and a failing final append keeps its own status visible. A refused symlinked receipt path still exits 0 and reports on stderr alone -- a non-zero exit would append through the symlink just refused. Receipt paths are fixed per directory, so concurrent runs sharing one directory overwrite each other: use the invocation's exact-owned root or serialize callers that intentionally share a documented deliverable directory. Pass a coherent installed bundle's matrix asset as `--matrix "$MODEL_MATRIX_ASSET"`; an unreadable or invalid matrix emits one stderr line, skips imputation, and never fails the emission. Populate events with `record-attempt` as each lane settles -- a standalone `--append-to` translator double-counts the attempt, and `lanes: 0` after a run that executed lanes means this boundary is not wired. Full flags: `cli-measurement-commands.md`; otherwise the flags named here are the complete required set.

Consume the orchestrator's terminal observation source handoff before cleaning
its private inputs. Materialize `plans/<feature>/observation-index-input.json`
under Workflow Kernel's `observation-index-contract.md`, with explicit
`producer.name: pipeline` and `producer.source_digest` bound to the terminal
receipt source whose `role` is `producer`. Bind the manifest, lifecycle,
authoritative receipts, attempts, metrics, cost summary, verification,
reconciliation, installed-bundle resolutions, and private router/provider
evidence by reference, digest, type, size, provenance, and freshness. Missing
facts stay unavailable; raw prompts, policies, transcripts, provider payloads,
and artifact bytes stay out of the document.

Invoke exactly once:

```text
"$WORKFLOW_KERNEL" emit-observation-index --input plans/<feature>/observation-index-input.json --output plans/<feature>/observation-index-<run-id>.json
```

Append `observation-index: plans/<feature>/observation-index-<run-id>.json
(<canonical digest>)` to `receipt.md`, or one closed
`observation-index: unavailable (invalid-or-unsafe-input|runtime-unavailable|write-conflict|emission-failed)`
line. Observation failure preserves the authoritative Pipeline outcome and can
neither make an incomplete run clean nor make a successful run fail. A stale
output is a refusal, not evidence from this invocation.

`bind-prediction` runs before corresponding authoritative actions, atomically seals the source, translated events, event digest, and RunSpec context, and appends exact binding authority to the canonical lifecycle ledger before `run.started`. `observe-pipeline` runs only after authoritative receipts exist and requires that ordered authority plus bound `pipeline-shadow-prediction.json`; direct comparison rechecks the same authority, and byte-identical predicted and authoritative receipts are valid only with the pre-start binding. It writes a separate `authoritative_observation` and never creates or changes the prediction. Without matching independent prediction evidence, observation and comparison fail closed. Keep the source and bound artifact until comparison completes. Write the compact shadow report and reliability metrics without changing the merge recommendation, cleanup disposition, or provider result. Never auto-delete the repository-lifetime `.workflow-kernel/repository-scope.json`; after fresh exact-scope Docker inventory proves zero exact-run objects, success removes terminal run state and disposable roots. Failure/interruption may retain only one bounded diagnostic root with the four required terminal fields.

Present the compact summary from the orchestrator. If an operator decision is
still needed, ask for it after `Recommended next action`; mention additional
choices only when they are genuinely live. Do not emit a standing five-option
menu.

The execution-orchestrator owns this invocation's terminal model report. It
loads model-router's `terminal-report-contract.md` only after final review,
repairs, requirements checks, and merge policy have settled; renders
`model-cost-report.json` and `.md` beside `run-cost-summary.json` before private
receipt cleanup; completes cleanup; and appends the compact Markdown or one
closed unavailable line after the human summary. Do not render it again and do
not dispatch any model after it is generated or displayed.

Any retained diagnostic report must name the one exact root, why it was kept,
what compact evidence it contains, and the exact safe cleanup command. Raw
review/pipeline output, temporary repositories, and caches are disposable.

If feedback given, suggest re-running `/pipeline-prompts` with the feedback to generate revision prompts, then `/pipeline-run` again on the same feature branch.
