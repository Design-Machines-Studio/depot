---
status: done
priority: p2
issue_id: "027"
tags: [review, documentation, release-preflight]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Release runbook describes the old preflight gate set

## Problem

CLAUDE omits installed Codex cache freshness and cross-lane equal-bump checks.
It also does not explain that `--no-net` leaves both equal-bump and origin-auth
coverage unverified.

## Fix

Update CLAUDE only. The stale script usage comment belongs to Batch B and must
remain untouched here.

## Acceptance Criteria

- [x] CLAUDE lists both new release-preflight gates
- [x] CLAUDE states both `--no-net` coverage gaps
- [x] Batch B ownership of the script comment is recorded

## Resolution

CLAUDE now lists installed Codex cache freshness and remote equal-version bump
inspection, and says `--no-net` leaves both equal-bump and origin-auth evidence
unverified. Batch B owns the matching script usage comment and is handling it
separately; this repair did not stage or edit the script.
