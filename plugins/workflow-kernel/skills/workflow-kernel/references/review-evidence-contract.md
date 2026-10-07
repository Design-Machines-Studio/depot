# Source-bound review evidence (>=0.26.0)


`assemble-review-evidence` constructs required evidence. dm-review owns
extraction from `reviewer-output-contract.md`, inspection judgments, selection,
synthesis and repairs. Kernel never dispatches a model or parses Markdown.

```text
"$WORKFLOW_KERNEL" assemble-review-evidence \
  --run-root <exact-owned-root> --repository-root <reviewed-checkout> \
  --request <bound-request.json> --receipts <authoritative-receipts.json> \
  --input <host-structured-input.json>
```

Inputs have exactly `schema_version: 1`, `operation: lane|coverage`, `run_id`
and `pass_id`, plus the operation's fields below. IDs are stable anonymous
identities. Caller supplies neither authoritative digests nor receipt sequences.
All referenced files are contained regular files under the owned root. Recovery
copies original inputs there byte-for-byte; original resources stay intact.

### Lane input

`lane` adds `lane`, positive `attempt`, `reviewer`, and these exact groups.
Every listed key is required, including explicit nulls and empty lists, except
the optional recheck field described below. Absence never rewrites sealed input.

| Group | Exact fields |
| --- | --- |
| `source` | `repository`, original `head`, `base`, nullable `worktree_ref`, `request_ref` |
| `requested` | `designation: full|scoped`, nonempty `paths`, `evidence_refs`, nonempty `required_evidence_refs`, nullable `patch_ref` |
| `inspected` | `paths`, `basis: repository|patch|host_evidence`, `limitations`, `missing_evidence_refs` |
| `literal` | `output_ref`, actual private `dispatch_receipt_ref`, existing anonymous public `companion_ref` |
| `result` | `status: findings|no_findings|incomplete`, existing raw-shape `findings`, `incomplete_reasons` |
| `provenance` | `kind: live|recovery|synthetic_test`, nullable original `executed_at`, `source_refs` |
| `recheck` | nullable `prior_record_ref`, nullable `selection_ref`, `repair_refs`; optional `pending_transition_refs` (absent means `[]`) |

Paths/references are unique relative filenames. `companion_ref` names the
router's existing anonymous completion companion. Kernel derives private lane
provenance from the actual dispatch receipt and recomputes digests/counts.
Historical structured private companions also remain readable when bound by
new lane records. Unknown implementation origin stays unknown; it never gates
inspection. Exact identities remain private.
`patch_ref` is mandatory for patch inspection: retain exact `git diff --binary
<base> <head> -- <requested paths>` bytes and list it in required evidence.
Full scope includes every changed path in that boundary. Live dirty inspection
also supplies exact `git diff --binary <head>` as `worktree_ref`. Kernel binds
actual tracked/untracked content and modes and retains dirty file bytes; equal HEAD never proves equal
source. Recovery cannot manufacture unknown dirty-source facts.

Missing required evidence or incomplete inspection preserves an incomplete
record without settling coverage. Missing auxiliary material limits dependent
claims; express limitations explicitly. Unknown original execution timestamps
stay null; `assembled_at` records assembly time. A router receipt's null
revision stays unknown: source attribution comes from request/prompt/patch and
host extraction. Production lanes require published served dispatch and reject
transport stubs. `--test-harness` explicitly marks disposable synthetic proof;
production coverage rejects `synthetic_test` records. Never claim this as live
or installed consumer verification.

The command retains literal bytes, extraction and a content-addressed record
under `review/evidence/`, then appends `review_lane_evidence` under the shared
receipt lock. Dispatch/attempt receipts retain their original meaning. Returned
`record_ref` settles inspection only after append. Identical run/pass/lane/
attempt retries verify bytes and reuse the record; changed inputs conflict.
Corrections use new linked attempts. Uncommitted partial files confer no
coverage; interrupted retries reuse matching sealed files.

New sealed lane and coverage records use `schema_version: 2`. Their existing
`source_snapshot` / `target_source` fields contain exactly
`{"snapshot_ref":"review/evidence/source-sha256-<digest>.json"}`. The source
seal contains the original `head` and complete `files` inventory; its name uses
the existing canonical document digest. Identical source inventories share one
seal through the existing helper. Required reference closure retains and
revalidates these seals, including historical, repair and reuse sources, before
terminal cleanup. Missing, malformed, unsafe or altered seals fail closed;
source heads must match the original record request. No current-HEAD inference
is permitted. Schema-1 inline records remain valid and immutable; resolution is
in memory and never rewrites their bytes or grants legacy terminal coverage.

### Coverage input and source transitions

`coverage` adds exactly `selection`, `decisions`, `occurred_at`,
`required_case_refs`, and `resolutions`. `selection` has exactly one row per
request lane in request order, with `lane`, `record_ref`, ordered full
`history_refs`, and `transition_refs`. Kernel never picks the latest filename.
Affected rechecks supply their predecessor chain. Unaffected reuse supplies
all intervening non-impact transitions.

Each transition has exactly `schema_version: 1`, `from_source`, `to_source`,
actual `changed_paths`, `patch_ref`, nullable `worktree_ref`, and `selection_ref`.
Copy source snapshots (`head` and `files` with mode/blob identities) from sealed
records; Kernel verifies actual changed paths, ancestry, binary patch bytes,
dirty content and final live source. Ancestry alone is insufficient.

For larger inventories, transitions and selection documents may instead use
`schema_version: 2`, with the same exact fields and rules, but `from_source`
and `to_source` each contain the explicit `snapshot_ref` object above. Retain
both original source seals, sharing the lane/coverage seals when identical.
Schema-1 transitions and selections keep their actual inline inventories.
Never embed repeated complete inventories into schema-2 repair/reuse records.

`selection_ref` has exactly `schema_version: 1`, exact `selected_full_set`,
receiver-confirmed `applied: true`, `iteration` (existing `review_iteration`
receipt), `finding_owner_lanes`, `file_trigger_lanes`, `from_source`,
`to_source`, `changed_paths`, `patch_ref`, nullable `worktree_ref`. Keep existing
owner-before-repair, committed plus uncommitted file triggers, ancestry guards,
full-fan-out fallback and receiver-confirmation rules. Rechecks appear in
`lanes_rerun`; reuse appears in `lanes_skipped`.

`iteration.lanes_pending` is optional (absent means `[]`). Rerun, skipped and
pending lists must be disjoint and partition the exact selected roster.
Finding-owner and file-trigger lanes must be rerun or pending, never skipped.
Pending means incomplete inspection and cannot establish terminal CLEAN or
unchanged-source carry. An intermediate selection can record completed reruns
while other affected lanes remain pending; final coverage must settle every
required lane with eligible inspection evidence.

Selections optionally add `pending_scope_paths` (absent means `{}`), mapping
exactly the pending lane IDs to nonempty, unique, safe relative path lists.
Each path must belong to that selection's actual `changed_paths` and, when
rechecking the lane, its original predecessor's inspected scope. The caller
owns rule (a)/(b) semantics and supplies this explicit source-bound map; Kernel
does not infer domains from extensions or parse Markdown. Different pending
lanes may share affected paths. The existing selection seal/reference closure
retains the map without rewriting historical selections.

A fresh recheck may supply ordered `pending_transition_refs` from its immutable
original predecessor snapshot to exactly its actual selection's `from_source`.
Every intervening receiver-confirmed selection must place this lane in pending;
the actual final selection must place it in rerun. The same strict transition,
source-seal, binary-patch, hash and reference-closure checks apply. Retain the
original predecessor and its baseline scope in history. Fresh `source.base`
must equal that predecessor's `source_snapshot.head`, not its older input base
or the intermediate selection head. The union of this lane's mapped paths
across pending transitions must appear in both fresh requested and inspected
paths; unchanged baseline paths need no fresh inspection claim. Retain the
exact cumulative binary patch for the fresh requested paths, receipts and
literal outputs. Ordinary coverage
`transition_refs` continue to require skipped/unaffected semantics. Do not
rewrite valid sealed history, relabel old output, infer coverage from ancestry
or success text, or invent historical applied events/timestamps. Recovery
selections are current receiver-confirmed reconstructions with explicit retained
provenance; unknown historical execution time stays unknown.

Host supplies existing synthesis decisions using retained finding evidence
references from the selected record's bindings. Kernel constructs all four
companions, validates exact effective finding/decision union through the
existing exporter in memory, seals the aggregate, then appends request/coverage.
Lane receipts schema 2 adds exactly `evidence_record_ref`, `evidence_history`,
`transition_refs` to schema-1 rows. The other three companions remain schema 1.
Legacy contributions remain readable for history/economics; they cannot
establish new terminal coverage.

An effective clean recheck describes its own inspection. Prior findings remain
in immutable history and synthesis snapshots. Every historical finding in a
recheck chain needs one explicit resolution with exactly `source_finding_id`,
`repair_ref`, `verification_record_ref`. Kernel checks accounting/links; the
host owns supported repair judgments.

Append is the commit point. Retry reconstructs missing derived companions
without dispatch. Conflicting fixed files cannot be replaced: use a new
exact-owned replay with the original committed stream/history. Preservation
reads the same locked snapshot and retains referenced history within existing
128-file/2 MiB limits. Optional contribution writers use that lock too;
economics and observations never settle or revoke required coverage.

Closed failure stages are `lane_input`, `lane_validation`,
`aggregate_validation`, `preservation_input`, `retained_validation`. Reasons
distinguish missing/invalid evidence, digest disagreement, source/scope
mismatch, unsafe paths, conflicts and retention limits, using safe artifact-role
filenames. Schema exits 2, incomplete/unsafe evidence 3, conflicts 6. Preserve
safe available inputs and originals on failure. #165 report-link behavior stays
unchanged.
