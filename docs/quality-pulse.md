# Repository Quality Pulse

Repository Quality Pulse is a deterministic scheduled or local repository
audit. It is separate from merge review: a pulse measures repository-owned
quality policy over time, while `/dm-review` reviews a change for merge.

## Ownership

| Layer | Owns |
|---|---|
| Repository | `.dm-review/quality-pulse.json`, scope, classifications, thresholds, lane declarations, output paths, and trend retention |
| dm-review | Workflow, trusted-local admission, evidence-state reporting, and authoritative-before-render publication order |
| workflow-kernel | Closed profile validation, digest binding, subprocess containment, redaction, canonical JSON, rendering, and compatible trend mechanics |
| Live Wires | Versioned generic quality-rule catalog and stable rule vocabulary |
| Pipeline | Installation-aware orchestration only; it does not own a second scanner or repository policy |
| OpenRouter | Optional bounded analysis after disclosure classification; it is never execution authority or a source of secrets |

## Invoke

Claude Code exposes the canonical command:

```text
/dm-review-quality-pulse
/dm-review-quality-pulse --profile configs/local-pulse.json
```

Codex exposes the generated command-skill alias:

```text
dm-review:dm-review-quality-pulse
dm-review:dm-review-quality-pulse --profile configs/local-pulse.json
```

Both surfaces use the same command body and quality-pulse skill. The default
profile is `.dm-review/quality-pulse.json`.

## Profile and Trust

The repository profile uses inspection schema version 1. It declares stable
repository-relative paths, surfaces, catalog identities and digests, rules,
metrics, classifications, immutable primary/fallback lane identities, evidence
paths, outputs, and trend compatibility fields. dm-review separately owns the
versioned `result-policy-v1.json` completion and blocker semantics. The kernel
validates and digest-binds both inputs, then applies the closed policy
mechanically.

Profile content is policy, not authority. Lane execution requires a
host-issued attestation stored outside the canonical repository root. That
attestation binds the repository root, profile path and digest, verified Git
ref and clean commit, purpose, dirty state, and the host-observed operator
authorization event. An untrusted PR may be validated and reported, but its
profile cannot authorize subprocess execution.

An explicit `--profile` override is a local operator choice. It still passes
the same complete validation and trust checks.

The kernel supplies the attested checkout to lanes at `/workspace` read-only
and supplies a fresh empty evidence mount at `/inspection-evidence`.
Profiles cannot nominate host mounts. A successful lane writes a lane-bound
schema-1 observation envelope to the fixed
`/inspection-evidence/observations.json` path. The kernel snapshots it with
no-link file handling and binds its digest and observation IDs into the lane
receipt; `inspection-run` does not accept a separate observations file.

## Evidence Lifecycle

Every declared lane has one literal state:

- `available`: primary completed with admissible evidence;
- `unavailable`: primary could not start;
- `failed`: primary ran but failed;
- `fallback`: declared fallback completed after its primary was unavailable or
  failed;
- `skipped`: declared lane was not needed or requested.

Fallback retains its `primary_lane_id`, reason, and lower confidence. A missing
or failed primary is never rewritten as fallback success. Producing-lane
status is recorded separately and never overwrites an observation's own
evidence status. Known classifications declare actionability explicitly in
the validated profile. Unknown schema,
surface, path, rule, metric, classification, or evidence vocabulary retains
redacted raw telemetry, becomes `classification: unknown`, remains actionable,
and fails the pulse.

## Outputs and Trends

Publication order is fixed:

1. produce authoritative JSON;
2. validate its closed schema and stable projection digest;
3. verify durable redaction;
4. bind compatible trend state or a structured baseline discontinuity with
   `inspection-finalize`;
5. render Markdown from that validated JSON;
6. bind `markdown_rendered` and later `published` only after those host actions
   succeed.

The published source of truth is the host-keyed authoritative JSON. A
content-addressed, read-only JSON/Markdown snapshot is stored under
`.inspection-publications/<inspection-id>/<state-digest>/`; consumers revalidate
its HMAC and regenerate the derived Markdown rather than trusting a pathname.
Profile-declared paths are replaceable reader views and never feed
classification or trend comparison. The host process and OS account are
trusted because that account owns the publication key. The stable projection
excludes volatile invocation time while retaining commit, profile/catalog,
metric, tool, lane, evidence, and redaction identities.

Trend deltas are calculated only when schema, profile digest, metric/catalog
bindings, and tool/image/service identities are compatible. Otherwise the
result names a baseline discontinuity and calculates no delta.

## OpenRouter Boundary

OpenRouter routing is threat- and content-based, not path-name-based.
Non-secret security-related prose, tests, configuration, and code may be sent
through OpenRouter when output and execution controls remain in force. Secrets,
credentials, private keys, authenticated DSNs, private customer data, and
other prohibited disclosure classes remain blocked or redacted before network
contact.

Anthropic models are never selected through OpenRouter. Native Codex remains
the preferred OpenAI coding rail; explicitly routed Terra/Luna API work may use
OpenRouter. Anthropic work uses the native Claude CLI.
Provider-origin receipts preserve requested, attempted, and actual providers.

## Validation

Focused offline proof:

```shell
./tools/validate-workflow-kernel.py
./tools/validate-quality-pulse.sh
./tools/validate-workflow-contracts.sh
./tools/validate-marketplace-capabilities.sh
```

Full repository composition proof:

```shell
./tools/validate-composition.sh --all
```

## Release Evidence States

Local validators, generated-surface checks, and a clean release preflight prove
only `ready-to-release`. They do not prove any of the following:

- local or remote tags;
- pushed marketplace source;
- Claude or Codex marketplace refresh;
- installed-cache versions;
- Claude command or Codex skill discovery in installed runtimes;
- a real repository invocation;
- closure of a consuming-repository issue.

Those claims require later live receipts. The Baseplate-specific requirements
are tracked in `docs/baseplate-quality-pulse-handoff.md`.
