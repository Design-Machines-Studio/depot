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
export PYTHONPATH="$KERNEL_REFS${PYTHONPATH:+:$PYTHONPATH}"
python3 -m workflow_kernel --help
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
- Use `EventStore.append(event, expected_sequence)` to append exactly the next
  event. Records and projected ledgers that exceed durable read limits are
  rejected before mutation. Use `EventStore.replay()` to reject gaps,
  corruption, conflicting run IDs, and bounded-input violations.
- Use `StateStore.load()` to read the bounded materialization. Unsafe paths or
  invalid state bytes fail with `CorruptStateError.code == "corrupt_state"`.
  Use `StateStore.prepare(state)` before publishing an event that derives the
  state. It returns an immutable capability containing the exact encoded state,
  bound to that store; pass only that capability to `StateStore.publish()`.
  Coordinated CLI append does this before event publication, while direct writes
  compose prepare and publish automatically. Oversized state is rejected before
  temporary-file creation or replacement.
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
  errors. Do not expose raw parser exceptions or rejected values.

## Security and Portability

Pass only evidence references into the ledger. Recursively redact token, key,
secret, password, authorization, cookie, DSN, and environment-value fields.
Never report a raw secret in errors or receipts. Evidence references containing
URL fragments are rejected before durable encoding.

Use only the Python standard library. Add no daemon, database, service, package
installer, or external API call. Keep JSON deterministic, UTF-8 encoded, and
newline terminated so Claude, Codex, and generic hosts consume identical bytes.

## Reference Runtime

Import the package from `references/workflow_kernel/`. Run its tests from
`references/tests/` before integrating an orchestrator.
