# Pipeline Metrics Ledger

Append one line per full pipeline run. This ledger tracks measured providerSplit, eligibleProviderSplit against the active target, exclusions/variance, cost, top routing recommendation, and recurrence promotion.

| Date | Feature | providerSplit | eligibleProviderSplit / Target | Exclusions / Variance | Tokens/Cost By Provider | Top Recommendation | Status |
|---|---|---|---|---|---|---|---|
| _template_ | `<slug>` | `claude/codex/openrouter` | `codex/openrouter vs <profile>` | `security:0; tools:0; outage:0; quality:0 / variance` | `claude:0/$0; codex:0/$0; openrouter:0/$0` | `none - optimal` | `template` |
| 2026-07-15 | `ai-developer-workflow-kernel` | `0%/100%/0% actual chunks` | `not measured (legacy receipt)` | `not measured (legacy receipt)` | `claude:unavailable/no receipt; codex:unavailable/unavailable; openrouter:0/$0 observed` | Complete requested/attempted/implemented provider receipts | `proposal awaiting approval` |
| 2026-07-22 | `adaptive-fusion-verification` | `0%/100%/0% actual chunks` | `codex 100% / openrouter 0% vs codex-20x 65/35` | `security:0; tools:0; outage:3; quality:0 / +35pp codex, -35pp openrouter` | `claude:0/no usage; codex:tokens and cost unavailable; openrouter:0/no execution` | Preserve shadow compatibility across self-hosting upgrades | `proposal awaiting approval` |
| 2026-08-07 | `r0-measurement-backbone` | `0%/0%/100% actual chunks` | `codex 0% / openrouter 100% vs codex-20x 65/35` | `security:0; tools:0; outage:3; quality:0 / -65pp codex, +65pp openrouter` | `claude:0/$0 (zero coding tokens); codex:0/$0 (subscription cap); openrouter:365,216/$2.9960` | Wire the Workflow Authority Broker -- cascade selects OpenRouter correctly but openrouter-exec.sh exits host_authority_unavailable | `proposal awaiting approval` |
