---
status: done
priority: p2
issue_id: "033"
tags: [review, documentation, openrouter, validation]
source_agents: [doc-sync-reviewer]
review_date: 2026-08-09
---

# Canonical matrix refresh metadata conflates independent evidence domains

## Problem

The matrix previously told operators to restamp every entry even though routing
and native API-equivalent cost evidence carry independent snapshot dates. Its
documentation anchor also named a removed heading, and validation did not fence
either invariant.

## Acceptance Criteria

- [x] routing refresh metadata owns only routing snapshot paths
- [x] native-cost refresh metadata owns only native-cost snapshot paths
- [x] each procedure explicitly preserves the other domain
- [x] documentation anchors name the current headings
- [x] OpenRouter validation fails when the two domains are conflated

## Resolution

The canonical matrix now has independent `refresh_protocol.routing` and
`refresh_protocol.native_api_equivalent_cost` procedures with exact owned and
preserved paths. The OpenRouter validator fences those paths and both current
documentation anchors. The focused contract test first failed against the
conflated structure, then passed both cases after the split; JSON parsing,
shell syntax, manifest generation, dependency validation, and workflow-contract
validation also passed. The full OpenRouter validator remains an environment
coverage gap because its controlled loopback sentinel cannot bind in this
sandbox.
