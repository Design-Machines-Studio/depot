# Components Reference

Templ components for Assembly. Located in `backend/internal/components/`.

## Display Components

### Avatar

Member avatar circle with initials. Name is rendered alongside initials.

```templ
@components.Avatar(name, size)
// size: "small", "large", or "" for default

// Convenience wrappers
@components.AvatarSmall("Jane Smith")
@components.AvatarLarge("Jane Smith")

// Initials-only (no name text)
@components.AvatarOnly("Jane Smith", "small")
```

### Badge

General-purpose badge with variants and size modifiers. All labels are auto-title-cased.

```templ
@components.Badge(label, variant)
// variant: "active", "pending", "passed", "failed", "draft", "voting",
//          "general", "special", "board", "ordinary", "director",
//          "success", "warning", "muted", "subtle", "accent", etc.

// Size variant
@components.BadgeSmall(label, variant)  // Compact, for inline use in headings/tables

// Examples
@components.Badge("Active", "active")
@components.BadgeSmall("Board", "board")
```

CSS provides a grey fallback for unrecognized variants so badges always render visibly.

### StatCard

Dashboard statistic card within a semantic `<dl>` wrapper. Templates control sizing and layout via the `Class` field; the component handles content structure.

```templ
// Full API — use StatCardData struct for maximum control
@components.StatCard(components.StatCardData{
    Label:     "Total Members",    // Metric label
    Value:     "24",               // Primary value
    Detail:    "18 Active, 6 On Leave", // Additional context (optional)
    SubDetail: "Based on roster",  // Secondary detail line (optional)
    Href:      "/members",         // Makes card clickable (optional)
    Status:    "healthy",          // Status indicator: "healthy", "watch", "critical" (optional)
    Scheme:    "subtle",           // Color scheme (optional)
    Class:     "text-center",      // Extra utility classes on outer element (optional)
})

// Convenience wrappers for common patterns
@components.StatCardSimple(label, value, detail, scheme)
@components.StatCardLink(label, value, detail, href, scheme)
@components.StatCardWithStatus(label, value, detail, status, scheme)
@components.StatCardWithSubDetail(label, value, detail, subDetail, scheme)
```

**StatCardGroup** wraps cards in a semantic `<dl>`:

```templ
@components.StatCardGroup("grid grid-columns-2 grid-columns-4@md") {
    @components.StatCardSimple("Members", "24", "18 active", "")
    @components.StatCardSimple("Revenue", "$12k", "This quarter", "")
}
```

Use `Class` for layout utilities (`text-center`), color utilities (`text-success`), or any other customization. The component renders as `<a>` when `Href` is set, `<div>` otherwise. Both get `stat-card box` plus any scheme and class values.

### InfoCard

Information card for sidebar panels (upcoming events, announcements).

```templ
@components.InfoCard(components.InfoCardData{
    Header:     "Upcoming",              // Category header (optional)
    Title:      "Board Meeting",         // Main title
    Href:       "/governance/meetings/1", // Link URL (optional)
    Subtitle:   "January 10, 2026",      // Secondary info (optional)
    AvatarName: "Ned Ludd",             // Avatar initials (optional)
    AvatarText: "Facilitated by Ned Ludd", // Text next to avatar (optional)
    Scheme:     "subtle",               // Color scheme (optional)
})

// Convenience wrapper for upcoming meetings
@components.UpcomingMeetingCard(title, href, datetime, facilitatorName)
```

### ActivityCard

Activity/timeline card for proposals, resolutions, and action items.

```templ
@components.ActivityCard(components.ActivityCardData{
    Title:        "Professional Development Fund",
    Href:         "/governance/proposals/prop-001",
    BadgeLabel:   "Ready to Vote",
    BadgeVariant: "ready",
    Timestamp:    "Dec 1, 2025",  // Optional
})

// Convenience wrappers
@components.ProposalCard(title, href, status)       // Auto-labels from status
@components.ResolutionCard(title, href, category, timestamp)
@components.ActionCard(title, href)                  // Always "Pending" badge
```

### MemberCard

Card for member directory listings.

```templ
@components.MemberCard(components.MemberCardData{
    Name:      "Jane Smith",
    Href:      "/members/usr_001",
    Role:      "Director",
    Status:    "active",
    JoinDate:  "2024-01-15",
    AvatarURL: "",
})
```

### ProgressBar

Progress indicator web component.

```templ
@components.ProgressBar(progress, variant, label)
// progress: 0-100 percentage
// variant: "thick" or "" for default
// label: accessible screen reader label (optional)

// Convenience wrappers
@components.ProgressBarThick(progress, label)
@components.ProgressBarWithTarget(progress, current, target, label)
```

### CommentCard

Comment with avatar, author, date, and body.

```templ
@components.CommentCard(author, body, date, badge)
// badge: "" to omit, or a label string (renders as BadgeSmall)

// Example
@components.CommentCard("Jane Smith", "Looks good to me.", "2026-01-15", "Director")
```

### CommentForm

Form for posting comments or replies.

```templ
@components.CommentForm(action, fieldName, label, placeholder)

// Example
@components.CommentForm("/proposals/prop-001/comments", "body", "Add a Comment", "Share your thoughts...")
```

### KanbanBoard

Kanban layout with columns and cards.

```templ
@components.KanbanBoard("board-id") {
    @components.KanbanColumn("To Do") {
        @components.KanbanCard("/items/1") {
            <p>Card content here</p>
        }
    }
    @components.KanbanColumn("In Progress") {
        // cards...
    }
}
```

### InfoPopup

Modal popup for contextual help. Uses `<popup-dialog>` web component.

```templ
@components.InfoPopup(body)
@components.InfoPopupWithTitle(title, body)

// Example
@components.InfoPopup("The minimum number of members required...")
```

### Loader

Loading indicator.

```templ
@components.Loader(label, variant)

// Example
@components.Loader("members", "")  // "Loading members…"
```

## Navigation Components

### ButtonLink

Link styled as button.

```templ
@components.ButtonLink(href, label, variant)
// variant: "", "accent", "danger"

// Examples
@components.ButtonLink("/members/new", "Add Member", "accent")
@components.ButtonLink("/back", "Cancel", "")
```

### Button / SubmitButton

Regular and submit buttons.

```templ
@components.Button(label, variant)
@components.SubmitButton(label, variant)
```

### QuickActions

Panel of quick action links.

```templ
@components.QuickActions(title, []components.QuickActionLink{
    {Href: "/proposals/new", Label: "New Proposal"},
    {Href: "/meetings/new", Label: "Schedule Meeting"},
})

// Default quick actions panel (pre-configured links)
@components.DefaultQuickActions()
```

## Form Components

### FormField

Complete form field with label, input, hint, and error handling.

```templ
@components.FormField(components.FormFieldData{
    Name:        "title",
    Label:       "Proposal Title",
    Type:        "text",  // "text", "email", "date", "number", "tel", "url"
    Placeholder: "Enter title...",
    Value:       "",
    Required:    true,
    Hint:        "Maximum 100 characters",
    Error:       "",
})

// Convenience wrappers
@components.FormFieldText(label, name, value, required)
@components.FormFieldEmail(label, name, value, required)
@components.FormFieldTel(label, name, value, placeholder)
```

### Textarea

Multi-line text input.

```templ
@components.Textarea(components.TextareaData{
    Name:        "description",
    Label:       "Description",
    Rows:        5,
    Value:       "",
    Required:    false,
    Placeholder: "Enter description...",
    Hint:        "",
})

// Convenience wrapper
@components.TextareaSimple(label, name, value, placeholder, hint)
```

### Select

Dropdown select.

```templ
@components.Select(components.SelectData{
    Name:        "status",
    Label:       "Status",
    Placeholder: "Choose...",
    Options: []components.SelectOption{
        {Value: "draft", Label: "Draft"},
        {Value: "active", Label: "Active"},
    },
    Selected: "draft",
    Required: true,
})

// Convenience wrapper
@components.SelectSimple(label, name, placeholder, options, required)
```

### Checkbox

Checkbox input with multiple variants.

```templ
@components.Checkbox(components.CheckboxData{
    Name:    "agree",
    Value:   "yes",
    Label:   "I agree to the terms",
    Checked: false,
    Icon:    "",     // Optional icon class
    Small:   false,  // Compact size
})

// Convenience wrappers
@components.CheckboxSimple(name, label, checked)
@components.CheckboxWithValue(name, value, label, checked)
@components.CheckboxIcon(name, value, label, checked)   // With icon
@components.CheckboxSmall(name, value, label, checked)   // Compact
```

### Radio

Radio button input.

```templ
@components.Radio(components.RadioData{
    Name:    "vote",
    Value:   "for",
    Label:   "Vote For",
    Checked: false,
})

// Convenience wrappers
@components.RadioSimple(name, value, label, checked)
@components.RadioSmall(name, value, label, checked)

// Radio group with legend and options
@components.RadioGroup(components.RadioGroupData{
    Name:    "vote",
    Label:   "Cast Your Vote",
    Options: []components.RadioData{
        {Name: "vote", Value: "for", Label: "For"},
        {Name: "vote", Value: "against", Label: "Against"},
        {Name: "vote", Value: "abstain", Label: "Abstain"},
    },
    Required: true,
})
```

### Checklist

Group of checkbox items with progress tracking.

```templ
@components.Checklist([]components.ChecklistItemData{
    {Label: "Submit bylaws", Completed: true, Href: ""},
    {Label: "Schedule AGM", Completed: false, Href: "/meetings/new"},
})

// Individual items
@components.ChecklistItemCompleted("Submit bylaws")
@components.ChecklistItemPending("Schedule AGM", "/meetings/new")

// Progress checklist with header and footer
@components.ProgressChecklist(title, completed, total, items, footerText)

// Profile completion checklist
@components.ProfileChecklist(completedCount, totalCount, items)
```

## Helper Functions

Located in `backend/internal/components/helpers.go`:

### Initials

Extract initials from a name.

```go
components.Initials("Jane Smith")       // "JS"
components.Initials("Alice Bob Chen")   // "ABC"
```

### Title

Convert string to title case.

```go
components.Title("active")   // "Active"
components.Title("on leave") // "On Leave"
```

### DateShort

Format date string as short display.

```go
components.DateShort("2026-01-15")  // "Jan 15, 2026"
```

### DateTimeFriendly

Format datetime as friendly display.

```go
components.DateTimeFriendly("2026-01-15T14:30:00")  // "January 15, 2026 at 2:30 PM"
```

### Year

Extract year from date string.

```go
components.Year("2026-01-15")  // "2026"
```

### Itoa

Convert int to string.

```go
components.Itoa(42)  // "42"
```

## Shared Helpers (helpers package)

Located in `backend/internal/helpers/format.go`. Import as `helpers`.

```go
helpers.VoteVariant("for")       // "success" (badge variant for vote values)
helpers.TotalVotes(proposal)     // Sum of for + against + abstain
helpers.ForPercentage(proposal)  // Percentage of votes in favor
helpers.IntOrZero(intPtr)        // String of pointer int, "0" if nil
helpers.FormatDate(dateStr)      // Truncate to YYYY-MM-DD
helpers.PtrVal(ptr, defaultVal)  // Generic pointer dereference with default
```

## Creating New Components

1. **Check if existing component can be extended**
2. **Create in `backend/internal/components/`**
3. **Follow the pattern** — use a `Data` struct for 3+ fields, convenience wrappers for common cases:

```templ
package components

type ComponentNameData struct {
    Title   string
    Variant string
}

templ ComponentName(data ComponentNameData) {
    <div class={ "component", templ.KV("component--" + data.Variant, data.Variant != "") }>
        { data.Title }
    </div>
}

// Convenience wrapper
templ ComponentNameSimple(title, variant string) {
    @ComponentName(ComponentNameData{Title: title, Variant: variant})
}
```

4. **Generate and test:**

```bash
docker compose exec app templ generate
docker compose exec app go build -o assembly ./cmd/api
```

## Usage in Templates

Import components in your templ file:

```templ
package mypage

import (
    "github.com/design-machines/assembly/internal/components"
)

templ MyPage() {
    @components.Avatar("Jane Smith", "")
    @components.Badge("Active", "active")
    @components.ButtonLink("/edit", "Edit", "accent")
}
```
