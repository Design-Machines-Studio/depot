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
not an interactive review finding and must not be added to the normal dm-review
P1/P2/P3 fix ledger. If a later interactive review accepts an observation as a
finding, the normal zero-deferral policy applies.

## Inputs

- Default profile: `.dm-review/quality-pulse.json`
- Optional override: `--profile <repository-relative-or-explicit-local-path>`
- Result policy: trusted dm-review asset `references/result-policy-v1.json`
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
`references/runtime-resolution.md` contract. Require workflow-kernel
`>=0.5.0` and
`skills/workflow-kernel/references/workflow-kernel-launcher.sh` from that
selected plugin root and verify it is executable. Reuse that launcher for the
entire pulse. Do not use an independent cache glob, mtime-first lookup, PATH
search, or a mixture of assets from different workflow-kernel versions.
Resolve `RESULT_POLICY_PATH` from the same installed dm-review bundle as this
skill and require `references/result-policy-v1.json`; repository content cannot
override that path.

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
compare compatible trend or emit discontinuity
bind compatible trend or baseline discontinuity
render Markdown digest
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
  --profile "$PROFILE_PATH" \
  --result-policy "$RESULT_POLICY_PATH"
```

Validation covers the entire profile, catalog bindings, closed IDs, paths,
argv arrays, timeouts, lane relationships, evidence paths, output paths,
classifications, and trend identity. Partial validation does not admit a
partial run.

### 3. Capture provenance and admit lanes

Capture the repository commit, dirty state, verified ref/source, profile
schema/version/digest, catalog identity/digest, selected plugin versions, tool
and immutable image identities, and invocation time before running lanes.

Admit only profile-declared pinned `docker run` argv arrays that passed kernel
validation. dm-review decides which declared lanes are requested and preserves
coverage; it does not rewrite argv or execute a shell. The kernel, not the
profile, synthesizes a fixed read-only mount of the attested checkout and a
fresh empty read-write evidence mount. Profile-supplied mounts remain invalid.

### 4. Run requested primary lanes and consume fallback receipts

Invoke `inspection-run` with requested primary lane IDs only. Repeat
`--lane-id` for multiple requested primaries in the same invocation:

```sh
"$WORKFLOW_KERNEL" inspection-run \
  --repository-root "$REPOSITORY_ROOT" \
  --profile "$PROFILE_PATH" \
  --result-policy "$RESULT_POLICY_PATH" \
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

Each successful lane must write this envelope to the kernel-owned fixed path
`/inspection-evidence/observations.json`:

```json
{"schema_version":1,"lane_id":"<declared-lane-id>","observations":[]}
```

The kernel opens that fresh file without following links, snapshots and
digests it, and binds the lane ID, declared evidence reference, observation
IDs, and digest into the receipt. Exit zero without valid bound evidence is
`failed`, never `available`.

Record requested, attempted, and actual lane/tool identities from those
receipts for every lane. Primary `available`, `unavailable`, and `failed`
states remain distinct. Fallback success is `fallback`, names
`primary_lane_id`, and uses fallback confidence. An unused or later fallback
is `skipped`. Never silently drop a receipt or rewrite fallback evidence as
primary-equivalent.

### 5. Normalize and classify

`inspection-run` classifies only the immutable observations returned by its
successful lane envelopes. A caller cannot supply a second observations file.
For non-authoritative profile development, normalize observations without
discarding their redacted raw form, then invoke the kernel's standalone
`inspection-classify` mechanics. dm-review applies the user-facing
classification contract:

```sh
"$WORKFLOW_KERNEL" inspection-classify \
  --repository-root "$REPOSITORY_ROOT" \
  --profile "$PROFILE_PATH" \
  --observations "$NORMALIZED_OBSERVATIONS"
```

```text
evidence.status: available | unavailable | failed | fallback | skipped
lane.status: available | fallback
finding.classification: actionable | informational | unknown
finding.actionability: actionable | informational
finding.surface: repository-profile-defined closed ID
finding.confidence: high | medium | low | unknown
finding.evidence_confidence: primary | fallback | unavailable
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
and recompute its stable projection digest. Bind an optional trend result and
each publication transition with `inspection-finalize`; the command validates
the closed lifecycle state and emits a re-digested artifact. The kernel embeds
a keyed host attestation for the exact result before authoritative JSON crosses
the process boundary. Every publication command loads the key from the fixed
OS-account path
`~/.config/design-machines/workflow-kernel/inspection-publication-authority.key`; `~` here
means the account-database home, not caller-controlled `$HOME`. The host must
provision that current-user-owned, single-link, mode-`0600` file before a pulse.
There is deliberately no CLI or profile key-path override:

```sh
"$WORKFLOW_KERNEL" inspection-finalize \
  --repository-root "$REPOSITORY_ROOT" \
  --input "$AUTHORITATIVE_JSON" \
  --publication-status authoritative_json_ready \
  [--baseline "$COMPATIBLE_BASELINE"]
```

Only after keyed attestation validation may `inspection-render` produce a
non-publishing Markdown preview:

```sh
"$WORKFLOW_KERNEL" inspection-render \
  --repository-root "$REPOSITORY_ROOT" \
  --input "$AUTHORITATIVE_JSON"
```

If JSON emission, validation, redaction, stable-digest verification, or render
input validation fails, do not publish or retain a new Markdown digest as
authority. Markdown is a view and is never parsed back into evidence.

Publish only through the operation-coupled command:

```sh
"$WORKFLOW_KERNEL" inspection-publish \
  --repository-root "$REPOSITORY_ROOT" \
  --input "$AUTHORITATIVE_JSON"
```

`inspection-publish` derives both destinations from the validated profile
snapshot. It durably writes the exact rendered Markdown before minting
`markdown_rendered`, durably writes that exact authoritative JSON before
minting `published`, then creates the signed JSON and Markdown read-only from
birth inside an unguessable staging directory. It atomically promotes that
directory to
`.inspection-publications/<inspection-id>/<publication-state-digest>/` before
emitting success. JSON and Markdown profile destinations must be distinct,
non-aliased regular-file paths whose parent identities remain stable for the
rendered transition. The signed JSON is the published authority; validation
derives the snapshot path from that envelope and checks its HMAC, exact derived
Markdown, bytes, ownership, link count, and read-only modes. Profile JSON and
Markdown are replaceable views. The host process and OS account are trusted
because that account can read the publication key; mode bits are accidental
write protection, not same-account isolation. A caller cannot request either
transition directly.

### 7. Compare a compatible baseline

Use `inspection-trend` only when the baseline matches the required schema,
profile, metric-definition, and lane tool/image/plugin identities. Otherwise
publish a baseline discontinuity with the incompatible identity fields; do not
calculate a misleading delta.

```sh
"$WORKFLOW_KERNEL" inspection-trend \
  --repository-root "$REPOSITORY_ROOT" \
  --current "$AUTHORITATIVE_JSON" \
  --baseline "$COMPATIBLE_BASELINE"
```

Pass the authoritative baseline directly to `inspection-finalize --baseline`;
the kernel computes and binds the result, so caller-supplied deltas are never
trusted. Bind the trend before rendering. The stable projection and Markdown
exclude publication status; a separate `publication_state_digest` binds that
operational envelope without invalidating rendered content. Every serialized
state—including the initial ready state—carries an HMAC attestation bound to
the host-owned publication key. The key is supplied only by the host, must be
outside the repository at the fixed OS-account path, owned by the current
user, mode `0600`, and cannot be nominated by a profile or command argument.
`inspection-finalize` accepts only `authoritative_json_ready`; rendered and
published attestations are coupled to the exact durable outputs verified by
`inspection-publish`. Validation with a missing, wrong, or replaced key fails.
Never relabel publication without the corresponding completed host action.

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
