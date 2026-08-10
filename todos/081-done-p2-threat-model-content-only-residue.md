---
status: done
priority: p2
issue_id: "081"
tags: [review, security, documentation]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Threat model retains a content-only preservation claim

Make the preservation paragraph describe complete schema-v2 request-envelope
binding rather than retired ordered-content-only membership.

## Resolution

The preservation paragraph now binds model, provider routing, roles, and
message content inside the complete request envelope. The validator forbids the
retired content-only claim.
