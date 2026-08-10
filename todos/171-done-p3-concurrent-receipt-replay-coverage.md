---
status: done
priority: p3
issue_id: "171"
---

# Receipt replay coverage was sequential only

Resolved with eight independent CLI launchers each publishing a unique ready
marker before waiting on one shared release gate. Only after all eight are
ready may they race to record the same OpenRouter receipt. Exactly one process
succeeds and the durable stream contains exactly its lane/usage pair, proving
replay detection remains inside the exclusive receipt-stream critical section.
