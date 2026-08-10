---
status: done
priority: p2
issue_id: "151"
---

# Interruption fixture left approval processes alive

Resolved by signaling the isolated PTY process group, requiring bounded EOF,
and asserting both the signal-specific cleanup receipt and absence of retained
authorization artifacts. The focused suite now exits with no approval process.
