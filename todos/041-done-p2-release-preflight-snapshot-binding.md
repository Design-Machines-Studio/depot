---
status: done
priority: p2
issue_id: "041"
tags: [review, release, preflight, git]
source_agents: [final-doc-recheck]
review_date: 2026-08-09
---

# Release preflight can certify a repository state it did not finish checking

## Problem

The release preflight previously read mutable `HEAD` throughout the run and did
not re-check the repository before its terminal receipt. A concurrent commit,
branch switch, or worktree mutation could therefore produce `READY` from a mix
of repository states.

## Acceptance Criteria

- [x] bind the full starting commit, branch, and porcelain status
- [x] use the bound commit for local and remote release comparisons
- [x] fail before the terminal receipt if commit, branch, or status changed
- [x] deterministic regressions prove concurrent mutations never print `READY`
- [x] focused tests, Bash syntax, and ShellCheck pass

## Resolution

The preflight now captures its starting full commit SHA, branch, and porcelain
status before checking anything. Tag and cross-lane comparisons use that bound
SHA, and the receipt reports the bound commit and branch. Immediately before the
receipt, fresh commit, branch, and status observations must exactly match the
starting snapshot or the run emits an explicit failure and blocks `READY`.

The regression harness deterministically mutates the repository during the
push-auth probe. Separate tests prove that a concurrent empty commit, branch
switch, and tracked-file edit each exit 1, name the snapshot change, and omit
`READY`. All 20 release-preflight tests passed, along with `bash -n`, ShellCheck,
the workflow-contract validator, and diff checking.
