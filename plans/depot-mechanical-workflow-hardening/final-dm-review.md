# Final dm-review: depot-mechanical-workflow-hardening

## Scope

- Base: `codex/adaptive-fusion-verification`
- Reviewed feature head before repair: `3d316c410f62587d1124d366a8eabfcfd0de1127`
- Repair commits: `7d8b71259493c69dd7f3877e0d4d25a7cf1fa736`, `e6426df`
- Mode: full, read-only architecture/security review with zero-deferral repair loop
- Workflow class: `feature` (`workflow_class_defaulted=false`)

## Iteration 1: BLOCKS MERGE

The independent architecture reviewer found two P1 findings:

1. `verification-run` trusted caller-authored repository JSON and could execute a stale plan against changed or different checkout state.
2. The read-only review boundary accepted an arbitrary caller-selected exclusion, was not physically bound to the EventStore run root, and had no stable launcher capture/compare commands.

## Repair

- Verification now captures live HEAD, tree, tracked diff, untracked content, branch/worktree state, and repository scope from the pinned checkout immediately before spawn. Plan and expected evidence must both match that live capture.
- Review boundary capture/compare now derives the sole exclusion from the canonical EventStore run root, persists content-addressed pre-state, checks physical repository/run/evidence-root identity, rejects caller exclusions, and exits fail-closed through stable launcher commands.
- A local exact re-review found and repaired one additional TOCTOU path: the persistence CLI originally bypassed post-provider-observation physical identity revalidation. Commit `e6426df` unifies capture, persistence, and compare through the checked path.

## Verification

- Fresh post-repair focused suite: 109 tests passed in 44.732 seconds.
- Full suite from the repair lane: 894 tests, zero Depot-owned failures, one skip, and one unchanged live sibling `assembly-baseplate` invalid UX/persona declaration error.
- `validate-workflow-kernel.py`: canonical runtime and schema/policy pass; suite status is nonzero solely for the same sibling declaration error.
- Workflow contracts, generated manifest/command parity, dependency graph, dual compatibility, composition references, and `git diff --check` pass.
- Regression coverage includes stale/different checkouts, hidden mutations, evidence-root displacement, run-root swaps during observation, real launcher invocation, and stable exit codes.

## Re-review disposition

The requested independent exact repair re-review was attempted twice; the host security filter rejected the second turn before a verdict. The Pipeline caller authorized a bounded local exact closer. That closer inspected both repair diffs, caught the persistence TOCTOU above, required the second repair, inspected the final two-file diff, and reran the 109-test focused suite fresh.

No unresolved P1, P2, or P3 finding remains in the owned diff. No finding was deferred.

VERDICT: APPROVED WITH EXPLICIT EXTERNAL BOUNDARY

## Coverage gaps

- No live browser run: these are backend/plugin chunks and no product UI route/persona was declared for the changed Depot surfaces.
- No GitHub, issue, release, marketplace, or installed-cache mutation was performed.
- The sibling `assembly-baseplate` declaration error remains visible and is not classified as a Depot-owned pass.
