# Extracted conditional reference

### Orchestrator Blind Spots (read before starting Phase 7)

The execution-orchestrator verifies per-chunk, but `curl` + `grep` + HTML regex CANNOT observe:

- **JS runtime state** -- whether `window.assemblyPopup` actually attached, whether an event listener bound, whether a module imported.
- **Visual cardinality** -- whether a button appears "exactly once" vs duplicated via a second code path that independently satisfies the same DOM assertion.
- **Layout regressions** -- whether a neighboring card got pushed off-screen by your margin change.
- **Duplicate elements** -- an AC saying "Post comment button is present" passes when there are two Post comment buttons as long as at least one is there.

Any `renderedSurface: required` receipt without complete browser evidence is blocked, regardless of host execution mode. Required browser cases run the recovery ladder below and cannot be delivered until complete or `human_help_required` is resolved. A validated `not_applicable` receipt carries its rationale and requires no fabricated browser evidence.

### Ambiguity Protocol Check (pipeline v1.10.0+)

The three-layer ambiguity defence added in v1.10.0 leaves an audit trail. Inspect each chunk's commit and receipt:

- **Commit trailers** -- each chunk commit may contain two trailers: `Chose: <interpretation>` and `Rejected: <alt-1>; <alt-2>`. Extract with `git log <featureBranch> --format=%B | git interpret-trailers --parse --only-trailers` or grep. Trailers are emitted only when a subagent had to pick between defensible interpretations in autonomous mode.
- **Receipt flag** -- chunk receipts may include `ambiguity_resolved: true` with a one-line summary. Cross-check against the commit trailers.
- **If trailers or the flag are present,** review the chosen path. If the chosen interpretation conflicts with what the user actually wanted, this is a Phase 7 gap -- fix inline on the feature branch, then re-run `/dm-review-quick` on the affected chunk.
- **If neither signal is present,** either the chunks were unambiguous OR the subagents silently picked. The plan-adversary's scope review should have caught the latter at Phase 5; if you suspect it didn't, sample one or two chunks' rendered output against the approved Key Requirements before approving merge.

