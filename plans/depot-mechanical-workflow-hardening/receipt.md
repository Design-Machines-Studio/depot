# Pipeline Receipt: depot-mechanical-workflow-hardening

- Date: 2026-07-22
- Branch: `codex/depot-mechanical-workflow-hardening`
- Base: `codex/adaptive-fusion-verification`
- Merge: `APPROVE WITH FIXES`; keep unmerged as required by `noMergeOnCompletion=true`
- Chunks: 8 executed, maximum 3 concurrent at one dependency level
- Mode: `codex_native`
- Isolation: `per-chunk-worktree`
- Workflow class: `feature`
- Workflow class defaulted: `false`
- providerSplit: `{claude: 0, codex: 8, openrouter: 0}` implemented chunks
- eligibleProviderSplit: `{codex: 7, openrouter: 0, targetProfile: codex-20x, routingVariance: codex +35pp / openrouter -35pp}`
- Usage/cost: unavailable; no zero or estimate substituted

## Evidence

| # | Requirement | Evidence |
|---|---|---|
| 1 | Preserve isolated stacked branch; no merge/release/cache publication. | `manifest.json`, `ref-registry.md`, no-merge proof and protected feature branch. |
| 2 | Deterministic configurable verification planner. | Repository planner/runtime/schema, Assembly profile/adapter, focused tests. |
| 3 | Tiered authority-preserving verification ladder. | Profile/planner selection and remote/post-merge authority tests. |
| 4 | Read-only review; explicit mutation-only fix paths. | dm-review contracts plus EventStore boundary commands/tests. |
| 5 | Exact state binding and stale invalidation. | Live repository capture, evidence binding, physical boundary identity, hostile tests. |
| 6 | Structured incremental findings. | Finding/lane schemas, persistence/consolidation, provenance tests. |
| 7 | Executable browser scenarios and immutable bundle. | Browser modules/schemas/recovery and bundle tests. |
| 8 | Artifact sensitivity/redaction/staging allowlist. | Artifact runtime/schema and hostile tests. |
| 9 | Provider-neutral CI evidence. | CI normalizer/schema/CLI/tests. |
| 10 | PR/issue closeout audit. | Closeout runtime/schema/CLI/tests. |
| 11 | Correct cross-plugin ownership and shadow-first judgment fences. | Kernel mechanics, Assembly defaults, Pipeline/dm-review consumers. |
| 12 | Hostile/release/canonical validation. | 109 focused pass; 894 full-suite tests with zero owned failures; canonical validator group pass. |
| 13 | Evidence-only economics. | `run-postmortem.md` and metrics ledger; unavailable telemetry remains unavailable. |
| 14 | Final cross-check and fresh review prompt. | `final-requirements-crosscheck.md`, `final-dm-review.md`, `final-dm-review-prompt.md`. |
| 15 | Proposal-only every-run Improvement Scout. | Sealed Stage A index; terminal structured report and generated prompt. |

## Review

- Independent final review initially: `BLOCKS MERGE` with two P1 findings.
- Zero-deferral repair commits: `7d8b712`, `e6426df`.
- Fresh focused verification after final repair: 109 tests passed in 44.732 seconds.
- Final owned findings: P1 0, P2 0, P3 0; deferred 0.
- Independent repair re-review: attempted, but the host security filter refused the turn. The authorized bounded local exact closer found the persistence TOCTOU, required `e6426df`, then approved the exact repair after fresh tests.
- External boundary: one live sibling `assembly-baseplate` invalid UX/persona declaration remains the only full-suite error; it is not a Depot-owned pass or owned failure.

## Cleanup

- Ephemeral removed: 0 files (Tier 1 directories absent)
- Pre-shadow run-scoped removed: 8 Tier 2 chunk prompt files
- Feature-scoped retained at cleanup boundary: 54 files
- Deferred findings: none
- Docker resources: created 0, removed 0, missing 0, retained/blocked 0
- Reconciliation: complete for current run and stale sweep; exact managed inventories empty
- Broad Docker prune: not used

## Branch & Worktree Inventory

### Created this run

| Ref | Kind | Disposition | Proof |
|---|---|---|---|
| `codex/depot-mechanical-workflow-hardening` | feature branch | kept | no merge proof; protected by `noMergeOnCompletion=true` |
| 8 paths under `.worktrees/pipeline/depot-mechanical-workflow-hardening/<chunk>` | chunk worktrees | deleted | each clean after merge; recorded individually in `ref-registry.md` |
| 8 refs under `pipeline/depot-mechanical-workflow-hardening/<chunk>` | chunk branches | deleted | each was an ancestor of the feature branch; recorded individually in `ref-registry.md` |

### Remaining after cleanup

| Ref | Kind | Reason kept | Follow-up command |
|---|---|---|---|
| `codex/depot-mechanical-workflow-hardening` | feature branch/worktree | delivery branch; no merge proof | review the draft PR; do not delete until explicitly merged or abandoned |

- Worktrees before terminal prune: 5; after: 5; pruned: 0
- Owned chunk branches deleted over run: 8; blocked: 0
- Unrelated worktrees/branches: untouched
- Repository status at receipt construction: owned terminal artifacts awaiting the final checkpoint commit; no unrelated residue in this worktree

## Terminal observation boundary

The authoritative Pipeline result is successful with the external boundary above. Shadow comparison and metrics run after this receipt is appended. Any parity gap remains observation-only and cannot change this receipt, merge state, cleanup, or review disposition.

Terminal shadow result: `unsafe_to_promote` with `semantic_transition_difference`; `safe_to_promote=false`. The observer consumed all 52 authoritative events but reported `prediction_bound=false`. Prediction, observation, comparison, metrics, manifest, receipts, and Docker terminal inputs are retained for diagnosis.

## Upstream Improvement Scout

- Structured authority: `upstream-improvements.json`
- Report digest: `sha256:8baa51fbf41ef2c545844f0d84e5a21d9b4b3779de2f9bc03e724f58a8dcf33d`
- Generated prompt: `upstream-improvement-prompt.md` (`sha256:d4c2519343eb72eafe853bca637661b9d7532cfea3f5eeca305696ce459a541e`)
- Eligible proposal: recurring split of Depot-owned release results from live sibling compatibility evidence.
- Eligible proposal: one-off pre-action shadow-binding self-check.
- Deduplicated completed controls: pre-export privacy return-to-Codex; live repository and EventStore-bound review verification.
- Authority: proposal only; no scheduling, source mutation, merge, release, publication, or installed-cache refresh.
