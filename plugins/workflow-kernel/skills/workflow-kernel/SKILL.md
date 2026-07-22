---
name: workflow-kernel
description: This skill should be used when the user asks to "validate workflow state", "replay workflow events", "inspect a workflow ledger", or "use the workflow kernel" for shared pipeline and review mechanics.
version: 0.1.0
---

# Workflow Kernel

Use the workflow kernel as the neutral, dependency-free mechanics layer shared by
workflow orchestrators. Keep routing, review expertise, security policy, and
human judgment in their canonical Markdown contracts.

## Runtime Resolution

Invoke the kernel exclusively through the launcher shipped beside the runtime:

```sh
"<references>/workflow-kernel-launcher.sh" <subcommand> [args...]
```

The launcher resolves the canonical runtime (its own repository checkout
first, then versioned cache directories under `~/.claude` and `~/.codex`
ordered by parsed semver -- never `ls -td` mtime, so re-pulling an older
version cannot shadow a newer one), verifies Python 3.12+, sets the module
path, and execs `python3 -m workflow_kernel`. Compatibility is same-major at
or above the declared `>=0.1.0` floor. The complete consumer-facing
resolution and fail-closed contract, including the launcher discovery
snippet, is `references/runtime-resolution.md`; consuming plugins link there
instead of restating it.

For repository-local development, either run the launcher directly from the
checkout or invoke the module with
`PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references python3 -m workflow_kernel`.

## Operating Contract

Initialize every run in shadow mode unless the caller explicitly selects
`enforce` or `native`. Append only validated events with the next exact sequence.
Acquire the run lease before publishing materialized state. Supply the expected
revision on every state write. Reconstruct state from the ledger after an
interruption rather than trusting a potentially stale materialization.
Initialization performs a descriptor-relative verified absence preflight for
both ledger and materialized-state names under the run lease, then prepares the
initial state before appending the first event. Append proceeds only when an
existing materialization exactly matches the replay-derived state; otherwise
stop before ledger mutation and run `replay` to reconcile the materialization.
After validating and reconstructing the ledger, replay uses private
ledger-derived prepared issuance and the one public publication path. Its
revision-bound, one-shot capability must be published immediately under the
same live lease, and performs a lease-protected authoritative replacement for
missing, behind, ahead, or equal-revision divergent materialization while
retaining expected-revision CAS checks. There is no public rollback API.

Treat event files and CLI input as untrusted. Reject schema drift, sequence gaps,
conflicting run IDs, illegal transitions, and non-JSON payload values. Preserve
`interrupted` as its own terminal outcome. Permit terminal mutation only for
evidence attachment and one cleanup reconciliation.

Use `workflow-kernel-launcher.sh --help` (or `python3 -m workflow_kernel
--help` in a repository checkout) for the `init`, `validate`, `append`,
`replay`, and `status` commands. Consume successful operational output and
errors as stable JSON. Treat `--help` output as plain text.

## Stable mechanical CLI surface

Kernel 0.4.0 adds sixteen file-bound operations: `verification-plan`,
`verification-run`, `verification-result`, `evidence-match`,
`artifact-classify`, `staging-allowlist`, `browser-scenario-validate`,
`browser-bundle-record`, `review-record`, `ci-evidence-normalize`,
`review-boundary-capture`, `review-boundary-compare`, `closeout-audit`,
`improvement-index`, `improvement-finalize`, and `improvement-render`. They
accept explicit local JSON and safe arguments only;
provider collection, credentials, routing judgment, issue mutation, and release
authority remain with consumers. Stable exits are 0 success, 2 invalid input,
3 blocked/unsafe, 4 unavailable/incompatible, 5 parity gap, and 6 conflict.

## Public API and Contracts

- Construct exact, final, immutable `WorkflowEvent`, `NodeState`, and `RunState`
  schema objects. Durable writers, receipt factories, and reducers reject
  substitutes instead of dispatching virtual serializers. Durable schema
  fields and recursive payloads require exact built-in `str`, `int`, `float`,
  and `bool` values as appropriate; mapping keys and evidence references
  require exact `str`. Subclasses cannot override validation or comparison.
  Reducers, event writers, receipt factories, and state writers rebuild exact
  fields through shared bounded internal snapshots before any public
  `to_dict()` projection. Direct Python
  construction follows normal signature semantics, so
  missing or extra positional arguments raise Python `TypeError`. Use
  `from_dict()` as the boundary for untrusted mappings; unknown fields, enums,
  versions, unsafe references, and invalid JSON shapes then fail with a stable
  `KernelError.code`.
- Construct `EventStore(run_root)`; its exact, final, weak-referenceable,
  slot-only identity records the physically parent-bound root, event, state,
  and lock paths in a closure-owned registry. It resolves the existing run
  root without following the final durable filename, then rejects parent or
  file identity displacement. It derives only `<run_root>/events.jsonl` and
  `<run_root>/run-state.json`, so neither public nor private instance mutation
  can pair paths or locks from different runs. Use
  `EventStore.append(event, expected_sequence, lease=same_run_lease)` to append
  exactly the next event. The exact live `RunLease` must authorize the bound
  state path before mutation and is revalidated immediately before the write.
  The open ledger descriptor must still match its exclusive pathname
  immediately before writing and after `fsync`; validation performs the same
  identity check after parsing and before returning. These operations retain a
  verified parent-directory descriptor and use descriptor-relative child opens
  and stats, so a parent rename or replacement cannot redirect the ledger.
  Records and projected ledgers that exceed durable read limits are rejected.
  Use `EventStore.replay()` to reject gaps, corruption, conflicting run IDs,
  and bounded-input violations.
- Use `StateStore.load()` to read the bounded materialization. Unsafe paths or
  invalid state bytes fail with `CorruptStateError.code == "corrupt_state"`.
  A loaded descriptor is revalidated after parsing. Publication keeps the
  verified parent and observed-state descriptors open through temporary-file
  creation, write and sync, a second revision observation, descriptor-relative
  replacement, and directory sync, then
  requires that descriptor to remain the authoritative state pathname before
  reporting success. Compare-and-swap and never-overwrite guarantees cover
  cooperating writers that honor the same `RunLease`; pinned checks cannot
  atomically exclude non-cooperating filesystem mutation in the final commit
  window. A detected valid revision race remains a `RevisionConflictError`
  rather than generic filesystem corruption. A missing file is the public
  missing/empty case only after the pinned parent is revalidated; parent
  disappearance or replacement is corruption.
  Use `StateStore.prepare(state)` before publishing an event that derives the
  state. It returns an opaque exact-type identity capability with no exposed
  state or encoded-byte fields. A closure-owned weak registry keyed by the
  exact store and capability owns only the captured revision, exact bytes, and
  immutable issuance mode. A replay capability also owns the materialized
  expected revision observed by the CLI;
  it never retains or later consults the caller's `RunState`. Pass only that
  capability to the one public publication path,
  `StateStore.publish(prepared, expected_revision, lease=lease)`; ordinary publication rejects backward revisions. After successful ledger validation
  and reconstruction, only CLI replay can use the module-private issuer for
  private ledger-derived prepared issuance. The capability registry owns its
  immutable issuance mode, so the same public `publish()` operation permits
  that ledger-authoritative replacement in either revision direction without a
  caller flag, alternate mutation method, or weakened path identity, lease, or
  cooperating-writer CAS enforcement. Replay issuance is revision-bound and
  one-shot: publication requires the issued expected revision. Prepared ownership,
  exact live lease/path authorization, expected-revision shape, and issuance
  binding are checked without consuming the capability. Immediately after those
  checks succeed, publication consumes it before any publication parent setup or
  binding, durable state observation, or temporary-file work, so success and any
  later publication failure both make it unusable. Ordinary prepared capabilities
  retain their existing reusable behavior. There is no public rollback API.
  Preparation uses the same field-wise bounded snapshot-and-encode helper as
  `encode_state()` but does not acquire or replace the live run lease.
  Coordinated CLI append prepares before event publication while holding that
  lease; direct writes compose prepare and publish automatically. Oversized
  state is rejected before temporary-file creation or replacement.
- Acquire `RunLease(state_path)` and pass that live capability to
  `StateStore.write(state, expected_revision, lease=lease)`. A lease for a
  different path or a released lease never authorizes a write. `RunLease` and
  `StateStore` are final, slot-only public identities; authoritative paths,
  handles, process ownership, and liveness remain in a closure-owned weak
  registry. Consumers use the module-owned non-dispatching authorization path,
  never caller-overridable instance state. POSIX advisory
  locks release on process exit, so crash residue does not become a lock. Hosts
  without POSIX `fcntl` locking fail closed with a stable conflict error; the
  kernel never falls back to crash-stale sentinel locking.
  Prefer `with RunLease(state_path) as lease:` so release is deterministic. If
  manual `acquire()` is necessary, call `release()` in `finally`; a weakref
  finalizer releases the underlying lock if an acquired lease is garbage
  collected, and explicit release or context exit invokes that finalizer only
  once. In a forked child, explicit release and GC only close the inherited
  descriptor without issuing `LOCK_UN` against the parent's lock ownership.
  Lease setup and explicit release errors are normalized to
  cause-suppressed `LeaseConflictError`; cleanup failures never replace an
  already-active primary kernel error.
- Hold the same run lease across authoritative ledger replay, current-state
  observation, validation comparison, event append or reduction, and
  materialized-state publication.
  Mutable lock, ledger, and state paths must be exclusive regular files; the
  kernel rejects symbolic links, hard links, and identity changes.
- Use `TransitionEngine.apply(state, event)` for one pure transition and
  `TransitionEngine.reconstruct(events)` for deterministic replay. Event
  and state inputs are captured through the shared exact field-wise snapshots
  before any comparison, initialization check, or dispatch. Event
  sequence equals the prior state revision; each accepted event increments the
  revision by one. A run may attach at most 1,024 evidence items across run and
  node state; transitions exceeding that aggregate limit fail before state
  reconstruction. Reconstruction streams at most 100,000 events and never
  eagerly exhausts a caller iterable. A bounded iterable accepts at most N
  items but may consume one lookahead item to prove that N was exceeded.
  Public `apply` validates the input state graph once and then constructs the
  legal output through a private trusted path. Reconstruction snapshots each
  untrusted event but does not revalidate the accumulated graph after every
  accepted event. The reducer maintains node, dependency-edge, evidence, and
  UTF-8 text counters before every trusted update. Reconstruction also charges
  the scalar event snapshot (`run_id`, `node_id`, `kind`, and `occurred_at`),
  recursive event payload snapshot, node-update creation, and graph copy/access
  operations against `MAX_RECONSTRUCTION_WORK=50100000`. Exact scalar and
  payload strings charge character and UTF-8 traversal before normalization.
  Charged work also includes evidence parsing, copying existing evidence into
  a set, membership scans, and dependency membership/access scans. Private
  trusted node updates reuse already-normalized dependency and evidence tuples
  without rescanning them, bounding total replay work by the supported state
  and event limits.
- One run-wide state-tree budget counts nodes, dependency edges, node evidence,
  and run evidence against `MAX_PAYLOAD_ITEMS` before dependency-graph helper
  structures are allocated. Node mappings and snapshots share one validated
  projection and private trusted frozen construction path, so dependencies and
  evidence are normalized once. The same aggregate bound applies to direct
  `RunState` construction, parsed state, and writer snapshots.
  Direct construction and `from_dict` share one run-state projection and one
  private trusted constructor. Exact strings are checked against
  `MAX_STRING_LENGTH` before UTF-8 encoding or aggregate byte counting.
- Recursive payload, raw-receipt, public-metadata, error-detail, and state-tree
  traversal has a cumulative 4,194,304-byte UTF-8 text budget. Mapping keys and
  string values consume that budget before they are retained; the independent
  depth, item, and per-string limits still apply. The package root exports the
  authoritative limits: `MAX_PAYLOAD_DEPTH=16`, `MAX_PAYLOAD_ITEMS=10000`,
  `MAX_STRING_LENGTH=65536`, `MAX_TOTAL_STRING_BYTES=4194304`,
  `MAX_EVIDENCE_ITEMS=1024`, `MAX_EVENT_ITEMS=100000`,
  `MAX_RECORD_BYTES=1048576`, `MAX_LEDGER_BYTES=16777216`, and
  `MAX_STATE_BYTES=4194304`. Record, projected-ledger, and materialized-state
  byte caps remain final writer/read caps after traversal validation.
- The package root also exports `PreparedState` for type-aware API consumers
  and `ErrorDetailKey` for the closed public error-detail vocabulary.
- Catch `KernelError` subclasses and serialize `to_dict()` for stable safe
  errors. `ErrorMessage` and `ErrorCode` are the closed developer-owned enums
  for public text and machine codes; raw or unknown candidates become the
  generic `workflow kernel error` / `kernel_error` pair. Dynamic, parser, and
  rejected-input context belongs only in recursively immutable details. Each
  error captures one frozen `ErrorEnvelope`; message, code, details,
  `to_dict()`, and `str(error)` delegate to that envelope. `BaseException` is
  initialized only with the catalogue-owned safe message, so inherited
  `args`, `repr`, formatting, logging, and pickle surfaces never retain raw
  constructor messages or details; pickle intentionally omits details. The
  exception hierarchy is an in-process extension surface: subclasses and
  runtime classes are trusted, and hostile monkeypatching inside the Python
  process is outside this boundary's threat model. `KernelError.to_dict()` is
  convenient normal dispatch. At CLI or other process/external boundaries, use
  the base-owned `serialize_kernel_error(error)`, which reads the captured
  envelope directly without subclass serialization dispatch.
  Sensitive-key paths become `[REDACTED]`; every other string value becomes a
  deterministic `value-sha256:<64 lowercase hex>` digest, while numbers,
  booleans, and null remain typed. `ErrorDetailKey` is the developer-owned
  vocabulary whose exact built-in `str` values remain readable. A `str`
  subclass is rejected before classification, without invoking
  attacker-defined equality, hashing, string, or encoding methods. Every
  exact-string unknown error-detail key at any depth becomes a
  deterministic `key-sha256:<64 lowercase hex>` digest. Canonical
  `value-sha256:` and `key-sha256:` tokens remain stable when already-sanitized
  metadata is sanitized or encoded again; a raw key colliding with a canonical
  key token fails closed. Literal caller strings `[REDACTED]` and `[UNSAFE]` are
  ordinary values and therefore hash. Only the sensitive-key sanitizer branch
  emits the trusted `[REDACTED]` marker. Use these digests only for stable correlation
  across receipts and logs -- the original plaintext is never recoverable from the
  public error. Do not expose raw parser exceptions or rejected values.

## Security and Portability

Pass only evidence references into the ledger. Recursively redact token, key,
secret, password, authorization, cookie, DSN, and environment-value fields.
Never report a raw secret in errors or receipts. Every receipt path uses the
shared bounded redaction traversal with receipt-owned schema callbacks, composing
durable-string normalization with public-value digesting in one recursion:
sensitive keyed values become `[REDACTED]`, every other
string value becomes `value-sha256:<64 lowercase hex>`, and every key outside
the selected exact built-in-string schema becomes
`key-sha256:<64 lowercase hex>`. `ReceiptField` and `WorkflowEventField` own the
explicit evidence, transition, and nested-event vocabularies; arbitrary
metadata and payload mappings use no trusted field vocabulary.
`evidence_receipt()` and `transition_receipt()` return final immutable canonical
`bytes`, ready for artifact scanners and durable writes. `encode_receipt()` is
the sole raw-mapping boundary and sanitizes its input exactly once before
canonical encoding. Parsed receipt JSON is therefore raw input if passed back
to `encode_receipt()`; there is no trusted re-encoding or provenance-inference
path. Raw
`key-sha256:` keys and all raw digest-shaped or marker-shaped values are therefore
re-digested and cannot infer provenance from their shape. Only the sensitive-key
branch emits `[REDACTED]`.
`evidence_receipt()` value-digests caller `run_id` and `evidence_type`, sanitizes
arbitrary metadata, and preserves only a separately validated evidence
reference. It sanitizes one digest-free projection, canonically encodes that
same projection for content addressing, adds the digest to the sanitized
projection, then canonically encodes the complete receipt without another
traversal.
All public collection boundaries count before allocation: raw schema mappings,
node mappings, error details, receipt metadata, evidence/dependency sequences,
and reconstruction iterables stop at their declared limits without eager
copies. Public file, state, lease, and event `KernelError` wrappers suppress raw
OS exception causes, including parent-directory, temporary-file, descriptor
stat/dup/read/readline/write/flush/fsync/close, identity-check, and lock-release
failures, so rejected paths and raw OS messages cannot reappear in formatted
tracebacks. Owned descriptor, pinned-directory, and temporary-name scopes always
attempt every close and unlink. If cleanup also fails, the primary error remains
authoritative; a sole cleanup failure is normalized to the operation's public
kernel error.
`transition_receipt()` sanitizes the full event through the shared
event schema, including its arbitrary payload, and accepts `state_digest` only
in the exact canonical form `sha256:<64 lowercase hex>`; raw, uppercase,
other-prefix, and non-string values fail closed. A run-relative artifact path is
one or more `/`-separated ASCII segments matching
`[A-Za-z0-9_][A-Za-z0-9._-]*`; absolute paths, empty or dot segments,
backslashes, controls, and ambiguous query or fragment syntax are rejected.
Content IDs use exactly `sha256:<64 lowercase hex>`. Replay also accepts the
kernel-generated `url-sha256:<64 lowercase hex>` form. Valid content IDs are
exempt from URI normalization, but surrounding whitespace on a standalone URI,
network-path URL, or content ID is rejected as ambiguous. Every whole-string URI
candidate matching `[A-Za-z][A-Za-z0-9+.-]*:`, every network-path URL beginning
with `//authority`, and every such token embedded in prose is treated as
URI-valued regardless of its field name or any adjacent punctuation, digit, or
delimiter. Exact or embedded `http`, `https`, and network-path URLs must have an
authority and valid port with no userinfo, query, or fragment; the kernel
immediately replaces each complete original UTF-8 token with its deterministic
`url-sha256:` digest. For embedded URLs, symmetric angle brackets, quotes,
parentheses, brackets, braces, and terminal punctuation are preserved; multiple
tokens normalize deterministically, and repeated normalization is idempotent.
Token scanning is linear in the bounded input length. After normalization, any
remaining `[A-Za-z][A-Za-z0-9+.-]*:` token whose colon is followed immediately by
a non-whitespace character, or any remaining `//` token, fails closed unless it
is a valid content ID. This intentionally rejects namespace-like prose such as
`Note:see`; labels such as `Note: see` and URI-free local paths remain unchanged.
Every recursive mapping key is also untrusted: if URI classification would
reject or rewrite a key, the complete payload is rejected without rewriting the
key or reporting its original bytes. Error-detail mappings are the stricter
exception: only `ErrorDetailKey` members retain their names, and every other key
is replaced by its opaque key digest without reporting the original bytes.
Schema timestamp fields use a separate raw
string validator before timezone-aware ISO-8601 parsing. No original URL
component enters events, receipts, errors, or state. Exact and embedded values
using all other URI schemes are rejected.

Use only the Python standard library. Add no daemon, database, service, package
installer, or external API call. Keep JSON deterministic, UTF-8 encoded, and
newline terminated so Claude, Codex, and generic hosts consume identical bytes.

## Reference Runtime

Import the package from `references/workflow_kernel/`. The test suite is a
repository development artifact at the depot's top-level `tests/` directory,
run by `tools/validate-workflow-kernel.py` as part of
`./tools/validate-composition.sh --all`; it does not ship into user plugin
caches, and installed hosts do not self-test. Validate in the depot
repository before integrating an orchestrator.
