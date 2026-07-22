# Fresh Final dm-review Prompt

Run a fresh, independent, read-only full dm-review in:

`/Users/trav/Websites/design-machines/depot/.worktrees/pipeline/depot-mechanical-workflow-hardening/feature`

Review the exact committed diff:

- Base: `codex/adaptive-fusion-verification`
- Feature: `codex/depot-mechanical-workflow-hardening`
- Target HEAD at prompt generation: `e6426df9ab0bb53c78298a90a462f444819eb72e`
- Diff: `codex/adaptive-fusion-verification..e6426df9ab0bb53c78298a90a462f444819eb72e`
- Workflow class: `feature` (`workflow_class_defaulted=false`)

Inspect architecture, security, stale-state invalidation, read-only boundaries, filesystem/process safety, browser recovery, provider-neutral CI/closeout semantics, exact Docker ownership, cleanup, generated Claude/Codex parity, and release integration. Read actual implementations and hostile tests; do not rubber-stamp structural presence.

Known context not to reflag as a Depot-owned defect: the live sibling checkout `/Users/trav/Websites/design-machines/assembly-baseplate` currently contains one invalid UX/persona task frontmatter declaration. The complete Depot suite reports that external integration error while 894 tests otherwise have zero Depot-owned failures and one skip. Verify the boundary remains visible; do not relabel it as owned success.

The run is `noMergeOnCompletion=true`. Do not merge, publish, release, mutate PR/issue state, refresh installed caches, or edit files. Report only current unresolved P1/P2/P3 findings with exact path and evidence, followed by a merge verdict and explicit coverage gaps.
