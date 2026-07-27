# Scheduled Quality Pulse: Executable-Boundary Decision

**Status:** Approved
**Date:** 2026-07-27
**Workflow class:** Feature
**Decision profile:** Medium uncertainty, high consequence

## Decision

Scheduled quality pulses use the existing workflow-kernel executable as their
only general runtime. The kernel gains neutral inspection mechanics, but it
does not gain product, repository, design-system, or review policy.

Ownership is deliberately split:

```text
dm-review: workflow, profile discovery, lane semantics, classification policy, digest contract
live-wires: generic stable-ID rule catalog
workflow-kernel: schema validation, path/argv containment, deterministic classification mechanics,
                 canonical JSON, redaction, compatibility comparison, rendering inputs
pipeline: gated delivery, independent review, receipts, and non-merging handoff
repository: paths, scopes, thresholds, exemptions, commands, output destinations
```

The consuming repository is the authority for its checked-in profile and all
repository-specific choices. `dm-review` is the policy owner that discovers and
interprets that profile. `live-wires` owns only reusable catalog definitions.
Pipeline delivers and verifies the feature but is not a second scanner.

Domain policy inside workflow-kernel is explicitly rejected. The kernel may
compare stable IDs and execute validated mechanics; it may not know product
names, choose thresholds, infer exemptions, invent supported lanes, or turn
generic telemetry into new policy.

## Trust and execution boundary

A profile is untrusted repository content. It cannot grant itself execution
authority. Before any plan or subprocess call, workflow-kernel:

1. reads the profile once with duplicate-key rejection;
2. validates the complete closed schema, catalogs, references, paths, and lane
   declarations;
3. freezes a canonical snapshot and computes its SHA-256 digest;
4. accepts a host-issued attestation only through a file outside the canonical
   repository root;
5. compares every attestation binding to observed inputs; and
6. verifies that the source pathname identity did not change before admission.

The attestation binds the canonical repository root, normalized profile path,
validated profile digest, verified Git source/ref and commit, dirty state,
operator authorization event ID, and execution purpose. A profile trust
Boolean, a repository-controlled attestation, a stale digest, or any mismatched
binding fails before lane planning. Execution consumes only the frozen snapshot
and never reopens profile content.

Admitted lane declarations are exact argv arrays beginning with `docker run` or
`docker compose`. Shells, shell operators, environment flags, implicit host
tools, mutable image aliases, undeclared outputs, absolute paths, traversal,
and symlink escape are rejected. The adapter uses no shell, the canonical
repository root as its working directory, the declared timeout, and a fixed
minimal environment. Primary and fallback lanes remain different evidence
states, and every attempted or deterministically skipped lane has a receipt.

## Catalog and result integrity

Every profile rule and metric binds to a catalog ID, schema version, semantic
version, source reference, and content digest. The catalog digest covers the
canonical catalog projection without its self-referential `content_digest`
field. Invalid catalogs and unknown or mismatched references fail before
execution admission.

Authoritative JSON precedes Markdown. It retains repository commit and dirty
state, profile identity and digest, catalog/tool/image/plugin identities,
invocation metadata, lane receipts, evidence states, classifications,
confidence, raw redacted telemetry, and redaction outcome. An explicit stable
projection excludes only volatile timing and captured process text; its digest
supports byte comparison while the complete receipt retains provenance.

Trend deltas are emitted only when schema, profile, metric-definition, and
tool/image/plugin identities match. Otherwise the result is a structured
baseline discontinuity. Markdown is rendered only from a validated
authoritative result whose stable projection digest recomputes correctly.
Markdown and prose are never parsed into authority.

## Installed-plugin bundle selection

Runtime callers resolve a coherent plugin bundle through
`resolve-plugin-bundle`. The resolver considers strict semantic-version
directories from both Claude and Codex caches, verifies the cache-specific
manifest name/version and every required relative asset, and chooses the
highest compatible version. Active-host cache class is only an equal-version
tie-breaker. The result names one root; callers derive every asset from that
root and never mix cache trees. Durable output uses a home-relative root and
does not disclose the absolute home directory.

## Consequences and verification

The change extends the sanctioned stdlib-only Python 3.12 runtime rather than
creating another executable. Repository profiles remain powerful only after a
separate host authorization event, making local Docker execution explicit and
auditable. Unknown observations remain useful as redacted raw telemetry but
classify fail-closed and actionable.

Because consequence is high, implementation requires an independent
architecture/security review in addition to focused unit/CLI tests and the full
offline workflow-kernel release gate. An unavailable or degraded independent
review is a release blocker.
