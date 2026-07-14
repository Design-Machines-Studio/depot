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
creates a run-scoped project name and an override that labels services, the
default and declared networks, and named volumes. External resources, anonymous
volumes, invalid config, and unsupported or ambiguous command forms are
explicitly unmanaged.

## Registration and cleanup proof

After creation, the registry records the command result and before/after
inventory delta against every registration intent. A current-run object is
removable only when its kind and ID, complete ownership-label snapshot, and
inspected creation time agree with its durable registry record. The registry
keys identity by kind plus ID. A stale orphan may lack a registry record only
when every label value is valid, the label timestamp agrees with Docker's
inspected creation time, its timestamp is strictly older than the typed TTL,
and an injected authoritative lease reader proves its run inactive. Missing,
unreadable, active, future, or stale lease proof retains the object. At the exact
TTL boundary it remains.

Chunk resources are planned for cleanup automatically after validation, review,
evidence capture, and merge disposition. Run resources remain while any declared
dependent node is active. `succeeded`, `failed`, `blocked`, `cancelled`, and
`interrupted` terminal paths all plan reconciliation. Chunk 05 is the sole
executor of these plans; Chunk 03 performs inventory, pure planning, durable
registration, and pure result recording.

Cleanup uses only exact IDs:

- a current, owned running container may be stopped with a bounded
  `docker stop --time N ID`, followed by `docker rm ID`;
- a stale running container is retained and never stopped;
- networks and volumes in use, system networks, and objects that cannot be
  inspected are retained or blocked with a reason; volume use is proven by an
  authoritative container-mount query, never inferred from absent inspect data;
- missing objects are an idempotent successful end state;
- volumes are discovered by the positive managed label and removed by explicit
  IDs only.

Broad cleanup is forbidden. The kernel never emits `docker system prune`, any
unfiltered or negative prune, wildcards, shell command strings, or name-based
ownership guesses. Receipts record kind, ID, owner, lifecycle, action, reason,
bounded evidence, and follow-up without copying command output that may contain
secrets. Runtime cleanup receipts serialize with schema version, scope, nested
owner, kind and ID, lifecycle, disposition, exact command evidence, reason, and
follow-up. Evidence is recursively bounded and secret-shaped values are hashed
before durable persistence.
