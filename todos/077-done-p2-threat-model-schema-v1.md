---
status: done
priority: p2
issue_id: "077"
tags: [review, security, documentation]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Threat model documents retired content-only authorization

Replace schema-v1 payload-digest and routing-unbound claims with the schema-v2
exact request-envelope boundary and its actual procedural residual risk.

## Resolution

The threat model now binds complete immutable request-envelope bytes, including
models and provider routing, and identifies same-user batch forgery as the
remaining procedural weakness. The workflow validator rejects old vocabulary.
