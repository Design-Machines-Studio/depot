---
status: done
priority: p3
issue_id: "143"
---

# Usage fixtures were indistinguishable from live capacity

Resolved by emitting a conspicuous stderr warning and `probe_source: fixture`
whenever test mode supplies capacity observations; cascade receipts preserve
that source instead of presenting fixture headroom as live evidence.
