---
status: done
priority: p2
issue_id: "069"
tags: [review, security, tests]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Runner policy gate stops on a stale assertion

The focused security gate still expects the old authorization-mode assignment
and exits before the new envelope/broker fixtures. Update the assertion and
ensure behavioral mode tests execute.
