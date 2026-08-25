# Pipeline Run Post-Mortem Schema

Every full pipeline run writes `plans/<slug>/run-postmortem.md` after the
orchestrator prepares the compact optional memory handoff. When the required
ai-memory tools are callable, the Pipeline caller applies that handoff and
records `written` or `already-present` in the existing receipt evidence before
presenting the final Summary Report. `Memory capture: failed -- <safe reason>`
retains nonblocking evidence when discovered callable tools fail during lookup
or write. When the tools are absent, the caller omits the write and all receipt
or summary mention; delivery remains complete.

## Required Sections

- `roleSplit` - chunk and lane counts by requested role.
- `effortSplit` - requested/effective normalized effort and every normalization.
- `fallbackStates` - role-level completed/unavailable disposition, fallback
  boolean, content-safe reason, and anonymous participant ID.
- `verification` - repository checks, review gates, browser evidence when
  required, and P1/P2/P3 closure state.
- `measurementSources` - private model-router receipt references and explicit
  unavailable token/cost provenance; never copy their concrete identity fields.
- `qualityLedger` - which anonymous lane and role found each review issue,
  retries, fallback states, and regressions shipped.
- `rankedRecommendations` - proposal-only changes for plugins exercised by this run.
- `standingRecommendations` - recommendations repeated in at least `N` runs, default `3`, with run citations.
- `kernelReliability` - shadow availability, semantic parity status, comparison reason counts, observation/adapter failures, missing authoritative evidence, browser recovery outcomes, owned-resource cleanup outcomes, and reconciliation results.
- `workflowClass` - validated class plus `workflow_class_defaulted`; metrics retain the authoritative manifest value unchanged.
- `privateRouterReceipts` - content-free operator-only receipt references for
  every routed attempt; exact model/provider/transport/billing remains there.
- `nextAction` - exactly one concrete next action or `none`.
- `wallClockSeconds` - elapsed seconds from the first authoritative event to the last event in the run.
- `activeComputeSeconds` - wall-clock seconds minus typed waits, floored at zero.
- `waitSecondsByCategory` - nonnegative durations grouped into `human_gate`, `external_dependency`, `capacity`, and `ci`. A wait receipt carries both `wait_category` and `duration_seconds`; unknown categories are invalid rather than silently folded into active work.

Kernel reliability data is measurement only. A parity report or reliability recommendation cannot mutate routing policy, workflow stages, cleanup state, merge results, or review outcomes. Promotion requires a separate human-approved source change after evidence review.

## Recommendation Shape

```markdown
### AWAITING APPROVAL: <short title>

- Plugin/file: `<path>`
- Concrete edit: `<role-policy entry or doc/validator change>`
- Expected token/cost delta: `<measured or bounded estimate>`
- Confidence: high|medium|low
- Evidence: `<run ids or receipt paths>`
```

Recommendations are never auto-applied. The human approves every plugin-source or routing-policy change.
