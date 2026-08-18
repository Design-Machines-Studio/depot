# Extracted conditional reference

```text
"$WORKFLOW_KERNEL" plan-create --state-dir .claude/ux-review/workflow-kernel --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json .claude/ux-review/workflow-kernel/docker/<node-id>-create-argv.json --dependent-node-ids-json .claude/ux-review/workflow-kernel/docker/<node-id>-dependent-node-ids.json --output .claude/ux-review/workflow-kernel/docker/<node-id>-creation-plan.json
"$WORKFLOW_KERNEL" plan-compose --state-dir .claude/ux-review/workflow-kernel --run-id ID --node-id ID --lifecycle SCOPE --cleanup-policy POLICY --argv-json .claude/ux-review/workflow-kernel/docker/<node-id>-compose-argv.json --dependent-node-ids-json .claude/ux-review/workflow-kernel/docker/<node-id>-dependent-node-ids.json --output .claude/ux-review/workflow-kernel/docker/<node-id>-creation-plan.json
```

Execute only its returned label-instrumented creation argv/override exactly once, then immediately invoke:

```text
"$WORKFLOW_KERNEL" record-create --state-dir .claude/ux-review/workflow-kernel --plan .claude/ux-review/workflow-kernel/docker/<node-id>-creation-plan.json --result .claude/ux-review/workflow-kernel/docker/<node-id>-create-result.json --before-inventory .claude/ux-review/workflow-kernel/docker/<node-id>-before-inventory.json --after-inventory .claude/ux-review/workflow-kernel/docker/<node-id>-after-inventory.json > .claude/ux-review/workflow-kernel/docker/<node-id>-create-receipt.json
```

Write the exact declared dependent node IDs to the dependency JSON file, using `[]` when there are none. Register partial Compose resources. Existing project containers and unsupported/ambiguous instrumentation are unmanaged/retained, not guessed owned. No returned cleanup argv is ever executed separately.

