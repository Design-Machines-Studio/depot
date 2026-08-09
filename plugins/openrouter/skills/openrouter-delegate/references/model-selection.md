# Model Selection

Decision tables for the three distinct routing systems that use these model names. Native Codex execution, dm-review/direct OpenRouter delegation, and the Pipeline cascade have different ordering and provenance; do not combine them into one fallback ladder.

> **Current production mode:** only direct interactive `/openrouter` calls may
> reach the API, after exact-digest approval. The dm-review and Pipeline tables
> describe the broker-enabled target topology and dry-run decisions. Their
> non-dry automated attempts currently record `host_authority_unavailable` and
> complete on Codex.

## Available Models

Prices below are a checked-in planning snapshot from 2026-08-03, in USD per
million input/output tokens; they are not current telemetry. Before a paid or
policy-changing run, obtain a live MCP receipt with `observedAt` and `expiresAt`
no more than 15 minutes apart and use it only before expiry.

| Slug | Name | Input / output | Context | Quality and role |
|------|------|----------------|---------|------------------|
| `moonshotai/kimi-k3` | Kimi K3 | $3 / $15; $0.30 cache read | 1,048,576 | AA intelligence 57.1 / coding 76.2 / agentic 50.1; quality-first security and bulk-analysis head; reasoning efforts low/high/max |
| `openai/gpt-5.6-terra` | GPT-5.6 Terra | $1 / $6; $0.10 cache read | 1,050,000 | AA intelligence 55.0 / coding 76.7 / agentic 47.4; high-quality OpenRouter backup; reasoning none through max |
| `openai/gpt-5.6-luna` | GPT-5.6 Luna | $0.10 / $0.60; $0.01 cache read | 1,050,000 | AA intelligence 51.2 / coding 71.4 / agentic 45.6; low-cost mechanical and config/doc work; reasoning none through max |
| `x-ai/grok-4.5` | Grok 4.5 | $2 / $6 | 500K | AA 54; near-frontier value fallback |
| `z-ai/glm-5.2` | GLM-5.2 | catalog $1.19 / $3.74; lower-cost endpoints exist | 1M | AA intelligence 51.1 / coding 68.8 / agentic 43.1; third-party mechanical and security-capacity fallback |
| `meta/muse-spark-1.1` | Muse Spark 1.1 | $1.25 / $4.25 | 1M | AA 51; multimodal frontier value |
| `google/gemini-3.5-flash` | Gemini 3.5 Flash | $1.50 / $9 | 1M | AA 50; multimodal frontier tail |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | $0.435 / $0.87 | 1M | AA 44; cheap code-analysis fallback through OpenRouter |
| `minimax/minimax-m3` | MiniMax-M3 | $0.30 / $1.20 | 1M model; top endpoint about 524K | AA 44; multimodal cost workhorse |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash | $0.098 / $0.196 | 1M | AA 40; cheapest mechanical checks |
| `qwen/qwen3-coder` | Qwen3 Coder | $0.30 / $1 | 1M model; top endpoint about 262K | Lower-quality final bulk fallback; validate endpoint capacity before very large prompts |

**Data source of truth:** the machine-readable
[`model-matrix.json`](model-matrix.json) is the canonical form of this table --
the prose above is the human view, and on any disagreement the JSON wins.
`tools/validate-openrouter-cascade.sh` pins the downstream consumers to it: a
`quality_rank` in `model-cascade.json` that disagrees with or is missing from
the matrix, a `routing-policy.json` agentType model or fallback slug that is
absent from the matrix, and a snapshot date that diverges from the date stated
above are all hard failures.

**Receipt requirement:** every routing decision recorded in a run receipt must
carry `matrix_snapshot_date` and a one-line `rung_rationale` naming the deciding
axis -- cost, context, strength, or availability. The same requirement is
declared as `matrixReceipt` in `plugins/pipeline/references/routing-policy.json`
so the delegation skill and the cascade consumers share one contract.

Native Codex identities (bare `gpt-*` names) and native Claude aliases are not
OpenRouter routing models and are deliberately absent from the routing matrix; `anthropic/`
slugs are rejected by `openrouter-wrapper.sh` before network contact and must
never be added to it. The matrix's `native_api_equivalent_cost` object is a
strictly observational exception: it maps a bare native identity to an explicit
API-equivalent price for cost imputation. Its deterministic input estimate uses
four UTF-8 input bytes per token, never populates token counter fields, and
names that estimate in row provenance. It does not add the native identity to
OpenRouter routing or assert billed spend. An alias absent from that object
remains unpriceable.

## Refreshing the matrix

Model preferences churn weekly with releases, so the matrix is a refreshable
recommendation instrument grounded in named external sources -- never a frozen
opinion. Refresh it on demand, and always before a paid or policy-changing run.
This is a documented human procedure; nothing here is automated.

- **Price, context, and availability** come from the OpenRouter live API. Record
  a receipt whose `observedAt` and `expiresAt` are no more than 15 minutes apart
  (the existing freshness rule, mirrored as `freshness_rule_minutes` in the
  JSON) and use it only before expiry.
- **Quality scores** come from the named evaluation source with its dataset
  version recorded in `aa_scores.source` and `aa_scores.source_version`. A score
  without provenance does not enter the matrix.
- **Every refresh bumps `snapshot_date`** -- both the top-level value and each
  entry -- and the prose snapshot date above must move with it, because the
  validator compares them.
- **Where a source is unreachable, keep the prior value** and mark it stale in
  the refresh write-up. Never guess, interpolate, or backfill from memory.
- **A refresh lands as an ordinary reviewed commit**, so the drift validator
  re-fences every downstream consumer against the new values.

The matrix recommends, routing policy decides, receipts record. Refreshing the
matrix never re-routes anything on its own; a routing change is a separate,
deliberate edit to `model-cascade.json`, `harness-profile.json`, or
`routing-policy.json`.

## Native Codex execution

Native Codex models run through the Codex host or `codex-companion`; they are not OpenRouter requests and retain `implementedBy: codex` provenance.

| Host | Coding role | Ordered native models |
|------|-------------|-----------------------|
| Codex | `premium_sub` | GPT-5.6 Sol -> GPT-5.6 Terra -> GPT-5.5 -> GPT-5.6 Luna |
| Claude Code | `premium_sub` via `codex-companion` | GPT-5.6 Sol (representative; Codex selects its configured native model) |
| Generic | `premium_sub` | unavailable |

## dm-review target topology and direct OpenRouter delegation

These calls use the OpenRouter API and retain `implementedBy: openrouter` even when the selected slug begins with `openai/`. A later Codex fallback is a separate native attempt with its own receipt.

| Workload | OpenRouter primary | OpenRouter fallback | Native completion |
|----------|--------------------|---------------------|-------------------|
| Direct `/openrouter` | Terra, unless `--model` overrides it | Kimi K3 | none implicit |
| Mechanical dm-review lanes | Luna | GLM-5.2 | Codex if the OpenRouter attempt cannot complete |
| Bulk / large-context dm-review | Kimi K3 | Terra | Codex if the OpenRouter attempt cannot complete |
| Security dm-review lens | Kimi K3 | GLM-5.2 | same logical lane completes on Codex; independent full-diff Codex sign-off is always required |
| One-shot config / doc generation | Luna | Terra quality fallback | caller owns writing and verification |

Review timeouts are 3600s, extended to 7200s for bulk diffs of at least 10K lines. One-shot config/doc generation uses 1800s.

## Pipeline execution cascade target topology

Pipeline resolves abstract roles through `harness-profile.json`, then walks the class ladder in `model-cascade.json`. Its agentic OpenRouter executor is GLM-5.2-headed; Kimi remains a later capacity rung and the head of analysis-only frontier/bulk wrapper roles.

| Role | Kind | Ordered models |
|------|------|----------------|
| `premium_sub` | native Codex / Codex companion | host-specific native ordering above |
| `openrouter_exec` | bounded agentic execution | GLM-5.2 -> DeepSeek V4 Flash -> Kimi K3 -> Grok 4.5 -> MiniMax-M3 |
| `frontier_api` | single-turn wrapper analysis | Kimi K3 -> Grok 4.5 -> GLM-5.2 -> Muse Spark 1.1 -> Gemini 3.5 Flash |
| `cheap_api` | single-turn wrapper text/analysis | DeepSeek V4 Flash -> GLM-5.2 -> MiniMax-M3 -> DeepSeek V4 Pro -> Qwen3 Coder |
| `bulk_api` | single-turn bulk analysis | Kimi K3 -> GLM-5.2 -> DeepSeek V4 Pro -> MiniMax-M3 -> DeepSeek V4 Flash |

The `codex` class walks `premium_sub -> openrouter_exec -> frontier_api -> cheap_api`; the `openrouter` class walks `openrouter_exec -> premium_sub -> frontier_api -> cheap_api`. Wrapper roles never autonomously implement complex logic, UI, or integration work.

The current `openrouter-wrapper.sh` accepts text prompts only. Model modality columns describe upstream capability, not an operational claim that this rail can yet attach images, audio, video, or files.

## Direct wrapper fallback behavior

The wrapper accepts a `[fallback-slug]` (4th positional arg) and sends the
primary plus fallback as one ordered OpenRouter `models` array. OpenRouter can
therefore walk to the fallback for any eligible model error without the wrapper
issuing a second client request:

```
bulk:       moonshotai/kimi-k3 -> openai/gpt-5.6-terra -> separate Codex fallback
mechanical: openai/gpt-5.6-luna -> z-ai/glm-5.2 -> separate Codex fallback
security:   moonshotai/kimi-k3 -> z-ai/glm-5.2 -> same-lane Codex completion + independent Codex sign-off
direct:     openai/gpt-5.6-terra -> moonshotai/kimi-k3 -> stop
```

The wrapper accepts one OpenRouter fallback slug. It does not invoke a native
Codex fallback; dm-review or Pipeline performs that as a separately receipted
attempt. The Pipeline cascade, not the wrapper, owns its longer role ladders.

OpenAI slugs are allowed through the receipted OpenRouter rail. Anthropic slugs
remain invalid as a primary or fallback and use native Claude only for allowed
non-coding/compatibility lanes.

## Kimi Provider Routing

The 2026-07-28 OpenRouter MCP snapshot exposed seven Kimi endpoints across
BaseTen, DigitalOcean, Nebius, Fireworks, Together, Moonshot AI, and a premium
Fireworks-fast variant. Endpoint health changes independently from the model
catalog and benchmark datasets, so do not convert one telemetry snapshot into a
permanent availability claim.

Quality and security Kimi calls default to `provider.sort: "exacto"` through
`openrouter-wrapper.sh`. Direct, bulk, and mechanical workloads default to
`provider.sort: "throughput"` so long generations favor faster capacity while
retaining provider fallback. An explicit `OPENROUTER_PROVIDER_SORT` or provider
order overrides the workload default. For a reproducible eval or incident
replay, set an explicit endpoint order:

```bash
OPENROUTER_PROVIDER_ORDER=baseten/fp8,moonshotai/mxfp4 \
OPENROUTER_ALLOW_FALLBACKS=0 \
/openrouter --model moonshotai/kimi-k3 "<approved evaluation prompt>"
```

`baseten/fp8` and `moonshotai/mxfp4` were the strongest-uptime standard-price
routes in the inspected snapshot; they are examples, not timeless defaults.
Refresh `list-model-endpoints` and `list-providers` before changing a durable
order. `OPENROUTER_FALLBACK_PROVIDER_ORDER` appends fallback-model endpoints to
the same native request, preserving one deterministic ordered provider list.
The response model, serving provider, generation ID, and usage belong in
the call receipt so an alias such as `moonshotai/kimi-k3` remains reproducible
after its canonical dated slug advances.

## Privacy (demoted -- opt-in only)

Model selection priority is **Quality > Price > Speed > Provider privacy** (user directive, 2026-07-18). `OPENROUTER_ZDR=1` is **opt-in**, never a default: Chinese first-party hosting (Moonshot/DeepSeek/Z.AI) is acceptable by default. Set it per-call only for genuinely sensitive material (client code under NDA, credentials-adjacent diffs); it pins providers with `data_collection: deny`.

**Kimi K3 interaction:** Kimi is available through multiple OpenRouter
providers, but ZDR eligibility and endpoint data policy can change independently
from model availability. Re-check live endpoint policy before a sensitive run.
If `OPENROUTER_ZDR=1` leaves no eligible Kimi endpoint, the cascade walks to the
next model rung and records the fallback.

## Note on roles vs slugs

The Pipeline cascade references slugs through abstract roles, while dm-review reads its lane-specific models from `routing-policy.json` and direct delegation uses command defaults. Similar model names do not make these routes interchangeable. Keep each matrix aligned with its own executable source.
