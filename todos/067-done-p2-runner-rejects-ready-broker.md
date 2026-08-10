---
status: done
priority: p2
issue_id: "067"
tags: [review, security, broker]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Runner rejects the advertised ready broker mode

dm-review selects broker authorization when the fixed probe is ready, but the
OpenRouter runner has no broker branch. Implement the broker-owned transport or
withhold availability until it exists, with an end-to-end ready fixture.
