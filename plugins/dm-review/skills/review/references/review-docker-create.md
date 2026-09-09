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


## Repository-owned lifecycle commands

A documented wrapper may fix its Compose project name. Keep that wrapper as
lifecycle authority: invoke its original start, status, setup, and clean commands
with one fresh instance and exact external state/run roots. Do not replace it
with an extracted `compose up`, edit its source, or strip its project name.
First prefer a suitable running target; reuse never registers or adopts it.

For an isolated target, the host may instrument the wrapper's Docker command
boundary for this invocation only. Inspect the directly linked wrapper before
installing that scoped hook. Bind its exact Compose prefix (project, project
directory, and files); reject unexpected commands. This is argv instrumentation,
not a second composer: the repository still generates its configuration, builds,
selects the service, waits for health, reports status, and requests cleanup.
The hook must cover `exec docker` as well as ordinary shell calls; an exported
shell function alone does not intercept `exec`. Use an invocation-local command
path and keep Kernel's real Docker runner on its fixed trusted path. Do not
install a global Docker shim or patch the repository's lifecycle script.

Use Workflow Kernel >=0.22.0. At each creating Compose call, supply the exact
wrapper argv to `plan-compose`, adding `--repository-project-name <exact-name>`
only when the host has verified this documented lifecycle binding. The ordinary
caller-project-name guard remains in effect without this explicit option.
Kernel inspects all service profiles so a profiled builder receives creation
labels too. It requires exactly one matching name, refuses container aliases, external
resources and network/volume aliases, and checks both the project inventory and
resolved resource names. Existing objects must already have exact active records
for this repository, run, and node with matching creation labels. A name or label
alone never grants ownership. Failed inspection is not absence.

Keep the returned project name, original argv (including literal multiline
builder arguments), and label-only override. Materialize the override in the
private run evidence, append it at the intercepted call, then execute that
creation once. Preserve the before inventory and pending plan before execution;
record the result and after inventory immediately, including partial failures.
`run --rm` may leave only its newly created network to register. Do not rewrite
script whitespace, flatten argv into shell text, or call the builder separately.
Already-owned network/volume creation labels remain stable across calls, so
Compose does not try to replace an in-use network merely because the next
builder or seed command has a newer timestamp. A later wrapper call must replan
against fresh inventory; an old successful plan
is not permission to start again after a collision or source change.

Before any wrapper mutation, also prove that its instance, image tag, filesystem
roots, and bind-mounted data are fresh or already positively created by this
invocation. Kernel's Docker registry does not own images or bind-mounted data.
Use the existing `owned-run-*` filesystem receipt and record the exact created
image ID for the wrapper's own image cleanup. A foreign collision stops the
attempt; never reset or rebuild the developer's default instance. If the host
cannot instrument this boundary, name that integration prerequisite and retain
`REVIEW INCOMPLETE`; do not call the raw start as a fallback.

The canary and its exact wrapper/source identities are recorded in
[UI-READY-03 evidence](../../../../../docs/ui-ready-03-governance.md).
