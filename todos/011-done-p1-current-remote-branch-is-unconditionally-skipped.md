---
status: done
priority: p1
issue_id: "011"
tags: [review, release-preflight, equal-bump, remote-correctness]
source_agents: [codex-focused-review]
review_date: 2026-08-09
---

# The current-named remote branch bypasses the equal-bump guard

## Problem

The equal-bump loop skips any remote branch whose name equals the current local
branch before comparing commits. A tracking branch can be ahead of or divergent
from its local branch after another checkout pushes or a force-update occurs.
If both sides changed the plugin and declare the same version, this early name
check suppresses the exact collision the guard is required to block.

## Location

- `tools/check-release-preflight.sh:311` -- skips by branch-name equality without checking commit ancestry

## Root Cause

Branch-name equality is treated as proof of shared history. The later
`merge-base --is-ancestor "$remote_sha" HEAD` check already identifies remote
heads actually contained in local history and is the correct deduplication.

## Suggested Fix

Remove the current-branch-name skip. Fetch and inspect that remote head like
every other advertised branch, then let the existing commit-ancestry and
merge-base checks exclude only genuinely shared history.

## Acceptance Criteria

- [x] A divergent `origin/<current-branch>` with an equal independent bump FAILs
- [x] An `origin/<current-branch>` already contained in HEAD is skipped as shared history
- [x] Differently named remote-branch behavior remains unchanged

## Resolution

The branch-name bypass was removed; commit ancestry is now the only shared-tip
exclusion. An isolated local remote advertised the current branch name first at
a divergent equal-bump commit, which FAILed naming both branches, and then at
the contained local HEAD, which passed with zero candidates. No differently
named branch logic changed.
