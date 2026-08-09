---
status: done
priority: p1
issue_id: "025"
tags: [review, documentation, openrouter]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Project-level OpenRouter guidance contradicts the canonical matrix

## Problem

README prohibits OpenAI models through OpenRouter and CLAUDE lists stale
Terra/Luna planning prices, while the canonical matrix permits the OpenAI
slugs and records different snapshot prices.

## Fix

Align both project docs to the canonical matrix and state the snapshot/live
verification boundary.

## Acceptance Criteria

- [x] README forbids only Anthropic-origin OpenRouter slugs
- [x] CLAUDE matches the checked-in Terra and Luna planning prices
- [x] CLAUDE states the snapshot date and live-refresh requirement

## Resolution

README now permits OpenAI slugs through OpenRouter with provider provenance and
keeps Anthropic-origin slugs native-only. CLAUDE records the checked-in
2026-08-03 Terra `$1/$6` and Luna `$0.10/$0.60` planning prices and requires a
fresh MCP receipt before paid or policy-changing use; these values were checked
against the canonical matrix.
