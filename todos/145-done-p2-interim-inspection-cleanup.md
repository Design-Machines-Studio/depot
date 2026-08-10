---
status: done
priority: p2
issue_id: "145"
---

# Unsuccessful batch approval retained private request envelopes

Resolved with one signal-aware cleanup owner covering success, decline,
unavailable TTY, interruption, and partial-lane validation. Every unsuccessful
exit attempts cleanup and batch rollback and reports when the filesystem
prevents either operation.
