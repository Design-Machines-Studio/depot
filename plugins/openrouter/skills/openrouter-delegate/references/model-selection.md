# Model Selection

Decision tables for the three distinct routing systems that use these model names. Native Codex execution, dm-review/direct OpenRouter delegation, and the Pipeline cascade have different ordering and provenance; do not combine them into one fallback ladder.

> **Current production mode:** direct interactive `/openrouter` calls require
> exact-digest approval. dm-review may use the temporary sunset-bound operator
> batch. A ready broker retires interim mode but remains
> `broker_transport_unavailable` until broker-owned transport lands. Pipeline
> retains its separate workflow-authority gate.

## Available Models

Prices below are a checked-in planning snapshot from 2026-08-12, in USD per
million input/output tokens; they are not current telemetry. Before a paid or
policy-changing run, obtain a live MCP receipt with `observedAt` and `expiresAt`
no more than 15 minutes apart and use it only before expiry.

| Slug | Name | Input / output | Context | Quality and role |
|------|------|----------------|---------|------------------|
| `moonshotai/kimi-k3` | Kimi K3 | $3 / $15; $0.30 cache read | 1,048,576 | AA v4.1.1 intelligence 60 at max; 130M evaluated output tokens; review-only, focused security first |
| `openai/gpt-5.6-terra` | GPT-5.6 Terra | $1 / $6; $0.10 cache read, $1.25 cache write | 1,050,000 | OpenRouter quality backup; old AA v4.1 quality fields are stale |
| `openai/gpt-5.6-luna` | GPT-5.6 Luna | $0.10 / $0.60; $0.01 cache read, $0.125 cache write | 1,050,000 | Economical mechanical/config/doc worker; old AA v4.1 quality fields are stale |
| `x-ai/grok-4.5` | Grok 4.5 | $2 / $6; $0.30 cache read | 500K | AA v4.1.1 intelligence 56 at high; Coding Agent Index 76 in Grok Build with 1.9M average tokens; demanding bounded-execution candidate |
| `z-ai/glm-5.2` | GLM-5.2 | $0.392 / $1.232; $0.0728 cache read | 1,048,576 | AA v4.1.1 intelligence 53 at max; 140M evaluated output tokens; experimental/last fallback after poor local ergonomics |
| `meta/muse-spark-1.1` | Muse Spark 1.1 | $1.25 / $4.25; $0.15 cache read | 1,048,576 | Specialist multimodal fallback; old AA v4.1 evidence is stale and the wrapper remains text-only |
| `google/gemini-3.5-flash` | Gemini 3.5 Flash | $1.50 / $9; $0.15 cache read, $0.0833 cache write | 1,048,576 | Specialist multimodal fallback; old AA v4.1 evidence is stale and the wrapper remains text-only |
| `deepseek/deepseek-v4-pro` | DeepSeek V4 Pro | $0.63168 / $1.26336; $0.053298 cache read | 1,048,576 | Legacy cheap fallback; old AA v4.1 evidence is stale |
| `minimax/minimax-m3` | MiniMax-M3 | $0.30 / $1.20; $0.06 cache read | 1,048,576 model; top provider 524,288 | Capacity fallback; old AA v4.1 evidence is stale |
| `deepseek/deepseek-v4-flash` | DeepSeek V4 Flash 0423 | $0.14 / $0.28; $0.028 cache read | 1,048,576 | Superseded routed identity; it is not the current 0731 release |
| `deepseek/deepseek-v4-flash-0731` | DeepSeek V4 Flash 0731 | $0.08 / $0.18; $0.016 cache read | 1,048,576 | Recommendation-only; AA v4.1.1 intelligence 52 at max and 210M evaluated output tokens; provisional default bounded-execution candidate |
| `qwen/qwen3-coder` | Qwen3 Coder | $0.30 / $1; $0.10 cache read | 262,144 | Lower-confidence final fallback; prior 1M description was misleading |

OpenRouter returned every routed slug as available at `2026-08-11T22:42:37Z`.
The dated DeepSeek 0731 slug is also available. The `~deepseek/...-latest`
catalog identity is an alias with only 262,144 tokens at its top provider and is
not durable enough for executable routing or reproducible evaluation.

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
API-equivalent slug whose entry carries the price used for cost imputation. Its
deterministic input estimate uses
four UTF-8 input bytes per token, never populates token counter fields, and
names that estimate in row provenance. It does not add the native identity to
OpenRouter routing or assert billed spend. An alias absent from that object
remains unpriceable.

## Refreshing the routing matrix

Model preferences churn weekly with releases, so the matrix is a refreshable
recommendation instrument grounded in named external sources -- never a frozen
opinion. Refresh it on demand, and always before a paid or policy-changing run.
This is a documented human procedure; nothing here is automated. Its
machine-readable ownership and preservation paths live under
`refresh_protocol.routing`.

- **Price, context, and availability** come from the OpenRouter live API. Record
  a receipt whose `observedAt` and `expiresAt` are no more than 15 minutes apart
  (the existing freshness rule, mirrored as `freshness_rule_minutes` in the
  JSON) and use it only before expiry.
- **Quality scores** come from the named evaluation source with its dataset
  version recorded in `aa_scores.source` and `aa_scores.source_version`. A score
  without provenance does not enter the matrix.
- **Every routing refresh bumps the routing `snapshot_date`** -- both the
  top-level value and every entry under top-level `models` -- and the prose
  snapshot date above must move with it, because the validator compares them.
  Do not restamp `native_api_equivalent_cost`; it is a separate evidence domain.
- **Where a source is unreachable, keep the prior value** and mark it stale in
  the refresh write-up. Never guess, interpolate, or backfill from memory.
- **A refresh lands as an ordinary reviewed commit**, so the drift validator
  re-fences every downstream consumer against the new values.

## Refreshing native API-equivalent cost evidence

The `native_api_equivalent_cost` object is refreshed independently because it
supports observation, not routing. Its machine-readable ownership and
preservation paths live under `refresh_protocol.native_api_equivalent_cost`.
Only when the corresponding evidence was actually refreshed, update its
`snapshot_date`, the snapshot on each changed entry under its `models`, aliases,
prices, bytes-per-token estimate, and cited sources. An alias that targets a
top-level routing model uses that routing model's own price and snapshot; do not
copy or restamp it into the native model list.

Record the source and observation date in the reviewed change. A native-cost
refresh never changes the top-level routing `snapshot_date`, routing-model
entries, the prose routing snapshot above, or routing policy. Conversely, a
routing refresh never restamps native-only evidence. If either source is
unreachable, retain the prior value and mark it stale rather than claiming a
fresh snapshot.

The matrix recommends, routing policy decides, receipts record. Refreshing the
matrix never re-routes anything on its own; a routing change is a separate,
deliberate edit to `model-cascade.json`, `harness-profile.json`, or
`routing-policy.json`.

## Recommended workload matrix

These are recommendations for the next routing-policy review, not the current
executable order. Assembly is the calibration target: small internal,
self-hosted Go applications for roughly 4-50 co-op members, maintained by two
developers. A future supervisor checks worker scope, correctness, and
unnecessary complexity; it does not re-run the entire worker task by default.

| Model | Use | Avoid | Cost, latency, and context caveats | Required supervision | Confidence |
|-------|-----|-------|------------------------------------|----------------------|------------|
| Kimi K3 | Focused security review and difficult independent review | Implementation, fixing its own findings, routine bulk review | $15/M output; AA max used 130M output tokens and measured 42.5 tok/s | Bound files/questions/output, then hand accepted findings to a cheaper executor; independent code-aware sign-off remains | High for focused security; medium elsewhere |
| DeepSeek V4 Flash 0731 | Default candidate for bounded low-cost config, docs, and mechanical code execution | Broad autonomous changes, architecture, or security sign-off | Very low catalog price, 1M context, but AA max used 210M output tokens; cheap tokens do not guarantee cheap tasks | Codex 5.6 checks scope, correctness, tests, and overbuilding | Medium; no local 0731 task receipts yet |
| Grok 4.5 | More demanding bounded execution and escalation after a cheaper worker fails | Very large prompts, unbounded implementation, or unsupervised security work | 500K context; catalog price doubles above 200K prompt tokens; Grok Build scored 76 on the AA Coding Agent Index with 1.9M average tokens | Codex 5.6 reviews the changed surface and simplest adequate design | Medium-low pending local Assembly evidence |
| GLM-5.2 | Experimental last fallback or a narrow task class proven locally | Default implementation, security, or tasks needing iterative judgment | Attractive catalog price and 1M context, but AA max used 140M output tokens | Strong native supervisor, explicit acceptance criteria, and stop after repeated correction | Low for default use; medium only for a proven narrow exception |
| GPT-5.6 Terra via OpenRouter | Bounded quality backup when cheap candidates fail | Routine mechanical work and very large prompts without a cost check | 1.05M context; catalog price rises above 272K prompt tokens | Native Codex checks provider/model provenance and the resulting diff | Medium |
| GPT-5.6 Luna via OpenRouter | High-volume mechanical, config, and documentation work | Architecture, ambiguous integration, and consequential security decisions | Lowest OpenRouter GPT-5.6 price; price rises above 272K prompt tokens | Scope and test review by Codex; escalate model only after a demonstrated miss | Medium |
| DeepSeek V4 Flash 0423 | Preserve only while executable policy still references the exact slug | Treating it as the refreshed model or choosing it for new work | Superseded identity despite continued availability; 1M context | Existing routing receipts must record the exact returned model | High identity confidence; low recommendation confidence |
| DeepSeek V4 Pro | Legacy cheap fallback for bounded analysis | Default execution while 0731 remains untested locally | Price rose from the prior snapshot; old quality evidence is stale | Native code review | Low-medium |
| MiniMax-M3 | Capacity fallback for bounded text work | Prompts that assume full model context at the selected endpoint | Model advertises 1M, top provider exposes 524,288 | Native code review and endpoint-capacity check | Low-medium |
| Qwen3 Coder | Final fallback for small, explicit code tasks | Bulk/large-context work or reasoning-heavy changes | Catalog and top-provider context are both 262,144; no catalog reasoning support | Full changed-surface code review | Low |
| Muse Spark 1.1 | Specialist fallback when its modality becomes usable | Assuming multimodal support through the current text-only wrapper | 1M context; current quality evidence is stale | Native review and modality-path verification | Low |
| Gemini 3.5 Flash | Specialist fallback when its modality becomes usable | Routine text work at its output price or assuming wrapper file support | 1M context, 65,536 top-provider max completion; current quality evidence is stale | Native review and modality-path verification | Low |
| Fable 5, native subscription only | Non-coding strategy/advisor checkpoint: set direction and delegate bounded work | OpenRouter routing, implementation by default, or duplicating a full code review | Subscription use is not measured API spend; frontier model can add ceremony to small apps | Operator or Codex turns advice into a small execution brief | High for advisor boundary; medium task-by-task |
| Codex 5.6 Sol, native | Code-aware supervisor/reviewer and hard-problem fallback | Automatically redoing the worker task or using maximum effort by habit | 1.05M context; API-equivalent planning price is $5/$30, not subscription spend | Review scope, correctness, tests, performance, ergonomics, and unnecessary complexity | High |

The local evidence outranks generic benchmarks for this harness. Kimi found
consequential security defects, but successful review lanes commonly emitted
roughly 8K-25K completion tokens and cost about $0.14-$0.32 each; large streamed
payloads also failed before output. GLM completed a mechanical lane, but the
operator's repeated Depot/Assembly experience is that it needs too much
handholding. Older DeepSeek lanes have produced wrapper failures, nonexistent
paths, and false positives; those observations do not establish quality for the
new 0731 variant. There is no local Grok 4.5 or DeepSeek 0731 execution receipt,
so both recommendations remain provisional.

Artificial Analysis v4.1.1 currently reports intelligence 60 for Kimi K3
`max`, 52 for DeepSeek V4 Flash 0731 `max`, 56 for Grok 4.5 `high`, and 53 for
GLM-5.2 `max`. A separate July 8 Coding Agent Index report scores Grok 4.5 in
the Grok Build harness at 76 using 1.9M average tokens; that source conflicts
with itself on per-task cost ($2.59 in its summary and $2.49 in detail), so this
matrix does not canonicalize either cost. Its price and speed figures are first-party or median-provider
observations, not OpenRouter catalog prices. Older matrix coding and agentic
fields are retained as stale because the current pages did not expose complete,
comparable values for those exact evaluated variants.

## Native Codex execution

Native Codex models run through the Codex host or `codex-companion`; they are not OpenRouter requests and retain `implementedBy: codex` provenance.

| Host | Coding role | Ordered native models |
|------|-------------|-----------------------|
| Codex | `premium_sub` | GPT-5.6 Sol -> GPT-5.6 Terra -> GPT-5.5 -> GPT-5.6 Luna |
| Claude Code | `premium_sub` via `codex-companion` | GPT-5.6 Sol (representative; Codex selects its configured native model) |
| Generic | `premium_sub` | unavailable |

Official OpenAI guidance positions Sol for frontier complex reasoning/coding,
Terra for a balance of intelligence and cost, and Luna for efficient
high-volume workloads. All three support `none`, `low`, `medium`, `high`,
`xhigh`, and `max`, with 1.05M context. Benchmark the current effort and one
level lower on representative tasks. Use `medium` as the balanced starting
point, `low` for latency-sensitive work, `high` or `xhigh` only after a measured
quality gain, and reserve `max` for the hardest quality-first work.

| Native task | Model | Default effort | Escalate only when |
|-------------|-------|----------------|--------------------|
| Mechanical verification, narrow review, scoped fix | Luna or Terra | `low` | A lower-effort attempt misses a named acceptance criterion |
| Ordinary code-aware supervision and review | Sol | `medium` | Ambiguity spans components, a defect has meaningful consequence, or medium failed |
| Architecture or hard debugging | Sol | `medium` | Competing hypotheses remain after evidence gathering; then try `high` |
| Consequential security review | Sol | `high` | Use `xhigh` only for unresolved attack paths or failed high-effort verification |
| Hardest quality-first fallback | Sol | `xhigh` | Use `max` only after xhigh fails or a named high-consequence uncertainty justifies it |
| Non-coding strategy checkpoint | Fable 5 native | lowest native setting adequate to frame direction | Increase only when the advisor cannot resolve a named strategic uncertainty |

API-equivalent planning prices, not measured subscription spend, were verified
from official OpenAI model pages on 2026-08-12: Sol $5/$30 with $0.50 cached
input, Terra $2/$12 with $0.20 cached input, and Luna $0.20/$1.20 with $0.02
cached input. Prompts above 272K input tokens carry higher API pricing. The
matrix's native cost-imputation object continues to price only Sol: Terra and
Luna aliases were removed because their OpenRouter catalog prices differ from
official native API prices and the existing schema cannot represent both
without conflation.

Sources: [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model),
[Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol),
[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), and
[Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna).

Anthropic describes Fable 5 as its frontier model for ambitious, long-running
knowledge and coding work, and separately documents an advisor pattern in which
Fable sets strategy while a smaller, cheaper model executes. Depot maps that
pattern narrowly: Fable is a native-subscription-only, non-coding advisor
checkpoint; a bounded OpenRouter worker may execute, and Codex remains the
code-aware supervisor. Fable does not enter OpenRouter data, does not duplicate
a full code review, and no `anthropic/*` routing slug is permitted. Sources:
[Fable 5](https://www.anthropic.com/claude/fable) and
[Anthropic's advisor/orchestration webinar](https://www.anthropic.com/webinars/building-on-the-claude-platform-claude-fable-5-and-model-orchestration-patterns).

## dm-review target topology and direct OpenRouter delegation

The tables in this section mirror executable policy as of this evidence-only
refresh. They intentionally do not implement the recommendations above. In
particular, bulk Kimi and GLM fallback seats remain visible until the later
routing chunk changes and reviews them.

These calls use the OpenRouter API and retain `implementedBy: openrouter` even when the selected slug begins with `openai/`. A later Codex fallback is a separate native attempt with its own receipt.

| Workload | OpenRouter primary | OpenRouter fallback | Native completion |
|----------|--------------------|---------------------|-------------------|
| Direct `/openrouter` | Terra, unless `--model` overrides it | Kimi K3 | none implicit |
| Mechanical dm-review lanes | Luna | GLM-5.2 | Codex if the OpenRouter attempt cannot complete |
| Bulk / large-context dm-review | Kimi K3 | Terra | Codex if the OpenRouter attempt cannot complete |
| Security dm-review lens | Kimi K3 | GLM-5.2 | same logical lane may complete locally; independent full-diff non-implementing-family sign-off is always required |
| One-shot config / doc generation | Luna | Terra quality fallback | caller owns writing and verification |

Review timeouts are 3600s, extended to 7200s for bulk diffs of at least 10K lines. One-shot config/doc generation uses 1800s.

## Pipeline execution cascade target topology

Pipeline resolves abstract roles through `harness-profile.json`, then walks the class ladder in `model-cascade.json`. Its agentic OpenRouter executor is GLM-5.2-headed; Kimi remains a later capacity rung and the head of analysis-only frontier/bulk wrapper roles.

That sentence reports current executable topology, not the refreshed
recommendation. The proposal for the later routing chunk is to test the dated
DeepSeek 0731 identity as the bounded execution head, use Grok 4.5 for harder
bounded escalation, remove Kimi from implementation, and demote GLM-5.2 to an
experimental last fallback. No order or policy changed in this refresh.

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
security:   moonshotai/kimi-k3 -> z-ai/glm-5.2 -> same-lane local completion + independent non-implementing-family sign-off
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
