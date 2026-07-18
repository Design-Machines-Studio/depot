# Repository Cleanup Contract

Binding on every automation run that creates git refs in a target repo. Two consumers:

- `pipeline` -- `execution-orchestrator` Steps 0e / 3b / 3j / 5b, and the `/pipeline`, `/pipeline-run`, `/pipeline-fix` commands.
- `dm-review` -- `review` skill Phase 8, `/dm-review-loop`, `/dm-review-fix`.

This file lives in `dm-review` because `pipeline` depends on `dm-review` and the reverse edge would be a cycle. It is not a review reference; it is a run-hygiene contract that both plugins read.

The contract exists because a run that leaves orphan worktrees and temp branches behind poisons the next run: `git worktree add` collides on a stale path, `git branch -d` collides on a stale name, and a dirty tree makes the next diff unreadable.

## 1. Ref registry

Every worktree and branch the automation creates is appended to an in-run registry **at the moment it is created**, never reconstructed afterward from a glob.

```text
| Ref | Kind | Created at step | Base |
| .worktrees/pipeline/auth-map/03-handlers | worktree | 3b | feature/auth-map |
| pipeline/auth-map/03-handlers | chunk-branch | 3b | feature/auth-map |
| feature/auth-map | feature-branch | 1 | main |
```

`kind` is one of `worktree`, `chunk-branch`, `review-branch`, `feature-branch`.

Two invariants:

- **Nothing is deleted outside the automation's owned path namespace.** For pipeline that namespace is `.worktrees/pipeline/<feature>/` and branches matching `pipeline/<feature>/*`; for dm-review it is the single batch-cleanup branch it created. A ref outside it is not the run's business, no matter how stale it looks. Report it, leave it.
- **Nothing registered is silently dropped.** Every registered ref appears in the final inventory with a disposition, even if that disposition is "kept".

The registry is the primary authority, but it cannot be the *only* one. A run that dies between `git worktree add` and registration leaves an orphan no registry knows about, and the end-of-run sweep is the only thing that will ever find it. So the sweep is scoped by **path namespace**, not by registry membership -- deliberately wider than the registry, and deliberately narrower than the repo.

The cost of that widening: **two concurrent runs on the same feature slug will sweep each other's worktrees.** Run A's sweep cannot distinguish run B's live, clean, registered worktree from a crash orphan -- both sit under `.worktrees/pipeline/<feature>/`. Only *clean* worktrees are removed, so no uncommitted work is lost and the branches survive, but run B loses its workspace mid-flight. Feature slugs must therefore be unique per concurrent run. If two runs must share a slug, neither may sweep; each cleans only its own registered refs and reports the rest.

Capture the *before* state at run start, so the inventory can report a delta rather than an absolute:

```bash
git worktree list --porcelain > "$REFS_BEFORE"
git branch --list > "$BRANCHES_BEFORE"
```

## 2. The cleanup phase is mandatory

It runs on:

- successful completion;
- review failure (`BLOCKS MERGE`, findings remaining, REVIEW INCOMPLETE);
- chunk-blocking and pipeline-blocking failures, before the failure is reported;
- every answer to a user gate, including "Give feedback" and "Done", not just the terminal one.

A run that exits without executing the cleanup phase is a contract violation. If the run is aborting because of an exception, the cleanup phase still runs -- it is deterministic git, it cannot make the failure worse.

Cleanup is plain git executed by the orchestrator. It is never delegated to a subagent, and never routed through `openrouter-wrapper.sh`, `openrouter-exec.sh`, or a Codex `multi_agent_v1.spawn_agent` call. Deleting refs is not a judgment task.

## 3. Safe-to-delete decision table

Evaluate each registered ref in order. First match wins.

| # | Condition | Test | Action |
|---|---|---|---|
| 1 | Fully merged into its target | `git merge-base --is-ancestor <ref> <target>` exits 0 | **delete** |
| 2 | Abandoned, no unique commits | `git rev-list --count <base>..<ref>` is `0` | **delete** |
| 3 | Worktree path gone, or branch gone | entry is `prunable` in `git worktree list --porcelain` | **delete + prune** |
| 4 | Worktree has uncommitted or untracked changes | `git -C <path> status --porcelain` non-empty | **keep**, report |
| 5 | Anything else | -- | **keep**, report |

Rows 1 and 2 are the only paths to deletion. There is no "it looks done" path.

Row 2 is **not** redundant with row 1, but it is narrower than it looks. When `base == target`, a branch with zero unique commits is already an ancestor of the target, so row 1 matches first and deletes it with the safer `git branch -d`. Row 2 only fires when the branch's **base differs from the merge target** -- an abandoned chunk branch cut from a base that was later rewritten, for example. That is the only case where `-D` is permitted, and it is permitted because the branch provably carries no unique work.

Every snippet below assumes `block` is defined. It is what makes a blocked ref appear in the receipt instead of vanishing.

Define it at the top of **each shell invocation** that cleans refs, not once per run. A per-chunk cleanup and an end-of-run sweep are separate shells; a function defined in the first is gone by the second, and an undefined `block` fails with `command not found` while the loop carries on. For the same reason `BLOCKED_REFS` does not accumulate across steps -- each step reports the refs it blocked, and the final inventory is assembled from those reports.

```bash
BLOCKED_REFS=""
block() {  # block <ref> <reason> <follow-up command>
  BLOCKED_REFS="${BLOCKED_REFS}| $1 | $2 | \`$3\` |
"
  printf 'BLOCKED %s -- %s\n' "$1" "$2" >&2
}
```

When iterating refs, feed the loop with process substitution -- `while ... done < <(cmd)` -- never `cmd | while`. A piped while-loop runs in a subshell, so every `BLOCKED_REFS` mutation inside it is discarded when the loop exits, and the receipt reports a clean run over refs that were actually blocked.

Deciding a branch's fate:

```bash
# Row 1 -- merged into the target
if git merge-base --is-ancestor "$ref" "$target"; then
  git branch -d "$ref" || block "$ref" "delete failed after merge check" "git branch -D $ref"
# Row 2 -- no unique commits over its own base (base != target)
elif [ "$(git rev-list --count "$base..$ref")" -eq 0 ]; then
  # -D still refuses when the branch is checked out in another worktree.
  # Unguarded, that refusal is swallowed and the ref is recorded as deleted.
  git branch -D "$ref" || block "$ref" "force-delete failed (checked out in another worktree?)" "git worktree list; git branch -D $ref"
else
  block "$ref" "unique commits not merged into $target" "git log $target..$ref"
fi
```

Worktree removal precedes branch deletion -- a branch checked out in a worktree cannot be deleted.

Check row 3 (`prunable`) **before** probing the worktree. Its path is gone, so `git status` on it can only fail -- probing first mislabels a prunable entry as "unreadable, blocked" and hands the operator a follow-up command that cannot succeed. Read the flag from the porcelain `prunable` field, tab-separated (splitting on the default `IFS` truncates paths containing spaces).

```bash
if [ "$prunable" = "prunable" ]; then
  continue   # `git worktree prune` clears it below; disposition = deleted
fi

wt_status="$(git -C "$wt" status --porcelain)"; rc=$?
if [ "$rc" -ne 0 ]; then
  block "$wt" "git status failed (rc=$rc) -- worktree unreadable" "git -C $wt status"
elif [ -n "$wt_status" ]; then
  block "$wt" "uncommitted or untracked changes" "git -C $wt status; git worktree remove --force $wt"
else
  git worktree remove "$wt" || block "$wt" "worktree remove failed" "git worktree remove --force $wt"
fi
```

Never suppress git's exit status with `2>/dev/null` -- not on a removal, and not on the dirtiness check that gates it. A silenced `git status` returns empty stdout, which reads as "clean" and routes an unreadable worktree straight to removal. A swallowed failure becomes a false "cleaned" line in the receipt.

## 4. Feature-branch protection

The main feature branch is **never** deleted without concrete merge proof:

```bash
git merge-base --is-ancestor "$featureBranch" main ||
git merge-base --is-ancestor "$featureBranch" origin/main
```

Absent a zero exit from one of those, the branch is kept and the receipt says `kept -- no merge proof`. "The review was clean", "the PR was opened", and "the user said done" are not merge proof.

`git branch -D` is **forbidden on the feature branch, always.** No condition unlocks it.

Chunk and review branches use `git branch -d`. Escalation to `-D` is permitted only after decision-table row 2 has already passed (the branch provably has no unique commits, so `-d`'s objection is about the *merge target*, not about losing work). Any use of `-D` is recorded in the inventory's Proof column.

## 5. Blocked-removal reporting

For every ref that could not be removed, the receipt records three things: the exact ref, the exact reason, and the exact command a human runs next.

```markdown
| .worktrees/pipeline/auth-map/04-views | worktree | uncommitted changes in internal/view/ | `git -C .worktrees/pipeline/auth-map/04-views status` |
| pipeline/auth-map/04-views | chunk-branch | 2 unique commits, not merged | `git log feature/auth-map..pipeline/auth-map/04-views` |
```

A blocked ref is never reported as cleaned, never counted in the "deleted" total, and never omitted. Reporting a ref as deleted when it still exists is the single worst failure this contract prevents -- it converts a visible mess into an invisible one.

## 6. Next-run readiness checks

After removals, prune and verify. Each check is stated in the receipt with its actual result, pass or fail.

```bash
git worktree prune
git worktree list --porcelain    # expect: no prunable entries, no automation paths
git status --porcelain           # expect: empty
```

`git worktree prune` removes admin entries whose path is **missing**, not merely unreadable. A permission-denied worktree whose directory still exists is left registered. Committed work in a vanished worktree survives in the shared object store and its branch ref persists -- only uncommitted work in a directory that no longer exists is beyond recovery, and it was already beyond recovery before the prune.

- **Clean tree.** `git status --porcelain` empty, or the exact residue listed verbatim.
- **No stale registrations.** `git worktree prune` has run; no `prunable` entries remain.
- **No untracked generated residue.** `.worktrees/`, `plans/<slug>/prompts/`, `plans/<slug>/manifest.json`, screenshot directories.

A failing check is reported as failing. It does not block the run's own result -- the work is already done -- but it must appear in the receipt so the next run's operator knows what they are inheriting.

## 7. Final inventory block

Emitted verbatim into every receipt and every terminal report.

```markdown
## Branch & Worktree Inventory

### Created this run
| Ref | Kind | Disposition | Proof |
|-----|------|-------------|-------|
| pipeline/auth-map/03-handlers | chunk-branch | deleted | merged into feature/auth-map |
| .worktrees/pipeline/auth-map/03-handlers | worktree | deleted | clean, removed + pruned |
| feature/auth-map | feature-branch | kept | no merge proof into main |

### Remaining after cleanup
| Ref | Kind | Reason kept | Follow-up command |
|-----|------|-------------|-------------------|
| feature/auth-map | feature-branch | not merged to main -- awaiting PR | `git merge-base --is-ancestor feature/auth-map origin/main` |

- Worktrees before: 3   after: 0   pruned: 1
- Branches deleted: 3   blocked: 0
- git status --porcelain: clean
```

Disposition is one of `deleted`, `kept`, `blocked`. Every registered ref from section 1 appears exactly once in "Created this run". Every `kept` or `blocked` ref appears again in "Remaining after cleanup" with a follow-up command.

## 8. Per-consumer notes

**pipeline.** Registers at Step 0e (before state) and Step 3b (each worktree + chunk branch). Applies the decision table at Step 3j per chunk, and again at Step 5b as a sweep for chunks whose 3j was interrupted. The feature branch is registered but never deleted by the orchestrator -- disposition is recorded, not acted on.

**pipeline-fix.** Runs on the current feature branch with `noMergeOnCompletion: true`. It creates no refs, so cleanup deletes nothing. It still emits the inventory block and the readiness checks -- a fix pass that leaves a dirty tree is the next run's problem.

**dm-review.** Creates no worktrees. Its cleanup phase prunes stale registrations, deletes only the batch-cleanup branch it created once that branch is merged (decision-table row 1), asserts a clean tree, and emits the inventory. When it finds automation refs it did not create, it reports them under "Remaining after cleanup" with a follow-up command and leaves them alone.

## 9. Non-Git owned resources

The Git decision table above remains authoritative and is not weakened by Docker
cleanup. Containers, networks, and volumes use the workflow kernel's separate
positive-ownership contract in `docker-ownership.md`:

- creation-time ownership labels plus a durable registry record are required
  for current-run cleanup; identity is kind plus ID and the exact non-empty
  label snapshot and inspected creation time must agree;
- stale-orphan cleanup requires a complete, internally consistent label set,
  strict TTL expiry, inspected-time agreement, and fresh authoritative proof
  that the run lease is inactive; missing or unreadable proof fails closed;
- chunk-owned cleanup is planned after validation, review, evidence capture,
  and merge disposition; all terminal outcomes plan run reconciliation;
- cleanup plans contain bounded, exact-ID argv only. Chunk 05 is their
  authoritative executor; planners and result recorders never execute Docker;
- no prune, wildcard, negative-filter, name-inference, or unrelated resource
  cleanup is permitted.

Git follows the same execution boundary: its adapter derives candidates from
the durable registry and emits a pure exact-argv plan. It never runs Git.
Proof input carries the explicit base and merge target, ownership namespace,
readability and dirtiness state, and a bounded capture time immediately adjacent
to planning. Chunk 05 alone executes the validated plan and records results.

Docker dispositions are `removed`, `retained_for_dependency`, `blocked`,
`foreign`, or `missing`. Every disposition records the resource kind and ID,
run/node owner, lifecycle, action, reason, evidence, and any follow-up. A
`removed` is recorded only after every required command succeeds and the object
is absent. `missing` is reserved for absence before planning or a later rerun;
a missing execution result is blocked. Blocked, retained, and foreign attempts
remain reconcilable, while successful terminal outcomes are immutable.
