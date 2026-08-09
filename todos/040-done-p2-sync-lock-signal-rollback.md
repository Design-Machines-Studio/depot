---
status: done
priority: p2
issue_id: "040"
tags: [review, testing, synchronizer, concurrency, signals]
source_agents: [code-simplicity-reviewer, test-coverage-reviewer]
review_date: 2026-08-09
---

# Synchronizer concurrency and signals can break transaction isolation

- [x] Concurrent invocations are serialized with a portable lock.
- [x] Cleanup removes only paths created by the lock-owning invocation.
- [x] INT, TERM, and HUP route through rollback after a partial commit.
- [x] Success and failure leave no replacement or backup files.
- [x] Focused and related verification passes.

## Resolution

The synchronizer now acquires a portable `mkdir` lock before reading consumer
state. A contender exits 2 without inspecting or cleaning the owner's staging
files. Every `mktemp` result is recorded immediately and cleanup removes only
those exact paths plus the lock owned by that invocation; the former broad glob
cleanup is gone.

INT, TERM, and HUP share the transaction rollback function. The rollback count
includes the in-flight move before the child command starts, closing the signal
window between a successful rename and the parent shell updating its counter.
Behavioral fixtures pause an owner while a contender runs, deliver TERM after
the first replacement, and assert that success and failure leave no replacement,
backup, or lock artifacts. Nine synchronizer tests, 60 related focused tests,
Bash syntax, workflow contracts, and diff checks passed.
