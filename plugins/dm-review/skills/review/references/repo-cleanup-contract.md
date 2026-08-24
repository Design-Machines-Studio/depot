# Repository Cleanup Contract

Binding on every automation run that creates git refs in a target repo. Consumers: `pipeline` (`execution-orchestrator` Steps 0e/3b/3j/5b and the three pipeline commands) and `dm-review` (`review` skill Phase 8, `/dm-review-loop`, `/dm-review-fix`).

This file lives in `dm-review` because `pipeline` depends on `dm-review` and the reverse edge would be a cycle. It states the Git rules only. The pipeline worktree implementation lives in `plugins/pipeline/references/execution-worktree-cleanup.md`, loaded only at Steps 3j/5b. The cross-resource terminal convention lives in Workflow Kernel's `exact-owned-cleanup.md`; Docker mechanics remain in `docker-ownership.md`.

A run that leaves orphan worktrees and temp branches behind poisons the next run: `git worktree add` collides on a stale path, `git branch -d` collides on a stale name, and a dirty tree makes the next diff unreadable.

## 1. Ref registry

Every worktree and branch the automation creates is appended to the run's durable exact-resource registry **in the same creation action**, never reconstructed afterward from a glob. `kind` is one of `worktree`, `chunk-branch`, `review-branch`, `feature-branch`. Capture the before state inside the exact-owned run root so the inventory can report a delta without leaving `/tmp` residue.

- **Nothing is deleted outside the exact creation records** -- for pipeline, paths and branches include the unique run ID; for dm-review, only the batch-cleanup branch this invocation created. A ref outside the registry is foreign and left alone, no matter how stale it looks.
- **Nothing registered is silently dropped.** Every registered ref appears in the final inventory with a disposition, even if that disposition is "kept".

Creation and registration are one guarded action: if registration fails after
`git worktree add`, that action rolls back its exact path/ref before returning.
There is no end-of-run namespace sweep. Concurrent runs may share a feature
slug because their run IDs, roots, branch names, and registry records are
distinct. An interruption resumes cleanup from those exact records.

## 2. The cleanup phase is mandatory

It runs on successful completion; on review failure (`BLOCKS MERGE`, findings remaining, REVIEW INCOMPLETE); on chunk- and pipeline-blocking failures, before the failure is reported; and on every answer to a user gate, including "Give feedback" and "Done". Exiting without it is a contract violation. It still runs when the run aborts on an exception -- it is deterministic git and cannot make the failure worse.

Cleanup is plain Git executed by the orchestrator in-process. It is never delegated to a subagent, and never routed through `openrouter-wrapper.sh`, `openrouter-exec.sh`, or a Codex `multi_agent_v1.spawn_agent` call. Deleting refs is not a judgment task. The host invokes the same terminal sequence for `EXIT`, `SIGINT`, and `SIGTERM`; a review abort before execution records an empty inventory and removes its disposable run root.

## 3. Safe-to-delete decision table

Evaluate each registered ref in order. First match wins.

| # | Condition | Test | Action |
|---|---|---|---|
| 1 | Fully merged into its target | `git merge-base --is-ancestor <ref> <target>` exits 0 | **delete** (`-d`) |
| 2 | Abandoned, no unique commits over its own base (base != target) | `git rev-list --count <base>..<ref>` is `0` | **delete** (`-D` permitted) |
| 3 | Recorded worktree path or branch already gone | exact path/ref lookup is absent | **record missing**; run no cleanup command |
| 4 | Worktree has uncommitted or untracked changes | `git -C <path> status --porcelain` non-empty | **keep**, report |
| 5 | Anything else | -- | **keep**, report |

Rows 1 and 2 are the only paths to deletion; there is no "it looks done" path. Row 2 fires only when the branch's base differs from the merge target -- when `base == target`, row 1 matches first and uses the safer `-d`. Check row 3 before probing a worktree: its path is gone, so `git status` can only fail, and probing first mislabels it "unreadable, blocked" with a follow-up command that cannot succeed. A missing exact record is already reconciled and never authorizes a repository-wide prune. Remove a present worktree before deleting its branch. Never suppress git's exit status with `2>/dev/null` -- a silenced `git status` returns empty stdout, reads as "clean", and routes an unreadable worktree straight to removal.

## 4. Feature-branch protection

The main feature branch is **never** deleted without concrete merge proof: a zero exit from `git merge-base --is-ancestor "$featureBranch" main` or the same test against `origin/main`. Absent that, the branch is kept and the receipt says `kept -- no merge proof`. "The review was clean", "the PR was opened", and "the user said done" are not merge proof. `git branch -D` is **forbidden on the feature branch, always** -- no condition unlocks it. Elsewhere, `-D` is permitted only after decision-table row 2 has passed, and every use is recorded in the inventory's Proof column.

## 5. Blocked-removal reporting

For every ref that could not be removed, the receipt records the exact ref, the exact reason, and the exact command a human runs next:

```markdown
| .worktrees/pipeline/auth-map/04-views | worktree | uncommitted changes in internal/view/ | `git -C .worktrees/pipeline/auth-map/04-views status` |
| pipeline/auth-map/04-views | chunk-branch | 2 unique commits, not merged | `git log feature/auth-map..pipeline/auth-map/04-views` |
```

A blocked ref is never reported as cleaned, never counted in the "deleted" total, and never omitted. Reporting a ref as deleted when it still exists is the single worst failure this contract prevents -- it converts a visible mess into an invisible one.

## 6. Next-run readiness checks

After removals, query each registered worktree/ref exactly and run `git status --porcelain` (expect empty). Do not run `git worktree prune` or scan for automation paths; both exceed this invocation's ownership records. Confirm no exact registered disposable path remains. A failing check is reported as failing; it does not block the run's primary result, but the next operator must know what they inherit.

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

**dm-review.** Creates no worktrees. Its cleanup phase reconciles only its exact records, deletes only the batch-cleanup branch it created once row 1 proves it merged, asserts a clean tree, and emits the inventory. Automation refs it did not create are reported under "Remaining after cleanup" with a follow-up command and left alone.

## 9. Non-Git owned resources

This Git table stays authoritative and is not weakened by filesystem or Docker cleanup. The shared terminal order and one-root diagnostic rule are in `exact-owned-cleanup.md`. Containers, networks, and volumes use the workflow kernel's separate positive-ownership contract in `docker-ownership.md`, loaded only when a run creates such a resource. Its invariants: creation-time ownership labels plus a durable registry record are required for current-run cleanup; stale-orphan cleanup additionally requires a complete consistent label set, strict TTL expiry, inspected-time agreement, and fresh authoritative proof that the run lease is inactive, failing closed when that proof is missing or unreadable; cleanup plans carry bounded exact-ID argv only; no prune, wildcard, negative-filter, or name-inference cleanup is permitted. Git follows the same boundary -- its adapter derives candidates from the durable registry and emits a pure exact-argv plan; it never runs Git itself.

Docker dispositions are `removed`, `retained_for_dependency`, `blocked`, `foreign`, or `missing`, each recording kind and ID, run/node owner, lifecycle, action, reason, evidence, and follow-up. `removed` is recorded only after every required command succeeds and the object is absent; a missing execution result is blocked. Successful terminal outcomes are immutable; blocked, retained, and foreign attempts stay reconcilable.
