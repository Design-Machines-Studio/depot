# Docker/Compose resource creation (review harness)

Loaded only when review setup creates a Docker or Compose resource -- a dev
server or review harness. A review that creates none never loads this file.

```text
"$WORKFLOW_KERNEL" plan-create --state-dir <exact-run-root>/review --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json <exact-run-root>/review/docker/<node-id>-create-argv.json --dependent-node-ids-json <exact-run-root>/review/docker/<node-id>-dependent-node-ids.json --output <exact-run-root>/review/docker/<node-id>-creation-plan.json
"$WORKFLOW_KERNEL" plan-compose --state-dir <exact-run-root>/review --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json <exact-run-root>/review/docker/<node-id>-compose-argv.json --dependent-node-ids-json <exact-run-root>/review/docker/<node-id>-dependent-node-ids.json --output <exact-run-root>/review/docker/<node-id>-creation-plan.json
```

Execute only its returned label-instrumented creation argv/override exactly once, then immediately invoke:

```text
"$WORKFLOW_KERNEL" record-create --state-dir <exact-run-root>/review --plan <exact-run-root>/review/docker/<node-id>-creation-plan.json --result <exact-run-root>/review/docker/<node-id>-create-result.json --before-inventory <exact-run-root>/review/docker/<node-id>-before-inventory.json --after-inventory <exact-run-root>/review/docker/<node-id>-after-inventory.json > <exact-run-root>/review/docker/<node-id>-create-receipt.json
```

Write the exact declared dependent node IDs to the dependency JSON file, using `[]` when there are none. Register partial Compose resources. Existing project containers and unsupported/ambiguous instrumentation are unmanaged/retained, not guessed owned. No returned cleanup argv is ever executed separately.

