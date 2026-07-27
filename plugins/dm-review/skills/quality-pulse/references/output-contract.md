# Quality-Pulse Output Contract

Authoritative JSON is the sole source of truth. Markdown is a validated,
derived view and never becomes an input to classification or trend comparison.

## Required Authoritative Evidence

The JSON artifact records at least:

- schema version, pulse ID, invocation time, completion state, and stable
  projection digest;
- canonical repository root identity, verified ref/source, commit, and dirty
  state;
- profile path, schema version, profile version, and canonical validated
  profile digest, plus the normalized profile snapshot needed to replay
  classification without repository I/O;
- catalog ID, schema version, catalog version, computed content digest, and
  selected rule/metric IDs;
- dm-review, workflow-kernel, catalog-plugin, tool, service, and immutable image
  versions/identities;
- requested, attempted, and actual lane/tool identities;
- one lane receipt per requested primary and fallback, including
  `available|unavailable|failed|fallback|skipped`, evidence references,
  declared argv identity, synthesized execution-policy digest, redacted source
  evidence snapshot and digest, bound observation IDs,
  classified-observation digest, fallback reason, and `primary_lane_id` when
  applicable;
- redacted source evidence and normalized observations, with each normalized
  observation bound to the digest of its exact source object;
- each finding's stable identity, closed surface, rule and metric IDs,
  classification, actionability, confidence, and raw observation reference;
- coverage gaps, blockers, redaction outcome, and publication status;
- trend identity, compatible comparison result, or baseline discontinuity.

Volatile invocation data is retained outside the stable projection. The kernel
computes the stable projection digest from the declared stable fields so
successive compatible runs can be compared without pretending timestamps are
quality changes.

## Independent Dimensions

```text
evidence.status: available | unavailable | failed | fallback | skipped
finding.classification: actionable | informational | unknown
finding.actionability: actionable | informational
finding.surface: repository-profile-defined closed ID
finding.confidence: primary | fallback | inferred | unavailable
```

Fallback evidence names its unavailable or failed primary and remains
lower-confidence. Evidence failure does not manufacture a finding
classification. Conversely, a finding classification does not erase its
evidence state.

Unknown vocabulary or schema retains redacted raw telemetry, sets
`classification: unknown`, sets `actionability: actionable`, and fails the
pulse.

## Publication Order

1. emit authoritative JSON;
2. validate its complete schema and closed vocabularies;
3. recompute and verify the stable projection digest;
4. run redaction checks;
5. render Markdown from that validated JSON;
6. publish the Markdown only when rendering succeeds.

Any failure in steps 1-4 prevents Markdown publication. A stale prior digest
must not be relabeled as current.

## Trend Compatibility

Compare trends only when all of these identities are compatible:

- authoritative schema version;
- profile ID, version, and validated digest;
- metric definitions and their catalog bindings;
- requested lane tool, immutable image/service, and plugin identities.

If any required identity differs or is unavailable, emit a baseline
discontinuity naming the mismatched fields. Do not calculate or display deltas
across the discontinuity.
