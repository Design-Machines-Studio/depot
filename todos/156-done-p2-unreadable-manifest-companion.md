---
status: done
priority: p2
issue_id: "156"
---

# Unreadable manifests stranded their private companions

Resolved by registering the deterministic manifest companion immediately after
lane-spec validation, before manifest I/O. Invalid-JSON and unreadable-manifest
fixtures both prove companion cleanup.
