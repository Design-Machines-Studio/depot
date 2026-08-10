---
status: done
priority: p2
issue_id: "167"
---

# Transport launch could precede PID ownership

Resolved by deferring handled signals across the background transport launch
until `$!` is published, replaying a pending signal through the one bounded
cleanup owner, and routing stream timeouts through the same TERM-to-KILL path.
The real wrapper harness injects a signal before PID publication and runs a
TERM-resistant timeout transport; neither can survive the bounded exit.
