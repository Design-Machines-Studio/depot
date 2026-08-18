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
WT=".worktrees/pipeline/<feature>/<chunk-id>"
BR="pipeline/<feature>/<chunk-id>"

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

## Terminal sweep (5b)

Parse `git worktree list --porcelain` field-wise. Do not `grep -o` porcelain for the feature slug. Use process substitution, not a piped `while`. Tab-separate awk output and read with `IFS=$'\t'`.

```bash
PREFIX=".worktrees/pipeline/<feature>/"

while IFS=$'\t' read -r WT PRUNABLE; do
  case "$WT" in
    */"$PREFIX"*|"$PREFIX"*) ;;
    *) continue ;;
  esac
  if [ "$PRUNABLE" = "prunable" ]; then
    printf 'PRUNABLE %s -- registration stale, path gone\n' "$WT"
    continue
  fi
  WT_STATUS="$(git -C "$WT" status --porcelain)"; WT_RC=$?
  if [ "$WT_RC" -ne 0 ]; then
    block "$WT" "git status failed (rc=$WT_RC) -- worktree unreadable" "git -C $WT status"
  elif [ -n "$WT_STATUS" ]; then
    block "$WT" "uncommitted or untracked changes" "git -C $WT status; git worktree remove --force $WT"
  else
    git worktree remove "$WT" || block "$WT" "worktree remove failed" "git worktree remove --force $WT"
  fi
done < <(git worktree list --porcelain | awk '
  /^worktree /{ if (p!="") printf "%s\t%s\n", p, f; p=substr($0,10); f="-" }
  /^prunable/ { f="prunable" }
  END        { if (p!="") printf "%s\t%s\n", p, f }
')

git worktree prune
```

Then apply the 3j decision table to every remaining chunk branch. Feature-branch protection stays in the orchestrator.
