# Run memory enrichment (optional personal source)

Loaded by `/pipeline-run` after execution only when the ai-memory tools are
callable in this session. When they are absent, omit the enrichment silently --
no warning, receipt line, summary mention, coverage gap, or install request --
and never load this file.

Immediately after the execution-orchestrator returns and before presenting its
human summary, consume the single optional `Memory observation handoff:` field
from the agent result. Keep the raw observation internal. Determine availability
from the callable-tool inventory or tool search without making a probe call.
Capability availability is the complete rule; do not use identity, environment,
or repository heuristics.

If the required ai-memory tools are callable, validate that the observation is
the dated Pipeline format for exact entity `DepotPlugin:pipeline` and is under
300 characters, then:

1. `search_entities` for `DepotPlugin:pipeline`; create it as type `Tool` with
   `add_entity` only when missing.
2. Read the entity and check its same-day observations for the exact handoff.
3. If absent, call `add_observation`, then `save`.

After a successful write or exact duplicate, append `Memory capture: written`
or `Memory capture: already-present` to `plans/<feature>/receipt.md` and retain
that outcome in internal summary evidence before presentation. If callable
tools fail during lookup or write, append `Memory capture: failed -- <safe reason>`
and retain the same nonblocking operational evidence without marking execution
or delivery incomplete. If the tools are absent, omit the write and every receipt or summary mention.
Do not show the raw handoff in ordinary human-facing chat, mark execution or
delivery incomplete because optional memory is absent, or ask the user to
install or configure the personal source. Only an explicit user request for an
ai-memory operation makes an unavailable capability reportable.
