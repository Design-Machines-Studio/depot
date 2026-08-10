---
status: done
priority: p1
issue_id: "072"
tags: [review, documentation, security]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Runner still advertises unsupported broker mode

The runner says ready-broker dispatch and `authorization_mode=broker` are
accepted after dm-review was corrected to withhold that unimplemented route.
Align the public runner contract with the fail-closed behavior.

## Resolution

The runner now lists only implemented authorization modes and explicitly states
that broker-owned transport remains unavailable. The authoritative staged
doc-sync re-review confirmed the stale broker prose is gone.
