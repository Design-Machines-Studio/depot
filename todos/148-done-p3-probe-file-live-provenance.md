---
status: done
priority: p3
issue_id: "148"
---

# Caller probe files could claim live provenance

Resolved by forcing every `--probe-file` input to fixture provenance, defaulting
missing live-probe provenance to unknown, and behaviorally rejecting a probe
file that self-asserts `probe_source: live`.
