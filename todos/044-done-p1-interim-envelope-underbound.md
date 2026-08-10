---
status: done
priority: p1
issue_id: "044"
tags: [review, security, openrouter]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Interim approval does not bind the request envelope

The interim operator-batch digest binds message content but not caller-selected
model and provider routing metadata. Bind authorization to the exact transmitted
request envelope, bound model length and identity, and add mutation regressions.
