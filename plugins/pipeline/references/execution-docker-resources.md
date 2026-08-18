# Docker resource commands

Load when creating, cleaning, or reconciling Docker/Compose resources.

## Creation

Before creating a container, network, named volume, or Compose project, invoke exactly one of:

```text
"$WORKFLOW_KERNEL" plan-create --state-dir plans/<feature-slug> --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json plans/<feature-slug>/docker/<node-id>-create-argv.json --dependent-node-ids-json plans/<feature-slug>/docker/<node-id>-dependent-node-ids.json --output plans/<feature-slug>/docker/<node-id>-creation-plan.json
"$WORKFLOW_KERNEL" plan-compose --state-dir plans/<feature-slug> --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json plans/<feature-slug>/docker/<node-id>-compose-argv.json --dependent-node-ids-json plans/<feature-slug>/docker/<node-id>-dependent-node-ids.json --output plans/<feature-slug>/docker/<node-id>-creation-plan.json
```

Write declared dependent node IDs to the dependency JSON (`[]` if none). These commands return label-instrumented argv and ownership proof; they do not execute. Execute that argv/labels-only Compose override exactly once. Caller-supplied project names, ambiguous forms, anonymous/external resources, symlink escapes, or unsupported instrumentation are `unmanaged/retained`. Never execute returned cleanup argv outside `execute-cleanup-step`.

After the creation attempt:

```text
"$WORKFLOW_KERNEL" record-create --state-dir plans/<feature-slug> --plan plans/<feature-slug>/docker/<node-id>-creation-plan.json --result plans/<feature-slug>/docker/<node-id>-create-result.json --before-inventory plans/<feature-slug>/docker/<node-id>-before-inventory.json --after-inventory plans/<feature-slug>/docker/<node-id>-after-inventory.json > plans/<feature-slug>/docker/<node-id>-create-receipt.json
```

Register partial Compose creation as individual resources. Every managed object must carry complete `com.designmachines.depot.*` ownership labels before creation. If ownership is unproven, do not later auto-remove the object.

## Chunk cleanup

```text
"$WORKFLOW_KERNEL" plan-cleanup --state-dir plans/<feature-slug> --run-id ID --node-id ID --node-statuses plans/<feature-slug>/docker/<node-id>-node-statuses.json --output plans/<feature-slug>/docker/<node-id>-cleanup-plan.json
"$WORKFLOW_KERNEL" next-cleanup-step --state-dir plans/<feature-slug> --plan plans/<feature-slug>/docker/<node-id>-cleanup-plan.json --outcomes plans/<feature-slug>/docker/<node-id>-cleanup-outcomes.json --output plans/<feature-slug>/docker/<node-id>-next-step.json
"$WORKFLOW_KERNEL" execute-cleanup-step --state-dir plans/<feature-slug> --plan plans/<feature-slug>/docker/<node-id>-cleanup-plan.json --step-index N --inventory plans/<feature-slug>/docker/<node-id>-inventory.json --node-statuses plans/<feature-slug>/docker/<node-id>-node-statuses.json --outcomes plans/<feature-slug>/docker/<node-id>-cleanup-outcomes.json --output plans/<feature-slug>/docker/<node-id>-step-N-outcome.json
"$WORKFLOW_KERNEL" record-cleanup --state-dir plans/<feature-slug> --plan plans/<feature-slug>/docker/<node-id>-cleanup-plan.json --outcomes plans/<feature-slug>/docker/<node-id>-cleanup-outcomes.json > plans/<feature-slug>/docker/<node-id>-cleanup-receipt.json
```

Rewrite the bound node-status file immediately before `plan-cleanup` and every `execute-cleanup-step`. `plan-cleanup` and `next-cleanup-step` return proposals only. `execute-cleanup-step` is the only authorization/execution boundary. Never execute cleanup argv returned by planning separately.

## Terminal reconcile

Atomically write `plans/<feature-slug>/docker/terminal-node-statuses.json`, then:

```text
"$WORKFLOW_KERNEL" plan-reconcile --state-dir plans/<feature-slug> --run-id ID --ttl-hours 24 --node-statuses plans/<feature-slug>/docker/terminal-node-statuses.json --output plans/<feature-slug>/docker/terminal-reconcile-plans.json
```

Descriptor shape:

```json
{"schema_version":1,"kind":"cleanup-plan-set","current_run_plan":"plans/<feature-slug>/docker/terminal-reconcile-plans.current-run.json","stale_sweep_plan":"plans/<feature-slug>/docker/terminal-reconcile-plans.stale-sweep.json","ttl_hours":24}
```

Each sibling has `schema_version: 1`, `kind: cleanup-plan-artifact`, `plan`, and `inventory`. Process current-run first with its own empty outcomes and receipt, then stale-sweep with a distinct empty outcomes and receipt. Refresh inventory and node-status proof before every execute. Never combine, reorder, or cross-use the two plan authorities.
