# Main driver and bounded workers

Human-facing policy, updated 2026-09-20. Optimize total completion cost:
input (including repeated cached context), output/reasoning, retries, integration
and review, defects/rework, elapsed time and maintainer attention. Start with the
lowest capable model for the whole job, not the cheapest token price. A stronger
model, including Astra as the initial choice, is justified by task-specific
uncertainty or evidence that it improves correctness, completeness or total
completion efficiency. Do not require a predictable cheap-model failure first.
Speed matters when it reduces total delivery cost; no model name guarantees it.
Concrete identities here are operator-only; `role-policy.json` owns selection.

| Work | Starting point | Escalation |
|---|---|---|
| Evidence gathering, release-readiness checks, routine planning and coordination | `research-fast`; GPT-5.6 Luna Medium in Codex | Sol Medium when evidence materially conflicts |
| Mechanical/docs changes | `builder-fast`; Luna Low or Medium | Increase only for demonstrated difficulty |
| Bounded implementation, including settled UI, logic and integration | `builder-fast`; Luna High | Terra after one focused failed attempt or named uncertainty |
| Complex implementation requiring unresolved judgment | `builder-deep`; Terra Medium | Sol, then Astra only for concrete difficulty |
| Unresolved architecture | `architect`; Sol Medium | Astra for particularly difficult architecture; not a routine planning default |
| Standalone review orchestration | `review-coordinator`; Sol Medium | Astra for difficult judgment; do not repeat already valid reviews |
| Narrow design question | `design-consultant`; Sol with the prototype as authority | Existing eligible specialist fallback, not a redesign mandate |
| Bounded inexpensive or specialized analysis | Eligible OpenRouter participant | Host retains tools, integration and verification unless transport proves otherwise |

Codex drives coding, integration and verification. Claude is excluded from the
default candidate policy, including design consultations; available Claude
credentials do not restore automatic eligibility. Native Claude transport remains
compatible for separately configured use, without any paid-overage default.

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
perspectives after capability and availability resolution. A quota response
exhausts that native rail for the run; do not retry it under another model name.
Unknown allowance mapping is not proof of exhaustion, and an active Codex driver
is not unavailable merely because a nested CLI cannot identify its parent.
Deliberate relief before exhaustion uses the existing direct `/openrouter`
choice or ignored local `disabledCandidates`; it does not require a quota error
or tracked provider override. An unknown monthly-spend/headroom measurement is
never described as verified affordability even when the API credential and
current balance make the rail attemptable.

Keep OpenAI and Anthropic on their native CLI rails; no Astra slug is added to
the OpenRouter routing catalog. That catalog's 2026-08-27 evidence is unchanged.
Astra's API-equivalent price is absent from the existing cost matrix, so report
it as unavailable while labeling native use `included subscription`. A later
native-cost refresh must handle current prices and long-input tiers rather than
applying a short-input price to every request. Never report API-equivalent
estimates as subscription charges.

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
