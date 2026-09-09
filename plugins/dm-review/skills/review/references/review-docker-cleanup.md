# Docker/Compose resource cleanup (review harness)

Loaded at Phase 8 only when this review created a Docker or Compose resource. A
review that created none never loads this file.

```text
"$WORKFLOW_KERNEL" plan-cleanup --state-dir <exact-run-root>/review --run-id ID --node-id ID --node-statuses <exact-run-root>/review/docker/<node-id>-node-statuses.json --output <exact-run-root>/review/docker/<node-id>-cleanup-plan.json
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/<node-id>-cleanup-plan.json --outcomes <exact-run-root>/review/docker/<node-id>-cleanup-outcomes.json --output <exact-run-root>/review/docker/<node-id>-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/<node-id>-cleanup-plan.json --step-index N --inventory <exact-run-root>/review/docker/<node-id>-inventory.json --node-statuses <exact-run-root>/review/docker/<node-id>-node-statuses.json --outcomes <exact-run-root>/review/docker/<node-id>-cleanup-outcomes.json --output <exact-run-root>/review/docker/<node-id>-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/<node-id>-cleanup-plan.json --outcomes <exact-run-root>/review/docker/<node-id>-cleanup-outcomes.json > <exact-run-root>/review/docker/<node-id>-cleanup-receipt.json
```

At terminal cleanup, invoke `plan-reconcile` with the fresh bound status proof:

```text
"$WORKFLOW_KERNEL" plan-reconcile --state-dir <exact-run-root>/review --run-id ID --ttl-hours 24 --node-statuses <exact-run-root>/review/docker/terminal-node-statuses.json --output <exact-run-root>/review/docker/terminal-reconcile-plans.json
```

That command writes a non-authorizing descriptor with exact fields `schema_version: 1`, `kind: cleanup-plan-set`, `current_run_plan`, `stale_sweep_plan`, and `ttl_hours`, plus independently sealed sibling artifacts `terminal-reconcile-plans.current-run.json` and `terminal-reconcile-plans.stale-sweep.json`. Each sibling has exact fields `schema_version: 1`, `kind: cleanup-plan-artifact`, `plan`, and `inventory`. Iterate each artifact independently with its own outcomes and receipt, current-run first:

```text
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/terminal-reconcile-plans.current-run.json --outcomes <exact-run-root>/review/docker/terminal-current-run-outcomes.json --output <exact-run-root>/review/docker/terminal-current-run-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/terminal-reconcile-plans.current-run.json --step-index N --inventory <exact-run-root>/review/docker/terminal-current-run-inventory.json --node-statuses <exact-run-root>/review/docker/terminal-node-statuses.json --outcomes <exact-run-root>/review/docker/terminal-current-run-outcomes.json --output <exact-run-root>/review/docker/terminal-current-run-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/terminal-reconcile-plans.current-run.json --outcomes <exact-run-root>/review/docker/terminal-current-run-outcomes.json > <exact-run-root>/review/docker/terminal-current-run-receipt.json
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/terminal-reconcile-plans.stale-sweep.json --outcomes <exact-run-root>/review/docker/terminal-stale-sweep-outcomes.json --output <exact-run-root>/review/docker/terminal-stale-sweep-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/terminal-reconcile-plans.stale-sweep.json --step-index N --inventory <exact-run-root>/review/docker/terminal-stale-sweep-inventory.json --node-statuses <exact-run-root>/review/docker/terminal-node-statuses.json --outcomes <exact-run-root>/review/docker/terminal-stale-sweep-outcomes.json --output <exact-run-root>/review/docker/terminal-stale-sweep-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/terminal-reconcile-plans.stale-sweep.json --outcomes <exact-run-root>/review/docker/terminal-stale-sweep-outcomes.json > <exact-run-root>/review/docker/terminal-stale-sweep-receipt.json
```

Never execute proposed cleanup argv separately or cross-use the two plan authorities. Persist only registry-issued ordered outcomes; actionless missing requires fresh exact-ID inspect inside the guard. Stale actions require fresh trusted inactive-lease proof from the fixed state directory; otherwise the stale plan contains blocked dispositions and no actions. Retain unmanaged, incomplete-label, in-use, uninspectable, run-shared, or incomplete-dependent resources and report exact follow-up. Broad Docker prune and name-based ownership are forbidden.

The cleanup report includes Docker before/after inventories and `removed|missing|retained|blocked|unmanaged` dispositions alongside Git. Cleanup runs on every terminal path. A cleanup failure never becomes a clean disposition or changes the authoritative code-review finding result.


## Repository lifecycle teardown

For an instrumented repository author loop, invoke its original clean command
with the same exact instance, state/run roots, and scoped Docker hook. Intercept
its Compose teardown request and execute the existing Kernel cleanup sequence
above for the registered IDs. Do not execute raw `compose down --remove-orphans`
or use the project name as deletion authority. A plan can contain safe container actions alongside an in-use network retained
for dependency. Execute and record the sealed eligible steps, then replan once
after removing the containers. An unchanged in-use dependency remains retained;
never turn a blocked disposition into a direct removal. Status and harmless inspection
continue to address the wrapper's unchanged target. A wrapper cleanup builder
is another creating call and must be planned and recorded before teardown.

Allow the wrapper's image removal only when the current exact image ID matches
the image this invocation positively created at an initially absent tag. Retain
its state and run roots on any ambiguous identity or cleanup failure. Let the
wrapper perform its documented filesystem cleanup, then finish only the
remaining exact-owned filesystem paths; its normal clean may preserve data.
Existing developer images, data, instances, and caches are never adopted.

On partial start or interruption, settle the saved pending creation plan against
fresh before/after evidence first. Run exact registered cleanup even when no
browser opened. Resume a persisted cleanup plan using its ordered outcomes;
after an interrupted command whose outcome could not be persisted, replan from
fresh exact-ID inspection instead of inventing a successful result or replaying
raw teardown. An absent object is handled by Kernel's exact absence proof.
If evidence cannot establish ownership, report retained resources and the
specific recovery prerequisite. Cleanup failure does not change the review
finding verdict or turn missing populated browser cases into passes.
