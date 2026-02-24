---
name: development
description: Assembly governance application development with Go, Templ, and Datastar. Covers pages, components, handlers, database patterns, setup, and deployment across all project phases.
---

# Assembly Development Skill

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

Before writing handlers, define your data shapes in `backend/internal/dto/responses.go`:

```go
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
func rowFilter(p dto.ProposalResponse) string {
    status := strings.ToLower(p.Status)
    return "($statusFilter === 'all' || $statusFilter === '" + status + "')"
}
```

```templ
<tr data-show={ rowFilter(p) }>
```

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

3. **Commit and push:**
   ```bash
   git add -A
   git commit -m "feat: Add {feature} page"
   git push
   ```

---

## File Organization

### Handler Files

Split by domain in `backend/internal/handlers/`:

| File | Domain |
|------|--------|
| `handlers.go` | Core infrastructure |
| `members.go` | Member CRUD, invites |
| `governance.go` | Proposals, meetings, resolutions, decisions |
| `health.go` | Financial dashboard |
| `account.go` | User account, profile |
| `documents.go` | Static documents |

### Page Templates

Organize by domain in `backend/internal/pages/`:

```
pages/
├── members/
│   ├── index.templ
│   ├── show.templ
│   └── new.templ
├── governance/
│   ├── proposals/
│   ├── meetings/
│   ├── resolutions/
│   └── decisions/
├── health/
└── documents/
```

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

## Cross-References

- **council plugin** (`decolonial-language` skill): For values-aligned terminology when naming components, writing UI labels, seeding mock data, and writing microcopy. Provides the three-layer architecture (legal → bridge → cultural) for mapping BC Act terms to solidarity economy language. Default to cultural layer in member-facing templates; use legal layer only in generated compliance documents.
- **Distribution docs** (in Assembly repo): `docs/DISTRIBUTION.md` (deployment model), `docs/PILOT-SCOPE.md` (pilot checklist), `docs/UPDATE-FLOW.md` (update sequence)
