---
name: quality-pulse
description: Runs a scheduled or local repository quality pulse from a trusted repository-owned profile, producing validated JSON evidence, a Markdown digest, and compatible trend comparison. Use for recurring quality audits, repository health pulses, or scheduled code-quality telemetry; do not use for PR review, visual testing, or feature implementation.
disable-model-invocation: true
argument-hint: "[--profile <path>]"
---

# dm-review Quality Pulse

Run an evidence-backed repository quality pulse without turning telemetry into
a merge recommendation. dm-review owns workflow policy, lane orchestration,
coverage, classification, digest organization, and user-facing guidance.
The workflow kernel owns deterministic validation, execution containment,
canonical JSON, classification mechanics, redaction, trend compatibility, and
rendering inputs.

A quality pulse is **not a merge recommendation**. Informational telemetry is
not a deferred P3 finding and must not be added to the normal dm-review
zero-deferral ledger.

## Inputs

- Default profile: `.dm-review/quality-pulse.json`
- Optional override: `--profile <repository-relative-or-explicit-local-path>`
- Authority: a local operator acting in a trusted checkout

The override chooses a profile; it does not grant execution authority. A
profile from an untrusted pull request may be validated and reported, but its
lanes must never run.

Read these focused contracts before execution:

- `references/profile-contract.md`
- `references/trust-boundary.md`
- `references/output-contract.md`
- `references/graceful-degradation.md`

## Runtime and Catalog Resolution

Resolve exactly one trusted workflow-kernel launcher per run using the host
dependency root and the kernel's canonical
`references/runtime-resolution.md` contract. Require
`skills/workflow-kernel/references/workflow-kernel-launcher.sh` from that
selected plugin root and verify it is executable. Reuse that launcher for the
entire pulse. Do not use an independent cache glob, mtime-first lookup, PATH
search, or a mixture of assets from different workflow-kernel versions.

Use the selected launcher's `resolve-plugin-bundle` command to resolve the
declared Live Wires bundle coherently. Require
`references/quality-rules-v1.json` from the one selected Live Wires root.
Capture the selected plugin version and asset path in provenance.

Before admitting any lane, load the declared catalog and verify:

1. its complete structure;
2. catalog ID, schema version, and catalog version;
3. the canonical content digest recomputed according to the catalog's declared
   canonical projection;
4. every profile rule ID and metric ID against that catalog.

An absent catalog, invalid structure, digest mismatch, version mismatch, or
unknown rule/metric reference is a profile-preflight failure. It is not a
runtime observation and no lane may start.

## Workflow

Execute these stages in order:

```text
discover profile
verify trusted-local authority
validate complete profile
capture repository/tool provenance
admit declared lanes
run primary/fallback lanes with separate receipts
normalize observations
classify against closed profile IDs
emit authoritative JSON
validate authoritative JSON
render Markdown digest
compare compatible trend or emit discontinuity
```

### 1. Discover and authorize

Resolve the requested profile according to `profile-contract.md`. dm-review
must inspect the checkout and source, obtain a host-derived operator
authorization event, and construct the separate trust attestation described in
`trust-boundary.md`. The profile cannot construct, contain, or nominate this
authority.

### 2. Complete preflight

Run `inspection-validate` before any repository command, Docker/Compose
invocation, evidence write, authoritative output, or digest rendering:

```sh
"$WORKFLOW_KERNEL" inspection-validate \
  --repository-root "$REPOSITORY_ROOT" \
  --profile "$PROFILE_PATH"
```

Validation covers the entire profile, catalog bindings, closed IDs, paths,
argv arrays, timeouts, lane relationships, evidence paths, output paths,
classifications, and trend identity. Partial validation does not admit a
partial run.

### 3. Capture provenance and admit lanes

Capture the repository commit, dirty state, verified ref/source, profile
schema/version/digest, catalog identity/digest, selected plugin versions, tool
and immutable image identities, and invocation time before running lanes.

Admit only profile-declared Docker or Compose argv arrays that passed kernel
validation. dm-review decides which declared lanes are requested and preserves
coverage; it does not rewrite argv or execute a shell.

### 4. Run requested primary lanes and consume fallback receipts

Invoke `inspection-run` with requested primary lane IDs only. Repeat
`--lane-id` for multiple requested primaries in the same invocation:

```sh
"$WORKFLOW_KERNEL" inspection-run \
  --repository-root "$REPOSITORY_ROOT" \
  --profile "$PROFILE_PATH" \
  --lane-id "$PRIMARY_LANE_ID" \
  [--lane-id "$ANOTHER_PRIMARY_LANE_ID"] \
  --attestation "$HOST_ATTESTATION" \
  --source git \
  --ref "$VERIFIED_REF" \
  --commit "$VERIFIED_COMMIT" \
  --dirty "$DIRTY_STATE" \
  --authorization-event-id "$AUTHORIZATION_EVENT_ID" \
  --purpose quality-pulse
```

Never invoke a fallback lane ID directly. The kernel owns fallback selection:
when a selected primary is `unavailable` or `failed`, it attempts that
primary's declared fallbacks from the same immutable validated snapshot.
Consume the complete returned receipt set, including the primary receipt and
every `fallback` or `skipped` receipt.

Record requested, attempted, and actual lane/tool identities from those
receipts for every lane. Primary `available`, `unavailable`, and `failed`
states remain distinct. Fallback success is `fallback`, names
`primary_lane_id`, and uses fallback confidence. An unused or later fallback
is `skipped`. Never silently drop a receipt or rewrite fallback evidence as
primary-equivalent.

### 5. Normalize and classify

Normalize observations without discarding their redacted raw form, then invoke
the kernel's `inspection-classify` mechanics against the validated profile.
dm-review applies the user-facing classification contract:

```sh
"$WORKFLOW_KERNEL" inspection-classify \
  --repository-root "$REPOSITORY_ROOT" \
  --profile "$PROFILE_PATH" \
  --observations "$NORMALIZED_OBSERVATIONS"
```

```text
evidence.status: available | unavailable | failed | fallback | skipped
finding.classification: actionable | informational | unknown
finding.actionability: actionable | informational
finding.surface: repository-profile-defined closed ID
finding.confidence: primary | fallback | inferred | unavailable
```

Evidence status and finding classification are independent. Unknown path,
metric, surface, rule, classification, evidence state, or observation schema
must retain the redacted raw observation and produce:

```json
{
  "classification": "unknown",
  "actionability": "actionable"
}
```

Any such unknown fails the pulse. Never coerce `unknown` to informational.

### 6. Publish JSON, then Markdown

Emit the authoritative JSON contract in `output-contract.md`, then validate it
and recompute its stable projection digest. Only after that succeeds may
`inspection-render` produce the Markdown digest:

```sh
"$WORKFLOW_KERNEL" inspection-render --input "$AUTHORITATIVE_JSON"
```

If JSON emission, validation, redaction, stable-digest verification, or render
input validation fails, do not publish or retain a new Markdown digest as
authority. Markdown is a view and is never parsed back into evidence.

### 7. Compare a compatible baseline

Use `inspection-trend` only when the baseline matches the required schema,
profile, metric-definition, and lane tool/image/plugin identities. Otherwise
publish a baseline discontinuity with the incompatible identity fields; do not
calculate a misleading delta.

```sh
"$WORKFLOW_KERNEL" inspection-trend \
  --current "$AUTHORITATIVE_JSON" \
  --baseline "$COMPATIBLE_BASELINE"
```

## Invocation Guidance

Claude local invocation:

```text
/dm-review-quality-pulse
/dm-review-quality-pulse --profile configs/local-quality-pulse.json
```

Claude scheduled automation should call the same command in a trusted checkout
and preserve the host authorization event and profile source evidence.

For Codex before release integration generates the command alias, ask Codex to
run the shared `dm-review:quality-pulse` skill with the same optional
`--profile` argument. Do not claim that the generated alias is discoverable
until the release-integration chunk has regenerated and validated it.

## Completion

Report:

- authoritative JSON path and stable digest;
- Markdown digest path, or the reason it was not published;
- profile/catalog/repository provenance;
- requested, attempted, and actual lanes with evidence status;
- actionable, informational, and unknown counts;
- coverage gaps and blockers;
- compatible trend result or baseline discontinuity.

Follow `graceful-degradation.md` for every non-success state. A partial report
must remain visibly partial and can never become a passing pulse.
