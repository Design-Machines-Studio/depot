# Pipeline Run Post-Mortem Schema

Every full pipeline run writes `plans/<slug>/run-postmortem.md` after memory capture and before the final Summary Report.

## Required Sections

- `providerSplit` - measured token and cost totals by `claude`, `codex`, `openrouter`, and `deepseek`.
- `measurementSources` - Claude JSONL delta, `ccusage blocks --json` cross-check when available, Codex `tokens used`, OpenRouter/DeepSeek API `usage` objects, and any estimated fallbacks with reasons.
- `routingTargetComparison` - configured target from `routing-policy.json`, actual split, and variance.
- `misroutes` - every Claude-executed task that the policy says should have gone to Codex/OpenRouter, including token cost and exact policy edit.
- `qualityLedger` - which provider found each review issue, retries, cap descents, and regressions shipped by cheaper models.
- `rankedRecommendations` - proposal-only changes for plugins exercised by this run.
- `standingRecommendations` - recommendations repeated in at least `N` runs, default `3`, with run citations.

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
