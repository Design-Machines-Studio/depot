# Pages Reference

Page templates for Assembly. Each page type has a consistent structure.

## Page Types

| Type | Template | Purpose |
|------|----------|---------|
| List | `index.templ` | Display collection with filters |
| Detail | `show.templ` | Display single item with actions |
| Form | `new.templ` | Create new item |
| Edit | `edit.templ` | Modify existing item |

## Layout Structure

All pages use the sidebar layout:

```templ
templ Index(data []dto.ItemResponse) {
    @layouts.Sidebar(layouts.PageMeta{
        Title:       "Page Title",
        Description: "Page description for SEO",
        BodyClass:   "pg-domain",  // e.g., pg-members, pg-proposals
    }) {
        @partials.NavDomain()  // Domain-specific navigation
        <article class="content">
            <header class="section prose">
                <h1>Page Title</h1>
                <p class="lead">Brief description</p>
                <div class="cluster mt-1">
                    @components.ButtonLink("/path/new", "Add Item", "accent")
                </div>
            </header>

            <section class="section">
                // Page content
            </section>
        </article>
    }
}
```

## Navigation Partials

Each domain has a navigation partial in `backend/internal/partials/`:

| Partial | Domain |
|---------|--------|
| `@partials.NavGovernance()` | Proposals, Meetings, Resolutions, Decisions |
| `@partials.NavHealth()` | Financial dashboard pages |
| `@partials.NavAccount()` | User account pages |
| `@partials.NavDocuments()` | Document pages |

## List Page Pattern

```templ
templ Index(items []dto.ItemResponse) {
    @layouts.Sidebar(...) {
        @partials.NavDomain()
        <article class="content" data-signals="{ filter: 'all' }">
            <header class="section prose">
                <h1>Items</h1>
                <p class="lead">Description</p>
                <div class="cluster mt-1">
                    @components.ButtonLink("/items/new", "Add Item", "accent")
                </div>
            </header>

            <section class="section">
                @ItemFilters()

                <table class="table--lined">
                    <thead>
                        <tr>
                            <th scope="col">Column 1</th>
                            <th scope="col">Column 2</th>
                        </tr>
                    </thead>
                    <tbody>
                        @ItemTableRows(items)
                    </tbody>
                </table>
            </section>
        </article>
    }
}
```

## Detail Page Pattern

```templ
templ Show(item dto.ItemResponse) {
    @layouts.Sidebar(...) {
        @partials.NavDomain()
        <article class="content">
            <header class="section prose">
                <nav class="breadcrumbs mb-1">
                    <a href="/items">Items</a>
                    <span>{ item.Title }</span>
                </nav>
                <h1>{ item.Title }</h1>
                @components.StatusBadge(item.Status)
            </header>

            <section class="section stack">
                // Item details
                <dl class="box">
                    <dt>Field</dt>
                    <dd>{ item.Field }</dd>
                </dl>

                // Actions
                <div class="cluster">
                    @components.ButtonLink("/items/" + item.ID + "/edit", "Edit", "")
                </div>
            </section>
        </article>
    }
}
```

## Form Page Pattern

```templ
templ New() {
    @layouts.Sidebar(...) {
        @partials.NavDomain()
        <article class="content">
            <header class="section prose">
                <nav class="breadcrumbs mb-1">
                    <a href="/items">Items</a>
                    <span>New Item</span>
                </nav>
                <h1>New Item</h1>
                <p class="lead">Create a new item</p>
            </header>

            <section class="section">
                <form method="POST" action="/items" class="stack">
                    @components.FormField(components.FormFieldProps{
                        Name:     "title",
                        Label:    "Title",
                        Type:     "text",
                        Required: true,
                    })

                    <div class="cluster mt-2">
                        <button type="submit" class="button button--accent">Create</button>
                        <a href="/items" class="button">Cancel</a>
                    </div>
                </form>
            </section>
        </article>
    }
}
```

## Existing Pages

### Governance Domain

| Route | Template | Handler |
|-------|----------|---------|
| `/governance` | `governance/index.templ` | `PageGovernance` |
| `/governance/proposals` | `governance/proposals/index.templ` | `PageProposals` |
| `/governance/proposals/{id}` | `governance/proposals/show.templ` | `PageProposalDetail` |
| `/governance/proposals/new` | `governance/proposals/new.templ` | `PageProposalNew` |
| `/governance/meetings` | `governance/meetings/index.templ` | `PageMeetings` |
| `/governance/meetings/{id}` | `governance/meetings/show.templ` | `PageMeetingDetail` |
| `/governance/meetings/new` | `governance/meetings/new.templ` | `PageMeetingNew` |
| `/governance/resolutions` | `governance/resolutions/index.templ` | `PageResolutions` |
| `/governance/resolutions/{id}` | `governance/resolutions/show.templ` | `PageResolutionDetail` |
| `/governance/resolutions/new` | `governance/resolutions/new.templ` | `PageResolutionNew` |
| `/governance/decisions` | `governance/decisions/index.templ` | `PageDecisions` |
| `/governance/decisions/{id}` | `governance/decisions/show.templ` | `PageDecisionDetail` |

### Members Domain

| Route | Template | Handler |
|-------|----------|---------|
| `/members` | `members/index.templ` | `PageMembers` |
| `/members/{id}` | `members/show.templ` | `PageMemberDetail` |
| `/members/new` | `members/new.templ` | `PageMemberNew` |

### Health Domain

| Route | Template | Handler |
|-------|----------|---------|
| `/health` | `health/index.templ` | `PageHealth` |
| `/health/income` | `health/income.templ` | `PageHealthIncome` |
| `/health/balance` | `health/balance.templ` | `PageHealthBalance` |
| `/health/equity` | `health/equity.templ` | `PageHealthEquity` |

### Account Domain

| Route | Template | Handler |
|-------|----------|---------|
| `/account` | `account/index.templ` | `PageAccount` |
| `/account/profile` | `account/profile.templ` | `PageAccountProfile` |
| `/account/finances` | `account/finances.templ` | `PageAccountFinances` |

## CSS Body Classes

Use `pg-` prefix for page-specific styling:

```templ
layouts.PageMeta{
    BodyClass: "pg-proposals",  // .pg-proposals in CSS
}
```

Available classes:
- `pg-governance`, `pg-proposals`, `pg-meetings`, `pg-resolutions`, `pg-decisions`
- `pg-members`
- `pg-health`
- `pg-account`
- `pg-documents`
