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
- bounded diff validation and independent Codex verification;
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

Before a major OpenRouter review or routing-policy refresh:

1. `ping`.
2. Find the policy model by stable alias.
3. Record its current canonical slug, context, modalities, reasoning efforts,
   and catalog price.
4. Inspect current endpoints and provider slugs.
5. Consult benchmarks as a separate snapshot; do not overwrite catalog pricing
   with benchmark-run pricing.
6. Record the observation timestamp and continue with the direct API runner.

MCP unavailability is an evidence gap, not permission to replace the requested
model silently. Continue with the checked-in matrix only when it is still within
its stated freshness window; otherwise return the lane to Codex and record
`live_catalog_unavailable`.

## `send-message` Boundary

`send-message` is suitable for an explicit, small, ad-hoc comparison. Automated
pipeline and dm-review payloads continue through the direct runner.

If a workflow ever opts into `send-message`, it must apply the same exact
artifact-delegation boundary first, send only the approved payload bytes, record
the generation ID, and retain independent Codex sign-off for consequential
security work. General permission to use OpenRouter is not payload-specific
authorization.
