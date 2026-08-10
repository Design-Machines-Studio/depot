---
status: done
priority: p2
issue_id: "099"
---

# Equal-set lane selection emitted a falsely selective receipt

Resolved by collapsing a computed rerun set equal to the full selected set into
an unfiltered full fan-out before dispatch, with `selective_rerun: false` and
`initial_full_fanout` reasons. The workflow-contract gate pins this rule.
