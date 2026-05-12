---
name: development
description: Assembly governance application development with Go, Templ, and Datastar. Use when building pages, adding handlers, creating Templ templates, writing database queries, scaffolding CRUD flows, configuring Docker, deploying to production, or working on any Assembly feature. Also use when asking about page types, DTO patterns, component library, Datastar integration, migration files, or module architecture. Covers pages, components, handlers, database patterns, setup, and deployment across all project phases.
---

# Assembly Development Skill

## Docker Status
!`docker compose ps --format "table {{.Name}}\t{{.Status}}" 2>/dev/null || echo "Docker not running"`

Build cooperative governance applications with Go, Templ, and Datastar. Build pages fast, review often, commit frequently.

## Philosophy

**Prototype toward production.** Every page you build is real code. Use mockup data in SQLite, but structure your handlers and DTOs for real queries. The prototype becomes the product.

**Optional companion plugins:**
- **council** — Governance domain knowledge and decolonial language for UI labels
- **design-machines** — Business strategy and product positioning context

This skill focuses on the **Assembly workflow** for building pages and features.

---

## CRITICAL: Docker-Only Go Commands

**NEVER run Go commands on the host.** All Go/Templ commands run in Docker:

```bash
# CORRECT
docker compose exec app templ generate
docker compose exec app go build ./cmd/api
docker compose exec app go test ./...

# WRONG - Never do this
templ generate
go build ./cmd/api
```

---

## CRITICAL: Never Modify the Live Wires Repository

**Assembly customizes its appearance through project-level CSS overrides, NOT by editing the Live Wires framework.**

Live Wires (`livewires/`) is a shared CSS framework. Assembly consumes it as a dependency. When you need to adjust a Live Wires component's appearance for Assembly:

1. **Override in Assembly's CSS:** Add or modify files in Assembly's `src/css/6_components/` directory
2. **Use cascade layers:** Assembly's component layer sits above Live Wires, so overrides take precedence naturally
3. **Never edit files in the `livewires/` repo** -- not `livewires/src/css/`, not component files, not token files
4. **Example:** To adjust `.card--stat` for Assembly, create or edit `src/css/6_components/_card-overrides.css`, not `livewires/src/css/6_components/_card.css`

This follows the Live Wires philosophy: "Start with Live Wires, make it your own." Each project customizes in its own CSS layer.

---

## The Prototyping Workflow

### 1. Create the Page Type

Think in **page types**, not individual pages. One template serves many instances.

```
/members/               → index.templ (list)
/members/{id}           → show.templ (detail)
/members/new            → new.templ (create form)
/governance/proposals/  → index.templ, show.templ, new.templ
```

### 2. Define DTOs First

Define data shapes in the fixture's `model/` directory (e.g., `internal/fixtures/governance/model/proposal.go`):

```go
package model

type ProposalResponse struct {
    ID          string  `json:"id"`
    Title       string  `json:"title"`
    Status      string  `json:"status"`
    ProposedBy  *string `json:"proposed_by,omitempty"`
    // Use pointers for optional fields
}
```

### 3. Build the Handler

Handlers fetch data and render templates. Keep them thin:

```go
func (h *Handlers) PageProposals(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "text/html; charset=utf-8")

    proposals, err := h.fetchProposals()
    if err != nil {
        log.Printf("Error fetching proposals: %v", err)
        proposals = []dto.ProposalResponse{}
    }

    proposalsPage.Index(proposals).Render(r.Context(), w)
}
```

### 4. Create the Templ Template

Templates live in `backend/internal/pages/{domain}/`:

```templ
templ Index(proposals []dto.ProposalResponse) {
    @layouts.Sidebar(layouts.PageMeta{
        Title:     "Proposals",
        BodyClass: "pg-proposals",
    }) {
        @partials.NavGovernance()
        <article class="content">
            // Page content using dto data
        </article>
    }
}
```

### 5. Add the Route

In `backend/cmd/api/main.go`:

```go
r.Get("/governance/proposals", h.PageProposals)
r.Get("/governance/proposals/{id}", h.PageProposalDetail)
```

### 6. Generate, Build, Test

```bash
docker compose exec app templ generate
docker compose exec app go build ./cmd/api
docker compose restart app
curl http://assembly.coop.site/governance/proposals
```

---

## Component-First Development

### Use Existing Components

Check `backend/internal/components/` before creating anything new:

| Component | Usage |
|-----------|-------|
| `components.Avatar(name, size, imageURL)` | Member avatars (circle only, name rendered by caller) |
| `components.Badge(text, variant)` | Status badges |
| `components.StatusBadge(status)` | Governance status |
| `components.ButtonLink(href, text, variant)` | Action buttons |
| `components.FormField(...)` | Form inputs |
| `components.StatCard(...)` | Dashboard metrics |

### Extend, Don't Duplicate

If a component needs new functionality:
1. Add parameters to the existing component
2. Update all existing usages if needed
3. Document the change

```templ
// Before: Badge only took text
templ Badge(text string)

// After: Badge takes optional variant
templ Badge(text string, variant string)
```

### Create New Components Only When Needed

Ask: "Will this be used in 3+ places?" If yes, create a component. Otherwise, inline it.

---

## Database Patterns

### Mockup Data in Migrations

Seed realistic data in `backend/migrations/`:

```sql
-- 010_seed_proposals.sql
INSERT INTO proposals (id, title, status, proposed_by) VALUES
('prop-001', 'Professional Development Fund', 'voting', 'member-001'),
('prop-002', 'Office Lease Renewal', 'discussion', 'member-002');
```

### Query Patterns

**List queries** - return slices:

```go
func (h *Handlers) fetchProposals() ([]dto.ProposalResponse, error) {
    rows, err := h.db.Query(`SELECT id, title, status FROM proposals`)
    // ...
}
```

**Detail queries** - return single item:

```go
func (h *Handlers) getProposal(id string) (*dto.ProposalResponse, error) {
    row := h.db.QueryRow(`SELECT id, title, status FROM proposals WHERE id = ?`, id)
    // ...
}
```

### Static SQL Preference

Prefer static SQL with optional predicates over dynamic `fmt.Sprintf` query building. Dynamic SQL triggers gosec G202 and risks injection.

```go
// CORRECT — static SQL with conditional append
query := `SELECT id, title, status FROM $TABLE WHERE 1=1`
args := []any{}
if status != "" {
    query += ` AND status = ?`
    args = append(args, status)
}
if memberID != "" {
    query += ` AND proposed_by = ?`
    args = append(args, memberID)
}
rows, err := db.QueryContext(ctx, query, args...)

// WRONG — dynamic SQL via fmt.Sprintf (gosec G202)
query := fmt.Sprintf(`SELECT * FROM %s WHERE status = '%s'`, table, status)
```

### Avoid N+1 Queries

Batch fetch related data:

```go
// 1. Fetch all meetings
meetings, ids := fetchMeetings()

// 2. Batch fetch related resolutions
resolutions := fetchResolutionsByMeetingIDs(ids)

// 3. Group in memory
resByMeeting := groupBy(resolutions, "meeting_id")
```

---

## Datastar Integration

### Page-Level Signals

Define signals at the article level for filtering:

```templ
<article class="content" data-signals="{ statusFilter: 'all', yearFilter: '2026' }">
```

### Filter Buttons

Use data-class for active states:

```templ
<button type="button" class="button button--small"
    data-class:button--accent="$statusFilter === 'all'"
    data-on:click="$statusFilter = 'all'">All</button>
```

### Row Visibility

Generate filter expressions for each row:

```go
// SAFETY: p.Status is a controlled enum from the database (draft, active, closed),
// not user-supplied text. Do NOT interpolate arbitrary user input into expressions.
func rowFilter(p dto.ProposalResponse) string {
    status := strings.ToLower(p.Status)
    return "($statusFilter === 'all' || $statusFilter === '" + status + "')"
}
```

```templ
<tr data-show={ rowFilter(p) }>
```

### Boolean vs String Signals

Use explicit string comparisons (`$filter === 'all'`) when CSS classes or visibility depend on exact values. Boolean signals (`$showDrafts`) work for simple show/hide but break when `data-class` needs to match one of several states. When in doubt, use string signals with `===` matching.

```templ
// CORRECT — string signal with exact matching
data-signals="{ view: 'grid' }"
data-class:active="$view === 'grid'"

// RISKY — boolean loses which state is active
data-signals="{ isGrid: true }"
data-class:active="$isGrid"  // Can't distinguish grid vs list vs table
```

---

## Application Context (appctx)

The `appctx` package (`backend/internal/appctx/modules.go`) provides request-scoped values shared across packages. It breaks import cycles between handlers (which set values) and templates (which read them).

### NavUser Struct

```go
type NavUser struct {
    MemberID          string
    Initials          string
    Name              string
    Status            string // "active", "probationary", "departed"
    IsBoard           bool
    IsOfficer         bool
    IsAdmin           bool
    ProfileIncomplete bool   // true when phone == "" || bio == ""
}
```

### Key Functions

| Function | Purpose |
|----------|---------|
| `SetNavUser(ctx, user)` / `GetNavUser(ctx)` | Store/retrieve member identity. GetNavUser returns safe fallback (`Initials: "?"`) if not set. |
| `SetEnabledModules(ctx, map)` / `IsModuleEnabled(ctx, slug)` | Module gating. `IsModuleEnabled` is fail-closed (returns false if no context). |
| `SetNavPath(ctx, path)` / `GetNavPath(ctx)` | Active nav state for sidebar highlighting. |
| `SetNavPrefs(ctx, closedGroups)` / `GetNavPrefs(ctx)` | Collapsed nav groups from `nav_closed` cookie. |

### Middleware Chain

`AppContextMiddleware` in `backend/internal/handlers/middleware.go` runs on every request:

1. Loads enabled modules from database (`db.EnabledModuleSlugs()`)
2. Parses `nav_closed` cookie for collapsed nav groups
3. Reads `coop_member` cookie for current member ID (via `resolveNavMemberID`)
4. Queries database for member details (`preferred_name`, `phone`, `bio`, `status`, `is_super_admin`)
5. Queries `member_roles` for board and officer status
6. Sets all values in context: `SetEnabledModules`, `SetNavPath`, `SetNavPrefs`, `SetNavUser`

### Template Usage

```templ
// Read the current user in any template
user := appctx.GetNavUser(ctx)
if user.IsAdmin {
    // render admin controls
}

// Check module availability before rendering nav items
if appctx.IsModuleEnabled(ctx, "governance") {
    // render governance nav section
}
```

### Member Switching (?member= parameter)

During development, switch the active member identity to test different personas and permission levels without modifying code or database.

**How it works:** `getCurrentMemberID()` in `backend/internal/handlers/handlers.go` checks three sources in order:

1. **`?member=` query parameter** (development only, gated by `ENV=development`). Validates the member exists in the database, then sets the `coop_member` cookie for 7 days.
2. **`coop_member` cookie** (persists across requests, HttpOnly, SameSite=Lax).
3. **Default:** `mem_009` (Ned Ludd) if neither source has a value.

**Prototype only:** This entire fallback chain is a prototype convenience. In production, `RequireAuth` middleware fires before any handler, so `getCurrentMemberID()` is never reached without a valid session. The `?member=` parameter and `mem_009` default are unreachable in production builds (gated by `ENV=development`).

**Usage:** Append `?member=mem_001` to any URL. The cookie persists, so subsequent requests use that identity automatically.

**Persona mapping for testing:**

| Persona | Member ID | Role |
|---------|-----------|------|
| David (casual member) | Use `mem_XXX` from seed data | Active member, no board role |
| Aisha (reluctant board member) | Use board member seed ID | Board role, mobile-first |
| Alex (new probationary) | Use probationary seed ID | Status: "probationary" |

**Security note:** This is UI-level identity only, NOT a security boundary. The `coop_member` cookie is unauthenticated and forgeable. Real authentication is required before production. The `?member=` param is environment-gated to `ENV=development` only.

### Auth Bypass for Test Users (fixture-discovery beacon)

Beacon for the pipeline's Fixture Discovery step (see `plugins/pipeline/skills/assess/SKILL.md`). Canonical persona list:

| Member ID | Persona | Use for |
|-----------|---------|---------|
| `mem_001` | Director | privileged actions, approvals |
| `mem_005` | Aisha -- member without position | empty-state views, unprivileged flows |
| `mem_009` | Ned Ludd (default) | baseline sanity |
| `mem_012` | David -- authored content | authored-content views |

Consult `internal/fixtures/<module>/seed.go` for the full seeded member list.

---

## Quality Workflow

### After Every Major Chunk

1. **Generate and build:**
   ```bash
   docker compose exec app templ generate
   docker compose exec app go build ./cmd/api
   ```

2. **Test in browser:**
   ```bash
   curl http://assembly.coop.site/{your-route}
   open http://assembly.coop.site/{your-route}
   ```

3. **Simplify:**
   Run `/simplify` on the files you just changed. This catches complexity creep, dead code, redundant abstractions, and over-engineering before they compound. If `/simplify` makes changes, rebuild and retest.

4. **Commit and push:**
   ```bash
   git add -A
   git commit -m "feat: Add {feature} page"
   git push
   ```

---

## File Organization

### Fixture-Owned Directories

Each fixture owns its code in `internal/fixtures/{name}/`:

```
internal/fixtures/governance/
├── routes.go           # Chi route registration
├── handlers.go         # Thin HTTP adapters (parse → call service → render)
├── services/           # Business logic
│   ├── proposals.go
│   └── meetings.go
├── model/              # DTOs and domain types (fixture-owned)
│   ├── proposal.go
│   └── meeting.go
└── pages/              # Templ page templates (fixture-owned)
    ├── proposals/
    │   ├── index.templ
    │   └── show.templ
    └── meetings/
        └── index.templ
```

Baseplate code (members, admin, auth, groups) lives in `internal/baseplate/`.

### Shared Components

Shared components in `internal/components/` accept **primitive props only** (strings, ints, bools). They never import fixture-specific DTOs or model packages. If a component needs fixture data, the caller maps it to primitives before passing.

```go
// CORRECT — primitive props
components.Avatar(member.Name, "md", member.ImageURL)

// WRONG — importing fixture model
components.ProposalCard(governance.Proposal{...})
```

---

## Mutation Invariant Checklist

Every state-changing operation (create, update, delete, status transition) must follow this sequence. Skipping a step is a review finding.

1. **Authorize** -- call `deps.Auth.Authorize(ctx, "entity.action", resource)` before any write. Route middleware (RBAC) is not sufficient; object-level auth is required for every mutation.
2. **Validate** -- validate all input fields (length, format, enum membership) in the service layer. Never trust handler-level parsing alone.
3. **Transaction** -- wrap multi-step mutations in `db.WithTx()`. Number generation (sequence IDs, resolution numbers) happens inside the transaction.
4. **Preserve invariants** -- enforce domain rules within the transaction (e.g., quorum thresholds, status transition validity, uniqueness constraints).
5. **Audit** -- write an audit log entry via `deps.Audit` inside the transaction. Include actor, action, entity, and changed fields.
6. **Publish event after commit** -- call `deps.Events.Publish()` only AFTER `tx.Commit()` returns nil. Never publish inside the transaction scope.
7. **Tests** -- service-layer tests verify the full sequence: mock deps, assert authorize was called, assert audit was written, assert event was published, assert state change in DB.

---

## Supporting Files

For detailed reference:
- [pages.md](pages.md) - Page structure and layout patterns
- [components.md](components.md) - Available components and usage
- [workflows.md](workflows.md) - Governance workflows and state machines
- [data.md](data.md) - Database schema and query patterns
- [setup.md](setup.md) - Development environment setup
- [deploy.md](deploy.md) - Production deployment pipeline

---

## Anti-Patterns to Avoid

### Don't Create Static HTML

Every page should be a Templ template with database data:

```html
<!-- WRONG: Static HTML in public/ -->
<h1>John Smith</h1>

<!-- RIGHT: Dynamic Templ template -->
<h1>{ member.FullName }</h1>
```

### Don't Hardcode in Templates

Data comes from handlers:

```templ
// WRONG
templ Show() {
    <h1>January Board Meeting</h1>
}

// RIGHT
templ Show(meeting dto.MeetingResponse) {
    <h1>{ meeting.Title }</h1>
}
```

### Don't Skip Code Review

Every major chunk gets reviewed. The review catches issues early.

### Don't Skip UX Testing

Every user-facing feature gets tested through the UX persona framework at `tests/ux/`. This isn't optional -- it catches issues that code review misses (jargon barriers, permission confusion, mobile dead ends).

### Don't Forget Null Handling

Use pointers for optional fields and check them:

```templ
if m.ChairName != nil {
    <dt>Chair</dt>
    <dd>{ *m.ChairName }</dd>
}
```

---

## Quick Commands

```bash
# Generate Templ files
docker compose exec app templ generate

# Build the Go binary
docker compose exec app go build ./cmd/api

# Restart to pick up changes
docker compose restart app

# Check a page works
curl http://assembly.coop.site/governance/proposals

# Run tests
docker compose exec app go test ./...

# View the app
open http://assembly.coop.site
```

---

## Modular Architecture: Baseplate + Fixtures

Assembly uses a **Baseplate + Fixtures** architecture.

### Terminology

- **Baseplate** = core features on every install (members, admin, auth, groups, permissions)
- **Fixtures** = optional modules per install (governance, documents, discussions, health, equity, calendar)
- **Mothership** = private Design Machines dashboard tracking all installs

### Key Decisions

- **Caddy-style compile-time registration**: Fixtures implement a `Module` interface, register via `init()`, included via blank imports
- **Single SQLite file**: Module-prefixed tables (`gov_`, `doc_`, `disc_`), not separate databases
- **Governance is one fixture** with sub-feature flags (proposals, meetings, resolutions), not separate fixtures
- **Members is fully baseplate**: Both data and directory UI always present
- **Event bus + service locator** for inter-module communication; always handle absent modules gracefully

### Prototype Phase Rules (Follow Now)

**Do:**

1. Prefix new tables with module slugs (`gov_`, `doc_`, `disc_`)
2. Keep handler files per-domain (already close to fixture boundaries)
3. Avoid circular imports between handler domains
4. Use `entity_references` for cross-module relationships
5. Check `modules.enabled` before rendering nav items

**Don't:**

1. Add FK constraints between fixture tables
2. Add fixture-specific fields to `config.Config` struct
3. Put fixture-specific types in shared `models/` package
4. Hardcode module names in navigation

### Distribution Phases

Assembly follows a three-phase distribution model. See `docs/DISTRIBUTION.md` for the full specification and `docs/PILOT-SCOPE.md` for what ships first.

1. **Phase 0 (Pilot)**: Single binary + runtime config toggles. Manual Docker deploy. No update mechanism.
2. **Phase 1 (Self-Updating)**: Registry + update client. One-click updates in Admin UI. Lightweight Mothership.
3. **Phase 2 (Platform)**: Builder service + fixture marketplace. Per-client binaries. License management.

---

## Production Architecture (DM-021)

The production backend lives in a separate repo (`assembly-baseplate`, DM-021) and is built from first principles. The prototype (`assembly`, DM-006) is the design workspace — patterns are validated there, then implemented properly in production. Neither blocks the other. See ADR-002.

### Two-Repo Model

| Repo | Project | Purpose |
|------|---------|---------|
| `assembly/` | DM-006 | Prototype, UI/UX design, persona testing, mockup data |
| `assembly-baseplate/` | DM-021 | Production platform, auth, NATS, SQLite, install, CLI |

Design in the prototype → extract validated pattern → implement in production.

### Module Interface

Fixtures implement the `Module` interface for clean isolation (Caddy-style compile-time registration):

```go
type Module interface {
    ID() string                                              // "governance"
    Name() string                                            // "Governance"
    SetupRoutes(r chi.Router, deps *app.Dependencies) error  // Mount routes
    Migrations() embed.FS                                    // Embedded SQL migrations
}

// Optional: declare NATS event patterns
type EventDeclarer interface {
    Events() module.EventConfig
}
```

Fixtures register via `init()` and are included via blank imports in `cmd/api/imports.go`:

```go
import _ "github.com/Design-Machines-Studio/assembly-governance"
```

### Dependencies Struct

Each fixture receives a `Dependencies` struct via `SetupRoutes()`:

```go
type Dependencies struct {
    DB            *ScopedDB         // Restricted to fixture's tables
    Auth          *Authorizer       // Object-level authorization
    Members       MemberReader      // Read-only member lookups
    Events        ScopedEventBus    // Restricted NATS subjects
    Audit         AuditWriter       // Shared audit log access
    Config        ConfigReader      // Co-op settings
    Logger        *slog.Logger
}
```

### ScopedDB

Wraps `*sql.DB` with table-prefix enforcement. Fixtures never bypass ScopedDB — this is the core data isolation contract.

- Baseplate tables: no prefix (`members`, `groups`, `permissions`, `audit_log`)
- Fixture tables: prefixed (`gov_proposals`, `doc_documents`, `eq_shares`, `health_metrics`)

Fixtures use `$TABLE` and `$PREFIX_` placeholders in queries — ScopedDB substitutes the correct prefix at runtime. See ADR-003 (in the `assembly-baseplate` repo at `docs/adr/`).

### ScopedNATS / ScopedEventBus

Each fixture gets a scoped event bus restricting NATS publishing to its subject prefix:

```go
type ScopedEventBus struct {
    bus       EventBus
    prefix    string   // "assembly.gov."
    allowRead []string // Cross-boundary read subjects
}
```

`allowRead` permits subscribing to specific cross-boundary subjects (e.g., governance subscribing to `assembly.member.status_changed`). See the **nats-jetstream** skill for full patterns.

**Note:** ADRs (ADR-002 through ADR-007) live in the `assembly-baseplate` repo at `docs/adr/`, not in the depot.

### Service Layer Pattern

Handlers → Services → ScopedDB. Services contain business logic. Handlers are thin HTTP adapters (parse request, call service, render response).

**Size limits:** No handler file over 200 lines. No service file over 500 lines. Split into focused files if needed.

```go
// Handler (thin adapter)
func (h *Handlers) ListProposals(w http.ResponseWriter, r *http.Request) {
    proposals, err := h.service.ListProposals(r.Context())
    if err != nil {
        http.Error(w, "Internal error", http.StatusInternalServerError)
        return
    }
    pages.Index(proposals).Render(r.Context(), w)
}

// Service (business logic)
func (s *GovernanceService) ListProposals(ctx context.Context) ([]Proposal, error) {
    return s.db.Query("gov_proposals", "SELECT * FROM $TABLE ORDER BY created_at DESC")
}
```

### Authorization

Three-layer authorization (ADR-004):

**Layer 1 — Route middleware:**
- `RequireAuth` — session exists
- `RequirePermission("governance.view")` — role-based
- `RequireModule("governance")` — fixture enabled
- `RequireAdmin` — board/officer/super_admin

**Layer 2 — Object-level (core):**
```go
func (a *Authorizer) Authorize(ctx context.Context, action string, resource Resource) error
```

Default-deny switch on action strings (`proposal.edit`, `meeting.manage`, `vote.cast`). The `Resource` struct carries `ID`, `AuthorID`, `Status`, `GroupID` for ownership/visibility checks.

**Layer 3 — Template conditional rendering:** Delegates to `Authorize()` internally. UX concern, not a security boundary.

### Install Identity & Federation

Each install generates a UUID (`install_id`) and Ed25519 keypair at first boot (ADR-005). The keypair lives at `data/identity.key` (0600 permissions).

**Well-known endpoint:**
```json
GET /.well-known/assembly
{
  "install_id": "uuid",
  "name": "TACO",
  "protocol_version": 1,
  "public_key": "base64-ed25519-public-key",
  "federation": true
}
```

Federation uses OAuth-style account linking with signed tokens: 5-minute TTL, single-use nonce, audience validation, HTTPS required in production. See ADR-006 for the full linking flow.

### Cobra CLI

`spf13/cobra` provides the CLI:

| Command | Purpose |
|---------|---------|
| `assembly serve` | Start HTTP server (default) |
| `assembly admin create` | Headless install (--name, --email, --password-file) |
| `assembly admin reset-password` | CLI password reset (--email) |
| `assembly migrate` | Run pending goose migrations |
| `assembly seed --demo` | Load Catalyst Cooperative demo data (dev only) |
| `assembly version` | Show version and install ID |
| `assembly backup` | Manual SQLite backup |

Passwords only via `--password-file` or `--password-stdin` — never env vars or CLI flags. See ADR-005.

### Build & Test (Production)

Same Docker-only rule as the prototype:

```bash
docker compose exec app go test -race -cover ./...
docker compose exec app go build ./cmd/api
docker compose exec app templ generate
```

---

## UX Testing Framework

Assembly has a persona-based UX test framework at `tests/ux/`. Use it when building or reviewing user-facing features.

### Personas

Six personas mapped to real seed accounts, covering the full spectrum of co-op member engagement:

| Persona | Account | Role | Key Testing Focus |
|---------|---------|------|-------------------|
| Reluctant Board Member | `mem_005` | Board, low engagement | Mobile usability, anxiety, dead ends |
| Power Secretary | `mem_003` | Officer, daily user | Efficiency friction, workflow bottlenecks |
| Engaged Chair | `mem_001` | Chair + admin | Admin/governance boundary, dual-role confusion |
| Casual Member | `mem_007` | Regular member | "Just let me do the thing" friction, jargon barriers |
| New Probationary | `mem_010` | Probationary | Permission boundaries, onboarding gaps |
| Numbers Treasurer | `mem_002` | Officer, detail-focused | Compliance visibility, data accuracy |

Read the full persona files at `tests/ux/personas/` for backstories, behavioral patterns, patience thresholds, and abandonment triggers.

### Heuristics

Two heuristic checklists at `tests/ux/heuristics/`:

- **nielsen-10.md** -- Nielsen's 10 usability heuristics adapted for cooperative governance
- **governance-specific.md** -- 10 governance-specific heuristics (G1-G10): permission clarity, lifecycle comprehension, position vs vote distinction, quorum awareness, and more

### When Building New Features

1. **Check the coverage matrix** (`tests/ux/coverage-matrix.md`) to see which personas and tasks cover the area you're working on
2. **Write task files** for new flows -- add them to `tests/ux/tasks/{area}/` following the frontmatter format in the README
3. **Update the coverage matrix** when adding new tasks
4. **Run UX tests** through the dm-review ux-quality-reviewer agent, which loads personas and governance heuristics for Assembly projects

### When to Write New Task Files

Write a task file when you add:
- A new page or route that members will use
- A new interactive flow (form, wizard, multi-step process)
- A new governance action (position, vote, motion, approval)
- Changes to navigation, permissions, or lifecycle stages

---

## Companion Skills

| Skill | Plugin | When to Load |
|-------|--------|--------------|
| **nats-jetstream** | assembly | Embedded NATS patterns, KV store, event bus, SSE streaming |
| **golang-patterns** | assembly | Go library choices (SQLite, sessions, CSRF, migrations, CLI) |
| **governance** | council | Co-op domain knowledge, voting thresholds, compliance requirements |
| **decolonial-language** | council | UI labels, member-facing copy, terminology mappings |
| **strategy** | design-machines | Product positioning, pricing, client pipeline context |
| **typography** | design-practice | Type scale, baseline rhythm, Live Wires alignment |

## Ecosystem Integration

Official and third-party Claude Code plugins that complement this skill:

| Plugin | Tool | When to Use |
|--------|------|-------------|
| **compound-engineering** | `go-build-verifier`, `css-reviewer`, `security-sentinel` agents | Go build verification, CSS compliance, security review |
| **context7** | `/context7` | Live documentation lookup for Go stdlib, Templ, Datastar |
| **playwright** | Browser tools | E2E visual testing beyond curl smoke tests |
| **superpowers** | `/debug`, `/verify` | Debug tricky Go issues, verify builds |
| **feature-dev** | `/feature-dev` | Structured feature development with architecture exploration |
| **userback** | Feedback tools (MCP) | Triage user feedback, read console/network logs, update status. HTTP endpoint: `https://mcp.userback.io/v1/mcp/` (OAuth) |

## Cross-References

- **council plugin** (`decolonial-language` skill): For values-aligned terminology when naming components, writing UI labels, seeding mock data, and writing microcopy. Provides the three-layer architecture (legal → bridge → cultural) for mapping BC Act terms to solidarity economy language. Default to cultural layer in member-facing templates; use legal layer only in generated compliance documents.
- **Distribution docs** (in Assembly repo): `docs/DISTRIBUTION.md` (deployment model), `docs/PILOT-SCOPE.md` (pilot checklist), `docs/UPDATE-FLOW.md` (update sequence)
