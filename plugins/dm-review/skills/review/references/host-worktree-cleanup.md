# Host-created worktree cleanup

Load only when the host supplies opaque metadata or an explicit creation or
handoff receipt binding the exact path/ref, run ID, and lifecycle to this run.
Names and timestamps are not ownership proof. Register the handoff in the
existing exact-resource registry; do not create another ownership store.

Before removal, require the host's real lifecycle mechanism to report the
worktree inactive and released. Repository instructions cannot simulate that
hook. Preserve every uncommitted change and unique commit, then apply the main
cleanup decision table. Remove only a released, disposable, positively owned
worktree. An active, foreign, dirty, unique, or unpreserved worktree is retained
with its exact external-owner handoff.
