# Main driver and bounded workers

Human-facing policy, updated 2026-10-11. Optimize total completion cost:
input (including repeated cached context), output/reasoning, retries, integration
and review, defects/rework, elapsed time and maintainer attention. A capable lead owns task understanding, meaningful design decisions,
integration, acceptance and final review judgment. Use economical workers for
bounded questions with independently checkable results. Token price alone does
not establish economical completion. A stronger
model, including Astra as the initial choice, is justified by task-specific
uncertainty or evidence that it improves correctness, completeness or total
completion efficiency. Do not require a predictable cheap-model failure first.
Speed matters when it reduces total delivery cost; no model name guarantees it.
Concrete identities here are operator-only; `role-policy.json` owns selection.

Use `claude-design` when available under the
[shared design contract](design-consultation.md#optional-design-skill).
Otherwise continue the required design consultation with the participant's own
judgment and supplied evidence; missing skill text alone never blocks it.

| Work | Starting point | Escalation |
|---|---|---|
| Narrow file discovery, extraction, supplied-log analysis and classification | `research-fast`; Haiku 5.5 when its live canary supports the required capability, then existing Luna Fast and Sol fallbacks; Low/Medium | Sol when evidence materially conflicts |
| Settled bounded application code and tests, including Go/Templ/Datastar | `builder-fast`; Luna Fast, Low/Medium (High with a reason) | Sol for unresolved/consequential judgment |
| Coordination, harder implementation and consequential review | `builder-deep`, `architect`, `review-deep` or `review-coordinator`; GPT-6.1 Sol | Astra for a named difficult problem or justified escalation |
| Applicable UI/UX design judgment and design repair | `design-consultant`; Opus 5.5, bounded affected surfaces | Sol; prototype and explicit user decisions remain authoritative |
| Inexpensive or specialized analysis | Eligible OpenRouter participant | Host owns tools, integration and verification unless transport proves otherwise |

Haiku is a narrow research/extraction candidate, not general feature ownership
or consequential review judgment. Builder-fast and review-fast continue to
start on Luna Fast pending comparative evidence. Fable/Claude is not the
ordinary first attempt for coding, architecture or code review. Preserve Opus for applicable design judgment and design fixes. One agent
can do substantial settled work; file count/language/UI/integration alone never
establishes difficulty. An explicit stronger starting role may reduce total cost;
state the concrete reason instead of requiring a cheap failed attempt.

A generic Pipeline invocation chooses direct, lean or full. Direct settled
low-impact work uses acceptance plus focused verification; bounded judgment uses
a short plan and proportional independent review; uncertainty/consequence adds
only useful research/planning/adversarial work. Preserve repository requirements,
explicit full requests, tests, prototype/browser checks and all retained findings.
New risk escalates the current run without discarding valid completed work.

## Bounded delegation contract

Prefer deterministic search, scripts and test runners for mechanical work. Do
not dispatch a worker merely to wrap a command. A narrow read-only question does
not trigger full Pipeline planning. The lead can answer directly when preparing
and integrating a worker would cost more than the task.

Each worker packet contains one clear question, relevant source-bound evidence,
owned files when writing, objective acceptance criteria, and a bounded result
format: answer/findings, source paths and lines, actions actually performed,
uncertainty and remaining checks. Keep necessary context; omit whole transcripts
and unrelated inventory. Routine workers start at low/medium effort. Higher
effort needs a task-specific reason. Mechanical implementation remains eligible
for builder-fast when settled patterns and independently specified tests make
success objectively verifiable. Workers do not own general feature design.

The lead collects shared GitHub/API evidence once and reuses that exact snapshot
across workers. The lead owns changes to maintained checkouts, shared serving
bindings, integration and publication. Workers write only their assigned files
in task-owned isolated checkouts. Use two concurrent workers by default for two
maintainers, fewer for dependent tasks or unknown rail availability. A concrete
independent workload may justify more. Never parallelize shared mutations or
send duplicate API requests. Settle the first unknown-availability attempt before
sending more work on that account, then reuse its run-local failure receipt.

A worker's completion is evidence for its bounded task, not tests, browser
coverage or review approval. Cite only commands and checks actually performed.
Read-only Claude tools are Read/Glob/Grep; Bash tests remain lead-owned. Browser
interaction remains host-owned for every current routed transport. The lead
runs independent acceptance and owns the final review judgment. Substantive
changes retain proportional independent review, automatic review-and-repair,
all retained P1/P2/P3 repairs, prototype/user authority, required browser checks,
commit/push and exact owned cleanup.

Reuse valid exact-source tests and review evidence. Changes or a concrete new
question require affected rechecks, not an entire review to try another model.
A different model family may provide a useful second opinion. It is not a new
mandatory gate, and missing implementation-origin receipts never block ordinary
review. Existing selected coverage and explicit independence requests still apply.

## Haiku release and activation evidence

The fixed identity is `claude-haiku-5-5`, with no dated alias. Official effort
supports low, medium, high, xhigh and max. Router requests remain
low|medium|high|max, transmitted unchanged to native Claude. Start short worker
requests at low/medium; do not carry Codex Fast or context settings into Claude.
Use native Claude subscription access only for this candidate. Do not enable
paid credits, upgrade accounts, add a direct API transport or route Anthropic
through OpenRouter. Unknown quota remains unknown and permits one bounded
attempt after subscription authentication; confirmed failures reuse the existing
run-local receipts and fall back across providers.

The API price per million input/output tokens is $0.10/$0.50 for a request with
at most 100,000 input tokens and $0.50/$2.50 above that threshold. All input
counts toward the threshold, including cache reads/writes. The higher tier prices
the whole request, not only excess tokens. Five-minute cache writes/read prices
are $0.125/$0.01, or $0.625/$0.05 above the threshold; one-hour writes are
$0.20/$1.00. These are API prices, not subscription charges. Claude list-price
`total_cost_usd`/`costUSD` is not a measured subscription charge. Keep cached
input, output/reasoning and unavailable measurements distinct. A shorter packet
can reduce repeated input, but do not claim savings without accepted-work data.
The new tokenizer also prevents comparing old token counts as equivalent work.

Sources verified 2026-10-11: [release](https://www.anthropic.com/claude-haiku-5-5),
[migration](https://platform.claude.com/docs/en/models/haiku-5-5/migration-guide),
[effort](https://platform.claude.com/docs/en/build-with-claude/effort) and
[pricing](https://platform.claude.com/docs/en/about-claude/pricing).
[HAIKU-DELEGATION-01 evidence](https://github.com/Design-Machines-Studio/depot/blob/main/docs/haiku-delegation-01.md)
records live capability limits and the small matched canary. Published model
benchmarks and the linked video are not local benchmark proof. Unproven
capabilities/default changes remain inactive; `enabled: false` in role policy
excludes a candidate from both recommendation and dispatch.

## Luna service mode

Every Luna role and fallback uses native Codex Fast. The dispatcher requests
`--config 'service_tier="fast"' --enable fast_mode --strict-config` separately
from `model_reasoning_effort`; never infer inheritance, use prompt text as proof,
or impose maximum reasoning. It checks native configuration support, records
requested/transmitted mode and separate native-event confirmation when present.
An unsupported/unavailable Fast configuration falls through to an eligible
candidate; confirmed Standard output is not accepted as Luna Fast. Missing
served-tier telemetry remains unavailable, never a fabricated confirmation.
No global driver/context settings or other provider settings change.

Verified against installed Codex 0.160.0 thread/turn serviceTier schemas and the
Luna catalog’s Fast/priority tier on 2026-10-09. Official [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
documents Fast mapping to priority; [speed documentation](https://learn.chatgpt.com/docs/agent-configuration/speed)
explains availability and higher usage. Fast is an explicit operator requirement,
not an assumption that it saves allowance. Ordinary effort is Low/Medium; High
requires a reason. Concrete dispatch remains solely in role-policy.json.

Do not add delegation automatically. For a small settled task, packet preparation,
duplicate context and synthesis may cost more than direct execution. When useful,
workers receive only relevant evidence, owned files and verifiable acceptance.
They never inherit the driver's model or effort. Agent cards remain `model: inherit`
as neutral metadata; dispatch uses each explicit role request.

Every human recommendation names the exact model, effort, harness and one exact
fallback from the router. Explain any choice above the lowest capable role with
one task-specific reason. OpenRouter text analysis/patch drafting is not autonomous
tool execution. Do not broaden worker capabilities merely because the host runs
Git, tests or browser acceptance. Do not drop capabilities the worker really needs.

The normalized request vocabulary stays `low|medium|high|max`. Explicit effort
is preserved across candidate fallback, with only the existing transport mapping
(OpenRouter `max` becomes `high`). Sol High is an optional operator starting
point/comparison, not a hidden rewrite of a Low request during automatic fallback.
Native host-only levels such as `xhigh` do not expand the routing contract.

## Evidence and limits

Earlier first-party Astra calibration is historical guidance, not evidence that
Astra is cheapest for every task. The lowest-capable policy supersedes the old
Astra-first defaults. Compare accepted results, corrections and total tokens when
available; never infer account allowance savings from API prices or model names.
Keep applicable specialist review and fix every retained P1/P2/P3.

## Reduce repeated context

- Refresh changed facts, not the entire project inventory, on every planning turn.
- Read required instructions once; use targeted ranges and bounded command output.
- Keep one concise current handoff with exact heads, decisions and remaining work.
  Start a fresh task session at a meaningful boundary when old context dominates;
  do not restart each turn and lose useful cache reuse.
- Reuse still-exact verification/browser evidence and recheck affected lanes only.
- Do not attach whole transcripts to agents or repeat full model reports per stage.
- Large context is optional. A shorter handoff or earlier compaction can reduce
  repeated input, but compaction also costs tokens; measure a real task before
  asserting savings. Never change user context settings silently.

## Subscription and provider boundaries

Prefer eligible subscription capacity for each role. Existing OpenRouter
candidates remain available as usage extenders and for useful independent
perspectives after capability and availability resolution. A known applicable
quota response exhausts that native rail for the run; do not retry it under
another model name. Confirmed Codex subscription authentication with missing or
incomplete allowance telemetry remains unknown and permits one bounded native
attempt. It is never described as verified healthy. Unknown allowance mapping
is not proof of exhaustion, and an active Codex driver is not unavailable
merely because a nested CLI cannot identify its parent.
Deliberate relief before exhaustion uses the existing direct `/openrouter`
choice or ignored local `disabledCandidates`; it does not require a quota error
or tracked provider override. An unknown monthly-spend/headroom measurement is
never described as verified affordability even when the API credential and
current balance make the rail attemptable.

An OpenRouter `insufficient_credits` response confirmed by its validated
receipt exhausts that paid rail for the current run when confirmed by its validated
provider receipt; continue to an
eligible native candidate without repeating OpenRouter models on the same
credential. A 429 `rate_limited` response remains distinct. Missing token or
cost measurements stay unavailable in the terminal receipt and never gate a
required review lane.

Native subscription order follows the role; OpenRouter eligibility stays in the role policy.
GPT-6.1 Sol/Luna guidance uses the 2026-09-30 OpenAI model cards; other catalog rows
retain their explicitly dated prior evidence. New native API-equivalent aliases
remain unavailable until imputation respects long-input tiers. Historical
GPT-5.6 prices remain historical only, never subscription charges. Published API
context limits do not prove this host's Codex context or rollout availability.

Use the existing bounded OpenRouter controls and exact terminal receipts. For
the current operator, the target is at most $50/month; this is a budget goal,
not an applied account limit or evidence of remaining headroom. No account-wide
budget service is required. Respect known remaining budget, avoid speculative
paid sweeps, and report missing monthly-spend measurements plainly.

## Optional Codex context settings

NED's user configuration already selected Astra Low on September 8:

```toml
model = "gpt-6-astra"
model_reasoning_effort = "low"
model_context_window = 1000000
model_auto_compact_token_limit = 400000
```

This is a local observation, not a shared configuration template. Do not copy
the context overrides into repositories, other models, Claude, or OpenRouter.
Do not overwrite an operator's explicit model or effort selection.

Codex CLI 0.153.4's cached catalog, fetched at 2026-09-07T23:20:32Z, advertises
Astra's default window as 272,000, maximum as 872,000, and usable percentage as
95. The matching release's [override code](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/models-manager/src/model_info.rs)
clamps the requested window to the catalog maximum. Its
[context calculations](https://github.com/openai/codex/blob/rust-v0.153.4/codex-rs/protocol/src/openai_models.rs)
therefore imply 872,000 total, 828,400 usable, and a 400,000 auto-compaction
threshold (the smaller of the explicit threshold and 90% of the total window).
These are source-and-catalog calculations, not an observed long-running session
or proof that a remote service accepts every such request.

The [API model card](https://developers.openai.com/api/docs/models/gpt-6-astra)
advertises a larger API window; it does not override Codex's catalog cap. Larger
context may reduce compaction frequency on long tasks while increasing retained
input, latency, and usage. The 400,000 threshold still compacts before filling
the maximum window. Keep this optional and compare real long tasks before
claiming a performance improvement; see the
[Codex configuration reference](https://developers.openai.com/codex/config-reference).
