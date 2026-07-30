# Repository Verification Planner

Workflow Kernel `0.6.0` provides deterministic repository test selection and
authenticated exact receipt reuse. Repository configuration declares commands
and policy; separate host approval authorizes the exact execution closure.

## Authority

The project profile is `.dm/verification.json`. It conforms to
`repository-verification-profile-schema.json` and contains closed lane records:

- `id`: stable lane identity;
- `tier`: `doctor|fast|focused|full|race|harness|remote`;
- `cadences`: workflow boundaries where the lane is eligible;
- `owner`: `local|github|blueprint|other|unresolved`;
- `argv`: exact command arguments, never a shell string;
- `changed_paths`: safe globs that trigger the lane;
- `input_paths`: safe globs whose regular-file content binds evidence reuse;
- `authority_paths`: command-interpreted scripts/configuration/build context
  whose identity requires host approval;
- `package_selector`: `none` or `go_changed`;
- `declared_dependents`: explicit Go package dependency additions;
- `required`: whether unresolved authority blocks;
- `cache`: `content` or `never`;
- `risks`: eligible `low|medium|high` run risks; and
- `cache_environment`: environment names whose values affect the key.
- `required_environment`: cache-bound environment values that must be present;
- `authority_environment`: cache-bound values, such as substrate identity, that
  are sealed into host approval;
- `after`: explicit lane dependencies, topologically ordered by the kernel;
- `mutates_repository`: declares a generation lane whose successful execution
  requires later lane identities to be refreshed; and
- `timeout_seconds`: a bounded per-command timeout.

Unknown fields, duplicate IDs, absolute/traversing paths, shell strings, arrays
over their declared bounds, invalid placeholders, symlinked input files or
directories, or a profile outside the repository fail before command
execution.

Repository content is not execution authorization. Before builder dispatch,
`approve-verification-profile` creates an immutable HMAC-authenticated artifact
binding repository scope, profile path/digest, authority paths/environment,
trusted base commit, run ID, authorization event, and time. Planning and
execution require that artifact. Bare executables resolve through a fixed path;
commands receive an empty temporary home, minimal environment, bounded time,
incrementally bounded output, and no Docker credential/config variables.

## Boundaries

| Boundary | Purpose |
|---|---|
| `chunk` | Doctor, fast, and focused checks for one implementation chunk |
| `revision_batch` | One affected recheck after all fixes from a review pass |
| `execution_level` | One integrated full non-race pass after sibling chunks merge |
| `merge_candidate` | Exact candidate evidence and explicit remote lanes |
| `post_merge` | Authoritative main-branch evidence |

A lane runs only when cadence, risk, and changed-path rules all match. A Go
focused lane expands `{packages}` to changed Go package directories plus
explicitly declared dependents. Templ paths use their containing Go package so
generation and focused testing remain connected. Changes to `go.mod`, `go.sum`,
`go.work`, or `go.work.sum` expand the package argument to `./...`.

Required `merge_candidate` and `post_merge` lanes are materialized even on a
clean worktree; exact content decides run versus reuse. Deleted paths are
included in Git discovery. These terminal boundaries require
`include_worktree=false` and a clean index/worktree so provider evidence maps
to the exact committed candidate.

## Planning

First issue approval from the host boundary. The stable authority key comes
from a broker outside the repository and worker process identity; it is
delivered on standard input and is never named in argv:

```sh
"$HOST_AUTHORITY_BROKER" | "$WORKFLOW_KERNEL" approve-verification-profile \
  --repository-root "$PWD" --profile "$PWD/.dm/verification.json" \
  --trusted-base-commit "$TRUSTED_BASE_SHA" \
  --candidate-commit "$EXACT_HEAD_SHA" --include-worktree \
  --run-id "$RUN_ID" \
  --authorization-event-id "$AUTHORIZATION_EVENT_ID" \
  --approved-at "$APPROVED_AT" --receipt-key-stdin \
  --output "$HOST_APPROVAL"
```

The approval seals the candidate commit and the changed-path digest derived
from the trusted base. Planning therefore accepts no caller-selected diff:

```sh
"$HOST_AUTHORITY_BROKER" | "$WORKFLOW_KERNEL" plan-verification \
  --repository-root "$PWD" \
  --profile "$PWD/.dm/verification.json" \
  --boundary chunk --risk medium \
  --approval "$HOST_APPROVAL" \
  --receipts plans/feature/repository-verification-receipts.json \
  --receipt-key-stdin \
  --output plans/feature/verification-plans/chunk-01.json
```

For an execution-level boundary, issue a new approval for the level candidate,
then plan from that same sealed range:

```sh
"$HOST_AUTHORITY_BROKER" | "$WORKFLOW_KERNEL" plan-verification \
  --repository-root "$PWD" \
  --profile "$PWD/.dm/verification.json" \
  --boundary execution_level --risk medium \
  --approval "$HOST_APPROVAL" \
  --receipts plans/feature/repository-verification-receipts.json \
  --receipt-key-stdin \
  --output plans/feature/verification-plans/level-01.json
```

A fresh plan re-derives the sealed Git range and emits every lane with one
disposition:

- `run`: execute locally;
- `reuse`: a prior passing receipt has the exact key;
- `remote`: the declared provider owns execution;
- `blocked`: required ownership is unresolved;
- `unavailable`: optional ownership is unresolved;
- `not_scheduled`: wrong boundary/risk; or
- `not_triggered`: changed paths do not affect the lane.

## Execution

```sh
"$HOST_AUTHORITY_BROKER" | "$WORKFLOW_KERNEL" run-verification \
  --repository-root "$PWD" \
  --profile "$PWD/.dm/verification.json" \
  --plan plans/feature/verification-plans/level-01.json \
  --approval "$HOST_APPROVAL" \
  --receipts plans/feature/repository-verification-receipts.json \
  --receipt-key-stdin \
  --output plans/feature/repository-verification-receipts.json
```

The authority broker is inaccessible to the repository and worker identity.
The runner consumes its standard input before starting children, reloads the
profile, recomputes the approval closure, lane plan, and relevant file digests,
and rejects stale or altered authority before executing. Commands run as
approved argv arrays in the repository root using a fixed executable path,
empty temporary home, minimal environment, and no implicit shell.

Input fingerprints are collected in one repository traversal per freshness
boundary. They bind relative path, regular-file content, and mode through
descriptor-relative no-follow reads. A passing lane with
`mutates_repository: true` causes remaining lanes to be replanned so generated
outputs receive current receipt identities. Explicit `after` dependencies
remove array-order semantics. Before a complete outcome is signed, the kernel
recomputes every selected input identity and fails on undeclared mutation.

The receipt ledger is append-only and HMAC-authenticated. It records profile,
status, owner, tier, boundary, command/input/cache digests, exit status,
measured duration, and stdout/stderr digests and byte counts. It does not
persist raw command output, environment values, or authentication keys.

Concurrent workers share one absolute orchestrator-owned ledger. Execution may
remain parallel; publication takes a short file lock and merges each worker's
authenticated suffix into the latest history. Divergent baselines fail with
exit `6` instead of losing receipts.

## Exact reuse

The cache key covers:

1. canonical profile digest;
2. lane ID and expanded argv;
3. content and relative paths of every matching `input_paths` regular file;
4. relevant file modes; and
5. hashes of the values named by `cache_environment`.

Boundary is intentionally not part of the key. An unchanged passing
`execution_level` full-suite receipt therefore satisfies the identical
`merge_candidate` full lane. A relevant source/config/profile change produces a
new key. Documentation, plans, receipts, or other metadata do not invalidate a
code lane unless the profile explicitly includes them.

`cache: never` always executes. Use it for doctor/preflight checks whose result
depends on unmodeled live state and for generation lanes whose outputs must be
materialized in the current checkout.

Docker-backed cacheable lanes include Dockerfile/build-context inputs and
require `DM_VERIFICATION_SUBSTRATE`, a caller-produced identity containing the
resolved image digest and compiler/generator toolchain.

Any local lane other than a fixed Git-only doctor must list
`DM_VERIFICATION_SUBSTRATE` in both `required_environment` and
`authority_environment`. The value identifies a host-provided containment unit
such as a container, cgroup, job object, or equivalent sandbox that descendants
cannot escape and that the host destroys at lane completion. Process-group
termination is defense in depth for ordinary descendants; it is not accepted as
the sole boundary for candidate-executing code.

## Evidence boundaries

- `reused` is valid only when backed by an earlier fully validated,
  HMAC-authenticated `passed` receipt.
- `remote_pending`, `blocked`, and `unavailable` are never passing evidence.
- The planner moves race/security/container/browser/accessibility lanes; it
  does not waive them.
- Provider CI must return its own exact-SHA authoritative evidence before the
  host broker validates it and seals a
  `repository_verification_provider_attestation`. The host integration passes
  only that attestation to `record-verification-result`; raw scalar assertions
  are not accepted. The kernel rechecks the attestation, approval, and lane
  identities before appending a passing receipt. Until then,
  required remote evidence makes `run-verification` emit `pending` and exit `3`.
- Coverage regression claims require a compatible measured baseline; this
  planner does not infer one.
