# Repository Verification Planner

Workflow Kernel provides deterministic repository test selection and fresh,
bounded execution. The repository owns the profile and commands; the developer
chooses an exact base and candidate ref from the current checkout.

## Profile

The project profile is `.dm/verification.json`. It conforms to
`repository-verification-profile-schema.json` and declares closed lane records:

- `id`, `tier`, `cadences`, `owner`, and exact `argv` arrays;
- `changed_paths` for lane selection and `input_paths` for evidence identity;
- `execution_paths` for scripts, configuration, and build context interpreted
  by a command;
- `package_selector` and `declared_dependents` for changed Go packages;
- `required`, `risks`, `after`, and `mutates_repository` policy;
- `required_environment` and `execution_environment`; and
- a bounded `timeout_seconds`.

Unknown fields, duplicate IDs, unsafe paths, shell strings, invalid
placeholders, symlinked inputs, and profiles outside the repository fail before
execution. Bare executables resolve through a fixed path. Commands receive a
minimal environment, an empty temporary home, bounded time and output, and no
implicit shell.

## Planning and execution

Use exact refs that resolve in the current checkout:

```sh
"$WORKFLOW_KERNEL" plan-verification \
  --repository-root "$PWD" --profile "$PWD/.dm/verification.json" \
  --boundary chunk --risk medium \
  --base-ref "$TRUSTED_BASE_SHA" --candidate-ref "$EXACT_HEAD_SHA" \
  --include-worktree \
  --output plans/feature/verification-plans/chunk-01.json

"$WORKFLOW_KERNEL" run-verification \
  --repository-root "$PWD" --profile "$PWD/.dm/verification.json" \
  --plan plans/feature/verification-plans/chunk-01.json
```

`--include-worktree` is appropriate for chunk and revision work. The kernel
rejects it for `merge_candidate` and `post_merge`; those boundaries require a clean
checkout so evidence maps to the exact candidate commit.

Planning derives changed paths from Git and rejects a requested candidate that
is not the current `HEAD`. It binds the repository scope, profile, base and head
commits, changed paths, execution paths, relevant environment values, lane
inputs, and expanded argv. Execution rebuilds that plan immediately before
running and rejects stale identity.

A lane has one disposition: `run`, `remote`, `blocked`, `unavailable`,
`not_scheduled`, or `not_triggered`. Callers independently collect ordinary
provider or CI evidence for pending remote lanes; Workflow Kernel does not
exchange provider results or convert caller assertions into passing results.

## Results

Each `run-verification` invocation prints one bounded result for that invocation.
It conforms to `repository-verification-result-schema.json` and includes the
canonical plan digest, repository/request identity, lane and profile identity,
the exact head and execution closure,
owner, command and input digests, exit status, duration, and stdout/stderr
digests and byte counts. It does not persist command output, environment values,
or a reusable ledger. Selected local lanes always execute.

Required remote, blocked, or unavailable lanes are never passing evidence.
Coverage claims still require a compatible measured baseline. The planner
moves expensive gates to the appropriate boundary; it does not waive them.

## Mutation and containment

After a lane with `mutates_repository: true` passes, the kernel refreshes the
remaining lane identities. It recomputes selected input identities and reports
undeclared mutation before returning a complete result.

Local lanes other than the fixed Git-only doctor declare
`DM_VERIFICATION_SUBSTRATE` in both `required_environment` and
`execution_environment`. This identifies the local
container or equivalent bounded substrate, not an approval credential.
