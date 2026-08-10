---
status: done
priority: p2
issue_id: "164"
---

# Wrapper signals left the provider transport child running

Resolved by making cleanup own the live curl PID, terminate it with a bounded
TERM-to-KILL sequence, reap it, and emit a content-free interrupted receipt.
The regression uses a sleeping transport child and proves it is gone.
