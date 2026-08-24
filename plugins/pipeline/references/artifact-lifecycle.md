# Artifact Lifecycle Policy

Governs all files that pipeline and dm-review plugins create in downstream repos.

## Tiers

| Tier | Lifecycle | Gitignored | Cleanup |
|------|-----------|------------|---------|
| **1 -- Ephemeral** | Auto-deleted on run completion (success or failure) | Yes | Orchestrator Step 5b |
| **2 -- Run-scoped** | Deleted on every terminal path after compact evidence projection | Yes | Orchestrator Step 5b |
| **3 -- Feature-scoped** | Persist until user disposes via delivery gate | No | User choice at Phase 7 GATE |
| **4 -- Durable** | Permanent (ai-memory, committed code) | N/A | Never |

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
| `.workflow-kernel/runs/<run-id>/run-state.json` | 2 | Canonical lifecycle and lease state; remove after terminal projection and fresh exact-scope Docker absence, or retain only inside the one bounded diagnostic root |
| `.workflow-kernel/runs/<run-id>/events.jsonl` | 2 | Canonical redacted lifecycle ledger; remove with the run root unless selected as bounded diagnostic evidence |
| `pipeline-shadow-observation.json` | 2 | Explicit `authoritative_observation` RunSpec/event snapshot generated after authoritative receipts |
| `pipeline-shadow-prediction.json` | 2 | Immutable, context/digest-bound `independent_prediction`; bound once and never overwritten by re-observation |
| `independent-prediction-receipts.json` | 2 | Independently produced pre-action prediction source; retained with the bound prediction through comparison and deleted only after semantic match |
| `shadow-report.json` | 2 | Predicted-versus-authoritative comparison; never changes run outcome |
| `metrics.json` | 2 | Proposal-only reliability aggregation generated after the terminal receipt |
| `docker/*.json` | 2 | Creation plans/receipts, bound node-status and inventory snapshots, sealed cleanup plans, outcomes, and cleanup receipts |
| `brainstorm.html` | 2 | Design decisions (HTML + `visualDecisions` island) |
| `original-prompt.md` | 3 | User's verbatim input -- ground truth (markdown) |
| `assessment.html` | 3 | Current state report (HTML + cached Key Requirements island) |
| `research.html` | 3 | Findings from research phase (HTML + island) |
| `plan.html` | 3 | Implementation plan (HTML + `chunks`/`decisions` island) |
| `final-requirements-crosscheck.md` | 3 | Delivery proof with evidence types |
| `receipt.md` | 3 | Compact post-cleanup summary; Step 5b writes the base receipt and a capable caller appends memory-capture status after a write, exact duplicate, or callable-tool failure |

### Pipeline git refs

Refs are not artifacts -- they are not deleted by tier, but by the safe-to-delete decision table in `plugins/dm-review/skills/review/references/repo-cleanup-contract.md`. That contract is authoritative for everything in this table.

| Ref | Removed when | Notes |
|-----|--------------|-------|
| `.worktrees/pipeline/<run-id>/<chunk>/` | clean working tree | Per-chunk workspace, removed in Step 3j or exact-record reconciliation in Step 5b |
| `pipeline/<run-id>/<chunk-id>` | merged, or zero unique commits | Chunk branch, deleted after its worktree |
| `<featureBranch>` | **never by the orchestrator** | Deleted only with merge proof into `main`/`origin/main`; `-D` forbidden |

### dm-review artifacts

| Path | Tier | Notes |
|------|------|-------|
| `<exact-run-root>/review/screenshots/*.png` | 1 | Raw screenshot evidence owned only by this invocation |
| `<exact-run-root>/review/manifest.json` | 2 | Run-scoped screenshot index |
| `.claude/ux-review/report.md` | 3 | Complete unified review, including findings, coverage, cleanup, provenance, and collapsed raw reports |
| `<exact-run-root>/review/workflow-kernel/request.json` | 2 | Validated review request with unchanged/defaulted workflow class |
| `<exact-run-root>/review/workflow-kernel/authoritative-receipts.json` | 2 | Cumulative ordered redacted review receipt array |
| `<exact-run-root>/review/workflow-kernel/review-shadow-observation.json` | 2 | Explicit authoritative review observation snapshot |
| `<exact-run-root>/review/workflow-kernel/review-shadow-prediction.json` | 2 | Immutable, context/digest-bound independent review prediction |
| `<exact-run-root>/review/workflow-kernel/independent-prediction-receipts.json` | 2 | Pre-action review prediction source retained through comparison, then deleted |
| `<exact-run-root>/review/workflow-kernel/{shadow-report,metrics}.json` | 2 | Terminal parity and proposal-only reliability inputs; compact conclusions project into the report |
| `<exact-run-root>/review/workflow-kernel/docker/*.json` | 2 | Owned-resource plans, proof snapshots, outcomes, and receipts |
| `todos/*-pending-*.md` | 3 | Active findings -- persist until resolved |
| `todos/*-done-*.md` | 1 | Resolved findings -- auto-cleaned before next review |
| `todos/*-deferred-*.md` | 3 | Tracked debt with justifications -- never auto-cleaned |

### Durable records (Tier 4)

| Record | Store | Written by |
|--------|-------|------------|
| Pipeline session observation (optional) | ai-memory (`DepotPlugin:pipeline`) | Capable Pipeline caller after orchestrator Step 5 prepares the handoff |
| Review session observation (optional) | ai-memory (project entity) | review-memory-recorder agent when its tools are callable |

Protected builder restore blobs are not ordinary artifacts. Store them only in permission-restricted package-owned storage with their own retention/deletion policy. Artifacts, receipts, events, shadow reports, Airlift bundles, and checkpoints may contain only a safe digest projection plus an authoritative receipt reference, never blob bytes or credentials.

## Cleanup Rules

Step 5b runs on every exit path -- success, failure, and every answer to the Phase 7 gate -- in one authoritative order: Docker reconciliation; artifact and Git cleanup while preserving terminal shadow inputs; final authoritative cleanup/terminal receipt; shadow observation/comparison/metrics; compact evidence projection; then exact-owned run-root cleanup. Receipt fields never precede their Docker/Git/artifact outcomes, and `manifest.json` is never removed before terminal observation finishes. The repository scope file is not eligible Tier 2, and parity match alone never authorizes terminal run-state deletion.

### On successful pipeline completion (Step 5b)

1. Complete authoritative Docker terminal reconciliation and capture before/after inventories plus every disposition.
2. Delete Tier 1 plus consumed prompts/brainstorm artifacts and complete Git cleanup/readiness checks. Preserve `manifest.json`, `authoritative-receipts.json`, and shadow/RunSpec artifacts.
3. Write `plans/<feature-slug>/receipt.md` from those completed authoritative outcomes.
4. Append the terminal receipt, run terminal observation, comparison, and metrics using the retained manifest and cumulative receipt array.
5. Delete consumed Tier 2 inputs after comparison regardless of parity. Project the compact parity result into `receipt.md`; raw predictions, manifests, receipts, and Docker proof inputs remain disposable. Preserve `.workflow-kernel/repository-scope.json` unconditionally. Remove the terminal run directory only after a fresh Docker inventory filtered by the exact `repository_scope_id` proves zero objects for that exact `(scope_id, run_id)` and contains no matching object whose inspect failed. Otherwise retain that directory as the one named bounded diagnostic root and report its exact safe cleanup command. Never retain a second raw-output root.
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
2. Delete Tier 1 and Tier 2 after projecting compact failure evidence into the receipt. A genuinely useful bounded subset may remain only inside the one named diagnostic root.
3. Write `plans/<feature-slug>/receipt.md` with completed failure and cleanup outcomes.
4. Run shadow observation/comparison/metrics, project compact conclusions, and remove raw inputs.
5. Report either complete cleanup or the diagnostic root's exact path, reason, contents, and safe removal command.

### On user "Done" at Phase 7 GATE

1. Run standard cleanup in the same ordered terminal sequence; do not delete the manifest or receipt inputs before observe/compare/metrics
2. Also delete Tier 3 files, leaving only `receipt.md`

### dm-review screenshot cleanup

Screenshots are created only beneath this invocation's exact-owned run root and
removed on every terminal path after the durable report is written. Review code
never rotates, scans, or deletes another run's screenshots.

### dm-review todo lifecycle

- `*-done-*.md` files auto-cleaned before creating new todos (Phase 6 pre-cleanup)
- `*-deferred-*.md` files never auto-cleaned -- represent tracked debt
- `*-pending-*.md` files persist until resolved via `/dm-review-fix`

## Receipt Format

Completed in up to two stages and kept under 2 KB. Step 5b writes the base
receipt after cleanup and MUST omit any `- Memory capture:` field because the
orchestrator does not know whether the optional personal-memory capability is
callable. A capable caller that successfully consumes the handoff appends
exactly one terminal `- Memory capture: written | already-present | failed --
<safe reason>` field. `Memory capture: failed -- <safe reason>` preserves
nonblocking evidence only when discovered callable tools fail during lookup or
write. When the tools are absent, the caller leaves the base receipt unchanged
and emits no absence or degraded-completion notice. The caller never rewrites
the authoritative Step 5b fields.

```markdown
# Pipeline Receipt: <feature-slug>

- Date: YYYY-MM-DD
- Branch: <featureBranch>
- Base: <baseBranch>
- Merge: CLEAN | APPROVE WITH FIXES | BLOCKS MERGE | BLOCKED PENDING CALLER VERIFICATION | BLOCKED PENDING REMOTE VERIFICATION
- Chunks: N executed, M parallel
- Mode: full_cli | codex_native | manual_walkthrough
- Isolation: per-chunk-worktree | sequential-on-branch
- providerSplit: `{claude: N, codex: N, openrouter: N}`
- eligibleProviderSplit: `{codex: N, openrouter: N, targetProfile: <name>, routingVariance: <measured>}`
- Workflow class: chore | bug | feature | hotfix | security | investigation | migration
- Workflow class defaulted: true | false

## Evidence
| # | Requirement | Evidence |
|---|-------------|----------|
| 1 | <text> | grep:`...` |
| 2 | <text> | screenshot (cleaned) |
| 3 | <text> | authorize-present:`grep -n "Authorize" internal/handler/foo.go` |
| 4 | <text> | event-published:`grep -n "Publish" internal/service/foo.go` |
| 5 | <text> | repository-verification:`go-full-non-race` current result, plan digest `<sha256:...>` |

## Cleanup
- Ephemeral removed: N files
- Pre-shadow run-scoped removed: N files
- Feature-scoped retained: N files
- Remaining findings: none | <list; any entry means NEEDS ATTENTION>
- Docker resources: created N, removed M, missing K, retained/blocked J
- Docker inventory: before <digest/count>, after <digest/count>
- Reconciliation: complete | blocked | unavailable (reason)

## Branch & Worktree Inventory

### Created this run
| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| pipeline/<run-id>/03-handlers | chunk-branch | deleted | merged into <featureBranch> |
| <featureBranch> | feature-branch | kept | no merge proof into main |

### Remaining after cleanup
| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| <featureBranch> | feature-branch | not merged -- awaiting PR | `git merge-base --is-ancestor <featureBranch> origin/main` |

- Worktrees created: N   removed: M   missing: K   blocked: J
- Branches deleted: N   blocked: M
- git status --porcelain: clean | <residue>
```

The inventory is mandatory in every receipt, including fix-pass receipts that created no refs. Disposition is `deleted`, `kept`, or `blocked` -- never inferred, never omitted.

## Gitignore Enforcement

See `gitignore-template.md` for canonical entries. The execution-orchestrator's Step 0d enforces these entries at the start of every run -- no passive suggestions.
