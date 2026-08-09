---
status: done
priority: p2
issue_id: "043"
tags: [review, documentation, workflow-kernel, openrouter]
source_agents: [fable-voice-editor]
review_date: 2026-08-09
---

# Final voice review found public contract drift

## Resolution

- Documented `resolve-plugin-asset`, including coherent selection, output, and
  failure behavior.
- Restored the Workflow Kernel `>=0.8.0` floor for ordinary no-matrix cost
  summaries alongside the `>=0.13.0` matrix-backed floor.
- Replaced provider-coupled kernel prose with caller-supplied matrix language.
- Removed duplicate Terra/Luna routing prose and aligned alias terminology.
- Clarified native-cost refresh wording and the README Anthropic route.
- Marked todo 003's original matrix selector as superseded by todo 013.

Generator, dependency, synchronization, workflow-contract, and composition
checks cover the resulting public documentation contract.
