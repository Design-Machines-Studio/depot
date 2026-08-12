# OpenRouter MCP Control Plane

The official hosted MCP at `https://mcp.openrouter.ai/mcp` is an optional
control-plane companion to this plugin's direct API runner. It is not the
pipeline execution transport.

## Responsibilities

Use the MCP read-only tools for:

- connection and credit checks (`ping`, `get-credits`);
- current model identity and capabilities (`list-models`, `get-model`);
- provider and endpoint telemetry (`list-providers`,
  `list-model-endpoints`);
- current benchmark/ranking context (`list-benchmarks`,
  `list-daily-model-rankings`);
- documentation lookup (`search-docs`, `view-skills`);
- post-call inspection when the OAuth identity can see the generation
  (`get-generation`).

The direct API runner remains authoritative for:

- the team `OPENROUTER_API_KEY` and its workspace policy;
- exact disclosure filtering and payload hashing;
- large stdin payloads, timeouts, provider preferences, and model fallbacks;
- bounded diff validation and independent non-implementing-family verification;
- content-free generation receipts returned with the workflow.

The hosted MCP does not expose an authenticated workspace/identity inspection
tool. Its OAuth credential is separate from `OPENROUTER_API_KEY`, expires, and
may have a different spend cap or workspace boundary. Never infer team-workspace
attribution from a successful `ping` or credit balance.

## Codex Setup

Register the MCP globally so discovery remains available even when the Depot
plugin is not installed:

```bash
codex mcp add openrouter --url https://mcp.openrouter.ai/mcp
codex mcp login openrouter
```

MCP servers are discovered when a task starts. After adding or changing the
registration, open a fresh Codex task before treating missing tools as an
authentication failure.

## ChatGPT Setup

Add the same HTTPS endpoint as a custom app/connector where the ChatGPT
workspace permits custom MCP servers. The connector exposes OpenRouter as tools;
it does not replace ChatGPT's native model provider or make the OAuth identity
equivalent to the team's direct API key.

## Workflow Preflight

Before a routing-policy refresh or any claim about current catalog state:

1. `ping`.
2. Find the policy model by stable alias.
3. Record its current canonical slug, context, modalities, reasoning efforts,
   and catalog price.
4. Inspect current endpoints and provider slugs.
5. Consult benchmarks as a separate snapshot; do not overwrite catalog pricing
   with benchmark-run pricing.
6. Record `observedAt` and `expiresAt` in UTC. The default freshness window is
   15 minutes; a stricter workflow-specific window may shorten it.

MCP unavailability is an evidence gap, not permission to make a current catalog
claim or mutate routing policy. A live catalog receipt is usable only when both
timestamps are present and current time is no later than `expiresAt`. Normal
execution follows the reviewed checked-in routing policy and records its
version; it does not pretend that policy is live telemetry. A policy-refresh
workflow without current evidence stops and records `live_catalog_unavailable`.

## `send-message` Boundary

`send-message` is suitable for an explicit, small, ad-hoc comparison. Automated
pipeline and dm-review payloads continue through the direct runner.

Automated workflows MUST NOT call `send-message`; validators enforce that
dm-review and pipeline contain no such invocation. For a user-requested ad-hoc
comparison, first apply the same artifact-delegation boundary and automatic
byte screening, send only the eligible payload, record the generation ID,
and retain independent non-implementing-family sign-off for consequential security work.
