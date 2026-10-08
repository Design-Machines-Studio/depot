# Review completion hook activation

dm-review ships one small backstop in `hooks/hooks.json`. It catches a supported
implementation that stopped before its owner ran the readiness check. It is
not a review owner, a review receipt or a publication gate. The existing
producer is the only coverage authority. The pre-PR gate in
`automatic-implementation-closeout.md` stays mandatory whether or not the hook
runs.

## What the hook does

Both events run `review-completion-hook.sh` from the installed bundle through
`${CLAUDE_PLUGIN_ROOT}`. Claude Code and Codex both set that variable for
plugin hooks.

| Event | Behavior |
|-------|----------|
| SessionStart | Calls `review-owner-context.sh init`. It creates an unbound `planning` pointer, or keeps a matching one on resume, and returns its path as `additionalContext`. |
| Stop, phase `executing` or `checking` | Validates the bound owner and its exact-owned metadata. On the first stop at a run and change boundary, it returns one `decision: block` with the fixed reason to resume this exact owner. |
| Stop, continuation still unchecked | When `stop_hook_active` is true and the owner is still `executing` or `checking`, it records `blocked` through the helper and returns a `Not ready` message. It does not continue again. |
| Stop, any other state | Silent. This covers questions, planning, plan approval, UI and merge waits, `blocked`, `complete`, missing or foreign pointers, workers, subdirectories and unrelated repositories. |

The hook reads only the native hook input and the session's own
`review-owner.json`. It never parses transcripts, searches for runs, invokes
model lanes or dispatches review. Its `continued-*` dedupe markers sit beside
the pointer and are never review coverage. Malformed input, a wrong event, a
missing helper, `jq` or `git` return a precise `systemMessage` and never claim
the hook is active.

## Proof levels

Keep each level separate. A lower level never implies a higher one.

| Level | Evidence | Status for this candidate |
|-------|----------|---------------------------|
| Source fixtures | `tools/test-review-completion-hook.sh` | Run against candidate source |
| Bundle shape | `tools/validate-dual-compat.sh` plugin hook check, `claude plugin validate plugins/dm-review` | Run. The generated Codex manifest includes the hook entry. |
| Claude native canary | Installed released plugin in a disposable repository | Not exercised |
| Codex native canary | Installed released plugin with Codex hooks enabled and trusted | Not exercised |
| T3 delivery | T3 Codex thread shows the Stop continuation | Not exercised. Report T3 hook enforcement as unavailable. |

NED state on 2026-10-08: Codex 0.160.0 has `[features] hooks = false` in the
global configuration, and the installed Codex dm-review is 1.86.0 without
hooks. Codex and T3 sessions therefore run no hook. Report
`hook activation unavailable` there.

## Native canary

Run this for each harness after release and activation. Use a disposable
repository with a GitHub-shaped `origin` and a disposable `TMPDIR`. Record
results per harness.

1. Start a session at the repository root. Expect `additionalContext` naming
   the pointer and a `planning` record.
2. Leave a dirty file while still planning and end the turn. Expect no hook
   output.
3. Bind a disposable owned run with `review-owner-context.sh bind`, commit a
   change so the tree is clean, then end the turn. Expect exactly one
   continuation with the fixed reason.
4. Let that continuation end without advancing the phase. Expect `Not ready`
   and a `blocked` record, with no second continuation.
5. Resume the owner, commit another change and end the turn. Expect one new
   continuation for the new boundary.
6. End a turn from another session ID or another checkout. Expect no output.

For T3, also confirm from the app-server stream that `hooks/list` shows the
plugin hooks and that `hook/completed` reports the Stop run as `blocked`
before the continuation turn starts.

## Activation after merge and release

These are one-time owner actions. Agents do not run them during candidate
development.

1. Publish through the normal release preflight. Update the dm-review plugin in
   each harness through its plugin manager. Never patch an installed cache.
2. Claude Code: start a new session after the update so the plugin hooks
   load. Check that `/hooks` lists the SessionStart and Stop entries from
   dm-review.
3. Codex: enabling `[features] hooks` is a global owner decision. It also
   enables every hook Codex has already trusted, including the
   assembly-baseplate project hooks. After enabling it, review and trust the
   dm-review hooks in Codex's `/hooks` view. Codex records the trust itself.
   Never write `trusted_hash` by hand or bypass the trust review.
4. T3 on NED: T3 runs Codex as `ned`. Start a new T3 thread after the Codex
   trust step so the session loads the trusted hooks. Do not restart system
   services for this.
5. Run the native canary for each harness before claiming enforcement there.

## Rollback

- Claude Code: disable the dm-review plugin or install the previous version,
  then start a new session.
- Codex and T3: untrust the dm-review hooks in `/hooks`, or restore
  `[features] hooks = false`, then start a new thread.
- Pointer and marker files under `$TMPDIR/claude-hook-state/review-*` are
  per-session state. Removing them only removes the backstop for that
  session.

Rollback never weakens the mandatory pre-PR producer gate.
