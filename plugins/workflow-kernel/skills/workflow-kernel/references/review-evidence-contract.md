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
reads the same locked snapshot and retains referenced history under the separate validated-required and diagnostic bounds below. Optional contribution writers use that lock too;
economics and observations never settle or revoke required coverage.

Closed failure stages are `lane_input`, `lane_validation`,
`aggregate_validation`, `preservation_input`, `retained_validation`. Reasons
distinguish missing/invalid evidence, digest disagreement, source/scope
mismatch, unsafe paths, conflicts and retention limits, using safe artifact-role
filenames. Schema exits 2, incomplete/unsafe evidence 3, conflicts 6. Preserve
safe available inputs and originals on failure. #165 report-link behavior stays
unchanged.

## Bounded retention (>=0.28.0)

Since 0.28.1, required review evidence is bounded to **128 MiB (134,217,728 bytes) / 1,024
files**. Disposable diagnostics retain **9 MiB (9,437,184 bytes) / 416 files**.
These are separate aggregate allowances, not per-file permissions. Both count
regular-file bytes without compression. The existing exact-owned diagnostic
child stores both; no new storage, registry or migration is introduced.

Only a package passing the existing source, scope, digest, provenance,
completeness, receipt and report checks receives required membership. Kernel
computes the exact set: six canonical review documents, report, selected
lane/browser references, every committed source/history/transition binding,
indexed private router receipts and index, and every local report link.
Identical references count once. Unindexed router files and unrelated additions
remain diagnostics, even inside a review-looking directory. A filename or
caller assertion never grants the larger retained allowance. Incomplete
preservation retains available inputs only under the diagnostic bound.

The 32 MiB allowance in 0.28.0 covered the earlier 9.5 MB package, but
Baseplate #1118 now retains 42,625,283 bytes in 54 assembly files. Six distinct
literal inputs are 6–8 MB each; no byte-identical duplicates can be removed.
The 128 MiB ceiling provides about three times that observed workspace size
for remaining lanes, source continuity and final report links. It remains a
finite per-run storage limit, not a promise that every future package will fit.
Diagnostic and file-count limits are unchanged. Original sealed bytes are
never rewritten or dropped to fit. Resume the existing producer with 0.28.1;
a larger allowance never grants missing review coverage or clears other gates.

`project-review-evidence` accepts exactly the preservation arguments. Call it
while assembling evidence (with the available companions and provisional
report) and again after the final report's evidence links settle. It emits
`status: projected`, `coverage_proof: false`, `within_limits`, whole-package
`files`/`bytes`, `missing`, and separate `retention` measurements with
`actual_bytes`, `actual_files`, `allowed_bytes`, `allowed_files`. It creates no
lock, diagnostic directory, metadata or copy. Missing early coverage remains
explicit and receives no larger allowance. Projection may race a producer and
never authorizes later copying: the preservation boundary rereads, validates,
measures and checks its exact staged bytes, then validates the durable copy.

Assembly uses the same required ceiling for its temporary evidence workspace;
this resource ceiling is not retained coverage authority. Preservation applies
the exact required/diagnostic partition before copying and again after byte
verification. Retained revalidation and owned-run finish use that same
partition before deleting sources. Errors include measured and allowed byte/file
counts, category and one next action, without rejected paths or credentials.
Keep originals and request a bounded policy repair if required evidence exceeds
the ceiling; move only unrelated diagnostics. Never prune required history.

Supported existing schema-1/schema-2 records and pinned historical retention
remain readable. Retries reuse identical sealed references and source inventories
through the existing helpers. Source or report growth is remeasured; interrupted
copying keeps originals and removes only task-owned staging.

## Retained historical terminal validation (>=0.26.1)

New assembly/preservation stay strict. Only `owned-run-finish --outcome succeeded`
accepts `--historical-review-digests <existing-saved-inventory>` for an already
retained exact-owned run. The option locates independently established bytes;
fresh hashes, failed retention or schema changes grant no authority.

The sole supported literal inventory SHA256 is
`b33733a078242d51f12968fe57214d313b5f09e85c963268cc3f41db33328981`,
for workflow `pipeline`, run `parity-1118-20261007-a`, repository
`github.com/Design-Machines-Studio/assembly-baseplate`, original head
`768532b154251d86ea585b730184629594e1ac5d`. This is a bounded recovery.

Kernel verifies original owner metadata/CLEANUP, every saved digest, contained
regular files without symlinks/hardlinks, complete reference closure, indexed
receipts/report links and the shared original contract: lanes, output digests,
finding/synthesis accounting and browser cases. Saved files cannot change or
vanish. Diagnostic additions outside the frozen review scope remain allowed
within existing retention limits; they grant no eligibility or coverage.

The result adds `review_validation.validation: historical_compatibility` with
original run/repository/head. It never approves current PR head
`5c11779293aff6d08a9eea185331dbc1ff9dc844` or claims current source-bound
coverage. Repeated validation returns unchanged evidence and the same result.
After release/synchronization, the owner reruns only terminal validation:

```sh
"$WORKFLOW_KERNEL" owned-run-finish --run-root "$RETAINED_RUN_ROOT" \
  --outcome succeeded --retain-diagnostics \
  --historical-review-digests "$ORIGINAL_SAVED_INVENTORY"
```

Unknown fingerprints report the missing independent retention baseline. Keep
retained evidence; use `assemble-review-evidence` recovery from existing outputs
and actual source/inspection evidence, then strict preservation in a new
exact-owned replay. Never fabricate versions, timestamps, inventories or
inspection. Unknown execution times stay unknown; missing inspection stays
incomplete. Do not preserve the historical original again.

Terminal errors carry closed reasons, safe `artifact_role`, plain messages and
one `next_action`; compatibility/missing/unsafe evidence exits 3, corruption or
incomplete coverage exits 2. No arbitrary supplied paths/raw exceptions appear.
Terminal cleanup uses the throwing validator; existing boolean callers stay
strict.

The final required GitHub/caller rechecks produced an eligible complete package
of 362 files and 8,080,697 bytes, including final coverage and every companion,
source/history/transition binding, private receipt and report. Actual production
preservation rejected both 6 MiB and 288 files. The bounded final allowance is
8 MiB/384 files; 8 MiB is evaluated against this complete package, and 384 leaves
room for the required final source transition (the previous measured transition
added 11 files). Required evidence and original sealed bytes are unchanged.
No digest, source, scope, provenance, path-safety or completeness check changes.

Release verification found PR172's digest race and repaired it in the existing
Kernel dependency. Required repair/source-continuity evidence then measured
386 files and 8,579,686 bytes; normal preservation rejected both 384 files and
8 MiB. The historical shared allowance was 9 MiB/416 files, including room for the
required finishing transition. Original bytes and validation remain strict.

## Native Codex host provenance (>=0.27.0)

`assemble-review-evidence` accepts a closed alternative lane `literal` object:

```json
{"output_ref":"review/recheck/security-output.md","native_trace_ref":"private/native-events.jsonl","native_index_ref":"private/native-index.json"}
```

Use actual T3 Code subagent host records. Retain the original private trace;
bounded excerpts copy its selected JSONL lines exactly, in original ordinal
order. A required bound index has exactly `schema_version:1`,
`full_trace_digest`, `excerpt_digest`, `thread_id`, `original_line_numbers`
and `original_ordinals`. The excerpt digest must match its exact bytes, the
thread must match the session, and ordered line numbers equal ordinals plus one.
The index is bounded to 64 KiB. The host independently byte-verifies and privately
preserves the original full trace and its declared digest.

Kernel validates structural witness and index consistency. It does not
authenticate T3 origin or check the declared full-trace digest against the
privately retained original. These are trusted host inputs, like existing
router evidence; never describe structural acceptance as origin authentication.
Never create router receipts for collaboration tool executions. The existing
router literal variant and its validation are unchanged; retain every actual
router receipt and its index for mixed runs.

The native variant requires coherent session/parent/agent/turn identity, the
assignment routing header, successful same-turn Git HEAD and clean-status observations,
an exact completed AddFile/FileChange output, its paired exec patch/result, and subsequent
assistant final answer and task completion. Encrypted assignment content stays
opaque. Trace bytes are inert: commands, patches and model messages are never
executed or interpreted as review findings. Existing declared inspection scope,
source snapshots, recheck history, finding extraction and aggregate checks remain
mandatory. Pairing requires a nonempty bounded call ID. Missing or mismatched
witnesses block production coverage.

For the exec witness, pass an inertly decodable literal AddFile patch with the
absolute output path and exact content. Computed JavaScript patches and relative
patch paths are not interpreted. Preserve unsupported original output/provenance
as diagnostic evidence; a required affected recheck uses this supported form.

Use standalone `git rev-parse HEAD` and `git status --short` (optional `rtk`
or `rtk proxy` prefixes). The HEAD result contains exactly one hash and status
is empty. Two closed historical read-only programs are also recognized:
Git status/HEAD/diff-stat and bounded cache-asset lookup/remote/HEAD/status.
Their output must prove one unambiguous HEAD and no dirty status. Arbitrary
combined commands, printed or quoted command text, and conflicting HEAD
observations do not establish source. A historical output lacking required
evidence stays diagnostic; preserve it and inspect only genuinely required
current changes rather than relabeling it.

Only committed-source review is supported. Recovery binds the original observed
commit; staged historical inspection remains supplemental evidence and cannot
be relabeled as a later commit. Review new affected changes at a clean committed
boundary. Native excerpts are bounded to 2 MiB, 4096 records and 512 KiB per
record, within the validated-required package allowance.

The participant ID is `native-` plus the first 16 SHA256 hex characters of the
actual host thread ID. Actual model/provider observations remain in the private
trace. Missing or unclassified model identity uses the existing `not_reported`
summary sentinel and unknown family; it never prevents otherwise evidenced
inspection. Family classification reuses the existing normalizer. Neither
thread token totals nor unreported charges become invented per-lane cost.

Use the ordinary assembler and strict preservation afterward. A relocated
exact-owned recovery copy may retain old companions under history and emit new
canonical companions; original streams, seals, literals and source identities
stay immutable. Recovery does not invoke a model or validate earlier consumer
dispatch retroactively. Unit/native-format fixtures are development artifacts,
never live inspection evidence.
