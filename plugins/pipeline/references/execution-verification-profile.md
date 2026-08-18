# Verification profile and contract (0f)

Loaded at Step 0f only when the run binds a behavioral verification contract --
a repository with a workflow-kernel verification profile. A run without one
records that profile materialization is not applicable and never loads this file.

### Verification profile and contract (0f)

The next canonical transition is `run.started`. After it, before the first builder dispatch, inspect the validated rendered-surface set:

- If at least one chunk is `required`, generate `plans/<feature-slug>/verification-profile.json` by running the complete project-declaration discovery and selection contract in `verification-contract.md` for the union of required chunks only. Materialize that profile before the behavioral contract; the contract copies its exact `profile_id`, full-document digest, and required case IDs. An absent declaration tree still materializes the authoritative `not_declared` profile with empty case arrays and therefore blocks required rendered work. Do not invoke `bind-verification-contract` until this required profile exists and has been reloaded successfully.
- When every chunk is `not_applicable`, do not discover or materialize a browser profile. Generate the closed contract with null profile ID/digest and empty persona/browser arrays, preserve every validated N/A rationale, and bind without `--verification-profile`. This is an explicit no-rendered-surface contract, not fabricated `not_declared` evidence.

Then generate `plans/<feature-slug>/verification-contract.json` from only the approved Key Requirements and final chunk acceptance criteria, using `behavioral-verification-contract-schema.json` with stable `REQ-*`, `REG-*`, `CHK-*` IDs. Resolve every selected persona/browser case ID against `verification-contract.md`; an unresolved persona, scenario, route binding, browser, viewport, authentication fixture, or case ID blocks dispatch. Generated matrices and invented sample personas are not authority.

Validate and bind the initial contract exactly once. Pass `--verification-profile` only when at least one chunk is `required`:

```text
# One or more rendered-surface chunks:
"$WORKFLOW_KERNEL" bind-verification-contract --state-dir .workflow-kernel/runs/<run-id> --contract plans/<feature-slug>/verification-contract.json --verification-profile plans/<feature-slug>/verification-profile.json > plans/<feature-slug>/verification-contract-binding.json

# Zero rendered-surface chunks:
"$WORKFLOW_KERNEL" bind-verification-contract --state-dir .workflow-kernel/runs/<run-id> --contract plans/<feature-slug>/verification-contract.json > plans/<feature-slug>/verification-contract-binding.json
```

Reject a non-zero exit, malformed receipt, or a receipt missing the exact current `contract_digest` and `revision`. The kernel seals and validates; it never selects ready nodes, schedules builders, changes Pipeline gates, or authorizes merge. Mark `0f` complete only after the binding receipt is durable.
