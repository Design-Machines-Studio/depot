---
name: nats-jetstream
description: Embedded NATS JetStream patterns for Assembly -- KV store, event bus, streams, consumers, and real-time SSE via KV Watch. Use when working with inter-module events, real-time data synchronization, KV-backed caching, SSE streaming from NATS, audit trails, presence tracking, or any messaging and eventing pattern in Assembly.
---

# NATS JetStream Patterns

Embedded NATS JetStream for Assembly's event bus, KV store, and real-time SSE pipeline.

---

## Embedded NATS Setup

All NATS communication is in-process. No external TCP port. Uses `github.com/delaneyj/toolbelt/embeddednats`.

```go
ns, err := embeddednats.New(ctx, embeddednats.WithNATSServerOptions(&natsserver.Options{
    JetStream:  true,
    NoSigs:     true,
    DontListen: true,  // IN-PROCESS ONLY — critical for security
    StoreDir:   "data/nats",
}))
```

Connect via `nats.InProcessConn()`. No TCP listener, no network exposure.

---

## DontListen Enforcement

**P1 violation if missing.**

NATS must always use `DontListen: true`. No external TCP connections under any circumstances. Add a runtime check at startup that fails hard if NATS is listening on the network.

- `data/nats/` directory permissions: `0700`
- No configuration override should disable `DontListen`
- Treat any network-exposed NATS as a security incident

---

## Subject Hierarchy

Pattern: `assembly.{scope}.{entity}.{event}`

| Scope | Owner | Example Subjects |
|---|---|---|
| `assembly.gov` | Governance fixture | `assembly.gov.proposal.created`, `assembly.gov.vote.cast` |
| `assembly.doc` | Documents fixture | `assembly.doc.document.created` |
| `assembly.eq` | Equity fixture | `assembly.eq.transaction.created` |
| `assembly.health` | Health fixture | `assembly.health.metric.updated` |
| `assembly.member` | Baseplate | `assembly.member.status_changed`, `assembly.member.role_assigned` |
| `assembly.system` | Baseplate | `assembly.system.module_toggled`, `assembly.system.settings_updated` |
| `assembly.audit` | Baseplate | `assembly.audit.action` |
| `federation` | Baseplate | `federation.link.requested` (Phase 2+) |

---

## Event Envelope

Standard envelope format (JSON):

```json
{
  "id": "evt_uuid",
  "type": "proposal.status_changed",
  "source": "assembly.gov",
  "timestamp": "2026-04-15T10:30:00Z",
  "actor_id": "mem_009",
  "entity_id": "dec_001",
  "entity_type": "proposal",
  "data": {
    "old_status": "draft",
    "new_status": "open_for_input"
  }
}
```

Minimal data in events: entity IDs and changed fields only, not full records. Consumers query SQLite for details if needed.

---

## KV Store Patterns

### Buckets

| Bucket | Purpose | TTL | Max Size |
|---|---|---|---|
| `presence` | Who is viewing what | 30s | 1MB |
| `ui-state` | Derived view state for SSE | None (persistent) | 16MB |
| `sessions` | SCS session data (optional) | 24h | 16MB |

### Key Naming

```
presence.proposal.{id}
presence.meeting.{id}
ui-state.proposal.{id}
ui-state.meeting.{id}
ui-state.dashboard.{member_id}
```

### Bucket Creation

```go
kv, err := js.CreateOrUpdateKeyValue(ctx, jetstream.KeyValueConfig{
    Bucket:      "ui-state",
    Description: "Derived view state for SSE",
    Compression: true,
    MaxBytes:    16 * 1024 * 1024,
})
```

### Get/Put with ErrKeyNotFound

```go
if entry, err := kv.Get(ctx, key); err != nil {
    if err != jetstream.ErrKeyNotFound {
        return fmt.Errorf("kv get: %w", err)
    }
    // Key doesn't exist — initialize default
} else {
    if err := json.Unmarshal(entry.Value(), &state); err != nil {
        return fmt.Errorf("unmarshal: %w", err)
    }
}
```

---

## KV Watch to SSE

The core real-time pattern. KV Watch drives Datastar SSE updates to connected browsers.

```go
func (h *Handlers) ProposalSSE(w http.ResponseWriter, r *http.Request) {
    // 1. Validate session
    memberID := session.GetMemberID(r.Context())
    if memberID == "" {
        http.Error(w, "Unauthorized", http.StatusUnauthorized)
        return
    }

    // 2. Create SSE writer
    sse := datastar.NewSSE(w, r)

    // 3. Watch KV key for updates
    proposalID := chi.URLParam(r, "id")
    watcher, err := h.kv.Watch(r.Context(), "ui-state.proposal." + proposalID)
    if err != nil {
        http.Error(w, err.Error(), http.StatusInternalServerError)
        return
    }
    defer watcher.Stop()

    // 4. Stream updates
    for {
        select {
        case <-r.Context().Done():
            return
        case entry := <-watcher.Updates():
            if entry == nil {
                continue
            }
            var state ProposalViewState
            if err := json.Unmarshal(entry.Value(), &state); err != nil {
                sse.ConsoleError(err)
                return
            }
            sse.PatchElementTempl(views.ProposalDetail(state))
        }
    }
}
```

- Session validation at connect time (check auth, extract member ID)
- `defer watcher.Stop()` for cleanup on disconnect
- Context cancellation handles client disconnect
- WriteTimeout: use `http.ResponseController` to extend per-connection for long-lived SSE
- Per-user SSE connection limits: max 5 concurrent

---

## Streams

| Stream | Subjects | Retention | Max Age | Purpose |
|---|---|---|---|---|
| `GOVERNANCE` | `assembly.gov.>` | Limits (by count) | 30 days | Event replay, audit |
| `AUDIT` | `assembly.audit.>` | Limits (by count) | 90 days | Full audit trail |
| `SYSTEM` | `assembly.system.>` | Limits (by count) | 7 days | System events |

---

## Consumers

Pull-based, durable, filtered:

```go
consumer, _ := js.CreateOrUpdateConsumer(ctx, "SYSTEM", jetstream.ConsumerConfig{
    Durable:       "gov-member-watcher",
    FilterSubject: "assembly.member.status_changed",
    AckPolicy:     jetstream.AckExplicitPolicy,
})
```

Naming convention: `{fixture}-{purpose}` (e.g., `gov-member-watcher`, `audit-recorder`).

---

## ScopedEventBus

Each fixture gets a scoped bus that restricts publishing to its prefix. `allowRead` permits subscribing to specific cross-boundary subjects.

```go
type ScopedEventBus struct {
    bus       EventBus
    prefix    string   // "assembly.gov."
    allowRead []string // Cross-boundary read subjects
}
```

Fixture event declaration:

```go
func (m *GovernanceModule) Events() module.EventConfig {
    return module.EventConfig{
        Publishes:  []string{"assembly.gov.>"},
        Subscribes: []string{"assembly.member.status_changed"},
    }
}
```

The baseplate uses `Events()` to configure ScopedEventBus allowlists.

**Post-commit publishing rule:** `ScopedEventBus.Publish()` must only be called AFTER `tx.Commit()` returns nil. The bus has no transaction awareness -- it fires immediately. Publishing inside a transaction scope means downstream consumers (KV cache, SSE, audit) see state that may roll back.

```go
// CORRECT
err := db.WithTx(ctx, func(tx *sql.Tx) error {
    // ... mutations ...
    return nil
})
if err != nil { return err }
deps.Events.Publish("assembly.gov.proposal.created", envelope)

// WRONG — publishes even if tx rolls back
err := db.WithTx(ctx, func(tx *sql.Tx) error {
    deps.Events.Publish(...)  // too early
    return nil
})
```

---

## Event Subject Coverage

Common event actions and their subject format. Use this as a reference when adding events to a fixture.

| Action | Subject Pattern | Example |
|--------|----------------|---------|
| Created | `assembly.{scope}.{entity}.created` | `assembly.gov.proposal.created` |
| Updated | `assembly.{scope}.{entity}.updated` | `assembly.gov.meeting.updated` |
| Status changed | `assembly.{scope}.{entity}.status_changed` | `assembly.gov.proposal.status_changed` |
| Deleted/archived | `assembly.{scope}.{entity}.archived` | `assembly.doc.document.archived` |
| Vote cast | `assembly.{scope}.vote.cast` | `assembly.gov.vote.cast` |
| Role assigned | `assembly.member.role_assigned` | (baseplate-owned) |

Every mutation that changes persisted state should publish an event. If a handler writes to SQLite but publishes no event, downstream real-time consumers (SSE, KV cache) will be stale.

---

## Write-Through Pattern

The critical data flow:

```
Handler mutation
  -> Write to SQLite (in db.WithTx transaction)
  -> After commit succeeds, publish event to NATS subject
  -> NATS watchers auto-notify subscribers
  -> SSE handlers push Datastar fragments to connected browsers
```

**NEVER publish before commit.** If the transaction rolls back, the event would be a lie. Events fire AFTER `tx.Commit()` returns nil.

---

## Testing NATS

```go
func NewTestNATS(t *testing.T) *embeddednats.Server {
    t.Helper()
    ns, err := embeddednats.New(t.Context(), embeddednats.WithNATSServerOptions(&natsserver.Options{
        JetStream:  true,
        NoSigs:     true,
        DontListen: true,
        StoreDir:   t.TempDir(),
    }))
    if err != nil {
        t.Fatal(err)
    }
    return ns
}
```

- Embedded NATS per test for isolation
- `t.TempDir()` for store directory (auto-cleaned)
- Test KV operations by writing and reading back values
- Test event publishing by subscribing before triggering mutation

---

## KV Rebuild Strategy

KV data is ephemeral -- it can be rebuilt from SQLite (the source of truth).

- **Startup rebuild**: On server start, rebuild `ui-state` bucket from current SQLite state
- **Lazy rebuild**: On cache miss (`ErrKeyNotFound`), query SQLite and populate KV
- **Idempotent creation**: Use `CreateOrUpdateKeyValue` (not `CreateKeyValue`) so restarts don't fail

NATS data is NOT backed up. The backup strategy covers SQLite only (via Litestream). NATS rebuilds from SQLite on restart.

---

## Companion Skills

| Skill | Plugin | When to Load |
|-------|--------|--------------|
| **development** | assembly | Full Assembly development patterns, handlers, DTOs |
| **golang-patterns** | assembly | Go library choices (SCS sessions, goose migrations, etc.) |
| **governance** | council | BC Act requirements that drive event patterns |
