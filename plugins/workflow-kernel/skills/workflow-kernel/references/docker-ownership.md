# Docker resource ownership

The workflow kernel recognizes a Docker object as owned only through a complete,
positive label set. Names are diagnostic and never establish ownership.

Every managed container, network, and named volume carries these labels before
Docker creates it:

| Label | Value |
|---|---|
| `com.designmachines.depot.managed` | exactly `true` |
| `com.designmachines.depot.run-id` | owning workflow run |
| `com.designmachines.depot.node-id` | creating node |
| `com.designmachines.depot.created-at` | RFC 3339 timestamp |
| `com.designmachines.depot.lifecycle` | `chunk` or `run` |
| `com.designmachines.depot.cleanup-policy` | `stop-remove`, `remove-when-stopped`, or `retain` |

`docker run`, `docker container create`, `docker network create`, and
`docker volume create` receive label flags in their creation argv. Compose is
first rendered with `docker compose ... config --format json`; the kernel then
requires and preserves the caller's explicit base `-f`/`--file` stack,
including Docker's attached `-fFILE` shorthand, creates a
run-scoped project name, and appends a labels-only override for services, the
default and declared networks, and named volumes. The rendered config is used
only for validation and intent discovery; interpolated environment values are
never copied into the override or durable plan. Caller-supplied `-p` and
`--project-name` options, including attached `-pNAME`, are rejected so project
ownership cannot be shadowed.
External resources, anonymous
volumes, invalid config, and unsupported or ambiguous command forms are
explicitly unmanaged.

## Registration and cleanup proof

After creation, the registry records the command result and before/after
inventory delta against every registration intent. A current-run object is
removable only when its kind and ID, complete ownership-label snapshot, and
inspected creation time agree with its durable registry record. The registry
keys identity by kind plus ID. Each registration or disposition takes an
exclusive registry lock bound to one physical parent and exclusive regular-file
inode. The transaction retains both lock and journal descriptors, reloads and
validates the full journal with exact event keys, then revalidates both names
immediately before and after append, flush, and fsync. Symlink, hardlink, parent
replacement, journal replacement, and lock replacement are rejected.
This keeps owner conflicts,
attempt history, and terminal dispositions immutable across concurrent kernel
instances. A stale orphan may lack a registry record only
when every label value is valid, the label timestamp agrees with Docker's
inspected creation time, both timestamps are strictly older than the typed TTL,
and an injected authoritative lease reader returns an exact, fresh `LeaseProof`
that proves its run inactive. Missing, malformed, unreadable, active, future, or
stale lease proof retains the object. At either exact TTL boundary it remains.

Git cleanup is likewise a pure plan. It requires exactly one registered
worktree and one registered branch for the requested scope plus an exact,
fresh `GitProof` whose normalized path, namespace, branch, base, and merge
target, resolved object IDs, and authoritative `git worktree list --porcelain`
row agree with both registry records. Prunable rows remain explicit blocked
decisions, and option-looking refs are rejected. The adapter canonicalizes its
absolute worktree ownership root, rejects filesystem root and unsafe or
unbounded roots, and checks containment by path components rather than string
prefix. Additional registered Git resources
make the scope ambiguous: deletion is blocked and every registered worktree and
branch receives a disposition.

Chunk resources are planned for cleanup automatically after validation, review,
evidence capture, and merge disposition. Run resources remain while any declared
dependent node is active. `succeeded`, `failed`, `blocked`, `cancelled`, and
`interrupted` terminal paths all plan reconciliation. Chunk 05 is the sole
executor of these plans; Chunk 03 performs inventory, pure planning, durable
registration, and pure result recording.

Every cleanup action is a proof-bound capability. Its schema carries an exact
kind and ID, argv, environment, owner, lifecycle, action, canonical evidence
and capability SHA-256 digests, explicit preconditions, dependency ordering,
and predecessor-result identity. Chunk 05 must refresh exact Git or
Docker evidence and call the adapter revalidation contract immediately before
executing the argv. Actions for records with declared dependents bind the exact
dependent-node IDs and an authoritative status row for every dependent. A
fresh, readable `IncompleteNodeProof` treats `pending`, `ready`, `running`, and
`waiting` nodes as incomplete; `succeeded`, `failed`, `blocked`, and `skipped`
are terminal. Missing status rows, any incomplete dependent, stale proof, or a
changed dependency/status snapshot invalidates the action. Changed ref count,
object identity, label, lease/use state, inspect result, or resource identity
likewise invalidates it. The lifecycle coordinator accepts and forwards this
typed proof; lower adapters expose no raw active-ID shortcut.
Execution-time Docker revalidation atomically reloads the exact durable registry
record and its active/retired state. Registered mode requires an active record
for the action owner and derives dependency-proof requirements only from that
record. Action precondition strings, Docker labels, cached plans, and shadow
state cannot declare a registered resource dependency-free. Stale-orphan
revalidation is an explicit separate mode: it proves the registry has no exact
kind-and-ID record under any owner; a retired historical record still blocks
orphan authorization. Complete positive labels and a fresh inactive lease are
also required. Command results remain a gap-free plan prefix
beginning at action zero; a dependent action is accepted only after its declared
predecessor result appears earlier and succeeded.

Cleanup uses only exact IDs:

- a current, owned running container may be stopped with a bounded
  `docker stop --time N ID`, followed by `docker rm ID`;
- a stale running container is retained and never stopped;
- networks and volumes in use, system networks, and objects that cannot be
  inspected are retained or blocked with a reason; volume use is proven by an
  authoritative container-mount query, never inferred from absent inspect data;
- missing objects are an idempotent successful end state only after a registered
  kind+ID inspect command returns exit code 1 and an exact Docker not-found
  response for that same kind and ID; transport failures and caller-asserted
  inventory source strings never prove absence;
- filtered managed-label inventory is used only for orphan reconciliation;
- volumes are removed by explicit IDs only.

Broad cleanup is forbidden. The kernel never emits `docker system prune`, any
unfiltered or negative prune, wildcards, shell command strings, or name-based
ownership guesses. Receipts record kind, ID, owner, lifecycle, action, reason,
bounded evidence, and follow-up without copying command output that may contain
secrets. Runtime cleanup receipts serialize with schema version, scope, nested
owner, kind and ID, lifecycle, disposition, exact command evidence, reason, and
follow-up. The complete serialized receipt—including scope, owner, identifiers,
reason, command evidence, and nested evidence—is traversed through the shared
bounded redaction policy. Cookie, bearer, DSN, environment-secret, overlong,
cyclic, and otherwise unsafe values are redacted or hashed before durable
persistence while safe resource identities remain available as evidence.
`REMOVED` and `MISSING` cannot be written through the public disposition API or
a detached receipt. They become durable only inside a registry-owned,
single-use result transaction after the canonical plan, exact command results,
and before/after inventories have been reconstructed. All observed orphan
registrations and outcomes are written in the same framed journal event. A
truncated final frame is ignored as interrupted; interior corruption fails
closed, so a multi-resource result can never partially retire ownership. If an
object reappears or exact absence evidence is missing, the terminal disposition
is downgraded to blocked.
