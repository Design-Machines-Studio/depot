---
status: pending
priority: p2
issue_id: "007"
tags: [review, security]
source_agents: [security-auditor]
review_date: 2026-03-25
---

# Server IP exposed in structured metadata

## Problem

The `the-local` deploy command description includes the production server IP `143.110.221.2` in plugin.json. Structured JSON is more likely to be scraped/parsed than freeform Markdown.

## Location

- `plugins/the-local/.claude-plugin/plugin.json:65` — deploy command description

## Fix

1. Replace literal IP with hostname or generic reference in the command description
2. Consider auditing the-local SKILL.md files for the same pattern (pre-existing, lower priority)

## Reference

- OWASP A05:2021 — Security Misconfiguration (information disclosure)

## Acceptance Criteria

- [ ] No literal IP addresses in plugin.json command descriptions
