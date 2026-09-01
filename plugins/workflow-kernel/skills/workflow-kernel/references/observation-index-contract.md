# Observation Index v1 Contract

`observation-index-v1` is a deterministic, bounded sidecar that lets different
development harnesses describe one run without replacing their authoritative
receipts. Workflow Kernel owns the schema and validator. A producer composes an
index only from explicitly named, digest-bound sources.

## Reuse-versus-gap map

This map is the placement decision. Existing contracts remain canonical where
they already own a fact; the index references those artifacts and adds only the
typed gaps in the final column.

| Requested observation | Canonical owner reused | Index gap, if any |
|---|---|---|
| Run identity and lifecycle | Workflow Kernel `WorkflowEvent`/`RunState` | Public run ID plus lifecycle source binding |
| Session identity | Harness terminal/session receipt | Explicit available/unavailable fact |
| Attempt identity | Pipeline/dm-review attempt receipts | Bounded public ID list |
| Workflow-node and action identity | Kernel nodes and authoritative receipts | Bounded public ID lists |
| Harness name, version, execution profile | Producer manifest/terminal receipt | Explicit digest-bound producer record |
| Loaded plugins, versions, digests | Installed-bundle resolution receipts | Bounded public plugin tuple list |
| Objective and budget | Pipeline prompt/plan and budget receipt | Objective fact; budget remains a reference |
| Typed completion contract | Behavioral/repository verification contract | Safe reference only |
| Requested/attempted/served model and provider | Attempt/router/provider receipts | Public role facts with no role inference |
| Routing rationale and fallback | Router/attempt receipts | Public bounded reason facts; private detail stays referenced |
| Input/output/cache/reasoning tokens | Attempt metrics receipts | Typed token facts with source provenance |
| Cost | Run cost summary and imputation matrix | Closed measured/imputed/unavailable union |
| Duration and model/tool counts | Metrics and attempt receipts | Typed numeric facts |
| Verifier result and evidence | Verification result artifacts | Result plus bounded evidence references |
| Artifact handle, digest, type, size, preview | Producer artifact receipts | Neutral bounded descriptor; no bytes/content |
| Failure and recovery | Failure/reconciliation receipts | Digest failure signature and bounded recovery decision |
| Stagnation and intervention | Convergence/intervention receipts | Minimal boolean plus bounded intervention code |
| Candidate lineage and disposition | dm-review contribution identities/receipts | Neutral IDs, parents, accepted/rejected disposition |
| Candidate score | No current cross-harness owner | Explicitly unavailable until consumer evidence exists |
| Next recorded action | Producer terminal receipt | Bounded text fact |
| Source provenance and freshness | Each canonical artifact | Uniform source binding and fact provenance |

## Authority and compatibility

- The index is observation-only. It never changes run state, stages, routing,
  verification, review disposition, recovery, or publication decisions.
- `WorkflowEvent`, `RunState`, Pipeline and dm-review stages, attempt receipts,
  `run-cost-summary-v1`, verification contracts, and reconciliation receipts
  retain their current meanings and byte formats.
- Exactly one source has role `producer`; `producer.source_digest` must bind to
  it. Shared stage names never determine producer identity.
- Available facts carry a typed value and provenance bound to a declared source
  digest. Unavailable facts carry `null` and one closed reason.
- Producer and plugin names are harness-neutral strings. `pipeline`,
  `dm-review`, vanilla Pi, and a future Foreman may use the same envelope; the
  schema does not encode any Foreman loop, supervisor, database, or UI choice.

## Cost honesty

- `measured` requires a finite non-negative USD value, an authoritative
  measurement reference, and provenance bound to the same declared `cost`
  source.
- `imputed` requires a finite non-negative USD value, ISO matrix snapshot date,
  canonical matrix digest bound to a declared `cost` source, bounded basis
  code, and bound provenance.
- `unavailable` requires `value_usd: null` and one closed reason. It cannot
  carry measurement or imputation fields.

## Bounds, privacy, and freshness

The canonical document is at most 256 KiB. Sources, plugins, model routes,
artifacts, candidates, IDs, strings, media types, timestamps, references, and
nested objects have explicit limits in the schema and validator. Unknown keys
and versions fail closed.

All integer and decimal observations are at most `9007199254740991`, preserving
exact integer interchange across JSON consumers. Timestamps use RFC 3339 with
seconds and an explicit timezone; matrix snapshots use exact calendar dates.
High-confidence credential shapes are rejected from every public text value.

References are run-relative paths or content identifiers accepted by Workflow
Kernel reference normalization. Absolute paths, dot segments, query strings,
fragments, URL credentials, control characters, and unbound provenance are
rejected. Large artifacts and previews are represented only by handles,
references, digests, media types, and byte sizes. Raw findings, prompts,
transcripts, provider payloads, policy files, plugin contents, and artifact
bytes never enter the index.

Every source declares a source timestamp, observation timestamp, and a closed
freshness state. Fresh and stale sources declare their own maximum age, and the
validator recomputes whether the elapsed time agrees. `fresh` has no reason;
`stale` requires `age_exceeded`. Unknown freshness has no maximum age and uses
`not_reported` or `clock_unknown`. The index reports this evidence but does not
invent a global freshness threshold.

Available-fact provenance falls within the closed interval from its bound
source's observation time through index emission. A fact cannot claim to have
been extracted before its source was observed or after the index was emitted.

Candidate lineage and accepted/rejected disposition are public in v1. Candidate
score remains explicitly unavailable because no current cross-harness consumer
owns comparable scoring semantics.

## Digest

The `digest` is `sha256:` plus the SHA-256 of canonical UTF-8 JSON with sorted
keys, compact separators, one trailing newline, and the top-level `digest`
field omitted. Producers must validate the complete document before writing it.
