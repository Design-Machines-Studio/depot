# Worktree and chunk-branch cleanup

Load at Step 3j and Step 5b repository cleanup. Apply `repo-cleanup-contract.md` -- it owns the rules; this file owns the pipeline implementation. Never suppress git exit status.

Define `block` at the top of **each shell invocation** that cleans refs, not once per run: 3j and 5b are separate shells, and an undefined `block` fails with `command not found` while the loop carries on. For the same reason `BLOCKED_REFS` does not accumulate across steps -- each step reports what it blocked and the final inventory is assembled from those reports.

```bash
BLOCKED_REFS=""
block() {  # block <ref> <reason> <follow-up command>
  BLOCKED_REFS="${BLOCKED_REFS}| $1 | $2 | \`$3\` |
"
  printf 'BLOCKED %s -- %s\n' "$1" "$2" >&2
}
```

## Per-chunk (3j)

Remove the worktree before deleting the branch.

```bash
WT=".worktrees/pipeline/<run-id>/<chunk-id>"
BR="pipeline/<run-id>/<chunk-id>"

WT_STATUS="$(git -C "$WT" status --porcelain)"; WT_RC=$?
if [ "$WT_RC" -ne 0 ]; then
  block "$WT" "git status failed (rc=$WT_RC) -- worktree unreadable" "git -C $WT status"
elif [ -n "$WT_STATUS" ]; then
  block "$WT" "uncommitted or untracked changes" "git -C $WT status; git worktree remove --force $WT"
else
  git worktree remove "$WT" || block "$WT" "worktree remove failed" "git worktree remove --force $WT"
fi

if git merge-base --is-ancestor "$BR" "<featureBranch>"; then
  git branch -d "$BR" || block "$BR" "branch delete failed after merge check" "git branch -D $BR"
elif [ "$(git rev-list --count "<featureBranch>..$BR")" -eq 0 ]; then
  git branch -D "$BR" || block "$BR" "force-delete failed (checked out in another worktree?)" "git worktree list; git branch -D $BR"
else
  block "$BR" "unique commits not merged into <featureBranch>" "git log <featureBranch>..$BR"
fi
```

Row 1 also deletes an abandoned chunk with zero unique commits over its base via `-d`. Row 2 fires when the chunk branch base differs from the merge target. Carry every `block` into the Step 5b inventory as `blocked`.

## Terminal exact-record reconciliation (5b)

Read only still-active worktree and chunk-branch records for this exact run ID
from the durable registry. Re-run the per-chunk decision table for each record
in creation order. A recorded path that has already disappeared is `missing`
and needs no command; its branch still receives an independent exact proof.

Do not enumerate `.worktrees/pipeline/**`, match the feature slug, infer refs
from a prefix, or run `git worktree prune`. Another concurrent run's clean
worktree is foreign even when it targets the same feature branch. Feature-branch
protection stays in the orchestrator.
