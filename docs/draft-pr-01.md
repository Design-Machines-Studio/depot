# DRAFT-PR-01

The reviewed publisher can open one early draft after committed, pushed source
and the repository's basic publication checks pass. `draft` does not call the
review producer. `create`, `request-review`, and `ready` still require complete
preserved coverage; ready additionally refreshes CI and feedback and checks
acceptance. The helper never merges.

The current owner records repository policy, actual basic checks and public-safe
labels in the existing readiness input. See
[the calling contract](../plugins/dm-review/skills/review/references/automatic-implementation-closeout.md#optional-early-draft).
Retry reuses a matching open draft and refreshes its exact-head summary.
Publication is serialized by the workflow owner; do not run two publishers for
the same branch concurrently.

## Source verification and later consumer proof

`tools/test-publish-reviewed-pr.sh` uses a disposable repository, real Kernel
ownership/producer and mocked GitHub. It tests replaced-directory failure,
early draft creation, strict rejection, original identity restoration and
existing-evidence recovery. These fixtures are not a live consumer canary.

After separate merge/release authority, prepare dm-review-v1.90.0 and
pipeline-v1.75.0 against the final integrated merge commit. Reconcile PR #192's
separate router/dm-review/Pipeline floors and versions when integrating; retain
the stronger floors and do not copy its optional-design source into this PR.
Run `./tools/check-release-preflight.sh --source-only` before tags, then use the normal Claude marketplace/plugin
update and Codex marketplace/plugin add/update procedure. Verify both installed
bundles against tagged source and run the default release preflight; do not edit caches or claim source fixtures prove
installed behavior. No Kernel release is needed.

Coordinate the later canary with the livewires-templ owner on board exchange
b4f087758a484d088884e2fb3405f853. Use a new owner-approved disposable consumer
branch/run, never the active product run. Prove one actual GitHub draft exists
before export completes, retry reuses its URL, and strict ready rejects while
acceptance/export is incomplete. Keep required CI pending, including checks
excluded on drafts; after completing strict candidate evidence, use
request-review, inspect actual GitHub results and fresh feedback, then verify
ready. Preserve receipts privately. No product source changes or merge are
part of this source PR.

## Removal conditions

Retain each task worktree, feature branch, private review outputs and run evidence
while its PR is open. Remove only task-owned disposable test directories after
their checks finish. After merge or an explicit abandonment decision and verified
evidence preservation, remove these task worktrees normally; keep unmerged refs.
