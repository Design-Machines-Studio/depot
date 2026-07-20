# Pipeline Run Post-Mortem Schema

Every full pipeline run writes `plans/<slug>/run-postmortem.md` after memory capture and before the final Summary Report.

## Required Sections

- `providerSplit` - measured token and cost totals by `claude`, `codex`, and `openrouter`; DeepSeek-model calls are OpenRouter usage.
- `eligibleProviderSplit` - chunk counts and percentages by Codex/OpenRouter after documented exclusions, including the active subscription profile.
- `routingExclusions` - chunk ID, excluded provider, and one of `security`, `required-live-tool`, `provider-unavailable`, or `quality-floor`; exclusions are not counted as target misses.
- `routingVariance` - eligible actual minus target for each provider, with a receipt-backed reason for every material variance.
- `measurementSources` - Claude JSONL delta, `ccusage blocks --json` cross-check when available, Codex `tokens used`, OpenRouter API `usage` objects, and any estimated fallbacks with reasons.
- `routingTargetComparison` - configured target from `routing-policy.json`, actual split, and variance.
- `misroutes` - every Claude-executed task that the policy says should have gone to Codex/OpenRouter, including token cost and exact policy edit.
- `qualityLedger` - which provider found each review issue, retries, cap descents, and regressions shipped by cheaper models.
- `rankedRecommendations` - proposal-only changes for plugins exercised by this run.
- `standingRecommendations` - recommendations repeated in at least `N` runs, default `3`, with run citations.
- `kernelReliability` - shadow availability, semantic parity status, comparison reason counts, observation/adapter failures, missing authoritative evidence, browser recovery outcomes, owned-resource cleanup outcomes, and reconciliation results.
- `workflowClass` - validated class plus `workflow_class_defaulted`; metrics retain the authoritative manifest value unchanged.
- `providerReceipts` - requested, attempted, implemented-by, fallback, and reason for every routed lane, including unavailable and misrouted lanes.

Kernel reliability data is measurement only. A parity report or reliability recommendation cannot mutate routing policy, workflow stages, cleanup state, merge results, or review outcomes. Promotion requires a separate human-approved source change after evidence review.

## Recommendation Shape

```markdown
### AWAITING APPROVAL: <short title>

- Plugin/file: `<path>`
- Concrete edit: `<routing-policy.json entry or doc/validator change>`
- Expected token/cost delta: `<measured or bounded estimate>`
- Confidence: high|medium|low
- Evidence: `<run ids or receipt paths>`
```

Recommendations are never auto-applied. The human approves every plugin-source or routing-policy change.
