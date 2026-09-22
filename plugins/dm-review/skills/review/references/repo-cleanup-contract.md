# Repository Cleanup Contract

Binding on every automation run that creates files or git refs in a target repo. Consumers: `pipeline` (`execution-orchestrator` Steps 0e/3b/3j/5b and the three pipeline commands) and `dm-review` (`review` skill Phase 8, `/dm-review-loop`, `/dm-review-fix`).

This file owns Git rules. Pipeline mechanics live in
`execution-worktree-cleanup.md`; cross-resource lifecycle and Docker remain in
Workflow Kernel.

## 1. Ref registry

Every worktree and branch the automation creates is appended to the run's durable exact-resource registry **in the same creation action**, never reconstructed afterward from a glob. `kind` is one of `worktree`, `chunk-branch`, `review-branch`, `feature-branch`. Capture the entry status, registered-worktree set, and before state inside the exact-owned run root so completion compares against the baseline rather than demanding that pre-existing changes disappear.

- **Nothing is deleted outside exact creation records.** Unregistered refs are foreign.
- **Nothing registered is silently dropped.** Every registered ref appears in the final inventory with a disposition, even if that disposition is "kept".

Creation and registration are one guarded action; registration failure rolls
back that exact creation. Runs use distinct IDs and resume exact records.

A host-created worktree is adopted only from explicit host creation/handoff
metadata. Load `host-worktree-cleanup.md` when such metadata exists; otherwise
it is foreign.

## 2. The cleanup phase is mandatory

It runs on success, every failure/abort, and every user-gate answer before
reporting. Exiting without it is a contract violation.

Cleanup is plain in-process Git, never model-delegated. The host uses the same
sequence for `EXIT`, `SIGINT`, and `SIGTERM`; a pre-execution abort records an
empty inventory and removes its disposable root.

## Task changes and delivery

Authorized implementation/repairs include commit and push to the existing PR
unless explicitly local-only. Settle exact task-owned source/docs/lessons and
tracked cleanup changes, run applicable checks, then verify local feature HEAD equals the remote PR
head. Do not merely suggest committing or stage foreign changes. Failed push
means incomplete delivery. Read-only review grants no repair authority. Keep
runtime evidence in its existing artifact location; avoid unsolicited lessons.

After the last UI repair, rebuild/recheck the maintained site and leave the
reviewed feature branch or exact detached head available for the operator.
Report `Preview: <domain> — <serving checkout> — <branch/head>` with existing
browser/build proof or the concrete blocker. Never repoint the server to an
implementation worktree, restore main by default or remove the serving folder.

## Final readiness

When a run captures browser artifacts, load `browser-artifact-cleanup.md` before
capture and apply it at closeout, including standalone visual review. Use exact
owned paths and preserve linked evidence before removing disposable copies.
After all report/receipt writes, check every used checkout against its baseline.
Deliver intentional changes and remove run-owned residue before reporting
`Next chunk: ready`; otherwise name exact paths and blockers. Preserve foreign
work and the running feature preview. A clean code verdict does not prove cleanup.

## 3. Safe-to-delete decision table

Evaluate each registered ref in order. First match wins.

| # | Condition | Test | Action |
|---|---|---|---|
| 1 | Fully merged into its target | `git merge-base --is-ancestor <ref> <target>` exits 0 | **delete** (`-d`) |
| 2 | Abandoned, no unique commits over its own base (base != target) | `git rev-list --count <base>..<ref>` is `0` | **delete** (`-D` permitted) |
| 3 | Recorded worktree path or branch already gone | exact path/ref lookup is absent | **record missing**; run no cleanup command |
| 4 | Worktree has uncommitted or untracked changes | `git -C <path> status --porcelain` non-empty | **keep**, report |
| 5 | Anything else | -- | **keep**, report |

Only rows 1–2 delete. Row 2 requires base != target; row 1 handles equal
base/target with `-d`. Check absence before status, remove worktree before
branch, and never suppress Git exit status. Missing records never authorize
pruning. Do not run `git worktree prune`.

## 4. Feature-branch protection

Delete the feature branch only after `git merge-base --is-ancestor` proves it
merged into `main` or `origin/main`; otherwise record `kept -- no merge proof`.
`git branch -D` is always forbidden for it and requires row 2 elsewhere.

## 5. Blocked-removal reporting

For every ref that could not be removed, the receipt records the exact ref, the exact reason, and the exact command a human runs next:

```markdown
| .worktrees/pipeline/auth-map/04-views | worktree | uncommitted changes in internal/view/ | `git -C .worktrees/pipeline/auth-map/04-views status` |
| pipeline/auth-map/04-views | chunk-branch | 2 unique commits, not merged | `git log feature/auth-map..pipeline/auth-map/04-views` |
```

A blocked ref is never reported as cleaned, never counted in the "deleted" total, and never omitted. Reporting a ref as deleted when it still exists is the single worst failure this contract prevents -- it converts a visible mess into an invisible one.

## 6. Next-run readiness checks

After removals, query each registered worktree/ref exactly and compare status
with the entry baseline plus intentional task-owned changes. Preserve and
report pre-existing/concurrent residue; fail only new unexplained residue or
exact-owned removal. Never prune or scan automation namespaces.

## 7. Final inventory block

Emitted verbatim into every receipt and terminal report.

```markdown
## Branch & Worktree Inventory

### Created this run
| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| pipeline/auth-map/03-handlers | chunk-branch | deleted | merged into feature/auth-map |
| feature/auth-map | feature-branch | kept | no merge proof into main |

### Remaining after cleanup
| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| feature/auth-map | feature-branch | not merged to main -- awaiting PR | `git merge-base --is-ancestor feature/auth-map origin/main` |

- Worktrees created: 3   removed: 2   missing: 1   blocked: 0
- Branches deleted: 3   blocked: 0
- git status --porcelain: clean
```

Disposition is one of `deleted`, `kept`, `blocked`. Every registered ref appears exactly once in "Created this run"; every `kept` or `blocked` ref appears again in "Remaining after cleanup" with a follow-up command.

## 8. Per-consumer notes

**pipeline.** Registers at Step 0e (before state) and Step 3b (each worktree + chunk branch); applies the decision table at Step 3j per chunk and again at Step 5b to any still-active exact record. The feature branch is registered only when this invocation creates it and is never deleted by the orchestrator.

**pipeline-fix.** Runs on the current feature branch with `noMergeOnCompletion: true`, creates no refs, so cleanup deletes nothing. It still emits the inventory and readiness checks.

**dm-review.** Ordinarily creates no worktrees; a host-owned handoff follows
`host-worktree-cleanup.md`. Reconcile exact records, compare against the entry
baseline, and leave foreign refs alone.

## 9. Non-Git owned resources

This Git table stays authoritative and is not weakened by filesystem or Docker cleanup. The shared terminal order and one-root diagnostic rule are in `exact-owned-cleanup.md`. Containers, networks, and volumes use the workflow kernel's separate positive-ownership contract in `docker-ownership.md`, loaded only when a run creates such a resource. Its invariants: creation-time ownership labels plus a durable registry record are required for current-run cleanup; stale-orphan cleanup additionally requires a complete consistent label set, strict TTL expiry, inspected-time agreement, and fresh authoritative proof that the run lease is inactive, failing closed when that proof is missing or unreadable; cleanup plans carry bounded exact-ID argv only; no prune, wildcard, negative-filter, or name-inference cleanup is permitted. Git follows the same boundary -- its adapter derives candidates from the durable registry and emits a pure exact-argv plan; it never runs Git itself.

Docker dispositions are `removed`, `retained_for_dependency`, `blocked`, `foreign`, or `missing`, each recording kind and ID, run/node owner, lifecycle, action, reason, evidence, and follow-up. `removed` is recorded only after every required command succeeds and the object is absent; a missing execution result is blocked. Successful terminal outcomes are immutable; blocked, retained, and foreign attempts stay reconcilable.
