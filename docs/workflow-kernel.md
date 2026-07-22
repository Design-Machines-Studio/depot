# Workflow Kernel

Workflow Kernel is Depot's neutral, dependency-free mechanics plugin for
durable workflow state, replay, shadow comparison, verification evidence, and
owned-resource cleanup. Pipeline and dm-review depend on it, while the kernel
depends on no Depot plugin. Domain judgment, routing, review findings, merge
decisions, and cleanup policy remain in their canonical Markdown workflows.

Version 0.3.0 retains observation-only shadow comparison and adds bounded
authoritative mechanics for behavioral-contract binding and revision,
validation-retry decisions, canonical review-contribution export, and guarded
owned-resource cleanup. Those commands are authoritative only where the
calling Markdown workflow explicitly delegates the mechanic; the kernel does
not choose providers, findings, merge disposition, or cleanup policy.

## Runtime and state layout

Invoke the kernel through `workflow-kernel-launcher.sh` (in the plugin's
`references/` directory). The launcher resolves the runtime from the canonical
Depot checkout or a compatible same-major `>=0.3.0` entry under the Claude
cache, then the Codex cache, ordered by parsed semver (never mtime). Version
0.3.0 is the minimum because authoritative consumers require the behavioral
contract, validation-retry, and review-contribution command surface. The
launcher verifies Python 3.12+, sets the module path, and execs the CLI. Never
discover the runtime from the downstream project, `PATH`, or a symlink escape.
The full consumer-facing contract is `references/runtime-resolution.md`; in
the templates below, `"$WORKFLOW_KERNEL"` is the resolved launcher path.

Each repository owns a random, durable `.workflow-kernel/repository-scope.json`.
Each run uses `.workflow-kernel/runs/<run-id>/` and includes:

- `events.jsonl`: append-only, sequence-checked event ledger;
- `run-state.json`: replay-derived materialized state;
- `run-state.json.lease`: advisory run lease;
- authoritative and shadow receipt references;
- the sealed prediction and authoritative observation;
- `shadow-report.json` and `metrics.json`;
- persona/browser verification evidence; and
- resource registry, cleanup plans, outcomes, and reconciliation receipts.

The materialization is a cache of the ledger, never a replacement for it.
After interruption, replay valid events and replace stale materialized state
under the run lease. A truncated final JSONL record can be reported with
`validate --recovery`; a corrupt middle record, sequence gap, stale revision,
or unknown major schema version fails closed. Minor-compatible readers must
still reject unknown fields rather than guess their meaning.

## CLI

For local development:

```sh
export PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references
python3 -m workflow_kernel --help
```

Use JSON files for file-taking structured inputs. The `append --event` argument
is the one exception: it accepts one inline JSON object. The examples below are
safe templates; replace placeholders only with run-owned paths and exact IDs.

### Base state

```sh
"$WORKFLOW_KERNEL" init .workflow-kernel/runs/RUN --run-id RUN --mode shadow --occurred-at 2026-01-01T00:00:00Z
"$WORKFLOW_KERNEL" validate .workflow-kernel/runs/RUN
"$WORKFLOW_KERNEL" validate .workflow-kernel/runs/RUN --recovery
"$WORKFLOW_KERNEL" append .workflow-kernel/runs/RUN --event '{"schema_version":1,"sequence":1,"run_id":"RUN","node_id":null,"kind":"run.started","occurred_at":"2026-01-01T00:00:01Z","payload":{}}'
"$WORKFLOW_KERNEL" replay .workflow-kernel/runs/RUN
"$WORKFLOW_KERNEL" status .workflow-kernel/runs/RUN
```

`init` defaults to `shadow`. Never initialize a production run in another mode
unless a separately approved promotion has made that authority available.

### Shadow observation and comparison

Seal an independent prediction before the first authoritative action, observe
only after canonical receipts exist, then compare:

```sh
"$WORKFLOW_KERNEL" bind-prediction --type pipeline --manifest manifest.json --prediction-receipts predicted.json --state-dir plans/feature
"$WORKFLOW_KERNEL" bind-prediction --type review --request request.json --prediction-receipts predicted.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" observe-pipeline --manifest manifest.json --receipts authoritative.json --state-dir plans/feature
"$WORKFLOW_KERNEL" export-review-contributions --request request.json --decisions synthesis-decisions.json --raw-findings raw-finding-inventory.json --lane-receipts review-lane-receipts.json --receipts authoritative.json --state-dir .claude/ux-review/workflow-kernel --output authoritative.json
"$WORKFLOW_KERNEL" observe-review --request request.json --receipts authoritative.json --state-dir .claude/ux-review/workflow-kernel
"$WORKFLOW_KERNEL" compare --state-dir plans/feature --authoritative-receipts authoritative.json --output shadow-report.json
"$WORKFLOW_KERNEL" metrics --events authoritative.json --output metrics.json
```

For dm-review, contribution export is part of consolidation and must run before
`observe-review`. It validates and content-addresses the exact synthesis, raw
finding, and lane-receipt inputs before adding both the per-finding contribution
events and a coverage receipt. The zero-finding case still emits coverage.
Review observation reloads the sealed inputs and fails closed when coverage is
absent, incomplete, or no longer reconstructs the contribution segment.

Shadow observation never selects a node, changes an executor, waives a finding,
blocks or approves a merge, or invokes cleanup. Disable it by omitting the
observation step. If runtime resolution or compatibility fails, record
`shadow unavailable` with the safe reason and continue the Markdown-authoritative
workflow. Do not delete event history when rolling back to Markdown-only mode.

Comparison distinguishes semantic match, explained host difference, missing
authoritative evidence, unexpected transition, prediction gap, and unsafe to
promote. Metrics aggregate observed reliability and produce proposal-only
routing recommendations; they never mutate routing policy.

### Behavioral contracts and validation retry

Pipeline binds the approved behavioral contract after `run.started` and before
the first implementation dispatch. The state directory is the canonical
`.workflow-kernel/runs/<run-id>` directory; the contract input must belong to
the same immutable repository scope.

```sh
"$WORKFLOW_KERNEL" bind-verification-contract --state-dir .workflow-kernel/runs/RUN --contract plans/feature/verification-contract.json --verification-profile plans/feature/verification-profile.json
"$WORKFLOW_KERNEL" authorize-verification-contract-revision --state-dir .workflow-kernel/runs/RUN --approval plans/feature/verification-contract-approval.json
"$WORKFLOW_KERNEL" revise-verification-contract --state-dir .workflow-kernel/runs/RUN --contract plans/feature/verification-contract.json --verification-profile plans/feature/verification-profile.json
"$WORKFLOW_KERNEL" decide-validation-retry --state-dir .workflow-kernel/runs/RUN --reason deterministic_validation_failure --signature FAILURE-SIGNATURE
```

`bind-verification-contract` accepts only an initial revision, validates it,
stores a content-addressed artifact under the run, and appends a
`verification_contract_bound` evidence event. Retrying the exact same binding
is idempotent. A different initial contract, foreign repository scope, unsafe
path, or invalid contract fails without replacing the current binding.

`revise-verification-contract` validates the complete append-only chain, the
previous digest, and the next revision before storing the new artifact and
appending `verification_contract_revised`. Obligation weakening also requires
validated, content-addressed human-approval evidence bound to the actor,
decision, normalized UTC timestamp, fresh host-issued nonce, run ID, and exact
prior/candidate contract digests. The dedicated authorization command records
that coordinator-owned event before revision; self-authored JSON passed only to
the revision command has no authority.
Selected persona/browser case IDs must exactly match the required cases in the
bound authoritative verification profile. A failed revision leaves the prior contract
authoritative. Downstream validation feedback and accepted builder output must
name the latest bound digest and revision.

Fresh Pipeline runs always materialize and bind the authoritative profile before
the contract. A missing declaration tree is represented by a non-null
`not_declared` profile with empty case arrays. Null profile ID/digest and omitted
`--verification-profile` remain valid only for legacy/no-profile contracts; if
the profile is null, both selected-case arrays must be empty.

`decide-validation-retry` reconstructs counts and signatures from the
authoritative lifecycle ledger, decides under the run lease, and atomically
appends and publishes the decision. It never trusts a caller-owned attempt
ledger and does not dispatch a builder. Pipeline resumes the same builder
only with proven session continuity, otherwise records an explicit replacement,
and stops with `human_help_required` when the budget is exhausted or an
identical signature has converged.

### Exit status and output

Successful commands return `0` and write their JSON result to standard output.
Failures write one redacted, machine-readable kernel error to standard error.
Callers must branch on the exit status and must not infer success from a partial
or previously existing output file.

| Status | Meaning | Caller action |
|---:|---|---|
| `0` | The command completed and its output is authoritative for that invocation. | Validate and retain the emitted receipt or artifact. |
| `2` | Invalid arguments, schema, state, path, or other fail-closed input/operation error. | Preserve evidence and correct the input; do not retry unchanged. |
| `3` | A creation or cleanup plan/result is unsafe or unmanaged. | Retain the resource and follow the reported guarded recovery path. |
| `4` | The compatible kernel runtime is unavailable. | Record `shadow unavailable` where permitted; never bypass an authoritative gate. |
| `5` | Shadow comparison found a parity or evidence gap. | Keep authoritative workflow results unchanged and investigate the report. |
| `6` | Sequence, revision, lease, registration, or guarded-authority conflict. | Re-read fresh state and reconcile ownership before retrying. |

The contract and retry commands return `0` or a fail-closed `2`/`6` result;
they never use a nonzero status as a policy decision. In particular, a valid
retry decision such as `stop` is successful JSON output with status `0`.

### Docker creation and cleanup

Plan creation before invoking Docker and register the exact before/after
inventory afterward:

```sh
"$WORKFLOW_KERNEL" plan-create --state-dir plans/feature --run-id RUN --node-id NODE --lifecycle chunk --cleanup-policy stop-remove --argv-json create-argv.json --dependent-node-ids-json dependents.json --output creation-plan.json
"$WORKFLOW_KERNEL" plan-compose --state-dir plans/feature --run-id RUN --node-id NODE --lifecycle run --cleanup-policy stop-remove --argv-json compose-argv.json --dependent-node-ids-json dependents.json --output creation-plan.json
"$WORKFLOW_KERNEL" record-create --state-dir plans/feature --plan creation-plan.json --result command-result.json --before-inventory before.json --after-inventory after.json
```

For per-chunk cleanup, use fresh authoritative node statuses and inventory. The
guarded execute command is the only authorization boundary; never execute argv
returned by a plan separately.

```sh
"$WORKFLOW_KERNEL" plan-cleanup --state-dir plans/feature --run-id RUN --node-id NODE --node-statuses node-statuses.json --output cleanup-plan.json
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir plans/feature --plan cleanup-plan.json --outcomes outcomes.json --output next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir plans/feature --plan cleanup-plan.json --step-index 0 --inventory inventory.json --node-statuses node-statuses.json --outcomes outcomes.json --output outcome-0.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir plans/feature --plan cleanup-plan.json --outcomes outcomes.json
```

At every terminal path -- success, failure, blocked, cancelled, or interrupted -- run
reconciliation before artifact and Git cleanup:

```sh
"$WORKFLOW_KERNEL" plan-reconcile --state-dir plans/feature --run-id RUN --ttl-hours 24 --node-statuses terminal-statuses.json --output terminal-plans.json
```

`plan-reconcile` writes independently sealed current-run and stale-sweep plan
artifacts. Process each through `next-cleanup-step`, `execute-cleanup-step`, and
`record-cleanup` with separate outcomes. A second pass is idempotent.

Resources require exact repository-scope, run, node, lifecycle, and policy
labels plus registry evidence. Chunk resources are removed after their declared
dependents finish. Run-shared resources remain until terminal reconciliation.
Volumes additionally require inspectable exact identity, safe mount/in-use
state, and TTL evidence. Foreign, contradictory, running, in-use, uninspectable,
or partially registered resources are retained and reported. Never use
`docker system prune`, unfiltered prune, negative-label filters, wildcard/name
ownership, or shell-built cleanup commands.

### Git worktree and branch cleanup

Git cleanup uses the pipeline ref registry, not Docker labels. Capture
`git worktree list --porcelain` and `git branch --list` before the run, then
register every created worktree, chunk branch, and feature branch at creation
with its exact path/ref, kind, base, run namespace, and lifecycle. Never infer
ownership afterward from a broad glob or delete a ref outside the registered
`.worktrees/pipeline/<feature>/` and `pipeline/<feature>/*` namespace.

After a chunk is integrated, remove its worktree only when `git status` is
readable and clean. Remove the worktree before its branch. Delete a chunk branch
with `git branch -d` when ancestry proves it is merged into its declared target;
use `-D` only when the registry proves the branch's unique commits were merged
to a different target. Dirty, unreadable, checked-out, unmerged, or ambiguously
owned refs are retained and reported as blocked with the recovery command.

At terminal reconciliation, parse `git worktree list --porcelain` field-wise,
reconcile every registered ref and namespace-bounded interrupted orphan, then
run `git worktree prune`. Record before/after inventories and every
`deleted|kept|blocked` disposition. The feature branch is always retained by
the pipeline; even external merge proof changes its receipt to merged/kept and
never authorizes automatic feature-branch deletion.

## Workflow and verification contracts

The supported workflow classes are `chore`, `bug`, `feature`, `hotfix`,
`security`, `investigation`, and `migration`. Legacy missing class data defaults
explicitly to `feature` with `workflow_class_defaulted=true`; it is never
inferred. Class policy defines legal transitions, retry reasons, required gates,
isolation, executor capability, and whether builder resumption is permitted.

Discover persona declarations from supported Assembly-shaped project layouts.
Validate every required case and report absent declarations honestly as
`not_declared`. Keep secrets out of state and receipts: redact credentials,
cookies, tokens, DSNs, environment values, and secret-bearing fixture fields.

For a missing browser tool, server, authentication fixture, route binding, or
verification profile:

1. preserve the failed attempt;
2. quit the primary browser process/session;
3. launch a demonstrably fresh primary profile and retry once;
4. try a genuinely different configured browser engine; and
5. stop with `human_help_required`, exact missing case IDs, and all attempts if
   the lane still cannot complete.

Curl proves reachability only; it never satisfies a browser evidence gate.
Application assertion failures are findings, not recovery triggers.

## Promotion

Promotion is an evidence decision, not a mode flag.

- `shadow -> enforce_available` requires zero unexplained representative
  receipt gaps; passing illegal-transition and terminal-cleanup scenarios;
  Claude, Codex, and generic host compatibility; complete persona and browser
  recovery scenarios; and unchanged provider security boundaries.
- `enforce_available -> native_available` retains every prior criterion and
  adds successful real shadow runs for supported hosts, interruption replay,
  builder resume/non-resume evidence, and Git/Docker success, failure, and
  blocking cleanup evidence.
- `native_available -> native_default` is forbidden in this epic and returns
  `separate_human_approval_required`.

Fixture evidence cannot masquerade as real-run evidence. Version 0.3.0 keeps
`shadow` as the `init` default while exposing only the bounded authoritative
commands named above. A caller must explicitly select an approved mode and
delegate each mechanic; no release promotion makes the kernel an autonomous
workflow orchestrator.

## Troubleshooting

- **Corrupt state:** run `validate`; use `--recovery` only for a truncated final
  record. Preserve evidence and stop on middle-record corruption or gaps.
- **Stale materialization:** acquire the run lease and run `replay`; never edit
  `run-state.json` by hand.
- **Lease conflict:** another writer is active. Stop and retry after it exits;
  do not remove the lock file to bypass ownership.
- **Blocked cleanup:** retain the resource, receipt, plan, fresh inventory, and
  exact follow-up reason. Resolve missing proof rather than broadening filters.
- **Missing browser tools:** execute the full recovery ladder, then ask for
  human help. Do not downgrade the required lane to skipped.
- **Unavailable runtime:** keep Markdown authority, record the safe resolution
  failure, and retain authoritative receipts. Event history remains intact for
  later replay and comparison.
- **Rollback:** disable shadow observation and continue with canonical Markdown
  workflows. Do not delete `events.jsonl`, terminal receipts, repository scope,
  or unresolved cleanup evidence.

Run `./tools/validate-workflow-kernel.py` for the deterministic offline
behavioral suite. By default it writes concise PASS/FAIL output and the
deterministic fixture-only receipt at
`plans/ai-developer-workflow-kernel/receipts/06-workflow-kernel-release-evidence.json`.
Use `--evidence-output plans/<feature>/workflow-kernel-evidence.json` to
override that path. The receipt explicitly sets `real_run_evidence` false and
cannot satisfy native promotion. Run `./tools/validate-composition.sh --all`
for the full Depot release gate.
