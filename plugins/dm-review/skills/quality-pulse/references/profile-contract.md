# Quality-Pulse Profile Contract

The consuming repository owns pulse scope and policy. dm-review and the
workflow kernel provide mechanics; neither embeds repository-specific paths,
thresholds, exemptions, commands, surfaces, or output destinations.

## Discovery

```text
default: .dm-review/quality-pulse.json
override: --profile <repository-relative-or-explicit-local-path>
authority: local operator / trusted checkout only
untrusted PR profile: validate and report, never execute lanes
```

Resolve a repository-relative profile beneath the canonical repository root.
An explicit local path must still pass the kernel's path and source validation.
The override is an operator choice, not proof that repository-authored content
is trusted.

## Complete Profile

Use workflow-kernel inspection-profile schema version 1. A repository profile
owns:

- stable profile ID and semantic profile version;
- repository scope paths;
- closed surface IDs;
- catalog bindings;
- selected rule and metric IDs;
- thresholds, exemptions, and classification policy;
- primary and fallback lane declarations, exact argv, immutable identities,
  timeouts, and evidence paths;
- authoritative JSON and Markdown output locations;
- trend compatibility identities.

Complete validation must finish before any declared repository command, lane,
evidence output, authoritative JSON write, or Markdown rendering.

## Canonical Catalog Binding

The canonical generic catalog is the selected Live Wires bundle asset:

```text
plugin: live-wires
asset: references/quality-rules-v1.json
catalog_id: live-wires-quality-rules
schema_version: 1
catalog_version: profile-declared and exact-match required
content_digest: externally computed from the catalog's declared canonical projection
```

The profile binds the catalog ID, schema version, catalog version, canonical
content digest, and every selected rule and metric ID. It must not copy,
redefine, or shadow catalog rules.

Before any lane is admitted:

1. resolve one coherent Live Wires plugin bundle with
   `resolve-plugin-bundle`;
2. validate the catalog's complete structure;
3. recompute its canonical digest;
4. compare all identity fields with the profile;
5. verify every rule and metric reference exists.

Absence or mismatch fails profile preflight and starts zero subprocesses.

## Repository Ownership

Repository policy belongs only in the profile. Generic dm-review content may
name the contract fields but must not contain a consuming repository's paths,
thresholds, exemptions, Docker commands, or output destinations.
