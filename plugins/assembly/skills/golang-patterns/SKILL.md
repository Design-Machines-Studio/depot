---
name: golang-patterns
description: Assembly-specific Go library patterns and conventions -- SQLite driver, migrations, session management, CSRF protection, rate limiting, CLI tooling, and testing. Use when choosing dependencies, configuring SQLite connection pools, setting up goose migrations, implementing SCS sessions, adding nosurf CSRF protection, building cobra CLI commands, or configuring httprate rate limiting for Assembly.
---

# Go Library Patterns

Assembly's dependency choices and configuration patterns. Each library was selected for a specific reason -- understand the rationale before reaching for alternatives.

---

## 1. SQLite: mattn/go-sqlite3

CGO-based SQLite driver. Chosen over `modernc.org/sqlite` for better performance and wider community testing.

DSN with production pragmas:

```go
dsn := "file:data/assembly.db?" +
    "_journal_mode=WAL&" +
    "_foreign_keys=on&" +
    "_busy_timeout=5000&" +
    "_synchronous=FULL&"     // Legal data durability
    "_cache_size=-32000&" +  // 32MB
    "_mmap_size=268435456&" + // 256MB
    "_temp_store=MEMORY"
```

Connection pools:

```go
readDB.SetMaxOpenConns(4)   // Concurrent readers (WAL allows this)
writeDB.SetMaxOpenConns(1)  // Single writer (SQLite limitation)
```

Transaction helper:

```go
func (db *DB) WithTx(ctx context.Context, fn func(*sql.Tx) error) error
```

All multi-step mutations use `WithTx`. Number generation (resolution numbers, sequence IDs) happens INSIDE the transaction.

---

## 2. Migrations: pressly/goose

Timestamp-prefixed SQL files with Up/Down sections.

```sql
-- +goose Up
CREATE TABLE gov_proposals (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- +goose Down
DROP TABLE gov_proposals;
```

Embed and run at startup:

```go
//go:embed migrations/*.sql
var migrations embed.FS

func RunMigrations(db *sql.DB) error {
    goose.SetBaseFS(migrations)
    return goose.Up(db, "migrations")
}
```

Pre-migration safety: auto `cp assembly.db backups/pre-migrate-{timestamp}.db` before running.

---

## 3. Embedded NATS: delaneyj/toolbelt/embeddednats

Wrapper around `nats-server`. See the **nats-jetstream** skill for full patterns. Key dependency versions:

- `github.com/delaneyj/toolbelt` v0.9.x
- `github.com/nats-io/nats-server/v2` v2.12.x
- `github.com/nats-io/nats.go` v1.49.x

---

## 4. Sessions: alexedwards/scs

Session middleware with SQLite backend.

```go
sessionManager := scs.New()
sessionManager.Store = sqlite3store.New(db)
sessionManager.Lifetime = 24 * time.Hour
sessionManager.IdleTimeout = 4 * time.Hour
sessionManager.Cookie.SameSite = http.SameSiteLaxMode
sessionManager.Cookie.Secure = true  // production only
sessionManager.Cookie.HttpOnly = true
```

Key rules:

- **SSE:** validate session at connect, store member ID, don't renew during active SSE
- **Per-user limits:** max 5 concurrent SSE connections
- **Password change:** invalidate all sessions for that member
- **Account lockout:** after 10 failed login attempts

---

## 5. CSRF: justinas/nosurf

Double-submit cookie pattern.

```go
r.Use(nosurf.NewPure)
```

Template delivery via meta tag:

```html
<meta name="csrf-token" content="{{ .CSRFToken }}">
```

Datastar reads the token:

```html
<form data-header.X-CSRF-Token="document.querySelector('meta[name=csrf-token]').content">
```

Exempt routes (configure in middleware):

- SSE GET endpoints
- `/healthz`
- `/.well-known/assembly`
- Static assets

---

## 6. CLI: spf13/cobra

```go
var rootCmd = &cobra.Command{
    Use:   "assembly",
    Short: "Assembly cooperative governance platform",
}

var serveCmd = &cobra.Command{
    Use:   "serve",
    Short: "Start the HTTP server",
    RunE:  runServe,
}

func init() {
    rootCmd.AddCommand(serveCmd)
    rootCmd.AddCommand(migrateCmd)
    rootCmd.AddCommand(seedCmd)
    rootCmd.AddCommand(adminCmd)
    rootCmd.AddCommand(versionCmd)
    rootCmd.AddCommand(backupCmd)
}
```

Commands:

- `assembly serve` -- Start HTTP server (default)
- `assembly admin create` -- Headless install (--name, --email, --password-file)
- `assembly admin reset-password` -- CLI password reset (--email)
- `assembly migrate` -- Run pending goose migrations
- `assembly seed --demo` -- Load Catalyst Cooperative demo data (dev only)
- `assembly version` -- Show version and install ID
- `assembly backup` -- Manual SQLite backup

Password security: ONLY via `--password-file` or `--password-stdin`. Never via env vars or CLI flags (prevents exposure in logs, `docker inspect`, `/proc`).

---

## 7. Rate Limiting: go-chi/httprate

```go
// Global
r.Use(httprate.LimitByIP(100, time.Minute))

// Login endpoint
r.With(httprate.LimitByIP(5, time.Minute)).Post("/login", handleLogin)

// SSE connections
r.With(httprate.LimitByIP(10, time.Minute)).Get("/sse/*", handleSSE)
```

| Endpoint | Limit | Window |
|----------|-------|--------|
| Login | 5 | 1 minute |
| API (global) | 100 | 1 minute |
| SSE connections | 10 | 1 minute |

---

## 8. Post-Commit Event Publishing

Events must publish AFTER `tx.Commit()`, never inside the transaction. If the transaction rolls back, a pre-commit event is a lie that corrupts downstream state (KV cache, SSE clients, audit trail).

```go
// CORRECT — publish after commit
err := db.WithTx(ctx, func(tx *sql.Tx) error {
    // ... mutations and audit write ...
    return nil
})
if err != nil {
    return err
}
deps.Events.Publish("assembly.gov.proposal.status_changed", envelope)

// WRONG — publish inside transaction
err := db.WithTx(ctx, func(tx *sql.Tx) error {
    // ... mutations ...
    deps.Events.Publish(...)  // fires even if tx rolls back
    return nil
})
```

---

## 9. Route Middleware Is Not Object Authorization

Route middleware (`RequireAuth`, `RequirePermission`, `RequireAdmin`) handles RBAC -- "can this role access this route?" Object-level authorization (`deps.Auth.Authorize()`) handles ownership and status -- "can this member edit this specific proposal?"

Both are required for mutations. Route middleware alone is insufficient because it cannot check resource ownership, status gates, or group membership. Every mutation handler must call `Authorize()` even if the route already has permission middleware.

```go
// Route: RequirePermission("governance.edit") gates the route
// Handler: Authorize() gates the specific resource
func (h *Handlers) UpdateProposal(w http.ResponseWriter, r *http.Request) {
    // Route middleware already checked role permission
    // Still need object-level auth:
    if err := h.deps.Auth.Authorize(ctx, "proposal.edit", resource); err != nil {
        http.Error(w, "Forbidden", http.StatusForbidden)
        return
    }
    // ... proceed with mutation
}
```

---

## 10. Testing Patterns

SQLite in tests:

```go
func NewTestDB(t *testing.T) *sql.DB {
    t.Helper()
    dbPath := filepath.Join(t.TempDir(), "test.db")
    db, err := sql.Open("sqlite3", dbPath+"?_journal_mode=WAL&_foreign_keys=on")
    if err != nil {
        t.Fatal(err)
    }
    t.Cleanup(func() { db.Close() })
    return db
}
```

Use `t.TempDir()` not `:memory:` -- WAL mode requires real files.

Interface injection for testability:

```go
type Querier interface {
    QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
    ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
}
```

Services accept `Querier` interface, allowing both real DB and test stubs.

Table-driven tests for handlers:

```go
tests := []struct {
    name       string
    method     string
    path       string
    wantStatus int
}{
    {"list proposals", "GET", "/governance/proposals", 200},
    {"not found", "GET", "/governance/proposals/nonexistent", 404},
}
```

### Service-Layer Mutation Tests

Test mutation flows end-to-end through the service layer. Mock the `Dependencies` struct interfaces and verify the full invariant sequence:

```go
func TestCreateProposal(t *testing.T) {
    db := NewTestDB(t)
    auth := &MockAuthorizer{}
    audit := &MockAuditWriter{}
    events := &MockEventBus{}

    svc := governance.NewService(governance.Deps{
        DB: db, Auth: auth, Audit: audit, Events: events,
    })

    err := svc.CreateProposal(ctx, input)
    require.NoError(t, err)

    // Verify invariant sequence
    assert.True(t, auth.AuthorizeCalled, "Authorize must be called")
    assert.Equal(t, "proposal.create", auth.LastAction)
    assert.True(t, audit.WriteCalled, "Audit entry must be written")
    assert.True(t, events.PublishCalled, "Event must be published")
    // Verify state change
    got, _ := svc.GetProposal(ctx, input.ID)
    assert.Equal(t, "draft", got.Status)
}
```

Focus: verify authorize was called with correct action, audit was written, event was published after commit, and DB state changed.

---

## 11. Security Headers

```go
w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
w.Header().Set("X-Content-Type-Options", "nosniff")
w.Header().Set("X-Frame-Options", "DENY")
w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'")
```

---

## 12. HTTP Server Timeouts

```go
srv := &http.Server{
    ReadTimeout:  15 * time.Second,
    WriteTimeout: 30 * time.Second,
    IdleTimeout:  120 * time.Second,
}
```

SSE handlers use `http.ResponseController` to extend WriteTimeout per-connection.

---

## Companion Skills

| Skill | Plugin | When to Load |
|-------|--------|--------------|
| **development** | assembly | Full Assembly development workflow |
| **nats-jetstream** | assembly | Embedded NATS patterns |
| **governance** | council | Domain requirements driving technical decisions |
