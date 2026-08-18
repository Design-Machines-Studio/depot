# Caller-side optional memory enrichment

Loaded by `/pipeline` Phase 7 only when the ai-memory tools are callable in this
session. When they are absent, omit the enrichment silently: create no warning,
skipped lane, coverage gap, or install request, and never load this file.

In full mode, immediately after the execution-orchestrator returns and before presenting its human summary, consume the single `Memory observation handoff:` field from the agent result. In lean mode, form the same single compact observation directly from the bounded implementation and final-review result; do not invent an orchestrator handoff or a second memory schema. Keep the raw observation internal. Determine availability from the callable-tool inventory or tool search without making a probe call. Capability availability is the complete rule; do not use identity, environment, or repository heuristics.

If the required ai-memory tools are callable, validate that the observation is the dated Pipeline format for exact entity `DepotPlugin:pipeline` and is under 300 characters, then:

1. `search_entities` for `DepotPlugin:pipeline`; create it as type `Tool` with `add_entity` only when missing.
2. Read the entity and check its same-day observations for the exact handoff.
3. If absent, call `add_observation`, then `save`.

After a successful write or exact duplicate, append `Memory capture: written` or `Memory capture: already-present` to `plans/<feature-slug>/receipt.md` and retain that outcome in internal summary evidence before Phase 7. If callable tools fail during lookup or write, append `Memory capture: failed -- <safe reason>` and retain the same nonblocking operational evidence without marking delivery incomplete. If the tools are absent, omit the write and every receipt or summary mention. Do not show the raw handoff in ordinary human-facing chat, mark delivery incomplete because optional memory is absent, or ask the user to install or configure the personal source. Only an explicit user request for an ai-memory operation makes an unavailable capability reportable.

The unconditional Phase 7 Deliver step (present the execution summary; load `phase7-caller-verification.md` when a `renderedSurface: required` chunk ran) lives in the `/pipeline` command, not in this ai-memory-conditional file.
