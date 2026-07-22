# Pipeline Receipt: adaptive-fusion-verification

- Date: 2026-07-23
- Branch: `codex/adaptive-fusion-verification`
- Base: `main`
- Merge: CLEAN; publish as a draft PR because the external Assembly declaration lane remains non-green
- Chunks: 6 executed, 2 parallel
- Mode: `codex_native`
- Isolation: `per-chunk-worktree`
- Workflow class: `feature`
- Workflow class defaulted: `false`
- providerSplit: `{claude: 0, codex: 6, openrouter: 0}`
- eligibleProviderSplit: `{codex: 3, openrouter: 0, targetProfile: codex-20x, routingVariance: codex +35pp / openrouter -35pp}`

## Evidence

| # | Requirement | Evidence |
|---|-------------|----------|
| 1 | Versioned behavioral verification contract | Schema, runtime, mutation/weakening tests, and bind/revision CLI tests pass. |
| 2 | Authoritative bounded feedback and browser recovery | Translation/retry/browser contracts and exact validators pass. |
| 3 | Provenance-preserving dm-review synthesis | Guardrails, consolidator contracts, adapter tests, and final three-lens review are clean. |
| 4 | Adaptive depth without provider/security authority drift | Closed decision profile, routing validator, and ordinary-path validator pass. |
| 5 | Attempt/model economics without double counting | Metrics, identity, ambiguity, intervention, and parity tests pass. |
| 6 | Release and existing safety compatibility | Release inventory is 9 schemas/23 CLI commands; generated, dependency, dual-compat, routing, dm-review, and workflow validators pass. Full 801-test discovery has 1 skipped test, exactly 1 pre-existing live `assembly-baseplate` declaration error, and no Depot-owned failure. |

## Cleanup

- Ephemeral removed: 6 prompt files
- Pre-shadow run-scoped removed: 0 files
- Feature-scoped retained: manifest, authoritative receipts, prediction/observation inputs, cleanup proofs, and final reports because terminal parity is unavailable
- Deferred findings: none
- Docker resources: created 0, removed 0, missing 0, retained/blocked 0
- Reconciliation: complete -- exact current-run and stale-sweep managed inventories were empty

## Branch & Worktree Inventory

### Created this run

| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| `codex/adaptive-fusion-verification` | feature branch | kept | protected for draft PR |
| `.worktrees/pipeline/adaptive-fusion-verification/feature` | worktree | kept | review/PR checkout; exact follow-up below |
| `pipeline/adaptive-fusion-verification/01-behavioral-contract-core` | chunk branch | deleted | merged at `91fa6dd` |
| `.worktrees/pipeline/adaptive-fusion-verification/01-behavioral-contract-core` | worktree | deleted | absent from porcelain inventory |
| `pipeline/adaptive-fusion-verification/04-review-synthesis-provenance` | chunk branch | deleted | merged at `b310635` |
| `.worktrees/pipeline/adaptive-fusion-verification/04-review-synthesis-provenance` | worktree | deleted | absent from porcelain inventory |
| `.worktrees/pipeline/adaptive-fusion-verification/baseline-kernel-check` | worktree | deleted | absent from porcelain inventory |
| `pipeline/adaptive-fusion-verification/02-contract-policy-integration` | chunk branch | deleted | merged at `b4b4280` |
| `.worktrees/pipeline/adaptive-fusion-verification/02-contract-policy-integration` | worktree | deleted | absent from porcelain inventory |
| `pipeline/adaptive-fusion-verification/03-authoritative-pipeline-feedback` | chunk branch | deleted | merged at `947545a` |
| `.worktrees/pipeline/adaptive-fusion-verification/03-authoritative-pipeline-feedback` | worktree | deleted | absent from porcelain inventory |
| `pipeline/adaptive-fusion-verification/05-attempt-economics-and-contribution` | chunk branch | deleted | merged at `421b0df` |
| `.worktrees/pipeline/adaptive-fusion-verification/05-attempt-economics-and-contribution` | worktree | deleted | absent from porcelain inventory |
| `pipeline/adaptive-fusion-verification/06-cross-plugin-release-integration` | chunk branch | deleted | merged at `b7e65c8` |
| `.worktrees/pipeline/adaptive-fusion-verification/06-cross-plugin-release-integration` | worktree | deleted | absent from porcelain inventory |

### Remaining after cleanup

| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| `codex/adaptive-fusion-verification` | feature branch | open draft PR | `git branch -d codex/adaptive-fusion-verification` after merge |
| `.worktrees/pipeline/adaptive-fusion-verification/feature` | worktree | open draft PR checkout | `git worktree remove .worktrees/pipeline/adaptive-fusion-verification/feature` after review |

- Worktrees before: 12   after: 4   pruned: 8
- Branches deleted: 6   blocked: 0
- git status --porcelain: clean at terminal review HEAD `42a3682`
