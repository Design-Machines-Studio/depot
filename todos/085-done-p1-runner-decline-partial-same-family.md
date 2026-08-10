---
status: done
priority: p1
issue_id: "085"
tags: [review, security, fallback]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Runner decline rules return sign-off to Codex

Apply the non-implementing-family exception to full disclosure decline and
partial held-path completion in the generic runner rules.

## Resolution

Runner rules now send both signals only to a non-implementing family for the
sign-off lane, otherwise `REVIEW INCOMPLETE`. Focused anchors pass.
