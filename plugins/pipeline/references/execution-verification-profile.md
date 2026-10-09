# Verification profile and contract (0f)

Loaded at Step 0f only when the run binds a behavioral verification contract --
a repository with a workflow-kernel verification profile. A run without one
records that profile materialization is not applicable and never loads this file.

### Verification profile and contract (0f)

Resolve the trusted Kernel launcher through its runtime-resolution contract.
Require runtime and coherent installed bundle >=0.27.0; resolve the contract asset:

```sh
"$WORKFLOW_KERNEL" kernel-info --minimum-version 0.27.0
VERIFICATION_CONTRACT=$("$WORKFLOW_KERNEL" resolve-plugin-asset \
  --plugin workflow-kernel \
  --asset skills/workflow-kernel/references/verification-contract.md \
  --minimum-version 0.27.0) || exit "$?"
```

Read the resolved `VERIFICATION_CONTRACT` before generation or binding. A
missing or incompatible bundle blocks this boundary; do not reconstruct the
contract from a different cache or a project file.

The next canonical transition is `run.started`. After it, before the first builder dispatch, inspect the validated rendered-surface set:

- If at least one chunk is `required`, generate `plans/<feature-slug>/verification-profile.json` with the command below for the approved task union of required chunks only. Materialize that profile before the behavioral contract; the contract copies its exact `profile_id`, full-document digest, and required case IDs. An absent declaration tree still materializes the authoritative `not_declared` profile with empty case arrays and therefore blocks required rendered work. Do not invoke `bind-verification-contract` until this required profile exists and has been reloaded successfully.
- When every chunk is `not_applicable`, do not discover or materialize a browser profile. Generate the closed contract with null profile ID/digest and empty persona/browser arrays, preserve every validated N/A rationale, and bind without `--verification-profile`. This is an explicit no-rendered-surface contract, not fabricated `not_declared` evidence.

For required work, map the approved scope to exact lowercase declared task IDs.
Repeat `--task-id` for every task in that union. This explicit union replaces
configured suite/status selection after the existing configuration is validated.
The default is every authoritative persona, engine and viewport combination for
those tasks, including all required cases and expected FRICTION/BLOCKED outcomes:

```sh
"$WORKFLOW_KERNEL" generate-verification-profile \
  --project-root . \
  --output plans/<feature-slug>/verification-profile.json \
  --target-origin '<verified-target-origin>' \
  --task-id <approved-task-id-1> --task-id <approved-task-id-2> \
  > plans/<feature-slug>/verification-profile-generation.json
```

Replace placeholders; select the complete approved task union. Never invent
personas, engines, viewports or route bindings. Omit `--target-origin` only when
project configuration supplies it. `--declaration-root .` requires explicit
fixture approval; ordinary projects discover `tests/ux/`. Without selectors,
existing suite/status selection applies.

If a narrower combination set is explicitly approved, first run the same command
with output `verification-profile-candidate.json` and receipt
`verification-profile-candidate-generation.json`, keeping the complete task union
and omitting `--case-id`. Compare its reloaded task, persona, engine and viewport cases with approved
acceptance, including required mobile coverage. Missing required dimensions
block dispatch: hand off the declaration gap. Never substitute a reduced fixture
or persona default for approved coverage. Then generate the final fresh output:

```sh
"$WORKFLOW_KERNEL" generate-verification-profile \
  --project-root . \
  --output plans/<feature-slug>/verification-profile.json \
  --target-origin '<verified-target-origin>' \
  --task-id <approved-task-id-1> --task-id <approved-task-id-2> \
  --case-id <exact-approved-case-id-1> --case-id <exact-approved-case-id-2> \
  > plans/<feature-slug>/verification-profile-generation.json
```

Every explicitly selected task must retain at least one exact approved case.
Case selection preserves each selected case's required flag and every other
primitive. Never silently omit required selected cases. Unknown, duplicate,
empty or malformed selectors are invalid; unresolved routes for selected tasks
block before case filtering. Exit 3 reports safe exact task/placeholder gaps and
writes no profile. Invalid declarations also write no profile. Existing output
is an immutable conflict (exit 6); use a fresh approved artifact path instead of
overwriting it.

Reject nonzero generation exits or malformed receipts. Require
`stage=verification_profile_generated`, `proof_kind=plan_generation_and_reload`
and `reload_verified=true`. Check the exact `profile_id`, full-document
`profile_digest`, `discovery_status`, `selection_status`, `selected_task_ids`,
`selected_case_ids` and `required_case_ids` against the final profile and approved
selection. The command validates bounded serialization before publication,
reloads the produced file through the behavioral-contract loader, compares its
canonical document, and removes only its new owned output on failure. The
receipt proves plan generation/reload only; it never proves browser execution.

Then generate `plans/<feature-slug>/verification-contract.json` from only the approved Key Requirements and final chunk acceptance criteria, using `behavioral-verification-contract-schema.json` with stable `REQ-*`, `REG-*`, `CHK-*` IDs. Resolve every selected persona/browser case ID against `verification-contract.md`; an unresolved persona, scenario, route binding, browser, viewport, authentication fixture, or case ID blocks dispatch. Generated matrices and invented sample personas are not authority.

Validate and bind the initial contract exactly once. Pass `--verification-profile` only when at least one chunk is `required`:

```text
# One or more rendered-surface chunks:
"$WORKFLOW_KERNEL" bind-verification-contract --state-dir .workflow-kernel/runs/<run-id> --contract plans/<feature-slug>/verification-contract.json --verification-profile plans/<feature-slug>/verification-profile.json > plans/<feature-slug>/verification-contract-binding.json

# Zero rendered-surface chunks:
"$WORKFLOW_KERNEL" bind-verification-contract --state-dir .workflow-kernel/runs/<run-id> --contract plans/<feature-slug>/verification-contract.json > plans/<feature-slug>/verification-contract-binding.json
```

Reject a non-zero exit, malformed receipt, or a receipt missing the exact current `contract_digest` and `revision`. The kernel seals and validates; it never selects ready nodes, schedules builders, changes Pipeline gates, or authorizes merge. Mark `0f` complete only after the binding receipt is durable.

For required work, also require the binding receipt's exact
`verification_profile_id` and `verification_profile_digest` to match the final
generation receipt. Both contract case arrays must equal `required_case_ids`.
An existing immutable binding permits only the exact supported idempotent retry.
Changed full digest or selected cases requires a newly planned run; never rewrite
the binding or validate earlier dispatch retroactively.
