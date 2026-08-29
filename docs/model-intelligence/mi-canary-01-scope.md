# MI-CANARY-01 implementation scope

Issue [#110](https://github.com/Design-Machines-Studio/depot/issues/110) adds
the production-canary boundary intentionally left out of the sealed v2 repair
merged in PR #111.

## Already supplied by PR #111

- A digest-bound `depot-role-v2` contract with two sealed cases for every
  policy role.
- Exact requested, served, provider, native-alias, and fallback attribution.
- Stage-owned benchmark faults, evaluator bindings, nullable measurement
  coverage, native/OpenRouter transports, and paid-cost stop controls.
- Model-intelligence views that keep sealed evidence, ordinary production
  observations, and economics distinct.

## Smallest missing boundary

One repository-owned canary contract must create a disposable worktree from an
immutable Depot revision, run one policy-admitted candidate, validate the
result with the existing v2 scorer plus bounded repository checks, and retain
one attributable, size-bounded attempt for a separate canary reporter and
routing-ledger view. It must never mutate the operator checkout or candidate
ordering.

## PR #106 prototype inventory

Reused:

- its small-team, real-repository work-unit framing;
- source selectors and exact-revision evidence binding;
- separate controlled and production gates;
- its explicit rejection of a blended leaderboard.

Superseded or omitted:

- the v1 portfolio state machine and stale benchmark conclusions;
- unsealed external Baseplate cases and their private-source assumptions;
- monthly/weekly sweep machinery and broad matrix scheduling;
- proposed routing changes and overlapping version edits.

PR #106 remains open and unchanged. Its owner must still decide whether to
close or replace it after this implementation is reviewed.

## Deliberate non-goals

No service, database, daemon, transcript warehouse, generic event platform,
scheduler, autonomous benchmark evolution, opaque leaderboard, automatic
routing mutation, approval system, or second orchestration framework.

## Expected footprint and versions

OpenRouter gains a production-canary schema, work-unit manifest, runner,
operator documentation, and offline fixtures. The existing model-intelligence
reporter and tests gain a separate canary ingestion path. OpenRouter moves from
`1.19.11` to `1.20.0`. Model-router remains `0.4.2`; its shipped policy and
contract do not change.
