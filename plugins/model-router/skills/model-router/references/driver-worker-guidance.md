# Main driver and bounded workers

Human-facing setup and calibration, observed 2026-09-08. Concrete identities in
this reference are for the operator; never copy them into worker, reviewer,
critic, or architect packets. The existing `role-policy.json` owns selection.

| Work | Starting point | Escalation |
|---|---|---|
| Main driver and orchestration | GPT-6 Astra Low in Codex | Medium for demanding reasoning; High or above only for a named difficult architecture, debugging, or review problem |
| Architecture and integration participant | `architect` or `builder-deep`; native Astra first | Medium for demanding work; explicit High/Max when justified |
| Bounded execution | `builder-fast`; native GPT-5.6 Luna at High | Max for demonstrated difficulty; lower effort for simple mechanical work |
| Final design, integration, and review decisions | Main driver | Keep applicable specialist review lanes and fix every retained P1/P2/P3 |
| Optional fallback or comparison | GPT-5.6 Sol High | Existing fallback candidate, never the primary driver |
| Specialist middle tier | Existing GPT-5.6 Terra critic/review candidates | No new tier, role, or orchestration branch |

Luna execution requires settled requirements, exact file ownership, and
verifiable acceptance criteria. The driver owns unresolved design and integrates
the result. Workers do not inherit the driver identity or effort: agent cards
remain `model: inherit` as neutral metadata, while actual dispatch uses each
explicit role request. Routine review workers remain separate from the driver.

The normalized request vocabulary stays `low|medium|high|max`. Explicit effort
is preserved across candidate fallback, with only the existing transport mapping
(OpenRouter `max` becomes `high`). Sol High is an optional operator starting
point/comparison, not a hidden rewrite of a Low request during automatic fallback.
Native host-only levels such as `xhigh` do not expand the routing contract.

## Evidence and limits

[Tibo's September 6 calibration](https://x.com/thsottiaux/status/2096688770523467947)
recommends moving from satisfactory Sol High usage to Astra Low or Medium. This
is first-party calibration guidance, not a guarantee on every Depot task. The
post was retrieved through the public FxTwitter mirror when direct X retrieval
failed. It supplies no evidence for Luna execution performance.

Luna High/Max bounded execution is a workflow hypothesis. Validate it with an
ordinary implementation chunk and its required review: accepted result, retained
defects, corrections, elapsed time, tokens when measured, and actual paid cost.
Do not call this a benchmark win or claim lower subscription usage without
measurements. Use one useful comparison when evidence warrants it, not a model
tournament. The [Astra migration guide](https://developers.openai.com/api/docs/guides/latest-model)
also supports clear instructions, deliberate delegation, and proportionate tests.

## Subscription and provider boundaries

Prefer eligible subscription capacity for each role. Existing OpenRouter
candidates remain available as usage extenders and for useful independent
perspectives after capability and availability resolution. A quota response
exhausts that native rail for the run; do not retry it under another model name.
Unknown allowance mapping is not proof of exhaustion, and an active Codex driver
is not unavailable merely because a nested CLI cannot identify its parent.

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
