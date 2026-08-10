---
status: done
priority: p2
issue_id: "166"
---

# OpenRouter usage receipts could be relabeled or crossed between lanes

Resolved by binding wrapper receipts to run, logical lane, and transmitted
request-envelope digest. Atomic `record-attempt` requires OpenRouter attempted
and implementing identity and exact run/lane equality for interim receipts;
crossed and Codex-relabeled mutations fail before ledger creation.
