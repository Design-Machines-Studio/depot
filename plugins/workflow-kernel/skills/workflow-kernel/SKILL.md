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

Resolve the newest installed runtime from the Claude cache first, then the Codex
cache. Avoid hardcoded version directories:

```sh
KERNEL_REFS=""
for CACHE_ROOT in "$HOME/.claude/plugins/cache/depot" "$HOME/.codex/plugins/cache/depot"; do
  KERNEL_REFS=$(find "$CACHE_ROOT/workflow-kernel" -type d \
    -path "*/skills/workflow-kernel/references" -prune \
    -exec ls -td {} + 2>/dev/null | head -1)
  [ -n "$KERNEL_REFS" ] && break
done
if [ -z "$KERNEL_REFS" ]; then
  echo "workflow-kernel runtime not found in Claude or Codex plugin cache" >&2
  exit 1
fi
(
  cd "$KERNEL_REFS" || exit 1
  PYTHONPATH="$KERNEL_REFS" python3 -m workflow_kernel --help
)
```

For repository-local development, invoke the module with
`PYTHONPATH=plugins/workflow-kernel/skills/workflow-kernel/references python3 -m workflow_kernel`.

## Operating Contract

Initialize every run in shadow mode unless the caller explicitly selects
`enforce` or `native`. Append only validated events with the next exact sequence.
Acquire the run lease before publishing materialized state. Supply the expected
revision on every state write. Reconstruct state from the ledger after an
interruption rather than trusting a potentially stale materialization.

Treat event files and CLI input as untrusted. Reject schema drift, sequence gaps,
conflicting run IDs, illegal transitions, and non-JSON payload values. Preserve
`interrupted` as its own terminal outcome. Permit terminal mutation only for
evidence attachment and one cleanup reconciliation.

Use `python3 -m workflow_kernel --help` for the `init`, `validate`, `append`,
`replay`, and `status` commands. Consume successful operational output and
errors as stable JSON. Treat `--help` output as plain text.

## Public API and Contracts

- Construct immutable `WorkflowEvent`, `NodeState`, and `RunState` schema
  objects. Direct Python construction follows normal signature semantics, so
  missing or extra positional arguments raise Python `TypeError`. Use
  `from_dict()` as the boundary for untrusted mappings; unknown fields, enums,
  versions, unsafe references, and invalid JSON shapes then fail with a stable
  `KernelError.code`.
- Construct `EventStore(event_path, state_path)` so ledger mutation is bound to
  the run's materialized-state lease. Use
  `EventStore.append(event, expected_sequence, lease=same_run_lease)` to append
  exactly the next event. The exact live `RunLease` must authorize the bound
  state path before mutation and is revalidated immediately before the write.
  Records and projected ledgers that exceed durable read limits are rejected.
  Use `EventStore.replay()` to reject gaps, corruption, conflicting run IDs,
  and bounded-input violations.
- Use `StateStore.load()` to read the bounded materialization. Unsafe paths or
  invalid state bytes fail with `CorruptStateError.code == "corrupt_state"`.
  Use `StateStore.prepare(state)` before publishing an event that derives the
  state. It returns an opaque exact-type identity capability with no exposed
  state or encoded-byte fields. The issuing store owns the authoritative
  validated state and exact bytes in a private weak registry; pass only that
  capability to `StateStore.publish(prepared, expected_revision, lease=lease)`. Preparation
  validates state bytes but does not acquire or replace the live run lease.
  Coordinated CLI append prepares before event publication while holding that
  lease; direct writes compose prepare and publish automatically. Oversized
  state is rejected before temporary-file creation or replacement.
- Acquire `RunLease(state_path)` and pass that live capability to
  `StateStore.write(state, expected_revision, lease=lease)`. A lease for a
  different path or a released lease never authorizes a write. POSIX advisory
  locks release on process exit, so crash residue does not become a lock. Hosts
  without POSIX `fcntl` locking fail closed with a stable conflict error; the
  kernel never falls back to crash-stale sentinel locking.
- Hold the same run lease across authoritative ledger replay, current-state
  observation, event append or reduction, and materialized-state publication.
  Mutable lock, ledger, and state paths must be exclusive regular files; the
  kernel rejects symbolic links, hard links, and identity changes.
- Use `TransitionEngine.apply(state, event)` for one pure transition and
  `TransitionEngine.reconstruct(events)` for deterministic replay. Event
  sequence equals the prior state revision; each accepted event increments the
  revision by one. A run may attach at most 1,024 evidence items across run and
  node state; transitions exceeding that aggregate limit fail before state
  reconstruction.
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
  subclass is always unknown, even when its content equals a known key, and is
  digested without invoking attacker-defined equality, hashing, string, or
  encoding methods. Every unknown error-detail key at any depth becomes a
  deterministic `key-sha256:<64 lowercase hex>` digest. Canonical
  `value-sha256:` and `key-sha256:` tokens remain stable when already-sanitized
  metadata is sanitized or encoded again; a raw key colliding with a canonical
  key token fails closed. Literal caller strings `[REDACTED]` and `[UNSAFE]` are
  ordinary values and therefore hash. Only the sensitive-key sanitizer branch
  emits the trusted `[REDACTED]` marker. Use these digests only for stable correlation
  across receipts and logs—the original plaintext is never recoverable from the
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

Import the package from `references/workflow_kernel/`. Run its tests from
`references/tests/` before integrating an orchestrator.
