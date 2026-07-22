# Artifact Lifecycle Policy

Governs all files that pipeline and dm-review plugins create in downstream repos.

## Tiers

| Tier | Lifecycle | Gitignored | Cleanup |
|------|-----------|------------|---------|
| **1 -- Ephemeral** | Auto-deleted on run completion (success or failure) | Yes | Orchestrator Step 5b |
| **2 -- Run-scoped** | Deleted after successful run; preserved on failure for debugging | Yes | Orchestrator Step 5b |
| **3 -- Feature-scoped** | Persist until user disposes via delivery gate | No | User choice at Phase 7 GATE |
| **4 -- Durable** | Permanent (ai-memory, committed code, Notion) | N/A | Never |

## Artifact Inventory

### Pipeline artifacts (`plans/<feature-slug>/`)

| File | Tier | Notes |
|------|------|-------|
| `baselines/*.png` | 1 | Pre-implementation screenshots from assess phase |
| `baselines-pre-fix/*.png` | 1 | Fix-pass before screenshots |
| `baselines-post-fix/*.png` | 1 | Fix-pass after screenshots |
| `screenshots/*.png` | 1 | Phase 7 verification screenshots |
| `prompts/*.md` | 2 | Chunk execution prompts consumed by orchestrator |
| `manifest.json` | 2 | Chunk ordering and dependency metadata; retained through terminal observe/compare/metrics |
| `authoritative-receipts.json` | 2 | Cumulative ordered redacted receipt array; canonical input to observe/compare/metrics |
| `.workflow-kernel/repository-scope.json` | 4 | Repository-lifetime durable identity; never Tier 2 and never auto-deleted |
| `.workflow-kernel/runs/<run-id>/run-state.json` | 2 | Canonical lifecycle and lease state; retain the terminal run directory or a durable tombstone until exact-scope Docker absence is proven |
| `.workflow-kernel/runs/<run-id>/events.jsonl` | 2 | Canonical redacted lifecycle ledger paired with the lease state and retained under the same terminal-run rule |
| `pipeline-shadow-observation.json` | 2 | Explicit `authoritative_observation` RunSpec/event snapshot generated after authoritative receipts |
| `pipeline-shadow-prediction.json` | 2 | Immutable, context/digest-bound `independent_prediction`; bound once and never overwritten by re-observation |
| `independent-prediction-receipts.json` | 2 | Independently produced pre-action prediction source; retained with the bound prediction through comparison and deleted only after semantic match |
| `shadow-report.json` | 2 | Predicted-versus-authoritative comparison; never changes run outcome |
| `metrics.json` | 2 | Proposal-only reliability aggregation generated after the terminal receipt |
| `improvement-input-index.json` | 3 | Immutable redaction-safe Stage A index sealed before cleanup; retained with an open draft PR |
| `upstream-improvements.json` | 3 | Authoritative proposal-only Stage B candidate/dedupe report |
| `upstream-improvement-prompt.md` | 3 | Deterministic projection of eligible candidates; never authority over the JSON report |
| `docker/*.json` | 2 | Creation plans/receipts, bound node-status and inventory snapshots, sealed cleanup plans, outcomes, and cleanup receipts |
| `brainstorm.html` | 2 | Design decisions (HTML + `visualDecisions` island) |
| `original-prompt.md` | 3 | User's verbatim input -- ground truth (markdown) |
| `assessment.html` | 3 | Current state report (HTML + cached Key Requirements island) |
| `research.html` | 3 | Findings from research phase (HTML + island) |
| `plan.html` | 3 | Implementation plan (HTML + `chunks`/`decisions` island) |
| `final-requirements-crosscheck.md` | 3 | Delivery proof with evidence types |
| `receipt.md` | 3 | Compact post-cleanup summary (written by Step 5b) |

### Pipeline git refs

Refs are not artifacts -- they are not deleted by tier, but by the safe-to-delete decision table in `plugins/dm-review/skills/review/references/repo-cleanup-contract.md`. That contract is authoritative for everything in this table.

| Ref | Removed when | Notes |
|-----|--------------|-------|
| `.worktrees/pipeline/<feature>/<chunk>/` | clean working tree | Per-chunk workspace, removed in Step 3j; swept in Step 5b |
| `pipeline/<feature>/<chunk-id>` | merged, or zero unique commits | Chunk branch, deleted after its worktree |
| `<featureBranch>` | **never by the orchestrator** | Deleted only with merge proof into `main`/`origin/main`; `-D` forbidden |

### dm-review artifacts

| Path | Tier | Notes |
|------|------|-------|
| `.claude/ux-review/screenshots/<date>/*.png` | 1 | Rotated: only today's date kept |
| `.claude/ux-review/manifest.json` | 2 | Overwritten each run |
| `.claude/ux-review/workflow-kernel/request.json` | 2 | Validated review request with unchanged/defaulted workflow class |
| `.claude/ux-review/workflow-kernel/authoritative-receipts.json` | 2 | Cumulative ordered redacted review receipt array |
| `.claude/ux-review/workflow-kernel/review-shadow-observation.json` | 2 | Explicit authoritative review observation snapshot |
| `.claude/ux-review/workflow-kernel/review-shadow-prediction.json` | 2 | Immutable, context/digest-bound independent review prediction |
| `.claude/ux-review/workflow-kernel/independent-prediction-receipts.json` | 2 | Pre-action review prediction source retained through comparison and deleted only after semantic match |
| `.claude/ux-review/workflow-kernel/{shadow-report,metrics}.json` | 2 | Terminal parity and proposal-only reliability outputs |
| `.claude/ux-review/workflow-kernel/docker/*.json` | 2 | Owned-resource plans, proof snapshots, outcomes, and receipts |
| `todos/*-pending-*.md` | 3 | Active findings -- persist until resolved |
| `todos/*-done-*.md` | 1 | Resolved findings -- auto-cleaned before next review |
| `todos/*-deferred-*.md` | 3 | Tracked debt with justifications -- never auto-cleaned |

### Durable records (Tier 4)

| Record | Store | Written by |
|--------|-------|------------|
| Pipeline session observation | ai-memory (`DepotPlugin:pipeline`) | Orchestrator Step 5 |
| Review session observation | ai-memory (project entity) | review-memory-recorder agent |
| Activity log row | Notion ops dashboard | Pipeline Phase 7 / dm-review Phase 7c |

Protected builder restore blobs are not ordinary artifacts. Store them only in permission-restricted package-owned storage with their own retention/deletion policy. Artifacts, receipts, events, shadow reports, Airlift bundles, and checkpoints may contain only a safe digest projection plus an authoritative receipt reference, never blob bytes or credentials.

## Cleanup Rules

Step 5b runs on every exit path -- success, failure, and every answer to the Phase 7 gate -- in one authoritative order: seal the safe Scout input index; Docker reconciliation; artifact and Git cleanup while preserving terminal shadow inputs; final authoritative cleanup/terminal receipt; shadow observation/comparison/metrics; finalize the Scout JSON and prompt projection; eligible shadow Tier 2 deletion only on semantic `match`; then manifest/receipt-input cleanup on that same match. Receipt fields never precede their Docker/Git/artifact outcomes, `manifest.json` is never removed before terminal observation finishes, and Scout source artifacts are never removed before Stage A seals their approved safe references. The repository scope file is not eligible Tier 2, and parity match alone never authorizes terminal run-state deletion.

### On successful pipeline completion (Step 5b)

1. Complete authoritative Docker terminal reconciliation and capture before/after inventories plus every disposition.
2. Delete Tier 1 plus consumed prompts/brainstorm artifacts and complete Git cleanup/readiness checks. Preserve `manifest.json`, `authoritative-receipts.json`, and shadow/RunSpec artifacts.
3. Write `plans/<feature-slug>/receipt.md` from those completed authoritative outcomes.
4. Append the terminal receipt, run terminal observation, comparison, and metrics using the retained manifest and cumulative receipt array.
5. Finalize `upstream-improvements.json` from the sealed index and exact terminal outcomes, then render `upstream-improvement-prompt.md`; preserve both feature-scoped artifacts.
6. On semantic `match`, delete eligible shadow Tier 2 such as the bound prediction, then delete the consumed manifest, authoritative receipt array, independent prediction source, and Docker plan/proof inputs. The source and bound prediction are never deleted before bind and comparison. Preserve `.workflow-kernel/repository-scope.json` unconditionally. Preserve the terminal run directory unless a fresh Docker inventory filtered by the exact `repository_scope_id` proves zero objects for that exact `(scope_id, run_id)` and contains no matching object whose inspect failed; only then may the directory be replaced by or reduced to a durable terminal tombstone. On any other parity result, preserve all terminal inputs and shadow artifacts for investigation.
6. Report: `Artifact cleanup: removed N files, retained M feature-scoped files`.

Shadow artifacts never authorize cleanup, supply receipt fields, or substitute for an authoritative receipt.

### Kernel scope and terminal-run retention

`.workflow-kernel/repository-scope.json` is repository-lifetime durable state. It
is never a Tier 2 artifact, never participates in semantic-match deletion, and
is never auto-deleted. A terminal run directory remains the authoritative lease
and ownership witness while any Docker object may still carry its scope and run
labels. Before removing detailed run state, obtain a fresh managed inventory
with the exact repository-scope filter, inspect every returned object, and prove
that no inspectable object has the run ID and no uninspectable match remains.
Missing, stale, cross-scope, or partially uninspectable inventory preserves the
run directory. Semantic parity `match` alone never authorizes its deletion.

### On failed pipeline run (Step 5b)

1. Complete authoritative Docker reconciliation and Git cleanup/readiness checks.
2. Delete Tier 1 only; preserve non-shadow Tier 2 for retry/debugging.
3. Write `plans/<feature-slug>/receipt.md` with completed failure and cleanup outcomes.
4. Run shadow observation/comparison/metrics and preserve the manifest, cumulative receipts, Docker proof artifacts, and shadow Tier 2.
5. Report: `Artifact cleanup (partial -- run failed): removed N ephemeral files, preserved prompts for debugging`.

### On user "Done" at Phase 7 GATE

1. Run standard cleanup in the same ordered terminal sequence; do not delete the manifest or receipt inputs before observe/compare/metrics
2. Also delete Tier 3 files, leaving only `receipt.md`

### dm-review screenshot rotation

Before creating today's screenshot directory, delete all previous date directories. Only the current day's screenshots survive to the next review.

### dm-review todo lifecycle

- `*-done-*.md` files auto-cleaned before creating new todos (Phase 6 pre-cleanup)
- `*-deferred-*.md` files never auto-cleaned -- represent tracked debt
- `*-pending-*.md` files persist until resolved via `/dm-review-fix`

## Receipt Format

Written by Step 5b after cleanup. Under 2 KB. This is the durable record that remains after ephemeral/run-scoped artifacts are deleted.

```markdown
# Pipeline Receipt: <feature-slug>

- Date: YYYY-MM-DD
- Branch: <featureBranch>
- Merge: CLEAN | APPROVE WITH FIXES | BLOCKS MERGE
- Chunks: N executed, M parallel
- Mode: full_cli | codex_native | manual_walkthrough
- Workflow class: chore | bug | feature | hotfix | security | investigation | migration
- Workflow class defaulted: true | false

## Evidence
| # | Requirement | Evidence |
|---|-------------|----------|
| 1 | <text> | grep:`...` |
| 2 | <text> | screenshot (cleaned) |
| 3 | <text> | authorize-present:`grep -n "Authorize" internal/handler/foo.go` |
| 4 | <text> | event-published:`grep -n "Publish" internal/service/foo.go` |
| 5 | <text> | docker-test-pass:`docker compose exec app go test ./...` |

## Cleanup
- Ephemeral removed: N files
- Pre-shadow run-scoped removed: N files
- Feature-scoped retained: N files
- Deferred findings: none | <list>
- Docker resources: created N, removed M, missing K, retained/blocked J
- Docker inventory: before <digest/count>, after <digest/count>
- Reconciliation: complete | blocked | unavailable (reason)

## Branch & Worktree Inventory

### Created this run
| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| pipeline/<feature>/03-handlers | chunk-branch | deleted | merged into <featureBranch> |
| <featureBranch> | feature-branch | kept | no merge proof into main |

### Remaining after cleanup
| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| <featureBranch> | feature-branch | not merged -- awaiting PR | `git merge-base --is-ancestor <featureBranch> origin/main` |

- Worktrees before: N   after: M   pruned: K
- Branches deleted: N   blocked: M
- git status --porcelain: clean | <residue>
```

The inventory is mandatory in every receipt, including fix-pass receipts that created no refs. Disposition is `deleted`, `kept`, or `blocked` -- never inferred, never omitted.

## Gitignore Enforcement

See `gitignore-template.md` for canonical entries. The execution-orchestrator's Step 0d enforces these entries at the start of every run -- no passive suggestions.
