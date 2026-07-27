# Quality-Pulse Output Contract

Authoritative JSON is the sole source of truth. Markdown is a validated,
derived view and never becomes an input to classification or trend comparison.

## Required Authoritative Evidence

The JSON artifact records at least:

- `schema_version`, `pulse_id`, invocation time, `completion_state`, and stable
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
- requested, attempted, and actual lane/tool identities, represented by
  `requested_identities`, `attempted_identities`, and `actual_identities`;
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
- `coverage_gaps`, `blockers`, redaction outcome, `publication_status`,
  `publication_state_digest`, and the embedded keyed
  `publication_attestation`;
- `trend_result`, initially `not_compared` when no baseline was supplied, or a
  compatible comparison/baseline discontinuity returned by trend comparison.

Volatile invocation data is retained outside the stable projection. The kernel
computes the stable projection digest from the declared stable fields so
successive compatible runs can be compared without pretending timestamps are
quality changes.

## Independent Dimensions

```text
evidence.status: available | unavailable | failed | fallback | skipped
lane.status: available | fallback
finding.classification: repository-profile-defined closed ID | unknown
finding.actionability: actionable | informational
finding.surface: repository-profile-defined closed ID
finding.confidence: high | medium | low | unknown
finding.evidence_confidence: primary | fallback | unavailable
```

Lane status never overwrites observation-level evidence status. Fallback
evidence names its unavailable or failed primary, records both
`lane_id` and `primary_lane_id`, and downgrades classification confidence by one
level in addition to `evidence_confidence: fallback`. Evidence failure does not manufacture a finding
classification. Conversely, a finding classification does not erase its
evidence state.

Unknown vocabulary or schema retains redacted raw telemetry, sets
`classification: unknown`, sets `actionability: actionable`, and fails the
pulse.

## Publication Order

1. load the host-owned publication authority key from the fixed OS-account
   path `~/.config/design-machines/quality-pulse/publication-authority.key`,
   with no profile, environment, or CLI path override;
2. build the ready JSON, validate its complete schema and redaction outcome,
   and embed an HMAC attestation before serialization;
3. pass an authoritative baseline to `inspection-finalize`, which computes
   the trend and replaces the attestation for the new exact content digest;
4. preview Markdown only after revalidating the embedded attestation with the
   host key;
5. use `inspection-publish` to durably write and byte-verify the
   profile-declared Markdown, then the rendered-state authoritative JSON,
   before minting `markdown_rendered` and `published`; each transition replaces
   the keyed attestation and cannot be requested through generic finalize.
   The two destinations must remain physically distinct, and both exact final
   files are revalidated before the published envelope is emitted.

Trend comparison must be bound before ready-state attestation and rendering.
Publication status is an
operational envelope excluded from the content stable projection and rendered
Markdown; `publication_state_digest` binds the operational status to the
content digest without making publication transitions stale the Markdown.
Every serialized state, including initial readiness, embeds a matching
host-keyed transition attestation. The HMAC covers the pulse, exact content and
state digests, prior and target states, completed host action, authorization
event, and authority-key ID. Validation without the correct host key fails
closed, even when a caller recomputes all public fields and hashes.

Any failure in steps 1-5 prevents Markdown publication. A stale prior digest
must not be relabeled as current.

## Trend Compatibility

Compare trends only when all of these identities are compatible:

- authoritative schema version;
- profile ID, version, and validated digest;
- metric definitions and their catalog bindings;
- requested lane tool, immutable image/service, and plugin identities.

If any required identity differs or is unavailable, emit a baseline
discontinuity naming the mismatched fields. Do not calculate or display deltas
across the discontinuity. Bind only a validated nonrecursive projection of the
prior pulse identity, stable digest, and numeric observation values; this keeps
week N comparable to week N-1 without recursively embedding older history.
