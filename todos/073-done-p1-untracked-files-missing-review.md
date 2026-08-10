---
status: done
priority: p1
issue_id: "073"
tags: [review, release, evidence]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Untracked release files are absent from final review

The new runner helper and invalid-baseline notice are required by tracked files
but absent from `git diff bec6485` until staged. Stage the complete intended
patch and repeat the final full fan-out against the exact staged/worktree diff.

## Resolution

Both required files are staged with the aggregate: the executable runner batch
helper and the unusable-baseline notice. The authoritative staged doc-sync
re-review confirmed both references resolve inside the index.
