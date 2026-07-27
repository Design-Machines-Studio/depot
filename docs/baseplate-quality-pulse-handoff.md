# Baseplate Quality-Pulse Post-Release Handoff

This is an executable handoff for a later Baseplate integration session. It
does not assert that Baseplate currently contains a quality-pulse profile, that
Depot has been released or installed, or that issue #572 can close.

## Required Depot Release Set

| Plugin | Required version | Intended tag |
|---|---:|---|
| workflow-kernel | 0.4.0 | `workflow-kernel-v0.4.0` |
| live-wires | 1.8.0 | `live-wires-v1.8.0` |
| dm-review | 1.46.0 | `dm-review-v1.46.0` |
| openrouter | 1.6.0 | `openrouter-v1.6.0` |
| pipeline | 1.33.0 | `pipeline-v1.33.0` |
| airlift | 1.3.0 | `airlift-v1.3.0` |

Before editing Baseplate, prove every intended tag with a retained provenance
receipt containing:

- local dereference and remote dereference;
- one identical target commit;
- the plugin manifest version at that target;
- the marketplace source revision used for refresh;
- the refreshed Claude and Codex installed-cache version;
- proof that the tag targets the commit that introduced that version.

An existing name or local tag alone is insufficient.

## Refresh and Discovery Gates

Retain all of these after the release exists:

1. Claude marketplace refresh against the released Depot revision.
2. Claude installed-cache versions for every required plugin.
3. Claude discovery of `/dm-review-quality-pulse`.
4. Codex marketplace refresh against the same released Depot revision.
5. Codex installed-cache versions for every required plugin.
6. Codex discovery of `dm-review:dm-review-quality-pulse`.

A source checkout or generated alias in Depot is not installed-runtime proof.

## Baseplate Profile Contract

Create the default profile only in the Baseplate session:

```text
.dm-review/quality-pulse.json
```

Use inspection profile schema version 1. Canonical serialization determines
the profile digest; every catalog, metric, rule, attestation, authoritative
result, and trend identity must bind the validated digest. A changed profile
creates a new compatibility identity rather than silently comparing unlike
baselines.

The profile is trusted-local policy, not execution authority. Require a
host-issued attestation outside the Baseplate repository, bound to the clean
verified commit, profile path/digest, repository root, purpose, dirty state,
and operator authorization event. Untrusted branch or PR content may be
validated but must start zero lanes.

### Exact Scope

The profile scope is exactly:

```text
internal/baseplate/admin/pages/design_panel_sections.templ
internal/components/shell/design_panel.templ
public/js/design-panel.js
src/css/6_components/design-panel.css
```

Do not include the full-page `/super/design` compatibility/library surface.

### Required Result Buckets

```text
baseplate_actionable
design_panel_informational
design_panel_actionable
unknown_fail_closed
```

Unknown schema, path, metric, surface, rule, classification, or evidence state
must retain redacted raw telemetry, remain actionable, and fail the pulse.

### Historical Wrapper Decision

Historical provenance:

```text
internal/baseplate/admin/pages/design.templ:93
```

Executable policy must use:

```text
stable path: internal/baseplate/admin/pages/design.templ
stable rule ID: bp-historical-wrapper
stable signature: design-theme-item-meta flex items-center
```

Inspect current Baseplate main. Then encode one explicit `compliant` or
`exempt` profile decision while keeping the alternative representable.
Do not infer the current production state from the historical line reference.
An omitted or unlisted decision must fail profile validation.

### Lane Contract

Declare one real dead-code/lint primary as an exact immutable Docker image
identity and one bounded fallback. The Baseplate session must validate the
actual image, argv, timeout, output path, and tool version against current main;
the synthetic conformance image is not a production pin.

Preserve:

```text
primary unavailable -> evidence status unavailable
declared fallback succeeds -> evidence status fallback
fallback primary_lane_id -> exact unavailable primary
fallback confidence -> lower than primary confidence
```

Do not treat fallback evidence as primary-equivalent or erase the primary
coverage gap.

### Stable JavaScript Metric

Define one stable metric ID and definition digest that counts:

- configured inline-script scopes in
  `internal/baseplate/admin/pages/design_panel_sections.templ`;
- configured inline-script scopes in
  `internal/components/shell/design_panel.templ`;
- configured JavaScript files including `public/js/design-panel.js`.

Use deterministic ascending path order. Validate current main before setting
thresholds.

## Proposed Commands and Artifact Paths

Validate these repository-specific destinations in the Baseplate session before
committing them:

```text
scheduled command: /dm-review-quality-pulse --profile .dm-review/quality-pulse.json
local Claude command: /dm-review-quality-pulse --profile .dm-review/quality-pulse.json
local Codex skill: dm-review:dm-review-quality-pulse --profile .dm-review/quality-pulse.json
authoritative JSON: .dm-review/quality-pulse/authoritative.json
rendered Markdown: .dm-review/quality-pulse/report.md
rendered digest: .dm-review/quality-pulse/report.md.sha256
trend state: .dm-review/quality-pulse/trend-state.json
retained receipts: .dm-review/quality-pulse/receipts/
```

The scheduler must invoke the same canonical workflow and preserve its complete
receipt. It must not create a parallel scanner.

## Migration

Use `weekly-pulse-rubric.md` as source context only:

- convert stable rules into versioned catalog/profile bindings;
- convert repository scope into closed surface IDs and exact paths;
- make exemptions explicit profile decisions;
- discard prose-only authority after the structured profile is reviewed.

Migrate historical flat `metrics.json` conservatively:

- retain it as historical evidence;
- import a baseline only when schema, profile digest, metric/catalog
  definitions, and tool identities can be proven compatible;
- otherwise record a baseline discontinuity and start a new trend;
- never invent missing evidence identities to preserve a chart.

## Clean-Commit Runtime Proof

Run against a clean current Baseplate commit. Retain one successful Claude
receipt and one successful Codex receipt against the same SHA. Each receipt
must bind:

- requested and actual runtime;
- the identical clean Baseplate commit and dirty state `false`;
- installed versions of every consumed plugin;
- profile path, version, and digest;
- all catalog IDs, versions, and digests;
- authoritative JSON path and digest;
- rendered Markdown/digest path and digest;
- trend-state path and compatibility result;
- requested, attempted, and actual lane/tool identities;
- literal lane evidence states and equivalent expected evidence.

A Claude-only or Codex-only success is insufficient. A runtime-specific
blocker is retained diagnostic evidence only and blocks #572 closure; it is
never substitute invocation evidence.

## Issue #572 Closure Checklist

Keep #572 open until every item is proven:

- [ ] All six intended tags have local/remote provenance receipts and target
  their version-introducing release commits.
- [ ] Claude marketplace refresh and installed-cache versions are retained.
- [ ] Codex marketplace refresh and installed-cache versions are retained.
- [ ] Claude command discovery is retained.
- [ ] Codex skill discovery is retained.
- [ ] `.dm-review/quality-pulse.json` exists on current Baseplate main and
  passes schema/catalog/profile validation.
- [ ] The exact four-path scope and four required buckets are encoded.
- [ ] The historical wrapper has a current-main-validated explicit decision.
- [ ] The primary Docker lane uses a real validated immutable production pin.
- [ ] Fallback evidence remains lower-confidence and preserves primary gaps.
- [ ] The stable JavaScript metric and digest are reviewed against current
  source.
- [ ] The run is bound to a clean current Baseplate commit.
- [ ] One retained successful Claude receipt exists.
- [ ] One retained successful Codex receipt exists against the same SHA.
- [ ] The two receipts bind equivalent expected evidence and all required
  plugin/profile/catalog/artifact identities.
- [ ] Authoritative JSON, rendered digest, and trend state are retained.
- [ ] No unresolved blocker, unknown fail-closed observation, failed lane, or
  incompatible evidence has been relabeled as a passing pulse.

Only then may the Baseplate session evaluate issue closure. This Depot handoff
has no closure authority.
