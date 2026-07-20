# Pipeline Metrics Ledger

Append one line per full pipeline run. This ledger tracks measured providerSplit, eligibleProviderSplit against the active target, exclusions/variance, cost, top routing recommendation, and recurrence promotion.

| Date | Feature | providerSplit | eligibleProviderSplit / Target | Exclusions / Variance | Tokens/Cost By Provider | Top Recommendation | Status |
|---|---|---|---|---|---|---|---|
| _template_ | `<slug>` | `claude/codex/openrouter` | `codex/openrouter vs <profile>` | `security:0; tools:0; outage:0; quality:0 / variance` | `claude:0/$0; codex:0/$0; openrouter:0/$0` | `none - optimal` | `template` |
| 2026-07-15 | `ai-developer-workflow-kernel` | `0%/100%/0% actual chunks` | `not measured (legacy receipt)` | `not measured (legacy receipt)` | `claude:unavailable/no receipt; codex:unavailable/unavailable; openrouter:0/$0 observed` | Complete requested/attempted/implemented provider receipts | `proposal awaiting approval` |
