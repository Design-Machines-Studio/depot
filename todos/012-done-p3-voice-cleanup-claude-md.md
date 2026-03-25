---
status: pending
priority: p3
issue_id: "012"
tags: [review, voice]
source_agents: [voice-editor]
review_date: 2026-03-25
---

# Minor voice cleanup in CLAUDE.md Plugin Discovery section

## Problem

Two small prose issues: "actually" is filler in triggers description, and the capabilities_summary sentence is orphaned without explaining why it exists.

## Location

- `CLAUDE.md:68` — "a user would actually type"
- `CLAUDE.md:71` — marketplace manifest sentence

## Fix

1. Remove "actually" from triggers description
2. Rewrite capabilities_summary sentence: "The marketplace manifest includes `capabilities_summary` for each plugin — counts and curated tags for quick search without loading full capabilities."

## Acceptance Criteria

- [ ] No filler words in Plugin Discovery section
- [ ] capabilities_summary sentence explains its purpose
