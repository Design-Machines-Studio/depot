# Exact-owned invocation cleanup

This is the shared lifecycle convention for Depot workflows that create
disposable filesystem roots, Git worktrees/branches, or Docker resources. It
reuses the existing Workflow Kernel Git and Docker adapters. The small
`owned-run-*` helper owns only filesystem roots and replaces duplicated
temporary-directory, temporary-repository, cache, and raw-output handling.

## Ownership boundary

One invocation has one unique `run_id`. Record each resource at creation, with
that exact run identity, through the adapter that creates it:

| Resource | Owner | Exact authority |
|---|---|---|
| Run root, temporary directory/repository, cache, raw output | `owned-run-*` | Fresh root identity plus recorded root-relative path |
| Worktree and branch | Workflow Kernel `GitAdapter` | Durable `ResourceRegistry` record plus fresh exact-ref proof |
| Container, network, volume, Compose project | Workflow Kernel `DockerAdapter` | Complete creation-time labels, durable registry record, and exact inspected ID |

An invocation never adopts a pre-existing path, worktree, branch, or Docker
object. A resource absent from its exact registry is foreign even if its name,
prefix, feature slug, label subset, or age resembles an owned resource. Do not
scan by age, prefix, wildcard, or broad glob. Do not call any Git or Docker
prune command as resource cleanup.

Git namespaces include the unique run ID, not only a feature slug:

```text
.worktrees/pipeline/<run-id>/<chunk-id>
pipeline/<run-id>/<chunk-id>
```

Two invocations for the same feature therefore have distinct roots and refs.
Cleanup reads only each invocation's registered exact entries; it never sweeps
the shared namespace.

## Disposable filesystem root

Resolve one compatible Workflow Kernel launcher, then create the invocation
root. With no `--base`, the helper uses the current OS account's XDG state root
(`$XDG_STATE_HOME` only when it is absolute, otherwise
`~/.local/state/design-machines/depot/runs`). Generic code never selects an
Assembly checkout path.

```sh
RUN_JSON=$(
  "$WORKFLOW_KERNEL" owned-run-start \
    --workflow pipeline \
    --run-id "$RUN_ID"
) || exit $?
RUN_ROOT=$(printf '%s' "$RUN_JSON" | jq -r '.path')

"$WORKFLOW_KERNEL" owned-run-create \
  --run-root "$RUN_ROOT" \
  --kind temporary-repository \
  --relative-path repository
```

Allowed kinds are `temporary-directory`, `temporary-repository`, `cache`,
`raw-output`, and `diagnostic`. The helper creates a new path; it refuses to
register or overwrite a pre-existing path. All are nested beneath the one
fresh run root. Use the returned exact path rather than reconstructing it.

Executable adapters that run one bounded argv command use `owned-run-exec`.
It places the exact root in `DEPOT_EXACT_RUN_ROOT`, forwards `SIGINT`/`SIGTERM`
to the child's process group, reconciles the root, prints the terminal JSON,
and returns `130`/`143` after the interrupt:

```sh
"$WORKFLOW_KERNEL" owned-run-exec \
  --workflow assembly-build \
  --run-id "$RUN_ID" \
  -- --exact-command arg1 arg2
```

This is a command supervisor, not a daemon. Hosts that span multiple command
invocations keep the exact `RUN_ROOT` in their existing run state and invoke
the same terminal sequence from their `EXIT`, `INT`, and `TERM` handling.

## Terminal sequence

Run this sequence for success, failure, cancellation, review abort before
execution, and interruption:

1. Reconcile exact registered Docker IDs. A missing object is already clean.
2. Reconcile exact registered Git worktrees and branches. Remove a worktree
   before its branch; retain dirty/unreadable work only as the one diagnostic
   root after capturing why it cannot be removed safely.
3. Preserve the requested deliverable and compact durable repository/GitHub
   evidence. Raw Pipeline/review output, temporary clones, and caches remain
   disposable.
4. Finish the filesystem root.

Success, cancellation with no useful diagnostic, and review abort before any
execution remove the complete exact-owned root:

```sh
"$WORKFLOW_KERNEL" owned-run-finish \
  --run-root "$RUN_ROOT" \
  --outcome succeeded
```

A failure or interruption retains nothing by default. When compact diagnostics
are genuinely useful, place only bounded regular files under the recorded
`diagnostic` path and request retention. This is an internal terminal decision,
not a new user-facing keep/debug option:

```sh
"$WORKFLOW_KERNEL" owned-run-finish \
  --run-root "$RUN_ROOT" \
  --outcome interrupted \
  --retain-diagnostics \
  --reason "required browser process stopped on SIGTERM" \
  --contains "bounded failure summary and exact reproduction command"
```

Retention deletes every other child of the exact-owned root, permits at most
128 regular files and 2 MiB, refuses links or special files, and emits all four
terminal fields:

```text
path
reason
contains
cleanup_command
```

It also writes those fields to `CLEANUP.txt` inside the retained root. The
cleanup command is one exact shell-quoted `rm -rf -- <path>` for that verified
owned root. If a dirty worktree itself is the retained diagnostic root, remove
the disposable filesystem root instead and report the worktree's exact path,
contents, reason, and exact `git worktree remove --force -- <path>` command.
Never retain both.

## Resume and retry

Resume from the exact root recorded in existing run state; never rediscover it
with a glob. `owned-run-exec --resume-root <exact-path>` verifies the original
workflow, run ID, parent identity, and root identity before reuse. A retry may
add a new exact child. Cleanup tolerates a recorded child that has already
disappeared and removes the remaining root exactly once. `owned-run-finish`
against an already-absent root reports `missing` and performs no deletion.
