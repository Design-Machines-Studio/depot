# Workflow Kernel

Workflow Kernel is Depot's neutral, dependency-free mechanics plugin for
durable workflow state, replay, shadow comparison, verification evidence, and
owned-resource cleanup. Pipeline and dm-review depend on it, while the kernel
depends on no Depot plugin. Domain judgment, routing, review findings, merge
decisions, and cleanup policy remain in their canonical Markdown workflows.

Version 0.1.0 ships observation-only shadow mode. It does not make the Python
runtime authoritative.

## Runtime and state layout

Resolve the runtime from the canonical Depot checkout or a compatible
`workflow-kernel/0.1.x` entry under the Claude cache, then the Codex cache. Do
not discover it from the downstream project, `PATH`, or a symlink escape.

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
python3 -m workflow_kernel init .workflow-kernel/runs/RUN --run-id RUN --mode shadow --occurred-at 2026-01-01T00:00:00Z
python3 -m workflow_kernel validate .workflow-kernel/runs/RUN
python3 -m workflow_kernel validate .workflow-kernel/runs/RUN --recovery
python3 -m workflow_kernel append .workflow-kernel/runs/RUN --event '{"schema_version":1,"sequence":1,"run_id":"RUN","node_id":null,"kind":"run.started","occurred_at":"2026-01-01T00:00:01Z","payload":{}}'
python3 -m workflow_kernel replay .workflow-kernel/runs/RUN
python3 -m workflow_kernel status .workflow-kernel/runs/RUN
```

`init` defaults to `shadow`. Never initialize a production run in another mode
unless a separately approved promotion has made that authority available.

### Shadow observation and comparison

Seal an independent prediction before the first authoritative action, observe
only after canonical receipts exist, then compare:

```sh
python3 -m workflow_kernel bind-prediction --type pipeline --manifest manifest.json --prediction-receipts predicted.json --state-dir plans/feature
python3 -m workflow_kernel bind-prediction --type review --request request.json --prediction-receipts predicted.json --state-dir .claude/ux-review/workflow-kernel
python3 -m workflow_kernel observe-pipeline --manifest manifest.json --receipts authoritative.json --state-dir plans/feature
python3 -m workflow_kernel observe-review --request request.json --receipts authoritative.json --state-dir .claude/ux-review/workflow-kernel
python3 -m workflow_kernel compare --state-dir plans/feature --authoritative-receipts authoritative.json --output shadow-report.json
python3 -m workflow_kernel metrics --events authoritative.json --output metrics.json
```

Shadow observation never selects a node, changes an executor, waives a finding,
blocks or approves a merge, or invokes cleanup. Disable it by omitting the
observation step. If runtime resolution or compatibility fails, record
`shadow unavailable` with the safe reason and continue the Markdown-authoritative
workflow. Do not delete event history when rolling back to Markdown-only mode.

Comparison distinguishes semantic match, explained host difference, missing
authoritative evidence, unexpected transition, prediction gap, and unsafe to
promote. Metrics aggregate observed reliability and produce proposal-only
routing recommendations; they never mutate routing policy.

### Docker creation and cleanup

Plan creation before invoking Docker and register the exact before/after
inventory afterward:

```sh
python3 -m workflow_kernel plan-create --state-dir plans/feature --run-id RUN --node-id NODE --lifecycle chunk --cleanup-policy stop-remove --argv-json create-argv.json --dependent-node-ids-json dependents.json --output creation-plan.json
python3 -m workflow_kernel plan-compose --state-dir plans/feature --run-id RUN --node-id NODE --lifecycle run --cleanup-policy stop-remove --argv-json compose-argv.json --dependent-node-ids-json dependents.json --output creation-plan.json
python3 -m workflow_kernel record-create --state-dir plans/feature --plan creation-plan.json --result command-result.json --before-inventory before.json --after-inventory after.json
```

For per-chunk cleanup, use fresh authoritative node statuses and inventory. The
guarded execute command is the only authorization boundary; never execute argv
returned by a plan separately.

```sh
python3 -m workflow_kernel plan-cleanup --state-dir plans/feature --run-id RUN --node-id NODE --node-statuses node-statuses.json --output cleanup-plan.json
python3 -m workflow_kernel next-cleanup-step --state-dir plans/feature --plan cleanup-plan.json --outcomes outcomes.json --output next-step.json
python3 -m workflow_kernel execute-cleanup-step --state-dir plans/feature --plan cleanup-plan.json --step-index 0 --inventory inventory.json --node-statuses node-statuses.json --outcomes outcomes.json --output outcome-0.json
python3 -m workflow_kernel record-cleanup --state-dir plans/feature --plan cleanup-plan.json --outcomes outcomes.json
```

At every terminal path—success, failure, blocked, cancelled, or interrupted—run
reconciliation before artifact and Git cleanup:

```sh
python3 -m workflow_kernel plan-reconcile --state-dir plans/feature --run-id RUN --ttl-hours 24 --node-statuses terminal-statuses.json --output terminal-plans.json
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

Fixture evidence cannot masquerade as real-run evidence. The 0.1.0 release
keeps `shadow` as the default and exposes no native authority.

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
