---
status: done
priority: p2
issue_id: "068"
tags: [review, security, routing]
source_agents: [security-auditor-codex-signoff]
review_date: 2026-08-09
---

# Security lane accepts any matrix model

Matrix membership does not enforce the security lane's policy-derived Kimi K3
primary and GLM fallback. Bind lane identity to the allowed model pair and test
listed-but-wrong-role rejection.
