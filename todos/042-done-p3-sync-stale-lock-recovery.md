---
status: done
priority: p3
issue_id: "042"
tags: [review, synchronizer, operations, recovery]
source_agents: [fable-second-perspective]
review_date: 2026-08-09
---

# Synchronizer stale lock lacks actionable recovery guidance

## Problem

A process terminated by SIGKILL, power loss, or OOM can leave the portable
`.sync-rcs.lock` directory behind. Later invocations failed closed but did not
name the lock or tell an operator how to recover after confirming no owner
remains.

## Resolution

The contention diagnostic now prints the exact lock path and the conservative
`rmdir -- <lock>` recovery command. Automatic stale-lock deletion remains
intentionally unsupported because PID reuse and cross-host ownership cannot be
proven safely from this lock format.

The concurrent-invocation regression asserts both the path and recovery hint.
All nine synchronizer tests, Bash syntax, ShellCheck, workflow contracts, and
diff checks pass.
