---
status: done
priority: p1
issue_id: "074"
tags: [review, documentation, security]
source_agents: [pattern-recognition-specialist]
review_date: 2026-08-09
---

# dm-review consumers advertise an unavailable broker mode

Align the canonical command and review skill with the runner's fail-closed
`broker_transport_unavailable` behavior, then regenerate the command alias.

## Resolution

Canonical, generated, manifest, README, model-selection, protocol, and routing
surfaces now describe ready-broker transport as unavailable. Command aliases
were regenerated and the workflow contract gate passes.
