# Extracted conditional reference

```text
"$WORKFLOW_KERNEL" plan-cleanup --state-dir .claude/ux-review/workflow-kernel --run-id ID --node-id ID --node-statuses .claude/ux-review/workflow-kernel/docker/<node-id>-node-statuses.json --output .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-plan.json
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-plan.json --outcomes .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-outcomes.json --output .claude/ux-review/workflow-kernel/docker/<node-id>-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-plan.json --step-index N --inventory .claude/ux-review/workflow-kernel/docker/<node-id>-inventory.json --node-statuses .claude/ux-review/workflow-kernel/docker/<node-id>-node-statuses.json --outcomes .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-outcomes.json --output .claude/ux-review/workflow-kernel/docker/<node-id>-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-plan.json --outcomes .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-outcomes.json > .claude/ux-review/workflow-kernel/docker/<node-id>-cleanup-receipt.json
```

At terminal cleanup, invoke `plan-reconcile` with the fresh bound status proof:

```text
"$WORKFLOW_KERNEL" plan-reconcile --state-dir .claude/ux-review/workflow-kernel --run-id ID --ttl-hours 24 --node-statuses .claude/ux-review/workflow-kernel/docker/terminal-node-statuses.json --output .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.json
```

That command writes a non-authorizing descriptor with exact fields `schema_version: 1`, `kind: cleanup-plan-set`, `current_run_plan`, `stale_sweep_plan`, and `ttl_hours`, plus independently sealed sibling artifacts `terminal-reconcile-plans.current-run.json` and `terminal-reconcile-plans.stale-sweep.json`. Each sibling has exact fields `schema_version: 1`, `kind: cleanup-plan-artifact`, `plan`, and `inventory`. Iterate each artifact independently with its own outcomes and receipt, current-run first:

```text
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.current-run.json --outcomes .claude/ux-review/workflow-kernel/docker/terminal-current-run-outcomes.json --output .claude/ux-review/workflow-kernel/docker/terminal-current-run-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.current-run.json --step-index N --inventory .claude/ux-review/workflow-kernel/docker/terminal-current-run-inventory.json --node-statuses .claude/ux-review/workflow-kernel/docker/terminal-node-statuses.json --outcomes .claude/ux-review/workflow-kernel/docker/terminal-current-run-outcomes.json --output .claude/ux-review/workflow-kernel/docker/terminal-current-run-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.current-run.json --outcomes .claude/ux-review/workflow-kernel/docker/terminal-current-run-outcomes.json > .claude/ux-review/workflow-kernel/docker/terminal-current-run-receipt.json
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.stale-sweep.json --outcomes .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-outcomes.json --output .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.stale-sweep.json --step-index N --inventory .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-inventory.json --node-statuses .claude/ux-review/workflow-kernel/docker/terminal-node-statuses.json --outcomes .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-outcomes.json --output .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/terminal-reconcile-plans.stale-sweep.json --outcomes .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-outcomes.json > .claude/ux-review/workflow-kernel/docker/terminal-stale-sweep-receipt.json
```

Never execute proposed cleanup argv separately or cross-use the two plan authorities. Persist only registry-issued ordered outcomes; actionless missing requires fresh exact-ID inspect inside the guard. Stale actions require fresh trusted inactive-lease proof from the fixed state directory; otherwise the stale plan contains blocked dispositions and no actions. Retain unmanaged, incomplete-label, in-use, uninspectable, run-shared, or incomplete-dependent resources and report exact follow-up. Broad Docker prune and name-based ownership are forbidden.

The cleanup report includes Docker before/after inventories and `removed|missing|retained|blocked|unmanaged` dispositions alongside Git. Cleanup runs on every terminal path. A cleanup failure never becomes a clean disposition or changes the authoritative code-review finding result.

