# Model-role portfolio benchmarking

Depot evaluates routing as a portfolio rather than as isolated model contests.
The complete object is the cross-product of exact available candidates and
policy roles, constrained by provider origin, security confinement, family
independence, capability, context, billing, and availability.

Every report reconstructs that complete grid. A cell can be evaluated without
making a call: a prohibited or capability-incompatible pairing is closed by its
policy evidence and exact exclusion reason. Calls are reserved for pairings
that could inform a real routing decision.

## Two evidence loops

The monthly full audit provides breadth. It screens every eligible cell with a
sealed applicable case, then deepens only incumbents, new candidates, close
challengers, and unresolved high-value gaps.

The weekly maintenance run provides freshness. It re-evaluates the whole grid
from live state and existing evidence but calls only changed, stale,
rotating-incumbent, or incomplete decision-relevant cells.

This prevents the unbounded cost of running every model on every role and case
three times while ensuring that no model, role, exclusion, or evidence gap
disappears from the report.

## Cell states

| State | Meaning |
|---|---|
| `ineligible` | A concrete policy, capability, context, security, family, provider, or availability constraint prevents routing. |
| `catalogued-untested` | The pairing is plausible but has no valid local evidence. |
| `stale` | Evidence predates a material model, case, scorer, dependency, or source change. |
| `screen-failed` | The retained first attempt failed completion, parsing, identity, fallback, or a mandatory assertion. |
| `screened` | One successful attempt; nomination evidence only. |
| `benchmarked` | Three comparable successful attempts on every applicable case. |
| `canary` | Admitted as a later rung and gathering attributable production evidence. |
| `incumbent` | Current routed candidate. |
| `promotion-blocked` | Competitive evidence exists, but a named promotion gate failed. |

Do not substitute `0` for missing evidence. A zero quality score is a retained
attempt result; an unsealed role is an instrumentation gap.

## Report views

The report keeps these axes separate:

- deterministic quality and retained failures;
- reliability and exact served identity;
- duration;
- prompt, completion, reasoning, and cache tokens;
- deterministic input bytes for native runs;
- provider-billed OpenRouter cost;
- native subscription marginal cost;
- native API-equivalent estimate;
- context and capabilities;
- family diversity;
- production completion, fallback, retry, first-pass validation, rework, and
  finding contribution;
- evidence freshness and missing instrumentation.

There is no weighted universal leaderboard. The decision is role-specific, and
the portfolio report also looks for unique coverage, redundancy, single-family
dependencies, missing roles, and subscription-capacity opportunities.

## Repository and private artifact boundary

Git contains reusable benchmark contracts, source selectors, deterministic
scorers, tests, hashes, complete grids, content-free aggregates, and routing
decision ledgers.

`/home/ned/benchmark-results` contains raw prompts assembled from private
source excerpts, raw model output, provider and native receipts, key-state
files, stderr, timing traces, and scorer history. Aggregate reports may cite
their hashes and source revisions without publishing their content.

This boundary makes the suite reproducible without turning a model-intelligence
commit into a repository-content or credential disclosure channel.

## Current coverage boundary

`depot-role-v1` has closed cases for `architect`, `builder-fast`, and
`review-fast`. The Baseplate portfolio catalog preserves prototype work for
federation architecture, scoped-DB implementation, and stack research, while
recording missing cases for `plan-critic`, `builder-deep`, `review-deep`,
`security-review`, `research-fast` standard-runner integration, and `editorial`.

The portfolio also records that Templ, Datastar, Live Wires, browser, and
accessibility implementation lacks a dedicated current role. That is a role
design question, not evidence that `builder-deep` should be permanently used
as a substitute.
