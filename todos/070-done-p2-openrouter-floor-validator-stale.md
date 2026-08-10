---
status: done
priority: p2
issue_id: "070"
tags: [review, validation, openrouter]
source_agents: [test-coverage-reviewer]
review_date: 2026-08-09
---

# OpenRouter resolver floor validator is stale

Composition still requires an exact 1.8.0 resolver floor in the runner and
dm-review after their authorization contract moved to 1.11.2. Validate floors
by consumer contract instead of enforcing the obsolete value globally.
