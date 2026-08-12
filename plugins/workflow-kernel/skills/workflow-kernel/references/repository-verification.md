# Repository Verification Planner

Workflow Kernel provides deterministic repository test selection and exact-input
receipt reuse. The repository owns the profile and commands; the developer
chooses an exact base and candidate ref from the current checkout.

## Profile

The project profile is `.dm/verification.json`. It conforms to
`repository-verification-profile-schema.json` and declares closed lane records:

- `id`, `tier`, `cadences`, `owner`, and exact `argv` arrays;
- `changed_paths` for lane selection and `input_paths` for evidence reuse;
- `execution_paths` for scripts, configuration, and build context interpreted
  by a command;
- `package_selector` and `declared_dependents` for changed Go packages;
- `required`, `cache`, `risks`, `after`, and `mutates_repository` policy;
- `cache_environment`, `required_environment`, and `execution_environment`; and
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
  --receipts plans/feature/repository-verification-receipts.json \
  --output plans/feature/verification-plans/chunk-01.json

"$WORKFLOW_KERNEL" run-verification \
  --repository-root "$PWD" --profile "$PWD/.dm/verification.json" \
  --plan plans/feature/verification-plans/chunk-01.json \
  --receipts plans/feature/repository-verification-receipts.json \
  --output plans/feature/repository-verification-receipts.json
```

`--include-worktree` is appropriate for chunk and revision work. It is rejected
for `merge_candidate` and `post_merge`; those boundaries require a clean
checkout so evidence maps to the exact candidate commit.

Planning derives changed paths from Git and rejects a requested candidate that
is not the current `HEAD`. It binds the repository scope, profile, base and head
commits, changed paths, execution paths, relevant environment values, lane
inputs, and expanded argv. Execution rebuilds that plan immediately before
running and rejects stale identity.

A lane has one disposition: `run`, `reuse`, `remote`, `blocked`, `unavailable`,
`not_scheduled`, or `not_triggered`. Remote lanes remain pending until ordinary
provider or CI evidence is independently collected; Workflow Kernel does not
exchange provider results or convert caller assertions into passing receipts.

## Evidence and reuse

The deterministic, content-free ledger records lane and profile identity,
boundary, owner, exact head, command/input/cache digests, exit status, duration,
and stdout/stderr digests and byte counts. It does not persist command output or
environment values. Publication takes a short file lock and merges against the
latest ledger so concurrent local lanes cannot silently discard receipts.

Only a structurally valid local `passed` receipt can be reused. Its cache key
covers the canonical profile, expanded argv, matching input files and modes,
and named cache-environment values. `cache: never` always executes. Remote
receipts are not synthesized by the local runner.

Required remote, blocked, or unavailable lanes are never passing evidence.
Coverage claims still require a compatible measured baseline. The planner
moves expensive gates to the appropriate boundary; it does not waive them.

## Mutation and containment

A passing lane with `mutates_repository: true` causes remaining lane identities
to be refreshed. Before a complete result is returned, the kernel recomputes
selected input identities and reports undeclared mutation.

Local lanes other than the fixed Git-only doctor declare
`DM_VERIFICATION_SUBSTRATE` in both `required_environment` and
`execution_environment`. This is an execution/cache identity for the local
container or equivalent bounded substrate, not an approval credential.
